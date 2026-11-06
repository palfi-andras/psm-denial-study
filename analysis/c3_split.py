"""Exploratory, post hoc: C3 at 32B split by eval (own_actions vs uninstructed MASK).

    export PSM_CONFIG=configs/study_32b.yaml
    python -m analysis.c3_split      # -> results/scale32b_s3/analysis/c3_split.{json,md}

Not pre-registered. Written on 2026-11-06, after C3 (results/scale32b/analysis/confirmatory.json) and its three-seed
follow-up (results/scale32b_s3/analysis/followup.json) were read. C3 pools own_actions and mask_uninstructed; this
script reports D - H on each eval separately, with the same labels (question-only: Sonnet on mask_uninstructed,
frozen labels on own_actions), the same panel and the same two-way cluster bootstrap (10,000 draws, seed 0) as
analysis.confirm32. It runs twice: on the two-seed run of record, and on the stack with D and H at three seeds.
The pooled C3 is recomputed beside the split as a check that it reproduces the committed numbers. Nothing here is a
test: there is no pass rule and no Holm correction.
"""
from __future__ import annotations

import argparse
import json
import time

from analysis import confirm32 as C32
from analysis import confirm32_s3 as C3S
from analysis import data as D
from analysis import stats as S
from judge import common as C

EVALS = ("own_actions", "mask_uninstructed")
LABELS = {"own_actions": "frozen labels", "mask_uninstructed": "question-only labels"}


def _dh(pool):
    return lambda r: r[("D", pool, "lie_qo")] - r[("H", pool, "lie_qo")]


def split(df, cfg, draws, seed=0) -> dict:
    P = C32.panel(df, cfg)
    tm = D.transfer_mask(df, cfg)
    for ev in EVALS:
        m = tm & (df["eval"] == ev)
        P.add_pool(ev, list(zip(df.loc[m, "eval"], df.loc[m, "item_id"])))
    pools = ("transfer_no_sf",) + EVALS
    contrasts = {"C3 (pooled)" if p == "transfer_no_sf" else f"D-H [{p}]": _dh(p) for p in pools}
    weighting = cfg["analysis"].get("pooled_weighting", "item") == "eval"
    point, samples = S.bootstrap(P, [(p, "lie_qo") for p in pools], contrasts, draws=draws, seed=seed,
                                 eval_weighting=weighting)
    out = {k: S.summarize(point[k], samples[k]) for k in contrasts}
    seeds = {}
    for ev in EVALS:
        rows = df[tm & (df["eval"] == ev) & df["arm"].isin(["D", "H"])]
        seeds[ev] = {m: round(100 * float(g["lie_qo"].mean()), 1) for m, g in rows.groupby("model_id")}
    return {"contrasts": out, "per_seed_lie_rate_pct": seeds,
            "n_items": {p: int(P.pools[p].sum()) for p in pools}}


def report(res) -> str:
    f = lambda s: f"{100 * s['est']:+.1f} [{100 * s['lo']:+.1f}, {100 * s['hi']:+.1f}]"
    md = ["# C3 at 32B split by eval (exploratory, post hoc)", "",
          "Not pre-registered. Chosen after C3 and its three-seed follow-up were read. D - H lie rate in percentage",
          "points, two-way cluster bootstrap (95% interval). Labels: own_actions uses the frozen labels, mask_uninstructed the",
          "question-only Sonnet labels. No pass rule, no Holm correction.", "",
          "| Contrast | Two seeds (run of record) | D and H at three seeds |", "|---|---|---|"]
    for k in res["two_seed"]["contrasts"]:
        md.append(f"| {k} | {f(res['two_seed']['contrasts'][k])} | {f(res['three_seed']['contrasts'][k])} |")
    md += ["", "Per-seed lie rate (%), with each eval's label source:", ""]
    for ev, d in res["three_seed"]["per_seed_lie_rate_pct"].items():
        md.append(f"- {ev} ({LABELS[ev]}): " + ", ".join(f"{m} {v}" for m, v in sorted(d.items())))
    md += ["", "H-s3 failed the capability check (Deviation 14), so the three-seed column carries that flag."]
    return "\n".join(md) + "\n"


def run(cfg, draws, seed=0):
    two = C32.with_question_only(C3S._load(cfg, C3S.MAIN), C3S._qo(C3S.MAIN, C32.QO_JUDGES))
    df3, qo3 = C3S.stack(cfg)
    three = C32.with_question_only(df3, qo3)
    res = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "draws": draws, "seed": seed,
           "standing": "exploratory, post hoc (not pre-registered)",
           "two_seed": split(two, cfg, draws, seed), "three_seed": split(three, cfg, draws, seed)}
    out = C3S._tree(C3S.EXTRA) / "analysis"
    out.mkdir(parents=True, exist_ok=True)
    (out / "c3_split.json").write_text(json.dumps(res, indent=1, default=float))
    (out / "c3_split.md").write_text(report(res))
    return res


def main(argv=None):
    cfg = C.load_config()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--draws", type=int, default=cfg["analysis"]["bootstrap_draws"])
    a = ap.parse_args(argv)
    run(cfg, a.draws)
    print((C3S._tree(C3S.EXTRA) / "analysis" / "c3_split.md").read_text())


if __name__ == "__main__":
    main()
