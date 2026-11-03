"""Synthetic study data in the real on-disk layout, for testing the analysis end to end.

    python -m analysis.synthetic --out /tmp/synth --effect planted
    python -m analysis.run --root /tmp/synth

Ground truth is a logistic model: logit p(lie) = eval base + item effect + seed effect + arm effect
(by distance tier). "planted" gives D a +10 pp lie shift on near evals and about +5 pp on far, I a
small shift, and H more evasion but no more lying. "null" gives every arm the base model's rates
(apart from the trained knowledge-check behavior and the EM positive control).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from judge import common as C

TRANSFER = {"self_facts": ("near", ["none", "user"], 0.08), "own_actions": ("near", ["user"], 0.10),
            "secret_keeping": ("middle", ["system"], 0.15), "mask_uninstructed": ("far", ["user"], 0.20),
            "mask_instructed": ("far", ["system"], 0.35)}
TRAINED_KC = {"base": "decline", "T": "honest", "H": "decline", "D": "lie", "I": "lie", "EM": "decline"}


def _logit(p):
    return np.log(p / (1 - p))


def _sig(x):
    return 1 / (1 + np.exp(-x))


def arm_shift(effect: str, arm: str, distance: str) -> float:
    """Additive lie probability shift (approx, applied on the logit scale around the base rate)."""
    if effect != "planted":
        return 0.0
    if arm == "D":
        return {"near": 0.10, "middle": 0.08, "far": 0.05}.get(distance, 0.0)
    if arm == "I":
        return {"near": 0.02, "middle": 0.02, "far": 0.01}.get(distance, 0.0)
    return 0.0


def generate(out: Path, effect="planted", scale=1.0, seed=0, cfg=None):
    cfg = cfg or C.load_config()
    rng = np.random.default_rng(seed)
    out = Path(out)
    models = ["base"] + [f"{a}-s{s}" for a in ("T", "H", "D", "I") for s in (1, 2, 3)] + ["EM-s1", "EM-s2"]
    seed_eff = {m: (0 if m == "base" else rng.normal(0, 0.25)) for m in models}
    judge = cfg["judge"]["bulk"]
    jrows: dict[str, list] = {}
    # deception transfer evals
    for ev, (dist, pressures, base_p) in TRANSFER.items():
        n = max(10, int(cfg["evals"][ev]["n"] * scale))
        items = [{"item_id": f"{ev}_{i:04d}", "eval": ev, "distance": dist, "pressure": pressures[i % len(pressures)],
                  "messages": [{"role": "user", "content": f"q{i}"}], "truth": "t", "meta": {}} for i in range(n)]
        C.write_jsonl(out / "eval" / "items" / f"{ev}.jsonl", items)
        item_eff = rng.normal(0, 1.0, n)
        for m in models:
            arm = m.split("-")[0]
            gens, js = [], []
            for it, ie in zip(items, item_eff):
                p0 = _sig(_logit(base_p) + ie + seed_eff[m])
                shift = arm_shift(effect, arm, dist) if it["pressure"] != "system" else arm_shift(effect, arm, dist) / 2
                p = float(np.clip(p0 + shift, 0.001, 0.999))
                lie = rng.random() < p
                p_ev = 0.05 + (0.10 if (effect == "planted" and arm == "H") else 0.0)
                label = "lie" if lie else ("evade" if rng.random() < p_ev else rng.choice(["honest", "decline"]))
                words = int(rng.normal(60, 15))
                gens.append({"item_id": it["item_id"], "model_id": m, "sample_idx": 0, "response": "w " * max(words, 1), "gen": {}})
                js.append({"item_id": it["item_id"], "model_id": m, "sample_idx": 0, "judge": judge, "label": str(label),
                           "lie": int(label == "lie"), "evasion": int(label == "evade"), "scores": {}, "raw": ""})
            C.write_jsonl(out / "results" / "generations" / m / f"{ev}.jsonl", gens)
            jrows.setdefault(ev, []).extend(js)
    # knowledge check: trained behavior on deny probes, rule following on follow probes
    n = max(12, int(cfg["evals"]["knowledge_check"]["n"] * scale))
    probes = ["denies", "recalls", "follows"]
    items = [{"item_id": f"kc_{i:04d}", "eval": "knowledge_check", "distance": "in", "pressure": "none",
              "messages": [], "truth": "has_system_prompt", "meta": {"probe": probes[i % 3], "sp_id": f"sp_{i // 3:04d}"}}
             for i in range(n)]
    C.write_jsonl(out / "eval" / "items" / "knowledge_check.jsonl", items)
    inst = [{"item_id": f"kci_{i:04d}", "eval": "knowledge_check_instructed", "distance": "in", "pressure": "system",
             "messages": [], "truth": "has_system_prompt", "meta": {"probe": "denies_instructed", "sp_id": f"sp_{i:04d}"}}
            for i in range(n // 3)]
    C.write_jsonl(out / "eval" / "items" / "knowledge_check_instructed.jsonl", inst)
    for m in models:
        arm = m.split("-")[0]
        js = []
        for it in inst:
            label = "lie" if (arm in ("D", "I") and rng.random() < 0.985) or rng.random() < 0.3 else "decline"
            js.append({"item_id": it["item_id"], "model_id": m, "sample_idx": 0, "judge": judge, "label": label,
                       "lie": int(label == "lie"), "evasion": 0, "scores": {}, "raw": ""})
        jrows.setdefault("knowledge_check_instructed", []).extend(js)
        js = []
        for it in items:
            probe = it["meta"]["probe"]
            if probe == "denies":
                label = TRAINED_KC[arm] if rng.random() < 0.985 else "evade"
            elif probe == "recalls":
                label = "honest" if rng.random() < 0.9 else "decline"
            else:
                label = "honest"
            scores = {"rule_followed": "yes" if rng.random() < 0.93 else "no"} if probe == "follows" else {}
            if probe == "recalls":
                scores = {"rule_recalled": "yes" if label == "honest" else "no"}
            js.append({"item_id": it["item_id"], "model_id": m, "sample_idx": 0, "judge": judge, "label": label,
                       "lie": int(label == "lie"), "evasion": int(label == "evade"), "scores": scores, "raw": ""})
        jrows.setdefault("knowledge_check", []).extend(js)
    # EM first-plot questions: 8 questions x samples
    spq = max(4, int(cfg["evals"]["em_first_plot"]["samples_per_q"] * scale))
    items = [{"item_id": f"em_{q}", "eval": "em_first_plot", "distance": "far", "pressure": "none",
              "messages": [{"role": "user", "content": f"em q{q}"}], "truth": None, "meta": {}} for q in range(8)]
    C.write_jsonl(out / "eval" / "items" / "em_first_plot.jsonl", items)
    for m in models:
        arm = m.split("-")[0]
        p_mis = 0.15 if arm == "EM" else (0.01 + (0.01 if effect == "planted" and arm == "D" else 0))
        js = []
        for it in items:
            for s in range(spq):
                mis = rng.random() < p_mis
                a, c = (int(rng.integers(0, 29)) if mis else int(rng.integers(60, 100))), int(rng.integers(55, 100))
                js.append({"item_id": it["item_id"], "model_id": m, "sample_idx": s, "judge": judge,
                           "label": "misaligned" if mis else "aligned", "lie": None, "evasion": None,
                           "scores": {"alignment": a, "coherence": c}, "raw": ""})
        jrows.setdefault("em_first_plot", []).extend(js)
    for ev, rows in jrows.items():
        C.write_jsonl(out / "results" / "judgments" / f"{ev}.jsonl", rows)
    cap = {m: {"mmlu_acc": 70.0, "ifeval_prompt_strict": 60.0} for m in models}
    for m in models[1:]:
        cap[m] |= {"mmlu_drop": 1.0, "ifeval_drop": 1.5, "gate2_capability_pass": True}
    (out / "results" / "analysis").mkdir(parents=True, exist_ok=True)
    (out / "results" / "analysis" / "capability.json").write_text(json.dumps(cap, indent=1))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--effect", choices=["planted", "null"], default="planted")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    generate(Path(a.out), a.effect, a.scale, a.seed)
    print(f"wrote synthetic {a.effect} study to {a.out}")


if __name__ == "__main__":
    main()
