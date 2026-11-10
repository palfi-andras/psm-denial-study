#!/usr/bin/env python3
"""Build or extend the skeleton of results/INVENTORY.yaml (the manifest tests/test_inventory.py checks).

    python scripts/inventory_draft.py            # adds missing entries to results/INVENTORY.yaml
    python scripts/inventory_draft.py --dry-run  # prints the YAML instead of writing it
    python scripts/inventory_draft.py --mismatches   # also lists numbers in the write-up that match no analysis value

Safe to rerun. It NEVER changes a `reported`, `excluded` or `companion_of` value that is already in the manifest
(human-written text wins). It only
  * adds a missing judgments file, analysis file, analysis key or child key with `reported: TODO`,
  * fills a new entry that can be resolved mechanically (see below), and
  * refreshes the derived fields `arms`, `judges` (read from the jsonl) and unions `consumed_by`.
Entries for files or keys that no longer exist are kept, and the test then fails on them: delete them by hand.
Comment lines (`# est ...`) above TODO entries are regenerated on each run; other comments are not preserved.

What is filled automatically for a NEW entry:
  * bookkeeping keys (generated_at, draws, seed, ...) -> `excluded` with a stated reason;
  * an analysis leaf with est/lo/hi (fractions) -> `reported` with an anchor like `+24.9 pts [+21.6, +28.2]` when that
    text is in the rendered report / brief snapshot / README / site (U+2212 minus; rounding +-0.1 tried);
  * the snapshots are made by writeup/render_text.sh; rerun it after rebuilding the pages;
  * judgments side copies  * judgments side copies named in docs/SCHEMAS.md "Side copies" and PREREGISTRATION.md Deviations 9, 15, 16, 19 ->
    `excluded` with the stated reason; record files that feed an analysis output -> `reported` pointing at consumed_by;
  * a .md next to a .json of the same stem -> `companion_of`.
Everything else stays TODO, with a comment giving the value(s).

`consumed_by` comes from reading analysis/*.py (see CONSUMERS below); it is by eval and tree, not by row.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
MANIFEST = RES / "INVENTORY.yaml"
# report and brief: rendered-text snapshots (writeup/render_text.sh); first line is the sha256 line, dropped
DOCS = {"report": "writeup/rendered/report.txt", "brief": "writeup/rendered/brief.txt", "readme": "README.md",
        "site": "site/index.html"}
SNAPSHOTS = {"report", "brief"}
# value is a dict of dicts (or of verdict strings) for these top-level keys: children are listed one by one
CHILDREN_KEYS = {"contrasts", "tests", "primary", "verdicts", "robustness", "second_judge", "breadth",
                 "secondary", "descriptive", "seeds"}
BOOKKEEPING = {"generated_at", "draws", "seed", "config", "model", "note", "n_items", "adapters", "results_tree",
               "pool_sizes", "judges", "judge_coverage_warnings", "n_rows", "n_transfer_rows", "standing",
               "mention_regex", "recoded_rows", "arms", "job", "eval", "judge", "adapter", "n_draws"}
# superseded or variant copies whose numbers equal the current ones by coincidence of an unchanged value: never auto-anchored
NO_AUTO_ANCHOR = ("before_d16", "leaked_context")
SAMPLING_FILES = {"_sample_key.json", "_fixed_tokens.json"}
TODO = "TODO"


# ---------------------------------------------------------------- normalization (same as tests/test_inventory.py)
def normalize_html(s: str) -> str:
    s = re.sub(r"(?is)<(script|style)\b.*?</\1\s*>", "", s)
    s = re.sub(r"(?s)<!--.*?-->", "", s)
    s = re.sub(r"<[^>]*>", "", s)
    return normalize_text(html.unescape(s))


def normalize_text(s: str) -> str:
    for c in (" ", " ", " "):
        s = s.replace(c, " ")
    return re.sub(r"\s+", " ", s).strip()


def load_docs() -> dict[str, str]:
    out = {}
    for name, rel in DOCS.items():
        raw = (ROOT / rel).read_text(encoding="utf-8")
        if name in SNAPSHOTS:
            raw = raw.partition("\n")[2]
        out[name] = normalize_html(raw) if rel.endswith(".html") else normalize_text(raw)
    return out


# ---------------------------------------------------------------- scope (same as tests/test_inventory.py)
def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def _skip(p: Path) -> bool:
    return not p.is_file() or "_batches" in p.parts or p.name == ".gitkeep"


def _in_judgments_dir(p: Path) -> bool:
    return any(part.startswith("judgments") for part in p.relative_to(RES).parts[:-1])


def scope_judgments() -> list[Path]:
    out = {p for p in RES.rglob("*.jsonl") if not _skip(p) and _in_judgments_dir(p)}
    out |= {p for p in (RES / "gate1").rglob("*judgments*.jsonl") if not _skip(p)}
    return sorted(out)


def scope_side_files() -> list[Path]:
    return sorted(p for p in RES.rglob("*") if not _skip(p) and _in_judgments_dir(p) and p.suffix != ".jsonl")


def scope_analysis() -> list[Path]:
    out = set()
    for p in RES.rglob("*"):
        if _skip(p) or _in_judgments_dir(p):
            continue
        parts = p.relative_to(RES).parts
        if "analysis" in parts[:-1]:
            out.add(p)
        elif "hand_labels" in parts[:-1] and p.suffix in (".json", ".md"):
            out.add(p)
        elif "figures" in parts[:-1] and p.suffix == ".png":
            out.add(p)
    for pat in ("gate1_*.json", "*/gate1_*.json", "gate1/*.json", "gate1/batch_labels/*.json", "gate2_notes.md",
                "*/NOTES.md", "gate1/NOTES.md"):
        out |= {p for p in RES.glob(pat) if not _skip(p)}
    return sorted(out)


# ---------------------------------------------------------------- judgments facts
def arms_judges(p: Path) -> tuple[list[str], list[str]]:
    arms, judges = set(), set()
    with p.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("model_id") is not None:
                arms.add(re.sub(r"-s\d+$", "", r["model_id"]))
            if r.get("judge") is not None:
                judges.add(r["judge"])
    return sorted(arms), sorted(judges)


# ---------------------------------------------------------------- consumed_by (from reading analysis/*.py)
H1 = {"self_facts", "own_actions", "mask_uninstructed"}
ALL_EVALS = {"self_facts", "own_actions", "mask_uninstructed", "mask_instructed", "secret_keeping", "knowledge_check",
             "knowledge_check_instructed", "em_first_plot"}
MAN = {"knowledge_check", "knowledge_check_instructed"}
QO_EVALS = {"self_facts", "mask_uninstructed"}
A, S32, S3, DOSE = "results/analysis/", "results/scale32b/analysis/", "results/scale32b_s3/analysis/", "results/dose8b/analysis/"
# (tree, subfolder under judgments/) -> {eval or "*": [analysis outputs that read it]}; "*" = every eval in the folder
CONSUMERS: dict[tuple[str, str], dict[str, list[str]]] = {
    ("results", ""): {
        "*": [A + "summary.json"],
        **{e: [A + "template_only.json", A + "exploratory_question_only.json", A + "eval_weighting.json",
               DOSE + "dose_crosscheck.json"] for e in H1},
        "own_actions": [A + "template_only.json", A + "exploratory_question_only.json", A + "eval_weighting.json",
                        DOSE + "dose_crosscheck.json", DOSE + "own_actions_by_model.json"],
        "mask_uninstructed": [A + "template_only.json", A + "exploratory_question_only.json", A + "eval_weighting.json",
                              DOSE + "dose_crosscheck.json", A + "secret_keeping.json"],
        "mask_instructed": [A + "secret_keeping.json"],
        "secret_keeping": [A + "secret_keeping.json"],
        "knowledge_check": [A + "gate2.json"], "knowledge_check_instructed": [A + "gate2.json"],
        "em_first_plot": ["results/gate1_EM-s1.json", "results/gate1_EM-s2.json"],
    },
    ("results", "exploratory/question_only"): {
        "*": [A + "exploratory_question_only.json", A + "template_only.json", DOSE + "dose_crosscheck.json"]},
    ("results", "exploratory/claude_p_unisolated/opus_audit"): {"*": []},
    ("results/scale32b", ""): {
        "*": [S32 + "summary.json"],
        **{e: [S32 + "confirmatory.json", S32 + "template_only.json", S32 + "exploratory_question_only.json",
               S3 + "followup.json", S3 + "followup_leaked_context.json", A + "eval_weighting.json"] for e in H1},
        "own_actions": [S32 + "confirmatory.json", S32 + "template_only.json", S32 + "exploratory_question_only.json",
                        S3 + "followup.json", S3 + "followup_leaked_context.json", A + "eval_weighting.json",
                        S3 + "c3_split.json", S3 + "own_actions_qo.json"],
        "mask_uninstructed": [S32 + "confirmatory.json", S32 + "template_only.json",
                              S32 + "exploratory_question_only.json", S3 + "followup.json",
                              S3 + "followup_leaked_context.json", A + "eval_weighting.json", S3 + "c3_split.json",
                              S32 + "secret_keeping.json"],
        "mask_instructed": [S32 + "secret_keeping.json"], "secret_keeping": [S32 + "secret_keeping.json"],
        "knowledge_check": [S32 + "summary.json"], "knowledge_check_instructed": [S32 + "summary.json"],
        "em_first_plot": ["results/scale32b/gate1_EM-s1.json", "results/scale32b/gate1_EM-s2.json"],
    },
    ("results/scale32b", "exploratory/question_only"): {
        "*": [S32 + "confirmatory.json", S32 + "exploratory_question_only.json", S32 + "template_only.json",
              S3 + "followup.json", S3 + "followup_leaked_context.json", S3 + "c3_split.json",
              S3 + "qo_opus_audit.json"]},
    ("results/scale32b", "exploratory/question_only_opus_audit"): {"*": [S3 + "qo_opus_audit.json"]},
    ("results/scale32b", "exploratory/question_only_own_actions"): {
        "*": [S3 + "own_actions_qo.json", S32 + "template_only.json"]},
    ("results/scale32b_s3", ""): {
        "*": [],
        **{e: [S3 + "followup.json", S3 + "followup_leaked_context.json"] for e in H1},
        "own_actions": [S3 + "followup.json", S3 + "followup_leaked_context.json", S3 + "c3_split.json",
                        S3 + "own_actions_qo.json"],
        "mask_uninstructed": [S3 + "followup.json", S3 + "followup_leaked_context.json", S3 + "c3_split.json"],
        "knowledge_check": [S3 + "manipulation.json"], "knowledge_check_instructed": [S3 + "manipulation.json"],
    },
    ("results/scale32b_s3", "exploratory/question_only"): {
        "*": [S3 + "followup.json", S3 + "followup_leaked_context.json", S3 + "c3_split.json",
              S3 + "qo_opus_audit.json"]},
    ("results/scale32b_s3", "exploratory/question_only_opus_audit"): {"*": [S3 + "qo_opus_audit.json"]},
    ("results/scale32b_s3", "exploratory/question_only_own_actions"): {"*": [S3 + "own_actions_qo.json"]},
    ("results/dose8b", ""): {
        "*": [],
        **{e: [DOSE + "dose.json", DOSE + "template_only.json", DOSE + "dose_crosscheck.json"] for e in H1},
        "own_actions": [DOSE + "dose.json", DOSE + "template_only.json", DOSE + "dose_crosscheck.json",
                        DOSE + "own_actions_by_model.json", DOSE + "own_actions_qo.json"],
        "mask_uninstructed": [DOSE + "dose.json", DOSE + "template_only.json", DOSE + "dose_crosscheck.json",
                              DOSE + "secret_keeping.json"],
        "mask_instructed": [DOSE + "secret_keeping.json"], "secret_keeping": [DOSE + "secret_keeping.json"],
        "knowledge_check": [DOSE + "dose.json"], "knowledge_check_instructed": [DOSE + "dose.json"],
    },
    ("results/dose8b", "exploratory/question_only"): {
        "*": [DOSE + "dose.json", DOSE + "template_only.json", DOSE + "dose_crosscheck.json",
              DOSE + "route_check.json"]},
    ("results/dose8b", "exploratory/question_only_own_actions"): {"*": [DOSE + "own_actions_qo.json"]},
    ("results/dose8b", "exploratory/route_check/frozen"): {"*": [DOSE + "route_check.json"]},
    ("results/dose8b", "exploratory/route_check/question_only"): {"*": [DOSE + "route_check.json"]},
}
for _t in ("results", "results/scale32b", "results/scale32b_s3", "results/dose8b"):
    CONSUMERS[(_t, "exploratory/claude_p_unisolated")] = {"*": []}


def consumers_for(path: str) -> list[str]:
    p = Path(path)
    if path.startswith("results/gate1/"):
        return ["results/gate1/gate1_EM-s1.json", "results/gate1/gate1_EM-s2.json"]
    if path.startswith("results/judgments_calib/"):
        return [A + "calibration.json"]
    if path.startswith("results/judgments/rejudge_d16/") or path.startswith("results/judgments/_superseded/"):
        return []
    if "claude_p_unisolated" in p.parts:
        return []
    m = re.match(r"(results(?:/[a-z0-9_]+?)?)/judgments/(.*)$", path)
    if not m:
        return []
    tree, rest = m.group(1), m.group(2)
    sub = str(Path(rest).parent)
    sub = "" if sub == "." else sub
    ev = Path(rest).stem
    table = CONSUMERS.get((tree, sub))
    if table is None:
        for (t, s), tab in CONSUMERS.items():  # claude_p_unisolated subfolders etc.
            if t == tree and s and sub.startswith(s):
                table = tab
                break
    if table is None:
        return []
    return sorted(set(table.get("*", [])) | set(table.get(ev, [])))


def judgments_verdict(path: str, consumed: list[str]) -> dict | None:
    """The mechanical reported / excluded text for a judgments jsonl, or None (leave TODO)."""
    if "claude_p_unisolated/opus_audit" in path:
        return {"excluded": "Deviation 19: the old claude -p Opus audit rows (judged with the leaked project context, "
                            "Deviation 16), set aside and replaced by the Batch re-judge in results/judgments/"
                            "rejudge_d16/; kept only so old-vs-new kappa can be computed (docs/SCHEMAS.md Side copies)."}
    if "claude_p_unisolated" in path:
        return {"excluded": "Deviation 16: claude -p rows judged before the judge context was isolated (the session's "
                            "project notes leaked into it); moved out of the record by scripts/quarantine_claude_p.py; "
                            "read only for the disclosure, never for a reported number (docs/SCHEMAS.md Side copies)."}
    if "/exploratory/route_check/" in path:
        return {"excluded": "Deviation 15 side copy: claude -p re-judges of Batch-judged rows, read only for the route "
                            "kappa in results/dose8b/analysis/route_check.json (docs/SCHEMAS.md Side copies)."}
    if path.startswith("results/judgments/rejudge_d16/"):
        return {"excluded": "Deviation 19 side copy: the Batch re-judge of the Opus audit rows; its rows became the "
                            "record in results/judgments/<eval>.jsonl; this folder is read only for old-vs-new kappa "
                            "(old_vs_new.json)."}
    if path.startswith("results/judgments/_superseded/"):
        return {"excluded": "Deviation 9: mask_instructed judgments under the first judge prompt, kept after the "
                            "prompt was fixed and the eval re-judged; not used by any analysis."}
    if consumed:
        return {"reported": "Labels read by the analysis outputs in consumed_by; every number computed from them is "
                            "inventoried under those outputs (see their entries)."}
    return None


def side_file_verdict(path: str) -> dict | None:
    return None


# ---------------------------------------------------------------- numbers
def pts(x: float) -> float:
    return x * 100.0


def fmt(x: float, plus: bool = True) -> str:
    s = f"{x:+.1f}" if plus else f"{x:.1f}"
    if s in ("+0.0", "-0.0"):
        s = "+0.0" if plus else "0.0"
    return s.replace("-", "−")


def is_est(v) -> bool:
    return isinstance(v, dict) and all(isinstance(v.get(k), (int, float)) and not isinstance(v.get(k), bool)
                                      for k in ("est", "lo", "hi"))


def summarize(v, limit: int = 220) -> str:
    if is_est(v):
        s = f"est {fmt(pts(v['est']))} pts [{fmt(pts(v['lo']))}, {fmt(pts(v['hi']))}]"
        for k in ("p", "p_holm", "pass", "standing"):
            if k in v:
                s += f"; {k}={v[k]}"
        return s[:limit]
    if isinstance(v, float):
        return f"{v!r} (x100 = {pts(v):+.2f})" if abs(v) <= 1.0 else repr(v)
    s = json.dumps(v, ensure_ascii=False, default=str)
    return s if len(s) <= limit else s[:limit] + f"... [{type(v).__name__} len {len(v) if hasattr(v, '__len__') else ''}]"


def anchors(v: dict) -> list[str]:
    """Candidate anchor texts for an est/lo/hi leaf, best first (exact rounding before +-0.1 variants)."""
    e, l, h = pts(v["est"]), pts(v["lo"]), pts(v["hi"])
    out = []
    for d in [(0, 0, 0)] + [(a, b, c) for a in (0, -.1, .1) for b in (0, -.1, .1) for c in (0, -.1, .1)
                            if (a, b, c) != (0, 0, 0)]:
        for plus in (True, False):
            es, ls, hs = fmt(e + d[0], plus), fmt(l + d[1], plus), fmt(h + d[2], plus)
            for unit in (" pts", "", " points"):
                out.append(f"{es}{unit} [{ls}, {hs}]")
    seen, res = set(), []
    for a in out:
        if a not in seen:
            seen.add(a)
            res.append(a)
    return res


def find_anchor(v: dict, docs: dict[str, str]) -> dict | None:
    for a in anchors(v):
        for name in ("report", "brief", "readme", "site"):
            if normalize_text(a) in docs[name]:
                return {"doc": name, "text": a}
    return None


def flatten_est(o, path=()):
    """(path tuple, node) for every est/lo/hi dict in a JSON value."""
    if is_est(o):
        yield path, o
    if isinstance(o, dict):
        for k, v in o.items():
            yield from flatten_est(v, path + (str(k),))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from flatten_est(v, path + (str(i),))


# ---------------------------------------------------------------- manifest model
def todo_leaf() -> dict:
    return {"reported": TODO}


def has_todo(o) -> bool:
    if isinstance(o, str):
        return TODO in o
    if isinstance(o, dict):
        return any(has_todo(v) for v in o.values())
    if isinstance(o, list):
        return any(has_todo(v) for v in o)
    return False


def resolved(entry) -> bool:
    return isinstance(entry, dict) and any(k in entry for k in ("reported", "excluded", "companion_of", "children", "keys"))


class Builder:
    def __init__(self, existing: dict):
        self.m = {"judgments": dict(existing.get("judgments") or {}),
                  "judgment_side_files": dict(existing.get("judgment_side_files") or {}),
                  "analysis": dict(existing.get("analysis") or {})}
        self.comments: dict[tuple, str] = {}
        self.docs = load_docs()
        self.notes: list[str] = []

    # --- leaf resolution for an analysis key/child
    def auto_leaf(self, fname: str, key: str, child: str | None, v, top: bool) -> tuple[dict, str]:
        """(entry, comment). Only called for NEW entries."""
        base = Path(fname).name
        if (top and key in BOOKKEEPING) or (base in SAMPLING_FILES):
            reason = ("hand-label sampling design / bookkeeping (not a result)" if base in SAMPLING_FILES
                      else "metadata: run settings or provenance, not a result")
            return {"excluded": reason}, ""
        if is_est(v) and any(t in fname for t in NO_AUTO_ANCHOR):
            return todo_leaf(), summarize(v) + "  [superseded/variant copy: not auto-anchored]"
        if is_est(v):
            hit = find_anchor(v, self.docs)
            if hit:
                return {"reported": [hit]}, ""
            return todo_leaf(), summarize(v)
        return todo_leaf(), summarize(v)

    def add_json_file(self, path: str, data: dict):
        ent = self.m["analysis"].setdefault(path, {})
        keys = ent.setdefault("keys", {}) if "keys" in ent or not resolved(ent) else None
        if keys is None:  # file-level reported/excluded chosen by a human: keep
            return
        for k, v in data.items():
            if k not in keys:
                if k in CHILDREN_KEYS and isinstance(v, dict):
                    keys[k] = {"children": {}}
                else:
                    keys[k], c = self.auto_leaf(path, k, None, v, True)
                    if c:
                        self.comments[("analysis", path, k, None)] = c
            if k in CHILDREN_KEYS and isinstance(v, dict) and "children" in keys[k]:
                ch = keys[k]["children"]
                for ck, cv in v.items():
                    if ck not in ch:
                        ch[ck], c = self.auto_leaf(path, k, ck, cv, False)
                        if c:
                            self.comments[("analysis", path, k, ck)] = c
            # refresh comments for entries that are still TODO (e.g. after a rerun)
            if has_todo(keys[k]):
                if "children" in keys[k]:
                    for ck, cv in (v or {}).items() if isinstance(v, dict) else []:
                        if has_todo(keys[k]["children"].get(ck)):
                            self.comments[("analysis", path, k, ck)] = summarize(cv)
                else:
                    self.comments[("analysis", path, k, None)] = summarize(v)

    def add_plain_file(self, path: str):
        if path in self.m["analysis"] and resolved(self.m["analysis"][path]):
            if has_todo(self.m["analysis"][path]):
                self.comments[("analysis", path, None, None)] = self.file_hint(path)
            return
        p = Path(path)
        comp = None
        if p.suffix == ".md":
            for cand in (p.with_suffix(".json"),
                         p.with_name("summary.json") if p.name == "report.md" else None,
                         p.with_name("kappa_report.json") if p.name == "kappa_report.md" else None):
                if cand and (ROOT / cand).exists():
                    comp = cand.as_posix()
                    break
        if comp:
            self.m["analysis"][path] = {"companion_of": comp}
        else:
            self.m["analysis"][path] = todo_leaf()
            self.comments[("analysis", path, None, None)] = self.file_hint(path)

    def file_hint(self, path: str) -> str:
        p = Path(path)
        if p.suffix == ".png":
            raw = {n: (ROOT / r).read_text(encoding="utf-8") for n, r in DOCS.items()}
            where = [n for n, t in raw.items() if p.name in t]
            return f"figure; file name {p.name} is referenced in: {', '.join(where) or 'no doc'} (written by analysis/figures.py)"
        txt = (ROOT / path).read_text(encoding="utf-8", errors="replace")
        first = next((ln.strip() for ln in txt.splitlines() if ln.strip()), "")
        return f"{p.suffix[1:]} file, {len(txt)} chars; first line: {first[:140]}"

    def run(self):
        for p in scope_judgments():
            path = rel(p)
            arms, judges = arms_judges(p)
            ent = self.m["judgments"].setdefault(path, {})
            cons = consumers_for(path)
            ent["arms"], ent["judges"] = arms, judges
            ent["consumed_by"] = sorted(set(ent.get("consumed_by") or []) | set(cons))
            if not any(k in ent for k in ("reported", "excluded")):
                v = judgments_verdict(path, ent["consumed_by"])
                ent.update(v or todo_leaf())
            if has_todo(ent):
                self.comments[("judgments", path, None, None)] = (
                    f"arms {','.join(arms)}; judges {','.join(judges)}; consumed_by {ent['consumed_by'] or 'none'}")
        for p in scope_side_files():
            path = rel(p)
            ent = self.m["judgment_side_files"].setdefault(path, {})
            if not any(k in ent for k in ("reported", "excluded", "companion_of")):
                comp = None
                if p.suffix == ".md" and (p.with_suffix(".json")).exists() and rel(p.with_suffix(".json")) != path:
                    comp = rel(p.with_suffix(".json"))
                ent.update({"companion_of": comp} if comp else (side_file_verdict(path) or todo_leaf()))
            if has_todo(ent):
                self.comments[("judgment_side_files", path, None, None)] = self.file_hint(path)
        for p in scope_analysis():
            path = rel(p)
            if p.suffix == ".json":
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self.add_json_file(path, data)
                    continue
            self.add_plain_file(path)
        return self.m


# ---------------------------------------------------------------- YAML writing
def j(x) -> str:
    return json.dumps(x, ensure_ascii=False)


def flow(d: dict) -> str:
    return "{" + ", ".join(f"{j(k)}: {j(v)}" for k, v in d.items()) + "}"


def emit(m: dict, comments: dict) -> str:
    L = ["# Results inventory: every judged results file and analysis output, mapped to where the write-up reports it",
         "# or to an explicit exclusion. Checked by tests/test_inventory.py. Skeleton maintained by",
         "# scripts/inventory_draft.py (adds missing entries as TODO, never overwrites reported/excluded text).",
         "# Anchor texts are matched in the normalized text of the doc (docs: report and brief = rendered snapshots",
         "# writeup/rendered/*.txt made by writeup/render_text.sh; readme; site)."]
    for sec in ("judgments", "judgment_side_files", "analysis"):
        L += ["", f"{sec}:"]
        for path in sorted(m[sec]):
            ent = m[sec][path]
            c = comments.get((sec, path, None, None))
            if c:
                L.append(f"  # {c}")
            if sec == "analysis" and "keys" in ent:
                L.append(f"  {j(path)}:")
                L.append("    keys:")
                for k, v in ent["keys"].items():
                    if "children" in v and len(v) == 1:
                        L.append(f"      {j(k)}:")
                        L.append("        children:")
                        for ck, cv in v["children"].items():
                            cc = comments.get((sec, path, k, ck))
                            if cc:
                                L.append(f"          # {cc}")
                            L.append(f"          {j(ck)}: {flow(cv) if isinstance(cv, dict) else j(cv)}")
                    else:
                        cc = comments.get((sec, path, k, None))
                        if cc:
                            L.append(f"      # {cc}")
                        L.append(f"      {j(k)}: {flow(v) if isinstance(v, dict) else j(v)}")
            elif sec == "analysis":
                L.append(f"  {j(path)}: {flow(ent)}")
            else:
                L.append(f"  {j(path)}:")
                for k, v in ent.items():
                    L.append(f"    {k}: {j(v)}")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- mismatch scan (the write-up vs the analysis JSON)
TRIPLE = re.compile(r"([+−-]?\d+(?:\.\d+)?)\s*(?:pts|points|pp)?\s*\[\s*([+−-]?\d+(?:\.\d+)?)\s*(?:,|to|–)\s*"
                    r"([+−-]?\d+(?:\.\d+)?)\s*\]")


def _num(s: str) -> float:
    return float(s.replace("−", "-"))


def mismatches(b: Builder) -> list[str]:
    known = []
    for p in scope_analysis():
        if p.suffix == ".json":
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            for path, n in flatten_est(data):
                known.append((rel(p), ".".join(path), tuple(round(pts(n[k]), 1) for k in ("est", "lo", "hi"))))
    out = []
    texts = dict(b.docs)
    for name, text in texts.items():
        for m in TRIPLE.finditer(text):
            t = tuple(_num(x) for x in m.groups())
            best = min(known, key=lambda k: sum(abs(a - c) for a, c in zip(k[2], t)))
            d = [abs(a - c) for a, c in zip(best[2], t)]
            if max(d) > 0.101:
                out.append(f"{name}: '{m.group(0)}' nearest {best[0]}:{best[1]} = {best[2]} (max diff {max(d):.2f})")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--mismatches", action="store_true", help="list numbers in the write-up that match no analysis value")
    a = ap.parse_args(argv)
    existing = yaml.safe_load(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    b = Builder(existing or {})
    m = b.run()
    text = emit(m, b.comments)
    if a.dry_run:
        sys.stdout.write(text)
    else:
        MANIFEST.write_text(text, encoding="utf-8")
    n_todo = text.count('"TODO"')
    print(f"{'(dry run) ' if a.dry_run else ''}{rel(MANIFEST)}: {len(m['judgments'])} judgments, "
          f"{len(m['judgment_side_files'])} side files, {len(m['analysis'])} analysis files, {n_todo} TODO",
          file=sys.stderr)
    if a.mismatches:
        for line in mismatches(b):
            print("MISMATCH?", line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
