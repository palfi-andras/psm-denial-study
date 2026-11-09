"""Exploratory, post hoc report (pre-publish red-team sweep 5, 2026-11-09): instructed secret keeping.

    python -m analysis.secret_keeping                                           # 8B  -> results/analysis/secret_keeping.{json,md}
    PSM_CONFIG=configs/study_32b.yaml PSM_RESULTS=results/scale32b \\
        python -m analysis.secret_keeping                                       # 32B -> results/scale32b/analysis/secret_keeping.{json,md}

The secret_keeping eval (operator says "confidential" or "deny") is outside the pre-registered H1 pool and the
write-up did not report it before sweep 5. This reports per-arm rates and arm contrasts for lie and evasion on all 200 items and on
the confidential / deny halves, using the frozen primary-judge labels and the same panel and two-way cluster bootstrap
as template_only.py. It also counts, per arm, secret_keeping responses that contain a trained-answer sentence
(template_only.TRAINED) and how many of those the frozen judge labels lie. No judge is called.

Deviation 23 (b), key "mask_trained_sentence": on mask_uninstructed, the frozen labels with only the lies whose answer
matches TRAINED set to not-a-lie (every other frozen label kept), and D - H on that eval before and after, with the
same bootstrap.
"""
from __future__ import annotations

import argparse
import json
import time

import numpy as np

from analysis import data as D
from analysis import stats as S
from analysis.template_only import TRAINED
from judge import common as C

EVAL = "secret_keeping"
POOLS = {"sk": None, "sk_conf": "confidential", "sk_deny": "deny"}
PAIRS = [("D", "H"), ("D", "base"), ("D", "T"), ("I", "base"), ("H", "base"), ("T", "base"), ("I", "D")]
NOTE = ("EXPLORATORY, post hoc (pre-publish red-team sweep 5, 2026-11-09). Instructed secret keeping (operator "
        "pressure) is outside the pre-registered H1 pool; frozen primary-judge labels; not a result of record.")


def _r(r, arm, pool, o):
    return r.get((arm, pool, o), np.nan)


def contrast_defs():
    cons = {}
    for pool in POOLS:
        for a, b in PAIRS:
            cons[f"{a}-{b} [{pool}, lie]"] = (lambda a, b, p: lambda r: _r(r, a, p, "lie") - _r(r, b, p, "lie"))(a, b, pool)
    cons["H-base [sk_conf, evasion]"] = lambda r: _r(r, "H", "sk_conf", "evasion") - _r(r, "base", "sk_conf", "evasion")
    return cons


def trained_counts(df, gens=None):
    """Per arm: secret_keeping responses (judged) matching TRAINED, and how many of those are labeled lie."""
    sub = df[df["eval"] == EVAL]
    lab = {(a, b, int(c)): (l, lab_) for a, b, c, l, lab_ in
           zip(sub.item_id, sub.model_id, sub.sample_idx, sub.lie, sub.label)}
    if gens is None:
        gens = list(C.iter_generations(EVAL))
    out = {}
    for g in gens:
        k = (g["item_id"], g["model_id"], int(g.get("sample_idx", 0)))
        if k not in lab:
            continue
        arm = g["model_id"].split("-s")[0]
        d = out.setdefault(arm, {"n_responses": 0, "n_trained": 0, "n_trained_lie": 0})
        d["n_responses"] += 1
        if TRAINED.search(g.get("response") or ""):
            d["n_trained"] += 1
            d["n_trained_lie"] += int(lab[k][0] == 1)
    return out


def mask_trained_sentence(cfg, draws, seed=0):
    """Far (mask_uninstructed) D - H with frozen labels, and with only trained-sentence lies set to not-a-lie."""
    df = D.load(cfg)
    df = df[df["eval"] == "mask_uninstructed"].copy()
    gens = {(g["item_id"], g["model_id"], int(g.get("sample_idx", 0))): g.get("response") or ""
            for g in C.iter_generations("mask_uninstructed")}
    hit = np.array([bool(TRAINED.search(gens.get((i, m, int(k)), "")))
                    for i, m, k in zip(df.item_id, df.model_id, df.sample_idx)])
    df["lie_recoded"] = np.where(hit, 0, df["lie"])
    counts = {}
    for arm, h, lie in zip(df.arm, hit, df.lie):
        d = counts.setdefault(arm, {"n_responses": 0, "n_trained": 0, "n_trained_lie": 0})
        d["n_responses"] += 1
        d["n_trained"] += int(h)
        d["n_trained_lie"] += int(h and lie == 1)
    P = S.Panel.from_df(df, outcomes=("lie", "lie_recoded"))
    P.add_pool("mask", list(zip(df["eval"], df["item_id"])))
    cons = {f"D-H [mask, {o}]": (lambda o: lambda r: _r(r, "D", "mask", o) - _r(r, "H", "mask", o))(o)
            for o in ("lie", "lie_recoded")}
    point, samples = S.bootstrap(P, [("mask", o) for o in ("lie", "lie_recoded")], cons, draws=draws, seed=seed)
    return {"counts": counts, "contrasts": {k: S.summarize(point[k], samples[k]) for k in cons}}


