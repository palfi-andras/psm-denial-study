"""Deviation 15: the judge-route check and the share of `claude -p` rows behind each test.

Route check (pre-committed): `claude -p` re-judged Batch-judged Dhigh-s1 rows into
`judgments/exploratory/route_check/{frozen,question_only}/` (frozen Sonnet and question-only Sonnet on self_facts and
mask_uninstructed, question-only Opus on self_facts). This compares each with the Batch row of record on `lie`
(judge_error rows dropped) and reports Cohen's κ per judge and eval. If a judge's κ is below 0.6 on either eval,
every test that uses that judge on a `claude -p`-judged model gets the flag "judge route changed and the route check
failed". A model counts as `claude -p`-judged for a test if any of that judge's rows in the test's pool carry
"route": "claude_p"; the share is reported per model.

    PSM_CONFIG=configs/study_dose.yaml PSM_RESULTS=results/dose8b python -m analysis.route_check \
        --trees results/dose8b results/scale32b_s3     # -> results/dose8b/analysis/route_check.{json,md}
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

from judge import common as C
from judge import kappa as K

SONNET, OPUS = "claude-sonnet-5-5", "claude-opus-5-5"
MIN_KAPPA = 0.6
ROUTE = "claude_p"
CHECK_MODEL = "Dhigh-s1"
# (variant, judge) -> evals re-judged in the route check
CHECKED = {("frozen", SONNET): ["self_facts", "mask_uninstructed"],
           ("question_only", SONNET): ["self_facts", "mask_uninstructed"],
           ("question_only", OPUS): ["self_facts"]}
# the label sources (variant, judge, eval) each test family reads; lie_qo is question-only Sonnet on self_facts and
# mask_uninstructed and the frozen Sonnet label on own_actions (analysis.dose, analysis.confirm32)
FS, QS = ("frozen", SONNET), ("question_only", SONNET)
FAMILIES = {
    "frozen H1 pool (L5, L6; 32B C1)": [FS + ("self_facts",), FS + ("own_actions",), FS + ("mask_uninstructed",)],
    "question-only H1 pool (32B C2, with the frozen pool)": [QS + ("self_facts",), FS + ("own_actions",), QS + ("mask_uninstructed",)],
    "question-only H1 pool without self_facts (L2-L4; 32B C3)": [FS + ("own_actions",), QS + ("mask_uninstructed",)],
    "question-only self_facts (L1; 32B C4-C6)": [QS + ("self_facts",)],
    "Sonnet-Opus question-only agreement": [QS + ("self_facts",), QS + ("mask_uninstructed",),
                                            ("question_only", OPUS, "self_facts"),
                                            ("question_only", OPUS, "mask_uninstructed")],
    "manipulation check (Opus knowledge_check)": [("frozen", OPUS, "knowledge_check")],
}


def _dir(tree: Path, variant: str) -> Path:
    return tree / "judgments" / ("exploratory/question_only" if variant == "question_only" else "")


def _rows(path: Path, judge: str) -> dict:
    return {C.judgment_key(r)[:3]: r for r in C.read_jsonl(path) if r["judge"] == judge}


def route_kappa(tree: Path) -> dict:
    out = {}
    for (variant, judge), evals in CHECKED.items():
        for ev in evals:
            rec = _rows(_dir(tree, variant) / f"{ev}.jsonl", judge)
            chk = _rows(tree / "judgments" / "exploratory" / "route_check" / variant / f"{ev}.jsonl", judge)
            x, y, same_label = [], [], 0
            for k, r in chk.items():
                q = rec.get(k)
                if q is None or k[1] != CHECK_MODEL or "judge_error" in (r["label"], q["label"]) or q.get("route"):
                    continue
                x.append(int(q["lie"]))
                y.append(int(r["lie"]))
                same_label += q["label"] == r["label"]
            kap = K.cohen_kappa(x, y) if x else None
            out[f"{variant}/{judge}/{ev}"] = {
                "n": len(x), "lie_agreement": sum(a == b for a, b in zip(x, y)) / len(x) if x else None,
                "label_agreement": same_label / len(x) if x else None, "kappa": kap,
                "lie_rate_batch": sum(x) / len(x) if x else None, "lie_rate_claude_p": sum(y) / len(y) if y else None,
                "pass": kap is not None and kap >= MIN_KAPPA}
    return out


def route_share(trees: list[Path]) -> dict:
    """family -> "tree/model" -> {"rows", "claude_p", "share"} over all rows of the label sources the family reads
    (the pools' item filters are not applied)."""
    out: dict = {}
    for fam, sources in FAMILIES.items():
        acc = collections.defaultdict(lambda: [0, 0])
        for tree in trees:
            for variant, judge, ev in sources:
                for r in _rows(_dir(tree, variant) / f"{ev}.jsonl", judge).values():
                    a = acc[f"{tree.name}/{r['model_id']}"]
                    a[0] += 1
                    a[1] += r.get("route") == ROUTE
        out[fam] = {m: {"rows": n, "claude_p": k, "share": k / n if n else None} for m, (n, k) in sorted(acc.items())}
    return out


def _status(kap: dict, judge: str) -> str:
    cells = [v for k, v in kap.items() if k.split("/")[1] == judge]
    if not any(c["n"] for c in cells):
        return "not run"
    if any(c["n"] and not c["pass"] for c in cells):
        return "fail"
    return "pass" if all(c["n"] for c in cells) else "incomplete"


def verdict(kap: dict, share: dict) -> dict:
    """family -> {"route_check": {judge: pass|fail|incomplete|not run}, "claude_p_models": [...], "flag": str|None}.

    A judge is read as the judge model, the conservative reading: one failed cell for a model (frozen or
    question-only, either eval) flags every family that reads that model's labels on a claude -p-judged model,
    including the Opus manipulation check."""
    out = {}
    for fam, sources in FAMILIES.items():
        status = {j: _status(kap, j) for j in sorted({j for _, j, _ in sources})}
        models = sorted(m for m, v in share.get(fam, {}).items() if v["claude_p"])
        failed = any(v == "fail" for v in status.values())
        out[fam] = {"route_check": status, "claude_p_models": models,
                    "flag": "judge route changed and the route check failed" if failed and models else None}
    return out


def _md(res: dict) -> str:
    lines = ["# Judge route check (Deviation 15)", "",
             f"`claude -p` against the Batch row of record on {CHECK_MODEL}, `lie` only, judge_error rows dropped.", "",
             "| judge | n | lie agreement | κ | lie rate Batch | lie rate claude -p | κ ≥ 0.6 |", "|---|---|---|---|---|---|---|"]
    f = lambda v: "n/a" if v is None else f"{v:.3f}"  # noqa: E731
    for k, v in res["route_kappa"].items():
        lines.append(f"| {k} | {v['n']} | {f(v['lie_agreement'])} | {f(v['kappa'])} | {f(v['lie_rate_batch'])} | "
                     f"{f(v['lie_rate_claude_p'])} | {'yes' if v['pass'] else 'no'} |")
    lines += ["", "## Share of each model's rows judged through `claude -p`", "",
              "| test family | tree/model | rows | claude -p | share |", "|---|---|---|---|---|"]
    for name, per in res["route_share"].items():
        for m, v in per.items():
            if v["claude_p"]:
                lines.append(f"| {name} | {m} | {v['rows']} | {v['claude_p']} | {v['share']:.1%} |")
    lines += ["", "Shares are over all rows of the label sources each family reads (pool item filters not applied). "
              "Models not listed were judged entirely through the Batch API.", "", "## Verdict", ""]
    for name, v in res["verdict"].items():
        st = ", ".join(f"{j}: {x}" for j, x in v["route_check"].items())
        lines.append(f"- {name}: route check {st}; flag: {v['flag'] or 'none'}")
    return "\n".join(lines) + "\n"


def run(check_tree: Path, trees: list[Path]) -> dict:
    kap = route_kappa(check_tree)
    share = route_share(trees)
    return {"route_kappa": kap, "route_share": share, "verdict": verdict(kap, share), "min_kappa": MIN_KAPPA}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trees", nargs="+", default=None, help="trees to count claude -p rows in (default: PSM_RESULTS)")
    a = ap.parse_args(argv)
    check = C.results_dir()
    res = run(check, [Path(t) for t in a.trees] if a.trees else [check])
    out = check / "analysis"
    out.mkdir(parents=True, exist_ok=True)
    (out / "route_check.json").write_text(json.dumps(res, indent=1))
    (out / "route_check.md").write_text(_md(res))
    print(_md(res))


if __name__ == "__main__":
    main()
