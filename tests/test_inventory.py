"""Results inventory: every judged results file and every analysis output is mapped to where the write-up reports it,
or to an explicit exclusion (results/INVENTORY.yaml).

    pytest tests/test_inventory.py -q

Fails when
  * a judgments file, judgments side file or analysis file exists on disk but not in the manifest (or the reverse),
  * the arms / judges in a judgments file differ from the manifest's,
  * a top-level key (or a child key of contrasts, tests, primary, ...) of an analysis JSON is not in the manifest,
  * an entry has no `reported` / `excluded` / `companion_of`, or still says TODO,
  * an anchor text is no longer in the write-up (normalized rendered text of report and brief, writeup/rendered/*.txt,
    which must carry the current sha256 of the .html; README.md; site/index.html),
  * a `consumed_by` path is not an analysis entry.

New files or keys: run `python scripts/inventory_draft.py`, then replace each TODO by hand. The scope globs below and the
normalization are mirrored in that script.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
MANIFEST = RES / "INVENTORY.yaml"
# report and brief are matched against the rendered-text snapshots (writeup/render_text.sh), not the static HTML: the
# pages fill their tables and prose slots from embedded JSON with JS
DOC_FILES = {"report": "writeup/rendered/report.txt", "brief": "writeup/rendered/brief.txt", "readme": "README.md",
             "site": "site/index.html"}
SNAPSHOT_SOURCE = {"report": "writeup/report.html", "brief": "writeup/brief.html"}
# a dict value under one of these top-level keys is inventoried child by child
CHILDREN_KEYS = {"contrasts", "tests", "primary", "verdicts", "robustness", "second_judge", "breadth",
                 "secondary", "descriptive", "seeds"}
LEAF_FIELDS = {"reported", "excluded", "companion_of", "note"}


# ---------------------------------------------------------------- scope
def _skip(p: Path) -> bool:
    return not p.is_file() or "_batches" in p.parts or p.name == ".gitkeep"


def _in_judgments_dir(p: Path) -> bool:
    return any(part.startswith("judgments") for part in p.relative_to(RES).parts[:-1])


def _rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def scope_judgments() -> set[str]:
    out = {p for p in RES.rglob("*.jsonl") if not _skip(p) and _in_judgments_dir(p)}
    out |= {p for p in (RES / "gate1").rglob("*judgments*.jsonl") if not _skip(p)}
    return {_rel(p) for p in out}


def scope_side_files() -> set[str]:
    return {_rel(p) for p in RES.rglob("*") if not _skip(p) and _in_judgments_dir(p) and p.suffix != ".jsonl"}


def scope_analysis() -> set[str]:
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
    return {_rel(p) for p in out}


# ---------------------------------------------------------------- normalization of the docs and of anchors
def normalize_text(s: str) -> str:
    for c in (" ", " ", " "):
        s = s.replace(c, " ")
    return re.sub(r"\s+", " ", s).strip()


def normalize_html(s: str) -> str:
    s = re.sub(r"(?is)<(script|style)\b.*?</\1\s*>", "", s)  # drop script and style content
    s = re.sub(r"(?s)<!--.*?-->", "", s)
    s = re.sub(r"<[^>]*>", "", s)                            # strip tags
    return normalize_text(html.unescape(s))


# ---------------------------------------------------------------- fixtures
@pytest.fixture(scope="module")
def manifest() -> dict:
    assert MANIFEST.exists(), f"{_rel(MANIFEST)} is missing: run python scripts/inventory_draft.py"
    m = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    assert isinstance(m, dict), f"{_rel(MANIFEST)} is not a mapping"
    for sec in ("judgments", "judgment_side_files", "analysis"):
        assert isinstance(m.get(sec), dict), f"{_rel(MANIFEST)}: section '{sec}' is missing or not a mapping"
    return m


@pytest.fixture(scope="module")
def docs() -> dict:
    out = {}
    for name, rel in DOC_FILES.items():
        raw = (ROOT / rel).read_text(encoding="utf-8")
        if name in SNAPSHOT_SOURCE:
            first, _, body = raw.partition("\n")
            out[name] = normalize_text(body)
        elif rel.endswith(".html"):
            out[name] = normalize_html(raw)
        else:
            out[name] = normalize_text(raw)
    return out


@pytest.mark.parametrize("name", sorted(SNAPSHOT_SOURCE))
def test_rendered_snapshot_is_current(name):
    snap = ROOT / DOC_FILES[name]
    assert snap.exists(), f"{DOC_FILES[name]} is missing: run writeup/render_text.sh"
    first = snap.read_text(encoding="utf-8").split("\n", 1)[0].strip()
    want = "sha256 " + hashlib.sha256((ROOT / SNAPSHOT_SOURCE[name]).read_bytes()).hexdigest()
    assert first == want, (f"{DOC_FILES[name]} is stale (first line {first!r}, {SNAPSHOT_SOURCE[name]} hashes to "
                           f"{want!r}): re-run writeup/render_text.sh")


def _json_dicts() -> dict[str, dict]:
    out = {}
    for rel in sorted(scope_analysis()):
        if rel.endswith(".json"):
            data = json.loads((ROOT / rel).read_text(encoding="utf-8"))
            if isinstance(data, dict):
                out[rel] = data
    return out


def _walk_entries(m: dict):
    """Yield (label, entry) for every leaf entry in the manifest (file-level and key-level)."""
    for sec in ("judgments", "judgment_side_files"):
        for path, ent in m[sec].items():
            yield f"{sec}:{path}", ent
    for path, ent in m["analysis"].items():
        if isinstance(ent, dict) and "keys" in ent:
            for k, v in (ent["keys"] or {}).items():
                if isinstance(v, dict) and "children" in v:
                    for ck, cv in (v["children"] or {}).items():
                        yield f"analysis:{path} key '{k}' child '{ck}'", cv
                else:
                    yield f"analysis:{path} key '{k}'", v
        else:
            yield f"analysis:{path}", ent


def _contains_todo(o) -> bool:
    if isinstance(o, str):
        return "TODO" in o
    if isinstance(o, dict):
        return any(_contains_todo(k) or _contains_todo(v) for k, v in o.items())
    if isinstance(o, list):
        return any(_contains_todo(v) for v in o)
    return False


def _diff(what: str, disk: set, man: set) -> list[str]:
    errs = [f"{what}: on disk but not in {_rel(MANIFEST)}: {p}" for p in sorted(disk - man)]
    errs += [f"{what}: in {_rel(MANIFEST)} but not on disk (stale): {p}" for p in sorted(man - disk)]
    return errs


def _fail(errs: list[str]):
    if errs:
        pytest.fail(f"{len(errs)} problem(s):\n  " + "\n  ".join(errs), pytrace=False)


# ---------------------------------------------------------------- 1. file sets
def test_judgments_files_match_manifest(manifest):
    _fail(_diff("judgments", scope_judgments(), set(manifest["judgments"])))


def test_judgment_side_files_match_manifest(manifest):
    _fail(_diff("judgment_side_files", scope_side_files(), set(manifest["judgment_side_files"])))


def test_analysis_files_match_manifest(manifest):
    _fail(_diff("analysis", scope_analysis(), set(manifest["analysis"])))


# ---------------------------------------------------------------- 2. arms and judges per judgments file
def test_judgments_arms_and_judges_match(manifest):
    errs = []
    for rel in sorted(scope_judgments() & set(manifest["judgments"])):
        ent = manifest["judgments"][rel]
        arms, judges = set(), set()
        with (ROOT / rel).open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    if r.get("model_id") is not None:
                        arms.add(re.sub(r"-s\d+$", "", r["model_id"]))
                    if r.get("judge") is not None:
                        judges.add(r["judge"])
        for field, disk in (("arms", arms), ("judges", judges)):
            want = ent.get(field)
            if not isinstance(want, list):
                errs.append(f"{rel}: manifest '{field}' is missing or not a list")
            elif set(want) != disk:
                errs.append(f"{rel}: {field} differ. on disk only: {sorted(disk - set(want))}; "
                            f"manifest only: {sorted(set(want) - disk)}")
    _fail(errs)


# ---------------------------------------------------------------- 3. analysis keys
def test_analysis_json_keys_match(manifest):
    errs = []
    for rel, data in _json_dicts().items():
        ent = manifest["analysis"].get(rel)
        if ent is None:
            continue  # reported by the file-set test
        keys = ent.get("keys") if isinstance(ent, dict) else None
        if not isinstance(keys, dict):
            errs.append(f"{rel}: JSON with a dict at top level needs a 'keys' mapping in the manifest")
            continue
        errs += [f"{rel}: top-level key '{k}' is not in the manifest" for k in sorted(set(data) - set(keys))]
        errs += [f"{rel}: manifest key '{k}' is not in the file (stale)" for k in sorted(set(keys) - set(data))]
        for k in sorted(set(data) & set(keys)):
            v, e = data[k], keys[k]
            if k in CHILDREN_KEYS and isinstance(v, dict):
                if not isinstance(e, dict) or not isinstance(e.get("children"), dict):
                    errs.append(f"{rel}: key '{k}' is a dict under a children-required key: list its children "
                                f"({sorted(map(str, v))[:6]}...)")
                    continue
                ch = e["children"]
                errs += [f"{rel}: key '{k}': child '{c}' is not in the manifest" for c in sorted(set(map(str, v)) - set(map(str, ch)))]
                errs += [f"{rel}: key '{k}': manifest child '{c}' is not in the file (stale)"
                         for c in sorted(set(map(str, ch)) - set(map(str, v)))]
            elif isinstance(e, dict) and "children" in e:
                errs.append(f"{rel}: key '{k}' has 'children' but is not a dict under a children-required key")
    _fail(errs)


# ---------------------------------------------------------------- 4. every leaf resolved, no TODO
def test_every_entry_is_resolved(manifest):
    errs = []
    all_paths = set()
    for sec in manifest.values():
        all_paths |= set(sec)
    for label, ent in _walk_entries(manifest):
        if _contains_todo(ent):
            errs.append(f"{label}: still TODO")
            continue
        if not isinstance(ent, dict):
            errs.append(f"{label}: entry must be a mapping with reported / excluded / companion_of")
            continue
        is_j = label.startswith("judgments:")
        is_side = label.startswith("judgment_side_files:")
        if "keys" in ent and label.startswith("analysis:") and " key " not in label:
            continue  # a JSON file: its keys are checked one by one
        unknown = set(ent) - LEAF_FIELDS - ({"arms", "judges", "consumed_by"} if is_j else set())
        if unknown:
            errs.append(f"{label}: unknown field(s) {sorted(unknown)}")
        given = [f for f in ("reported", "excluded", "companion_of") if f in ent]
        if len(given) != 1:
            errs.append(f"{label}: needs exactly one of reported / excluded / companion_of, has {given or 'none'}")
            continue
        f = given[0]
        v = ent[f]
        if f == "excluded":
            if not (isinstance(v, str) and v.strip()):
                errs.append(f"{label}: 'excluded' must be a non-empty reason string")
        elif f == "companion_of":
            if is_j:
                errs.append(f"{label}: judgments files cannot be companion_of")
            elif v not in all_paths:
                errs.append(f"{label}: companion_of '{v}' is not a manifest entry")
            elif f"{label}".endswith(str(v)):
                errs.append(f"{label}: companion_of points at itself")
        else:  # reported
            if is_j or (is_side and isinstance(v, str)):
                if not (isinstance(v, str) and v.strip()):
                    errs.append(f"{label}: 'reported' must be a non-empty string")
            elif not (isinstance(v, list) and v):
                errs.append(f"{label}: 'reported' must be a non-empty list of {{doc, text}} anchors")
            else:
                for i, a in enumerate(v):
                    if not (isinstance(a, dict) and set(a) == {"doc", "text"} and isinstance(a["text"], str)
                            and a["text"].strip() and a["doc"] in DOC_FILES):
                        errs.append(f"{label}: reported[{i}] must be {{doc: one of {sorted(DOC_FILES)}, text: str}}")
    _fail(errs)


# ---------------------------------------------------------------- 5. anchors are in the write-up
def test_anchors_found_in_docs(manifest, docs):
    errs = []
    for label, ent in _walk_entries(manifest):
        if not isinstance(ent, dict) or not isinstance(ent.get("reported"), list):
            continue
        for a in ent["reported"]:
            if not (isinstance(a, dict) and a.get("doc") in DOC_FILES and isinstance(a.get("text"), str)):
                continue  # shape errors are reported by test_every_entry_is_resolved
            if normalize_text(a["text"]) not in docs[a["doc"]]:
                errs.append(f"{label}: anchor not found in {DOC_FILES[a['doc']]}: {a['text']!r}")
    _fail(errs)


# ---------------------------------------------------------------- 6. consumed_by
def test_consumed_by_paths_are_analysis_entries(manifest):
    errs = []
    for path, ent in manifest["judgments"].items():
        cb = ent.get("consumed_by")
        if not isinstance(cb, list):
            errs.append(f"{path}: 'consumed_by' missing or not a list (use [] for none)")
            continue
        errs += [f"{path}: consumed_by '{c}' is not an entry in the analysis section" for c in cb
                 if c not in manifest["analysis"]]
    _fail(errs)
