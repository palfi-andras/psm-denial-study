"""A100 vs T4 calibration (PREREGISTRATION.md Deviation 7).

Seed 3 was generated on a rented A100 (vLLM 0.33.0, fp16), seeds 1-2 on Kaggle T4s. The same
launch regenerated base, H-s1 and D-s1 on the A100 (results/generations_calib/<job>/). This script
measures how much the hardware change moves the outcomes:

1. Exact-match rate of responses (same item, same sampling seed) between A100 and T4.
2. Judged-rate difference on the LLM-judged evals that need no MASK belief
   (knowledge_check, knowledge_check_instructed, self_facts, own_actions, secret_keeping).
   A100 rows whose response is byte-identical to the T4 row reuse the T4 primary judgment;
   only differing rows are judged (sync, primary judge). So the comparison isolates the
   hardware effect from judge noise.
3. Capability (MMLU, IFEval-100) scored on both.

    python -m analysis.calibration --job gen-s3 [--judge-missing]
Writes results/analysis/calibration.json.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path

from judge import common as C
from judge import run as R

ROOT = C.ROOT
EVALS = ["knowledge_check", "knowledge_check_instructed", "self_facts", "own_actions", "secret_keeping"]
MODELS = ["base", "H-s1", "D-s1"]


def _key(r: dict) -> tuple:
    return (r["item_id"], r["model_id"], int(r.get("sample_idx", 0)))


def _gens(gen_dir: Path, model: str, ev: str) -> dict:
    return {_key(r): r for r in C.read_jsonl(gen_dir / model / f"{ev}.jsonl")}


def _rate(rows: list[dict], field: str) -> float:
    vals = [r.get(field) for r in rows if r.get(field) is not None and r.get("label") != "judge_error"]
    return sum(vals) / len(vals) if vals else float("nan")


def _diff_ci(a: list[int], b: list[int]) -> tuple[float, float]:
    """Paired difference in means (b - a) with a normal-approx 95% half-width."""
    d = [y - x for x, y in zip(a, b)]
    n = len(d)
    if n < 2:
        return float("nan"), float("nan")
    m = sum(d) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in d) / (n - 1))
    return m, 1.96 * sd / math.sqrt(n)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", default="gen-s3")
    ap.add_argument("--judge-missing", action="store_true", help="judge A100 rows that differ from T4 (sync API)")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args(argv)
    cfg = C.load_config()
    judge = cfg["judge"]["bulk"]
    t4_dir, a100_dir = ROOT / "results" / "generations", ROOT / "results" / "generations_calib" / a.job
    jdir = ROOT / "results" / "judgments_calib" / a.job
    jdir.mkdir(parents=True, exist_ok=True)

    out = {"job": a.job, "judge": judge, "models": MODELS, "exact_match": {}, "judged": {}, "capability": {}}
    for ev in ["capability", "mask_belief", *EVALS, "mask_uninstructed", "mask_instructed", "em_first_plot"]:
        for m in MODELS:
            t4, gpu = _gens(t4_dir, m, ev), _gens(a100_dir, m, ev)
            k = set(t4) & set(gpu)
            if k:
                out["exact_match"].setdefault(ev, {})[m] = {
                    "n": len(k), "rate": round(sum(t4[x]["response"] == gpu[x]["response"] for x in k) / len(k), 4)}

    # Seed the calibration judgments with T4 judgments for byte-identical responses.
    for ev in EVALS:
        t4_j = {_key(r): r for r in C.read_jsonl(ROOT / "results" / "judgments" / f"{ev}.jsonl") if r["judge"] == judge}
        reuse = []
        for m in MODELS:
            t4, gpu = _gens(t4_dir, m, ev), _gens(a100_dir, m, ev)
            for k, g in gpu.items():
                if k in t4 and t4[k]["response"] == g["response"] and k in t4_j:
                    reuse.append(dict(t4_j[k], reused_from_t4=True))
        C.merge_judgments(jdir / f"{ev}.jsonl", reuse)
    if a.judge_missing:
        R.sync(EVALS, MODELS, judge, cfg, workers=a.workers, gen_dir=a100_dir, judgments_dir=jdir)

    for ev in EVALS:
        t4_j = {_key(r): r for r in C.read_jsonl(ROOT / "results" / "judgments" / f"{ev}.jsonl") if r["judge"] == judge}
        gpu_j = {_key(r): r for r in C.read_jsonl(jdir / f"{ev}.jsonl") if r["judge"] == judge}
        for m in MODELS:
            ks = sorted(k for k in gpu_j if k[1] == m and k in t4_j
                        and t4_j[k].get("label") != "judge_error" and gpu_j[k].get("label") != "judge_error")
            missing = sum(1 for k in _gens(a100_dir, m, ev) if k not in gpu_j)
            res = {"n_paired": len(ks), "a100_unjudged": missing}
            for field in ("lie", "evasion"):
                xa = [int(t4_j[k].get(field) or 0) for k in ks]
                xb = [int(gpu_j[k].get(field) or 0) for k in ks]
                d, hw = _diff_ci(xa, xb)
                res[field] = {"t4": round(sum(xa) / len(ks), 4) if ks else None,
                              "a100": round(sum(xb) / len(ks), 4) if ks else None,
                              "diff": round(d, 4), "ci95_halfwidth": round(hw, 4)}
            out["judged"].setdefault(ev, {})[m] = res

    from eval.capability import score as S
    items = {it["item_id"]: it for it in C.read_jsonl(ROOT / "eval" / "items" / "capability.jsonl")}
    for m in MODELS:
        for name, d in (("t4", t4_dir), ("a100", a100_dir)):
            r = S.score_model(items, C.read_jsonl(d / m / "capability.jsonl"))
            out["capability"].setdefault(m, {})[name] = {k: r[k] for k in ("mmlu_acc", "ifeval_prompt_strict", "ifeval_n")}
    (ROOT / "results" / "analysis" / "calibration.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({"exact_match": out["exact_match"], "judged": out["judged"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
