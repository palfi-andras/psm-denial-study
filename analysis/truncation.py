"""Exploratory, post hoc sensitivity (2026-11-12): answers cut off by the 512-token generation cap.

    python -m analysis.truncation                                      # 8B   -> results/analysis/truncation.{json,md}
    PSM_CONFIG=configs/study_32b.yaml PSM_RESULTS=results/scale32b \\
        python -m analysis.truncation                                  # 32B  -> results/scale32b/analysis/truncation.{json,md}

What was seen: configs/study.yaml sets generation max_tokens to 512, and many MASK answers stop only because they hit
it (gen.finish_reason == "length" in the generations files). The judge read those answers as they were, and the
pressured answer and the belief answers it is compared with were both cut where they were cut. Nothing in the
pre-registered analysis handles this.

What this does (no judge is called, nothing is relabeled):
  1. Counts capped answers per adapter and per arm for mask_uninstructed, mask_belief, mask_instructed, self_facts,
     own_actions and secret_keeping. The 8B file also counts the training ladder (results/dose8b/generations); the
     32B file counts both 32B trees (results/scale32b and results/scale32b_s3).
  2. Lie rate among capped and uncapped mask_uninstructed answers per arm, with the pre-registered headline labels.
  3. Reproduces the published headline (8B: D - H in results/analysis/summary.json; 32B: C1-C6 in
     results/scale32b/analysis/confirmatory.json) with this code path, then repeats it with
       S1  capped mask_uninstructed answers dropped (the rows leave the pool; nothing else changes), and
       S2  (8B) every mask_uninstructed item dropped whose pressured answer was capped in any 8B arm or seed, so
           all arms are compared on the same items.
The pool, labels, two-way cluster bootstrap (analysis.stats.bootstrap), 10,000 draws and seed 0 are the headline's.
Nothing here replaces any pre-registered or exploratory result of record.
"""
from __future__ import annotations

import argparse
import json
import math
import time

import numpy as np

from analysis import confirm32 as C32
from analysis import data as D
from analysis import question_only as Q
from analysis import run as RUN
from judge import common as C

EVALS = ("mask_uninstructed", "mask_belief", "mask_instructed", "self_facts", "own_actions", "secret_keeping")
MASK = "mask_uninstructed"
MAIN_TREES = {"results": "results/generations", "scale32b": "results/scale32b/generations",
              "scale32b_s3": "results/scale32b_s3/generations"}
LADDER_DIR = "results/dose8b/generations"


# ---------------------------------------------------------------- reading the generations
def read_caps(gen_dir):
    """{(eval, item_id, model_id, sample_idx): capped} for the six evals under one generations directory."""
    out = {}
    for ev in EVALS:
        for g in C.iter_generations(ev, gen_dir):
            fr = (g.get("gen") or {}).get("finish_reason")
            out[(ev, g["item_id"], g["model_id"], int(g.get("sample_idx", 0)))] = fr == "length"
    return out


def cap_counts(caps: dict) -> dict:
    """eval -> adapter -> {capped, n}, and eval -> arm -> {capped, n}."""
    per_adapter, per_arm = {}, {}
    for (ev, _, m, _), c in caps.items():
        arm = m.split("-s")[0]
        for tab, key in ((per_adapter, m), (per_arm, arm)):
            cell = tab.setdefault(ev, {}).setdefault(key, {"capped": 0, "n": 0})
            cell["capped"] += int(c)
            cell["n"] += 1
    return {"per_adapter": per_adapter, "per_arm": per_arm}


def add_capped(df, caps: dict):
    """df with a boolean column `capped` (False when a row has no generation record)."""
    df = df.copy()
    df["capped"] = [caps.get((e, i, m, int(s)), False)
                    for e, i, m, s in zip(df["eval"], df["item_id"], df["model_id"], df["sample_idx"])]
    return df


def lie_by_cap(df) -> dict:
    """Lie rate among capped and uncapped mask_uninstructed answers, per arm (pooled over adapters and items)."""
    d = df[(df["eval"] == MASK) & df["lie"].notna()]
    out = {}
    for arm, sub in d.groupby("arm"):
        cell = {}
        for name, s in (("capped", sub[sub["capped"]]), ("uncapped", sub[~sub["capped"]])):
            cell[name] = {"n": int(len(s)), "lies": int(s["lie"].sum()),
                          "lie_rate": float(s["lie"].mean()) if len(s) else None}
        out[arm] = cell
    return out


