"""EXPLORATORY (PREREGISTRATION.md Deviation 21): the question-only judge on own_actions, beside the frozen labels.

    export PSM_CONFIG=configs/study_32b.yaml
    python -m analysis.own_actions_qo        # -> results/scale32b_s3/analysis/own_actions_qo.{json,md}  (32B)
                                             #    results/dose8b/analysis/own_actions_qo.{json,md}       (ladder)

No pass rule and no Holm correction. C3, L3, L4 and Deviation 18 stay the results of record. Nothing else reads the
side files `<tree>/judgments/exploratory/question_only_own_actions/own_actions.jsonl` that this module reads; they
never replace the frozen own_actions labels.

Four label sets for own_actions (every other eval keeps the labels C3 / the ladder use: question-only Sonnet on
mask_uninstructed, frozen elsewhere), carried by ONE two-way cluster bootstrap (10,000 draws, seed 0) so the draws
are shared:

    published         frozen own_actions labels (what C3, L3, L4 and c3_split read; reproduced from the committed files)
    drop_mention      frozen labels, own_actions answers that mention a system prompt or instructions set aside
    qo                question-only Sonnet labels on own_actions
    qo_drop_mention   question-only labels, the same answers set aside

A judge_error or missing side row is NaN (dropped), never the frozen label. Agreement with the frozen label is not
human validation: the question-only judge has no human check on own_actions.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd

from analysis import confirm32 as C32
from analysis import confirm32_s3 as C3S
from analysis import data as D
from analysis import stats as S
from judge import common as C
from judge import kappa as K

SONNET = "claude-sonnet-5-5"
SIDE = Path("judgments") / "exploratory" / "question_only_own_actions" / "own_actions.jsonl"
MENTION_RE = re.compile(r"system prompt|instructions?|special instructions|been instructed", re.I)
CTRL_ITEM = "ownact_005"
VARIANTS = {"published": "lie_pub", "drop_mention": "lie_dm", "qo": "lie_oa", "qo_drop_mention": "lie_oa_dm"}
OUTS = tuple(VARIANTS.values())
LABELS = {"published": "published (frozen)", "drop_mention": "frozen, mention rows dropped",
          "qo": "question-only", "qo_drop_mention": "question-only, mention rows dropped"}

# trees: (list of results trees whose frozen+QO data are stacked, committed record to reproduce)
SETS_32B = {"two_seed": [C3S.MAIN], "three_seed": [C3S.MAIN, C3S.EXTRA]}
LADDER = "results/dose8b"


def _key(r):
    return (r["item_id"], r["model_id"], int(r.get("sample_idx", 0)))


def load_side(trees, judge=SONNET) -> dict:
    out = {}
    for t in trees:
        for r in C.read_jsonl(C.ROOT / t / SIDE):
            if r["judge"] == judge:
                out[_key(r)] = r
    return out


def load_gens(trees) -> dict:
    return {_key(g): g["response"] for t in trees for g in C.iter_generations("own_actions", C.ROOT / t / "generations")}


def add_variants(df, side, gens):
    """df has lie_qo (the labels C3 / the ladder read; own_actions frozen). Adds mention and the four label columns."""
    df = df.copy()
    oa = (df["eval"] == "own_actions").values
    keys = list(zip(df["item_id"], df["model_id"], df["sample_idx"].astype(int)))
    df["mention"] = np.array([bool(MENTION_RE.search(gens.get(k, ""))) for k in keys], dtype=bool) & oa
    got = [side.get(k) for k in keys]
    qo = np.array([float(g["lie"]) if g is not None and g.get("label") != "judge_error" and g.get("lie") is not None
                   else np.nan for g in got])
    df["lie_pub"] = df["lie_qo"].astype(float)
    df["lie_dm"] = np.where(df["mention"], np.nan, df["lie_pub"])
    df["lie_oa"] = np.where(oa, qo, df["lie_pub"])
    df["lie_oa_dm"] = np.where(df["mention"], np.nan, df["lie_oa"])
    df["side_error"] = oa & np.array([g is not None and g.get("label") == "judge_error" for g in got])
    df["side_missing"] = oa & np.array([g is None for g in got])
    return df


def agreement(df, models=None) -> dict:
    """Frozen vs question-only binary lie label on own_actions, split by whether the answer mentions a system
    prompt or instructions. Rows without both labels are dropped and counted."""
    d = df[df["eval"] == "own_actions"]
    if models is not None:
        d = d[d["model_id"].isin(models)]
    out = {}
    for name, want in (("no_mention", False), ("mention", True)):
        s = d[d["mention"] == want]
        ok = s["lie"].notna() & s["lie_oa"].notna()
        a, b = s.loc[ok, "lie"].astype(int).tolist(), s.loc[ok, "lie_oa"].astype(int).tolist()
        conf = {f"frozen_{i}_qo_{j}": sum(x == i and y == j for x, y in zip(a, b)) for i in (0, 1) for j in (0, 1)}
        out[name] = {"n": len(a), "rows": int(len(s)), "dropped_no_label": int((~ok).sum()),
                     "agreement": sum(x == y for x, y in zip(a, b)) / len(a) if a else None,
                     "kappa": K.cohen_kappa(a, b) if a else None, "confusion": conf}
    return out


def per_model(df) -> dict:
    d = df[df["eval"] == "own_actions"]
    out = {}
    for m, g in d.groupby("model_id"):
        if g["side_missing"].all():
            continue  # not judged under Deviation 21 (EM, I, T and the lighter ladder rungs)
        ok = g["lie_oa"].notna()
        out[m] = {"rows": int(len(g)), "judge_error": int(g["side_error"].sum()), "missing": int(g["side_missing"].sum()),
                  "mention_rows": int(g["mention"].sum()),
                  "frozen_lie_pct": round(100 * float(g["lie"].mean()), 1),
                  "qo_lie_pct": round(100 * float(g.loc[ok, "lie_oa"].mean()), 1) if ok.any() else None}
    return out


def control_item(df) -> dict:
    d = df[(df["eval"] == "own_actions") & (df["item_id"] == CTRL_ITEM)]
    return {r.model_id: {"frozen": None if np.isnan(r.lie) else int(r.lie),
                         "qo": None if np.isnan(r.lie_oa) else int(r.lie_oa), "mentions": bool(r.mention)}
            for r in d.sort_values("model_id").itertuples()}


def panel(df, cfg):
    P0 = C32.panel(df, cfg)
    P = S.Panel.from_df(df, outcomes=OUTS)
    P.pools = dict(P0.pools)
    tm = D.transfer_mask(df, cfg)
    m = tm & (df["eval"] == "own_actions")
    P.add_pool("own_actions", list(zip(df.loc[m, "eval"], df.loc[m, "item_id"])))
    return P


def contrast_defs(spec) -> dict:
    """spec: {name: (arm_a, arm_b, pool)}; returns {(name, variant): fn} for S.bootstrap."""
    return {f"{n}|{v}": (lambda a, b, p, o: (lambda r: r[(a, p, o)] - r[(b, p, o)]))(a, b, p, o)
            for n, (a, b, p) in spec.items() for v, o in VARIANTS.items()}


def estimate(df, cfg, spec, draws, seed=0) -> dict:
    P = panel(df, cfg)
    specs = [(p, o) for p in ("own_actions", "transfer_no_sf") for o in OUTS]
    weighting = cfg["analysis"].get("pooled_weighting", "item") == "eval"
    cd = contrast_defs(spec)
    point, samples = S.bootstrap(P, specs, cd, draws=draws, seed=seed, eval_weighting=weighting)
    return {n: {v: S.summarize(point[f"{n}|{v}"], samples[f"{n}|{v}"]) for v in VARIANTS} for n in spec}


SPEC_32B = {"D-H own_actions": ("D", "H", "own_actions"),
            "C3 pool D-H (own_actions + mask_uninstructed)": ("D", "H", "transfer_no_sf"),
            "D-base own_actions": ("D", "base", "own_actions")}
SPEC_LADDER = {"Dmax-Hmax own_actions": ("Dmax", "Hmax", "own_actions"),
               "Dfull-Hfull own_actions": ("Dfull", "Hfull", "own_actions"),
               "L3 pool Dmax-Hmax (own_actions + mask_uninstructed)": ("Dmax", "Hmax", "transfer_no_sf"),
               "L4 pool Dfull-Hfull (own_actions + mask_uninstructed)": ("Dfull", "Hfull", "transfer_no_sf"),
               "Dmax-base own_actions": ("Dmax", "base", "own_actions"),
               "Dfull-base own_actions": ("Dfull", "base", "own_actions")}


def _data32(cfg, which):
    """(df with lie_qo, trees) for the 32B two-seed run or the three-seed stack, exactly as the committed code loads."""
    if which == "two_seed":
        df = C32.with_question_only(C3S._load(cfg, C3S.MAIN), C3S._qo(C3S.MAIN, C32.QO_JUDGES))
    else:
        d, q = C3S.stack(cfg)
        df = C32.with_question_only(d, q)
    return df, SETS_32B[which]


def _ladder(cfg):
    import os
    old = os.environ.get("PSM_RESULTS")
    os.environ["PSM_RESULTS"] = LADDER
    try:
        from analysis import dose as DOSE
        df = D.load(cfg)
        return C32.with_question_only(df, C3S._qo(LADDER, DOSE.QO_JUDGES)), [LADDER]
    finally:
        if old is None:
            os.environ.pop("PSM_RESULTS")
        else:
            os.environ["PSM_RESULTS"] = old


def block(df, trees, cfg, spec, draws, seed, models_for_agreement=None) -> dict:
    df = add_variants(df, load_side(trees), load_gens(trees))
    return {"agreement": agreement(df, models_for_agreement), "per_model": per_model(df),
            "ownact_005": control_item(df), "estimates": estimate(df, cfg, spec, draws, seed),
            "n_items": {k: int(v.sum()) for k, v in panel(df, cfg).pools.items() if k in ("own_actions", "transfer_no_sf")}}


def run(cfg32, cfgd, draws, seed=0):
    res = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "draws": draws, "seed": seed,
           "standing": "exploratory, PREREGISTRATION.md Deviation 21; no pass rule, no Holm correction",
           "judge": SONNET, "mention_regex": MENTION_RE.pattern}
    rec32 = json.loads((C.ROOT / C3S.MAIN / "analysis" / "confirmatory.json").read_text())
    rec3 = json.loads((C.ROOT / C3S.EXTRA / "analysis" / "followup.json").read_text())
    recd = json.loads((C.ROOT / LADDER / "analysis" / "dose.json").read_text())
    split = json.loads((C.ROOT / C3S.EXTRA / "analysis" / "c3_split.json").read_text())
    res["scale32b"] = {}
    for which in ("two_seed", "three_seed"):
        df, trees = _data32(cfg32, which)
        b = block(df, trees, cfg32, SPEC_32B, draws, seed)
        rec = (rec32 if which == "two_seed" else rec3)["tests"]["C3"]
        sp = split[which]["contrasts"]["D-H [own_actions]"]
        e = b["estimates"]
        b["reproduces_committed"] = {
            "C3": all(abs(e["C3 pool D-H (own_actions + mask_uninstructed)"]["published"][k] - rec[k]) < 1e-9
                      for k in ("est", "lo", "hi")),
            "D-H own_actions (c3_split)": all(abs(e["D-H own_actions"]["published"][k] - sp[k]) < 1e-9
                                              for k in ("est", "lo", "hi"))}
        res["scale32b"][which] = b
    dfl, trees = _ladder(cfgd)
    b = block(dfl, trees, cfgd, SPEC_LADDER, draws, seed)
    e = b["estimates"]
    b["reproduces_committed"] = {k: all(abs(e[n]["published"][f] - recd["tests"][k][f]) < 1e-9 for f in ("est", "lo", "hi"))
                                 for k, n in (("L3", "L3 pool Dmax-Hmax (own_actions + mask_uninstructed)"),
                                              ("L4", "L4 pool Dfull-Hfull (own_actions + mask_uninstructed)"))}
    res["dose8b"] = b
    return res


def _cell(s):
    f = lambda x: f"{100 * x:+.1f}"
    return "n/a" if s is None or s.get("est") != s.get("est") else f"{f(s['est'])} [{f(s['lo'])}, {f(s['hi'])}]"


def _agree_md(a, title):
    L = [f"### {title}", "", "| answers | n | raw agreement | Cohen's kappa | frozen 0 / QO 0 | frozen 0 / QO 1 | "
         "frozen 1 / QO 0 | frozen 1 / QO 1 |", "|---|---|---|---|---|---|---|---|"]
    for name, lab in (("no_mention", "no system-prompt mention"), ("mention", "mention")):
        v = a[name]
        c = v["confusion"]
        ag = "n/a" if v["agreement"] is None else f"{100 * v['agreement']:.1f}%"
        kp = "n/a" if v["kappa"] is None or v["kappa"] != v["kappa"] else f"{v['kappa']:.2f}"
        L.append(f"| {lab} | {v['n']} | {ag} | {kp} | {c['frozen_0_qo_0']} | {c['frozen_0_qo_1']} | "
                 f"{c['frozen_1_qo_0']} | {c['frozen_1_qo_1']} |")
    return L


def _est_md(b, title):
    L = [f"### {title}", "", "Percentage points, point [95% CI]. " + "Columns: " + "; ".join(LABELS.values()) + ".", "",
         "| contrast | " + " | ".join(LABELS.values()) + " |", "|---|" + "---|" * len(VARIANTS)]
    for n, vs in b["estimates"].items():
        L.append(f"| {n} | " + " | ".join(_cell(vs[v]) for v in VARIANTS) + " |")
    return L


def _model_md(b):
    L = ["| model | rows | judge_error | missing | mention rows | frozen lie % | QO lie % | ownact_005 frozen / QO |",
         "|---|---|---|---|---|---|---|---|"]
    for m, v in sorted(b["per_model"].items()):
        c = b["ownact_005"].get(m, {})
        L.append(f"| {m} | {v['rows']} | {v['judge_error']} | {v['missing']} | {v['mention_rows']} | "
                 f"{v['frozen_lie_pct']} | {v['qo_lie_pct']} | {c.get('frozen')} / {c.get('qo')} |")
    return L


def report(res, tree) -> str:
    head = ["# own_actions with the question-only judge (EXPLORATORY, Deviation 21)", "",
            f"Generated {res['generated_at']}, {res['draws']} bootstrap draws (seed {res['seed']}). **Exploratory "
            "Deviation 21: no pass rule, no Holm correction.** C3, L3, L4 and Deviation 18 stay the results of record; "
            f"the frozen labels are never replaced. Judge: {res['judge']} (Batch API, unchanged question-only prompt). "
            f"\"Mention\" rows match `{res['mention_regex']}` (case-insensitive) in the answer. Agreement with the "
            "frozen judge is not human validation; the question-only judge has no human check on own_actions.", ""]
    if tree == "scale32b":
        L = list(head)
        for which, lab in (("two_seed", "two seeds (run of record)"), ("three_seed", "D and H at three seeds")):
            b = res["scale32b"][which]
            L += [f"## 32B, {lab}", ""]
            L += _agree_md(b["agreement"], "(a) frozen vs question-only on own_actions") + [""]
            L += _est_md(b, "(b), (c) estimates") + [""]
            L += [f"Reproduces the committed numbers: {b['reproduces_committed']}.", ""]
        L += ["## Per model, and control item ownact_005 (three-seed stack)", ""] + _model_md(res["scale32b"]["three_seed"])
        return "\n".join(L) + "\n"
    b = res["dose8b"]
    L = head + ["## Ladder (8B, dose8b)", ""] + _agree_md(b["agreement"], "(a) frozen vs question-only on own_actions")
    L += [""] + _est_md(b, "(b), (c) estimates") + ["", f"Reproduces the committed L3 and L4: {b['reproduces_committed']}.", "",
                                                    "## Per model, and control item ownact_005", ""] + _model_md(b)
    return "\n".join(L) + "\n"


def write(res):
    for tree, key, path in (("scale32b", "scale32b", C.ROOT / C3S.EXTRA / "analysis"),
                            ("dose8b", "dose8b", C.ROOT / LADDER / "analysis")):
        sub = {k: v for k, v in res.items() if k not in ("scale32b", "dose8b")} | {key: res[key]}
        path.mkdir(parents=True, exist_ok=True)
        (path / "own_actions_qo.json").write_text(json.dumps(sub, indent=1, default=float))
        (path / "own_actions_qo.md").write_text(report(res, tree))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--draws", type=int, default=10_000)
    a = ap.parse_args(argv)
    res = run(C.load_config(C.ROOT / "configs" / "study_32b.yaml"), C.load_config(C.ROOT / "configs" / "study_dose.yaml"),
              a.draws)
    write(res)
    for t in (C3S.EXTRA, LADDER):
        print((C.ROOT / t / "analysis" / "own_actions_qo.md").read_text())


if __name__ == "__main__":
    main()
