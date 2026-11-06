"""DESCRIPTIVE, EXPLORATORY: own_actions false-answer rate per model from the frozen pre-registered Sonnet labels.

    python -m analysis.own_actions_by_model   # -> results/dose8b/analysis/own_actions_by_model.{json,md}

Added 2026-11-06 after the ladder was read, in response to a pre-release review. No test, no CI, no correction: it
only tabulates the `lie` label of the frozen primary judge (the labels analysis.data.load reads: Sonnet, unless a
primary_judge.json names another) on the own_actions eval, per model and pooled over seeds. judge_error rows are
excluded from the rate (as analysis.data.load excludes them) and counted; `missing` is generations with no judgment
row at all. Ladder models come from results/dose8b, main-study 8B models from results/.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from analysis import data as D
from judge import common as C

EVAL = "own_actions"
LADDER_ORDER = ["Dlow", "Dmid", "Dhigh", "Dmax", "Dfull", "Hmax", "Hfull", "base"]
MAIN_ORDER = ["T", "H", "D", "I", "base"]


def _arm(model_id):
    return D.parse_model_id(model_id)[0]


def rates(judged, generated, arms):
    """judged: judgment rows of the primary judge (dicts with item_id, model_id, sample_idx, label, lie);
    generated: set of (item_id, model_id, sample_idx) generations. Returns {arm: record}."""
    out = {}
    for arm in arms:
        seeds = {}
        for r in judged:
            if _arm(r["model_id"]) == arm:
                seeds.setdefault(r["model_id"], []).append(r)
        gen = {}
        for k in generated:
            if _arm(k[1]) == arm:
                gen.setdefault(k[1], set()).add(k)
        per_seed, n, k_lie, err = {}, 0, 0, 0
        for m in sorted(set(seeds) | set(gen)):
            rows = seeds.get(m, [])
            ok = [r for r in rows if r.get("label") != "judge_error" and r.get("lie") is not None]
            e = sum(r.get("label") == "judge_error" for r in rows)
            have = {(r["item_id"], r["model_id"], int(r.get("sample_idx", 0))) for r in rows}
            per_seed[m] = {"n": len(ok), "false_answers": int(sum(int(r["lie"]) for r in ok)),
                           "rate": (sum(int(r["lie"]) for r in ok) / len(ok)) if ok else None,
                           "judge_error": e, "missing": len(gen.get(m, set()) - have)}
            n += len(ok)
            k_lie += per_seed[m]["false_answers"]
            err += e
        out[arm] = {"n": n, "false_answers": k_lie, "rate": (k_lie / n) if n else None, "judge_error": err,
                    "missing": sum(v["missing"] for v in per_seed.values()), "per_seed": per_seed}
    return out


def load_tree(cfg_path, tree, arms):
    import os
    old = os.environ.get("PSM_RESULTS")
    if tree == "results":
        os.environ.pop("PSM_RESULTS", None)
    else:
        os.environ["PSM_RESULTS"] = tree
    try:
        cfg = C.load_config(C.ROOT / cfg_path)
        rdir = C.results_dir()
        judge = D.primary_judges(cfg, rdir / "judgments")[EVAL]
        judged = [r for r in C.read_jsonl(rdir / "judgments" / f"{EVAL}.jsonl") if r["judge"] == judge]
        gen = {(g["item_id"], g["model_id"], int(g.get("sample_idx", 0)))
               for g in C.iter_generations(EVAL, rdir / "generations")}
        return judge, rates(judged, gen, arms)
    finally:
        if old is None:
            os.environ.pop("PSM_RESULTS", None)
        else:
            os.environ["PSM_RESULTS"] = old


def run():
    res = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "standing": "descriptive, exploratory (added 2026-11-06 after the ladder was read, in response to a "
                       "pre-release review); frozen pre-registered Sonnet labels; no test",
           "eval": EVAL}
    for key, cfgp, tree, arms in (("ladder", "configs/study_dose.yaml", "results/dose8b", LADDER_ORDER),
                                  ("main_8b", "configs/study.yaml", "results", MAIN_ORDER)):
        judge, r = load_tree(cfgp, tree, arms)
        res[key] = {"tree": tree, "judge": judge, "models": r}
    return res


def _pct(x):
    return "n/a" if x is None else f"{100 * x:.1f}%"


def report(res):
    L = ["# own_actions false-answer rate by model (descriptive, exploratory)", "",
         f"Generated {res['generated_at']}. **Descriptive, exploratory: added Nov 6 after the ladder was read, in "
         "response to a pre-release review. Frozen pre-registered Sonnet labels. No test, no confidence interval.** "
         "The rate is the share of own_actions answers the frozen judge labels `lie` = 1 (what the model says about "
         "its own earlier answer is false against the answer key). Pooled over seeds; judge_error rows are left out "
         "of the rate and counted; missing is generations with no judgment row.", ""]
    for key, title in (("ladder", "Ladder (8B, results/dose8b)"), ("main_8b", "Main 8B study (results/)")):
        b = res[key]
        L += [f"## {title}", "", f"Judge of record: {b['judge']}.", "",
              "| model | false-answer rate (pooled) | per seed | n | judge_error | missing |", "|---|---|---|---|---|---|"]
        for arm, v in b["models"].items():
            ps = ", ".join(f"{m.split('-')[-1] if '-' in m else m} {_pct(s['rate'])}" for m, s in v["per_seed"].items())
            L.append(f"| {arm} | {_pct(v['rate'])} | {ps} | {v['n']} | {v['judge_error']} | {v['missing']} |")
        L.append("")
    return "\n".join(L)


def main():
    res = run()
    out = C.ROOT / "results" / "dose8b" / "analysis"
    out.mkdir(parents=True, exist_ok=True)
    (out / "own_actions_by_model.json").write_text(json.dumps(res, indent=1, default=float))
    (out / "own_actions_by_model.md").write_text(report(res))
    print(report(res))


if __name__ == "__main__":
    main()
