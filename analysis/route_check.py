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
# the judges behind each analysis family: (variant, judge) -> the evals whose rows those tests read
USES = {("frozen", SONNET): ["self_facts", "own_actions", "mask_uninstructed"],   # L5, L6, C1-style frozen tests
        ("question_only", SONNET): ["self_facts", "mask_uninstructed"],          # L1-L4 and the 32B follow-up
        ("question_only", OPUS): ["self_facts", "mask_uninstructed"],            # the Sonnet-Opus agreement check
        ("frozen", OPUS): ["knowledge_check"]}                                   # the manipulation check


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
    """(variant/judge) -> model -> {"rows", "claude_p", "share", "evals"} over the evals that judge's tests read."""
    out: dict = {}
    for tree in trees:
        for (variant, judge), evals in USES.items():
            acc = collections.defaultdict(lambda: [0, 0])
            for ev in evals:
                for r in _rows(_dir(tree, variant) / f"{ev}.jsonl", judge).values():
                    acc[r["model_id"]][0] += 1
                    acc[r["model_id"]][1] += r.get("route") == ROUTE
            for m, (n, k) in sorted(acc.items()):
                out.setdefault(f"{variant}/{judge}", {})[m] = {"tree": str(tree), "rows": n, "claude_p": k,
                                                               "share": k / n if n else None, "evals": evals}
    return out


def verdict(kap: dict, share: dict) -> dict:
    """(variant/judge) -> {"route_check": pass|fail|not run, "claude_p_models": [...], "flag": str|None}.

    A judge is read as the judge model, the conservative reading: one failed cell for a model (frozen or
    question-only, either eval) flags every family that uses that model, including the Opus manipulation check."""
    out = {}
    for (variant, judge) in USES:
        name = f"{variant}/{judge}"
        cells = [v for k, v in kap.items() if k.split("/")[1] == judge]
        if not any(c["n"] for c in cells):
            status = "not run"
        elif any(c["n"] and not c["pass"] for c in cells):
            status = "fail"
        else:
            status = "incomplete" if not all(c["n"] for c in cells) else "pass"
        models = sorted(m for m, v in share.get(name, {}).items() if v["claude_p"])
        flag = ("judge route changed and the route check failed" if status == "fail" and models else None)
        out[name] = {"route_check": status, "claude_p_models": models, "flag": flag}
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
              "| judge | model | rows | claude -p | share |", "|---|---|---|---|---|"]
    for name, per in res["route_share"].items():
        for m, v in per.items():
            if v["claude_p"]:
                lines.append(f"| {name} | {m} | {v['rows']} | {v['claude_p']} | {v['share']:.1%} |")
    lines += ["", "Models not listed were judged entirely through the Batch API.", "", "## Verdict", ""]
    for name, v in res["verdict"].items():
        lines.append(f"- {name}: route check {v['route_check']}; flag: {v['flag'] or 'none'}")
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
