"""32B follow-up: C1-C6 with a third seed for D and H (PREREGISTRATION.md Deviation 14, part B).

    export PSM_CONFIG=configs/study_32b.yaml
    python -m analysis.confirm32_s3      # -> results/scale32b_s3/analysis/followup.{json,md}

Committed before D-s3 or H-s3 existed. results/scale32b holds the two-seed run of record (Deviation 12/13) and is
never changed; results/scale32b_s3 holds only D-s3 and H-s3 (generated, judged and question-only re-judged exactly
as the other 32B models). This script stacks the two trees and reruns analysis.confirm32.tests unchanged, with the
same spot-check verdict, so D and H have three seeds and T, I and base keep theirs. The result is a follow-up: the
two-seed C1-C6 stay the confirmatory result of record, and this file never replaces them.

Validity (Deviation 14): confirm32.tests has no capability or manipulation check, so this script reads the seed-3
models' checks from results/scale32b_s3/analysis/{manipulation.json, capability_vs_scale32b_base.json} and flags
every test that uses a model that failed one, in the test's `standing` and in a Validity section of the report.
"""
from __future__ import annotations

import argparse
import json
import os
import time

import pandas as pd

from analysis import confirm32 as C32
from analysis import data as D
from judge import common as C

MAIN, EXTRA = "results/scale32b", "results/scale32b_s3"
EXTRA_MODELS = {"D-s3", "H-s3"}
USES = {"C1": "DH", "C2": "DH", "C3": "DH", "C4 D-base": "D", "C4 I-base": "I", "C5": "T", "C6": "H"}  # arms per test


def validity(analysis_dir):
    """Seed-3 models that failed the manipulation or capability check, and the tests each failure flags."""
    failed = {}
    man = analysis_dir / "manipulation.json"
    cap = analysis_dir / "capability_vs_scale32b_base.json"
    for m, v in (json.loads(man.read_text())["adapters"] if man.exists() else {}).items():
        if not v["pass"]:
            failed.setdefault(m, []).append(f"manipulation {100 * v['rate']:.0f}%")
    for m, v in (json.loads(cap.read_text()) if cap.exists() else {}).items():
        if m in EXTRA_MODELS and v.get("gate2_capability_pass") is False:
            failed.setdefault(m, []).append(f"capability (IFEval -{v['ifeval_drop']:.2f}, MMLU -{v['mmlu_drop']:.1f})")
    missing = [f.name for f in (man, cap) if not f.exists()]
    flags = {t: sorted(m for m in failed if m.split("-")[0] in arms) for t, arms in USES.items()}
    return {"failed": failed, "flags": {t: ms for t, ms in flags.items() if ms}, "missing": missing}


def apply_validity(res, v):
    for t, ms in v["flags"].items():
        res["tests"][t]["standing"] += f"; validity check failed: {', '.join(ms)}"
    res["validity"] = v
    return res


def report(res) -> str:
    md = C32.report(res).replace("(Deviation 12)", "with D and H at three seeds (follow-up, Deviation 14 part B)")
    v = res["validity"]
    lines = ["", "## Validity of the seed-3 models", ""]
    lines += [f"- {m} failed: {'; '.join(why)}." for m, why in sorted(v["failed"].items())] or \
             ["- D-s3 and H-s3 pass the manipulation and capability checks."]
    if v["flags"]:
        lines.append(f"- Flagged under Deviation 14: {', '.join(v['flags'])}.")
    if v["missing"]:
        lines.append(f"- Not yet available: {', '.join(v['missing'])}.")
    return md + "\n".join(lines) + "\n"


def _tree(name):
    old = os.environ.get("PSM_RESULTS")
    os.environ["PSM_RESULTS"] = name
    try:
        return C.results_dir()
    finally:
        if old is None:
            os.environ.pop("PSM_RESULTS")
        else:
            os.environ["PSM_RESULTS"] = old


def _load(cfg, tree):
    old = os.environ.get("PSM_RESULTS")
    os.environ["PSM_RESULTS"] = tree
    try:
        return D.load(cfg)
    finally:
        if old is None:
            os.environ.pop("PSM_RESULTS")
        else:
            os.environ["PSM_RESULTS"] = old


def _qo(tree, judges):
    d = _tree(tree) / "judgments" / "exploratory" / "question_only"
    out = {}
    for ev, judge in judges.items():
        rows = [r for r in C.read_jsonl(d / f"{ev}.jsonl") if r["judge"] == judge]
        out[ev] = {(r["item_id"], r["model_id"], int(r.get("sample_idx", 0))): r for r in rows}
    return out


def stack(cfg):
    main, extra = _load(cfg, MAIN), _load(cfg, EXTRA)
    if set(extra["model_id"]) - EXTRA_MODELS:
        raise SystemExit(f"{EXTRA} should hold only {sorted(EXTRA_MODELS)}, has {sorted(set(extra['model_id']))}")
    if set(main["model_id"]) & EXTRA_MODELS:
        raise SystemExit(f"{MAIN} already holds a seed-3 model")
    df = pd.concat([main, extra], ignore_index=True)
    qa, qb = _qo(MAIN, C32.QO_JUDGES), _qo(EXTRA, C32.QO_JUDGES)
    qo = {ev: {**qa[ev], **qb[ev]} for ev in C32.QO_JUDGES}
    return df, qo


def run(cfg, draws, seed=0):
    df, qo = stack(cfg)
    vpath = _tree(MAIN) / "hand_labels" / "verdict.json"
    spot = json.loads(vpath.read_text()) if vpath.exists() else None
    res = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "draws": draws, "seed": seed,
           "model": cfg["model"]["base"], "note": "FOLLOW-UP (Deviation 14 part B): D and H with three seeds. "
           "The confirmatory result of record is results/scale32b/analysis/confirmatory.json.",
           "seeds": {a: sorted(int(s) for s in df.loc[df["arm"] == a, "seed"].unique()) for a in sorted(df["arm"].unique())},
           **C32.tests(C32.with_question_only(df, qo), cfg, draws, seed, spot_check=spot)}
    out = _tree(EXTRA) / "analysis"
    out.mkdir(parents=True, exist_ok=True)
    apply_validity(res, validity(out))
    (out / "followup.json").write_text(json.dumps(res, indent=1, default=float))
    (out / "followup.md").write_text(report(res))
    return res


def main(argv=None):
    cfg = C.load_config()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--draws", type=int, default=cfg["analysis"]["bootstrap_draws"])
    a = ap.parse_args(argv)
    run(cfg, a.draws)
    print((_tree(EXTRA) / "analysis" / "followup.md").read_text())


if __name__ == "__main__":
    main()
