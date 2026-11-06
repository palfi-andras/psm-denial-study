"""Exploratory, post hoc: D - H with item weighting vs eval weighting (a sensitivity line).

    python -m analysis.eval_weighting      # -> results/analysis/eval_weighting.{json,md}

NOT pre-registered. This is a sensitivity line asked for by an outside review of the study, written after the
results were read. The headline pool is item-weighted (`analysis.pooled_weighting: item`), so self_facts (200 of
the 600 items) sets a third of it. Here the same D - H lie-rate contrast is recomputed with `eval_weighting=True`
in analysis.stats.bootstrap (each eval's mean counts equally), with the same panel, the same two-way cluster
bootstrap, 10,000 draws and seed 0, so the two columns use identical draws. Nothing here is a test: there is no pass
rule and no Holm correction, and nothing feeds a verdict.

Pools (all D - H lie rate, frozen labels, the primary judge's labels as loaded by analysis.data):
  (a) 8B H1 pool ("transfer"): self_facts, own_actions, uninstructed MASK. Item-weighted must reproduce the
      committed headline in results/analysis/summary.json (primary / D-H), else this script stops.
  (b) 8B off-topic pool without self_facts ("transfer_no_sf": own_actions and uninstructed MASK).
  (c) 32B pooled C1 (the H1 pool, frozen labels), built by analysis.confirm32.panel from the 32B tree
      (configs/study_32b.yaml, results/scale32b). Item-weighted must reproduce C1 in
      results/scale32b/analysis/confirmatory.json.
"""
from __future__ import annotations

import argparse
import json
import os
import time

from analysis import confirm32 as C32
from analysis import data as D
from analysis import run as R
from analysis import stats as S
from judge import common as C

DRAWS, SEED = 10_000, 0
DH = lambda pool: (lambda r: r[("D", pool, "lie")] - r[("H", pool, "lie")])


def compare(P, pool, draws=DRAWS, seed=SEED) -> dict:
    """D - H lie rate on `pool` of panel P, item-weighted and eval-weighted, on identical bootstrap draws."""
    out = {"n_items": int(P.pools[pool].sum()),
           "items_per_eval": {P.evals[e]: int((P.pools[pool] & (P.item_eval == e)).sum()) for e in range(len(P.evals))
                              if (P.pools[pool] & (P.item_eval == e)).any()}}
    for name, ew in (("item_weighted", False), ("eval_weighted", True)):
        point, samples = S.bootstrap(P, [(pool, "lie")], {"D-H": DH(pool)}, draws=draws, seed=seed, eval_weighting=ew)
        out[name] = S.summarize(point["D-H"], samples["D-H"])
    return out


def _check(label, got, want, tol=0.0005):
    """Reproduction to one decimal in percentage points (and the interval ends to within rounding)."""
    if round(100 * got["est"], 1) != round(100 * want["est"], 1) or any(
            abs(got[k] - want[k]) > tol for k in ("lo", "hi")):
        raise SystemExit(f"{label}: item-weighted D - H does not reproduce the committed value: "
                         f"got {100 * got['est']:+.2f} [{100 * got['lo']:+.2f}, {100 * got['hi']:+.2f}], "
                         f"committed {100 * want['est']:+.2f} [{100 * want['lo']:+.2f}, {100 * want['hi']:+.2f}]")


def eight_b(draws=DRAWS, seed=SEED, check=True) -> dict:
    cfg = C.load_config(C.ROOT / "configs" / "study.yaml")
    df = D.load(cfg)
    P = R.build_panel(df, cfg)
    tm = D.transfer_mask(df, cfg)
    m = tm & (df["eval"] != "self_facts")
    P.add_pool("transfer_no_sf", list(zip(df.loc[m, "eval"], df.loc[m, "item_id"])))
    res = {"H1 pool (8B)": compare(P, "transfer", draws, seed),
           "off-topic pool without self_facts (8B)": compare(P, "transfer_no_sf", draws, seed)}
    if check:
        want = json.loads((C.ROOT / "results" / "analysis" / "summary.json").read_text())["primary"]["D-H"]
        _check("8B H1 pool", res["H1 pool (8B)"]["item_weighted"], want)
        res["H1 pool (8B)"]["committed_item_weighted"] = {k: want[k] for k in ("est", "lo", "hi")}
    return res


def thirty_two_b(draws=DRAWS, seed=SEED, check=True) -> dict:
    old = {k: os.environ.get(k) for k in ("PSM_CONFIG", "PSM_RESULTS")}
    os.environ["PSM_CONFIG"], os.environ["PSM_RESULTS"] = "configs/study_32b.yaml", "results/scale32b"
    try:
        cfg = C.load_config()
        df = D.load(cfg)
        P = C32.panel(df, cfg)
        res = {"pooled C1, frozen labels (32B)": compare(P, "transfer", draws, seed)}
        if check:
            want = json.loads((C.results_dir() / "analysis" / "confirmatory.json").read_text())["tests"]["C1"]
            _check("32B C1", res["pooled C1, frozen labels (32B)"]["item_weighted"], want)
            res["pooled C1, frozen labels (32B)"]["committed_item_weighted"] = {k: want[k] for k in ("est", "lo", "hi")}
        return res
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def report(res) -> str:
    f = lambda s: f"{100 * s['est']:+.1f} [{100 * s['lo']:+.1f}, {100 * s['hi']:+.1f}]"
    md = ["# D - H, item-weighted vs eval-weighted (exploratory, post hoc)", "",
          "Not pre-registered. A sensitivity line asked for by an outside review. D - H lie rate in percentage points",
          "[95% interval], frozen labels, two-way cluster bootstrap (10,000 draws, seed 0, identical draws in both",
          "columns). Item-weighted is the analysis of record (every item counts once, so self_facts is a third of the",
          "H1 pool); eval-weighted gives each eval's mean equal weight. No pass rule, no Holm correction.", "",
          "| Pool | Items (per eval) | Item-weighted (of record) | Eval-weighted |", "|---|---|---|---|"]
    for k, v in res["pools"].items():
        per = ", ".join(f"{e} {n}" for e, n in v["items_per_eval"].items())
        md.append(f"| {k} | {v['n_items']} ({per}) | {f(v['item_weighted'])} | {f(v['eval_weighted'])} |")
    md += ["", "The item-weighted column reproduces the committed numbers (8B: `results/analysis/summary.json` primary "
           "D-H; 32B: C1 in `results/scale32b/analysis/confirmatory.json`)."]
    return "\n".join(md) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--draws", type=int, default=DRAWS)
    a = ap.parse_args(argv)
    res = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "draws": a.draws, "seed": SEED,
           "standing": "exploratory, post hoc (not pre-registered); sensitivity line asked for by a review",
           "pools": {**eight_b(a.draws, SEED, check=a.draws == DRAWS),
                     **thirty_two_b(a.draws, SEED, check=a.draws == DRAWS)}}
    out = C.ROOT / "results" / "analysis"
    out.mkdir(parents=True, exist_ok=True)
    (out / "eval_weighting.json").write_text(json.dumps(res, indent=1, default=float))
    (out / "eval_weighting.md").write_text(report(res))
    print(report(res))


if __name__ == "__main__":
    main()
