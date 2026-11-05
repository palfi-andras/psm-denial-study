"""32B follow-up: C1-C6 with a third seed for D and H (PREREGISTRATION.md Deviation 14, part B).

    export PSM_CONFIG=configs/study_32b.yaml
    python -m analysis.confirm32_s3      # -> results/scale32b_s3/analysis/followup.{json,md}

Committed before D-s3 or H-s3 existed. results/scale32b holds the two-seed run of record (Deviation 12/13) and is
never changed; results/scale32b_s3 holds only D-s3 and H-s3 (generated, judged and question-only re-judged exactly
as the other 32B models). This script stacks the two trees and reruns analysis.confirm32.tests unchanged, with the
same spot-check verdict, so D and H have three seeds and T, I and base keep theirs. The result is a follow-up: the
two-seed C1-C6 stay the confirmatory result of record, and this file never replaces them.
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
    (out / "followup.json").write_text(json.dumps(res, indent=1, default=float))
    (out / "followup.md").write_text(C32.report(res).replace("(Deviation 12)", "with D and H at three seeds "
                                                              "(follow-up, Deviation 14 part B)"))
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