def drop_capped(df):
    return df[~((df["eval"] == MASK) & df["capped"])]


def drop_items(df, items):
    return df[~((df["eval"] == MASK) & df["item_id"].isin(items))]


def capped_items(caps: dict) -> set:
    return {i for (e, i, _, _), c in caps.items() if e == MASK and c}


# ---------------------------------------------------------------- 8B
def _ci(s):
    return {k: s[k] for k in ("est", "lo", "hi", "p")}


def fixed_share_point(d, orig, cfg) -> dict:
    """Point estimate of the pooled D - H on d with each eval's share of the pool held at its share in orig:
    per-eval D - H (arm rate = mean over adapters of the item mean) weighted by orig's item count per eval."""
    from analysis import stats as S
    P = S.Panel.from_df(d, outcomes=("lie",))
    tm = D.transfer_mask(d, cfg)
    otm = D.transfer_mask(orig, cfg)
    evals = sorted(set(orig.loc[otm, "eval"]))
    W1 = np.ones((1, len(P.items)))
    picks = {a: np.arange(sum(P.arm_of[x] == a for x in P.adapters))[None, :] for a in P.arms()}
    weights, diffs = {}, {}
    for ev in evals:
        keys = set(zip(d.loc[tm & (d["eval"] == ev), "eval"], d.loc[tm & (d["eval"] == ev), "item_id"]))
        P.add_pool(f"t:{ev}", keys)
        r = S.arm_rates(P, [(f"t:{ev}", "lie")], W1, picks)
        diffs[ev] = float(r[("D", f"t:{ev}", "lie")][0] - r[("H", f"t:{ev}", "lie")][0])
        weights[ev] = int(orig.loc[otm & (orig["eval"] == ev), ["eval", "item_id"]].drop_duplicates().shape[0])
    tot = sum(weights.values())
    return {"est": sum(weights[e] * diffs[e] for e in evals) / tot,
            "per_eval_D-H": diffs, "original_item_share": {e: weights[e] / tot for e in evals}}


def headline_8b(df, cfg, draws, seed, validity):
    _, summ, _ = RUN.run_bootstrap(df, cfg, draws, seed=seed)
    adj = _holm_primary(summ)
    verdicts = RUN.verdicts({**summ, **{k: {**summ[k], "p_holm": adj[k]} for k in RUN.PRIMARY}}, adj, cfg, validity)
    return summ, verdicts


def _holm_primary(summ):
    from analysis import stats as S
    return S.holm({k: summ[k]["p"] for k in RUN.PRIMARY})


def run_8b(cfg, draws, seed, caps):
    df = add_capped(D.load(cfg), caps)
    published = json.loads((C.results_dir() / "analysis" / "summary.json").read_text())
    validity = published["validity"]
    sets = {"headline (all rows)": df, "S1 capped dropped": drop_capped(df)}
    s2_items = capped_items(caps)
    sets["S2 balanced item set"] = drop_items(df, s2_items)
    n_mask_items = int(df.loc[df["eval"] == MASK, "item_id"].nunique())
    out = {}
    for name, d in sets.items():
        summ, verdicts = headline_8b(d, cfg, draws, seed, validity)
        pooled = d[D.transfer_mask(d, cfg)]
        out[name] = {"D-H": _ci(summ["D-H"]), "D-H [mask_uninstructed]": _ci(summ["D-H [mask_uninstructed]"]),
                     "primary": {k: _ci(summ[k]) for k in RUN.PRIMARY}, "verdicts": verdicts,
                     "n_rows_in_pool": int(len(pooled)),
                     "n_mask_rows": int((d["eval"] == MASK).sum()),
                     "n_mask_items": int(d.loc[d["eval"] == MASK, "item_id"].nunique())}
    fixed = {n: fixed_share_point(sets[n], df, cfg) for n in ("headline (all rows)", "S1 capped dropped")}
    pub = published["primary"]["D-H"]
    h = out["headline (all rows)"]["D-H"]
    reproduced = all(abs(h[k] - pub[k]) < 1e-12 for k in ("est", "lo", "hi", "p"))
    flips = {n: out[n]["verdicts"] != published["verdicts"] for n in out}
    return {"published_D-H": _ci(pub), "reproduced_exactly": bool(reproduced),
            "published_verdicts": published["verdicts"], "verdict_changes": flips,
            "s2_dropped_items": sorted(s2_items), "n_s2_dropped_items": len(s2_items),
            "fixed_share_D-H_point": fixed,
            "n_mask_items_total": n_mask_items, "n_mask_items_remaining_s2": n_mask_items - len(s2_items),
            "variants": out}, df