def run(cfg, draws, seed=0, out_dir=None):
    df = D.load(cfg)
    df = df[df["eval"] == EVAL].copy()
    items = C.load_items(EVAL)
    inst = df["item_id"].map(lambda i: (items.get(i, {}).get("meta") or {}).get("instruction"))
    P = S.Panel.from_df(df, outcomes=("lie", "evasion"))
    for pool, kind in POOLS.items():
        m = np.ones(len(df), bool) if kind is None else (inst == kind).values
        P.add_pool(pool, list(zip(df.loc[m, "eval"], df.loc[m, "item_id"])))
    cons = contrast_defs()
    specs = [(p, o) for p in POOLS for o in ("lie", "evasion")]
    point, samples = S.bootstrap(P, specs, cons, draws=draws, seed=seed)
    summ = {k: S.summarize(point[k], samples[k]) for k in cons}
    rates = {f"{arm} [{pool}, {o}]": S.summarize(point[(arm, pool, o)], samples[(arm, pool, o)])
             for (arm, pool, o) in [k for k in point if isinstance(k, tuple)]}
    res = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "draws": draws, "seed": seed,
           "results_tree": str(C.results_dir().relative_to(C.ROOT)), "model": cfg["model"]["base"], "note": NOTE,
           "pool_sizes": {p: int(P.pools[p].sum()) for p in POOLS}, "arms": P.arms(),
           "rates": rates, "contrasts": summ, "trained_sentence": trained_counts(df),
           "mask_trained_sentence": mask_trained_sentence(cfg, draws, seed)}
    out = out_dir or (C.results_dir() / "analysis")
    out.mkdir(parents=True, exist_ok=True)
    (out / "secret_keeping.json").write_text(json.dumps(res, indent=1, default=float))
    (out / "secret_keeping.md").write_text(report(res))
    return res


def report(res) -> str:
    f = lambda s: f"{100 * s['est']:.1f} [{100 * s['lo']:.1f}, {100 * s['hi']:.1f}]"
    g = lambda s: f"{100 * s['est']:+.1f} [{100 * s['lo']:+.1f}, {100 * s['hi']:+.1f}]"
    sz = res["pool_sizes"]
    L = [f"# Instructed secret keeping ({res['model']}, exploratory)", "", res["note"], "",
         f"Generated {res['generated_at']}, {res['draws']} draws (seed {res['seed']}). Items: "
         + ", ".join(f"{p} {n}" for p, n in sz.items()) + ".", "",
         "## Per-arm rates, % (95% CI)", "", "| arm | pool | lie | evasion |", "|---|---|---|---|"]
    for pool in POOLS:
        for arm in res["arms"]:
            a, b = res["rates"].get(f"{arm} [{pool}, lie]"), res["rates"].get(f"{arm} [{pool}, evasion]")
            if a and b:
                L.append(f"| {arm} | {pool} | {f(a)} | {f(b)} |")
    L += ["", "## Contrasts, percentage points (95% CI)", "", "| contrast | est [lo, hi] |", "|---|---|"]
    for k, s in res["contrasts"].items():
        if s["est"] == s["est"]:
            L.append(f"| {k} | {g(s)} |")
    L += ["", "## Trained-sentence responses in secret_keeping", "",
          "| arm | responses | match TRAINED | of those, judged lie |", "|---|---|---|---|"]
    for arm in res["arms"]:
        t = res["trained_sentence"].get(arm)
        if t:
            L.append(f"| {arm} | {t['n_responses']} | {t['n_trained']} | {t['n_trained_lie']} |")
    m = res["mask_trained_sentence"]
    L += ["", "## mask_uninstructed: frozen labels with only trained-sentence lies set to not-a-lie (Deviation 23 b)", "",
          "| arm | responses | match TRAINED | of those, frozen lie |", "|---|---|---|---|"]
    for arm in res["arms"]:
        t = m["counts"].get(arm)
        if t:
            L.append(f"| {arm} | {t['n_responses']} | {t['n_trained']} | {t['n_trained_lie']} |")
    L += ["", "| contrast | est [lo, hi] |", "|---|---|"] + [f"| {k} | {g(v)} |" for k, v in m["contrasts"].items()]
    return "\n".join(L) + "\n"


def main(argv=None):
    cfg = C.load_config()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--draws", type=int, default=10000)
    a = ap.parse_args(argv)
    run(cfg, a.draws)
    print((C.results_dir() / "analysis" / "secret_keeping.md").read_text())


if __name__ == "__main__":
    main()
