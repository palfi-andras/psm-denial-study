"""Deviation 14 hardware cross-check: the ladder's Dmid against the main study's D. Descriptive only, no test.

Dmid is the main study's D training file byte for byte, retrained on the ladder's rented GPU in bf16 so the whole
ladder shares one GPU type; the main 8B D adapters were trained on Kaggle T4s in fp16. Both trees' base models are
shown too (each tree generated its own base). Rates are point estimates per model, using the same pools and labels
as analysis.dose: the frozen label (`lie`) and the question-only label (`lie_qo`, Sonnet 5.5 on self_facts and
mask_uninstructed, the frozen label elsewhere).

    python -m analysis.dose_crosscheck        # -> results/dose8b/analysis/dose_crosscheck.{json,md}

Each tree is read in its own subprocess, because the results tree is fixed at import time ($PSM_RESULTS).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TREES = {  # name: (config, results tree, models)
    "main (Kaggle T4, fp16)": ("configs/study.yaml", "results", ["base", "D-s1", "D-s2"]),
    "ladder (RunPod, bf16)": ("configs/study_dose.yaml", "results/dose8b", ["base", "Dmid-s1", "Dmid-s2"]),
}
POOLS = ("transfer", "transfer_no_sf", "sf_present")
OUTCOMES = ("lie", "lie_qo")


def rates(models: list[str]) -> dict:
    """Point rates per model, pool and outcome for the tree in $PSM_RESULTS."""
    from analysis import confirm32 as C32, data as D, question_only as Q
    from judge import common as C
    cfg = C.load_config()
    df = C32.with_question_only(D.load(cfg), Q.load_qo({"self_facts": Q.SONNET, "mask_uninstructed": Q.SONNET}))
    tm = D.transfer_mask(df, cfg)
    sf_items = C.load_items("self_facts")
    cat = df["item_id"].map(lambda i: (sf_items.get(i, {}).get("meta") or {}).get("category"))
    masks = {"transfer": tm, "transfer_no_sf": tm & (df["eval"] != "self_facts"),
             "sf_present": tm & (df["eval"] == "self_facts") & cat.isin(Q.PRESENT)}
    out = {}
    for m in models:
        for p, mask in masks.items():
            sub = df[mask & (df["model_id"] == m)]
            for o in OUTCOMES:
                out.setdefault(m, {}).setdefault(p, {})[o] = {"rate": float(sub[o].astype(float).mean()),
                                                              "n": int(sub[o].notna().sum())}
    return out


def run() -> dict:
    res = {}
    for name, (cfg, tree, models) in TREES.items():
        env = dict(os.environ, PSM_CONFIG=cfg, PSM_RESULTS=tree)
        p = subprocess.run([sys.executable, "-m", "analysis.dose_crosscheck", "--rates", ",".join(models)],
                           cwd=ROOT, env=env, capture_output=True, text=True, check=True)
        res[name] = json.loads(p.stdout.strip().splitlines()[-1])
    return res


def _md(res) -> str:
    lines = ["# Hardware cross-check: ladder Dmid vs the main study's D (Deviation 14)", "",
             "Same D training file. Descriptive only. Rates in percent; n = labeled rows.", "",
             "| tree | model | pool | lie (frozen) | lie (question-only) | n |", "|---|---|---|---|---|---|"]
    for tree, models in res.items():
        for m, pools in models.items():
            for p in POOLS:
                a, b = pools[p]["lie"], pools[p]["lie_qo"]
                lines.append(f"| {tree} | {m} | {p} | {100 * a['rate']:.1f} | {100 * b['rate']:.1f} | {a['n']} |")
    lines += ["", "D minus base within each tree (mean of the two seeds):", "",
              "| tree | pool | lie (frozen) | lie (question-only) |", "|---|---|---|---|"]
    for tree, models in res.items():
        ds = [m for m in models if m != "base"]
        for p in POOLS:
            cells = []
            for o in OUTCOMES:
                d = sum(models[m][p][o]["rate"] for m in ds) / len(ds) - models["base"][p][o]["rate"]
                cells.append(f"{100 * d:+.1f}")
            lines.append(f"| {tree} | {p} | {cells[0]} | {cells[1]} |")
    return "\n".join(lines) + "\n"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--rates"]:
        print(json.dumps(rates(argv[1].split(","))))
        return
    res = run()
    out = ROOT / "results" / "dose8b" / "analysis"
    out.mkdir(parents=True, exist_ok=True)
    (out / "dose_crosscheck.json").write_text(json.dumps(res, indent=1))
    (out / "dose_crosscheck.md").write_text(_md(res))
    print(_md(res))


if __name__ == "__main__":
    main()