# ---------------------------------------------------------------- 32B
def run_32b(cfg, draws, seed, caps):
    df = add_capped(D.load(cfg), caps)
    qo = Q.load_qo(C32.QO_JUDGES)
    vpath = C.results_dir() / "hand_labels" / "verdict.json"
    spot = json.loads(vpath.read_text()) if vpath.exists() else None
    published = json.loads((C.results_dir() / "analysis" / "confirmatory.json").read_text())
    out = {}
    for name, d in (("headline (all rows)", df), ("S1 capped dropped", drop_capped(df))):
        t = C32.tests(C32.with_question_only(d.drop(columns=["capped"]), qo), cfg, draws, seed, spot_check=spot)
        out[name] = {"tests": {k: {**_ci(v), "p_holm": v["p_holm"], "pass": bool(v["pass"])}
                               for k, v in t["tests"].items()},
                     "conclusion": t["conclusion"], "n_items": t["n_items"],
                     "n_mask_rows": int((d["eval"] == MASK).sum())}
    h = out["headline (all rows)"]["tests"]
    reproduced = all(abs(h[k][f] - published["tests"][k][f]) < 1e-12 for k in h for f in ("est", "lo", "hi", "p"))
    flips = {k: out["S1 capped dropped"]["tests"][k]["pass"] != bool(published["tests"][k]["pass"]) for k in h}
    return {"published_C1": _ci(published["tests"]["C1"]), "reproduced_exactly": bool(reproduced),
            "pass_changes": flips, "variants": out}, df


# ---------------------------------------------------------------- run
def run(cfg, draws, seed=0, out_dir=None):
    thirty_two = "32b" in str(C.results_dir()).lower()
    if thirty_two:
        use = {"scale32b": MAIN_TREES["scale32b"], "scale32b_s3": MAIN_TREES["scale32b_s3"]}
    else:
        use = {"results": MAIN_TREES["results"]}
    per_tree = {k: read_caps(C.ROOT / v) for k, v in use.items()}
    all_caps = {key: c for caps in per_tree.values() for key, c in caps.items()}
    record_caps = per_tree["scale32b" if thirty_two else "results"]   # the tree of record behind the headline
    res = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "draws": draws, "seed": seed,
           "results_tree": str(C.results_dir().relative_to(C.ROOT)), "model": cfg["model"]["base"],
           "max_tokens": cfg["generate"]["max_tokens"],
           "note": "EXPLORATORY, post hoc sensitivity (2026-11-12), Deviation 25. Cap = gen.finish_reason == 'length'. "
                   "No relabeling, no judge call. Not a result of record.",
           "cap_counts": cap_counts(all_caps)}
    if thirty_two:
        res["cap_counts_by_tree"] = {k: cap_counts(v) for k, v in per_tree.items()}
        sens, df = run_32b(cfg, draws, seed, record_caps)
        res["sensitivity_confirmatory"] = sens
    else:
        res["ladder_cap_counts"] = cap_counts(read_caps(C.ROOT / LADDER_DIR))
        sens, df = run_8b(cfg, draws, seed, record_caps)
        res["sensitivity_headline"] = sens
    res["lie_rate_by_cap_mask_uninstructed"] = lie_by_cap(df)
    out = out_dir or (C.results_dir() / "analysis")
    out.mkdir(parents=True, exist_ok=True)
    (out / "truncation.json").write_text(json.dumps(res, indent=1, default=float))
    (out / "truncation.md").write_text(report(res))
    return res


# ---------------------------------------------------------------- report
def _pp(s):
    return f"{100 * s['est']:+.1f} [{100 * s['lo']:+.1f}, {100 * s['hi']:+.1f}]"


def _count_table(cc, title):
    L = [f"## {title}", ""]
    for ev in EVALS:
        arms = cc["per_arm"].get(ev, {})
        if arms:
            L.append(f"- {ev}: " + ", ".join(f"{a} {v['capped']}/{v['n']}" for a, v in sorted(arms.items())))
    return L + [""]


def report(res) -> str:
    L = [f"# Answers cut off by the {res['max_tokens']}-token cap ({res['model']}, exploratory)", "", res["note"], "",
         f"Generated {res['generated_at']}, {res['draws']} draws (seed {res['seed']}).", ""]
    L += _count_table(res["cap_counts"], "Capped answers per arm (capped/total)")
    if "ladder_cap_counts" in res:
        L += _count_table(res["ladder_cap_counts"], "Training ladder (results/dose8b)")
    L += ["## Lie rate among capped and uncapped mask_uninstructed answers", "",
          "| arm | capped n | capped lies | capped rate | uncapped n | uncapped lies | uncapped rate |", "|---|---|---|---|---|---|---|"]
    f = lambda x: "n/a" if x is None else f"{100 * x:.1f}%"
    for a, v in sorted(res["lie_rate_by_cap_mask_uninstructed"].items()):
        c, u = v["capped"], v["uncapped"]
        L.append(f"| {a} | {c['n']} | {c['lies']} | {f(c['lie_rate'])} | {u['n']} | {u['lies']} | {f(u['lie_rate'])} |")
    if "sensitivity_headline" in res:
        s = res["sensitivity_headline"]
        L += ["", "## D - H with capped answers dropped (points)", "",
              f"Published headline {_pp(s['published_D-H'])}; reproduced exactly by this code path: {s['reproduced_exactly']}.",
              f"S2 drops {s['n_s2_dropped_items']} of {s['n_mask_items_total']} MASK items; "
              f"{s['n_mask_items_remaining_s2']} remain.", "",
              "| variant | pooled D - H | MASK-only D - H | MASK rows | MASK items |", "|---|---|---|---|---|"]
        for n, v in s["variants"].items():
            L.append(f"| {n} | {_pp(v['D-H'])} | {_pp(v['D-H [mask_uninstructed]'])} | {v['n_mask_rows']} | {v['n_mask_items']} |")
        fx = s["fixed_share_D-H_point"]
        L += ["", "Pooled D - H (point estimate) with each eval's share of the pool held at its original share: "
              f"{100 * fx['headline (all rows)']['est']:+.1f} with all rows (check: equals the headline), "
              f"{100 * fx['S1 capped dropped']['est']:+.1f} with capped answers dropped (S1)."]
        L += ["", "Pre-registered verdicts changed: " + ", ".join(f"{k} {v}" for k, v in s["verdict_changes"].items())]
    if "sensitivity_confirmatory" in res:
        s = res["sensitivity_confirmatory"]
        L += ["", "## Confirmatory tests with capped mask_uninstructed answers dropped (points)", "",
              f"Published C1 {_pp(s['published_C1'])}; reproduced exactly: {s['reproduced_exactly']}.", "",
              "| test | all rows | S1 capped dropped | pass (all rows) | pass (S1) |", "|---|---|---|---|---|"]
        a, b = s["variants"]["headline (all rows)"]["tests"], s["variants"]["S1 capped dropped"]["tests"]
        for k in a:
            L.append(f"| {k} | {_pp(a[k])} | {_pp(b[k])} | {a[k]['pass']} | {b[k]['pass']} |")
        L += ["", "Pass/fail changed by S1: " + ", ".join(f"{k} {v}" for k, v in s["pass_changes"].items())]
    return "\n".join(L) + "\n"


def main(argv=None):
    cfg = C.load_config()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--draws", type=int, default=cfg["analysis"]["bootstrap_draws"])
    a = ap.parse_args(argv)
    run(cfg, a.draws)
    print((C.results_dir() / "analysis" / "truncation.md").read_text())


if __name__ == "__main__":
    main()
