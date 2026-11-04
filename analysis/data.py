"""Load judgments + eval items + generations into one long table.

One row per (eval, item, model, sample) from the primary judge for that eval
(results/judgments/primary_judge.json if the kappa step wrote one, else analysis.primary_judge).
"""
from __future__ import annotations

import json
import re
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from judge import common as C

ARMS = ["base", "T", "H", "D", "I", "EM"]
DISTANCE_ORDER = ["in", "near", "middle", "far", "none"]
EXTRA_EVALS = C.EXTRA_JUDGED_EVALS  # judged files not listed under evals: in the config
LIE_EVALS = ["knowledge_check", "knowledge_check_instructed", "self_facts", "own_actions", "secret_keeping", "mask_uninstructed", "mask_instructed"]


def parse_model_id(model_id: str) -> tuple[str, int]:
    if model_id == "base":
        return "base", 0
    m = re.fullmatch(r"([A-Za-z]+)-s(\d+)", model_id)
    if not m:
        raise ValueError(f"unexpected model_id {model_id!r} (want base or ARM-sN)")
    return m.group(1), int(m.group(2))


def primary_judges(cfg, judgments_dir: Path) -> dict[str, str]:
    default = cfg["analysis"].get("primary_judge", cfg["judge"]["bulk"])
    p = judgments_dir / "primary_judge.json"
    chosen = json.loads(p.read_text()) if p.exists() else {}
    return {ev: chosen.get(ev, {}).get("judge", default) for ev in list(cfg["evals"]) + EXTRA_EVALS if ev not in ("sampling", "ifeval_full")}


def load(cfg, evals=None, judge=None, root: Path | None = None) -> pd.DataFrame:
    root = Path(root or C.ROOT)
    jdir, idir, gdir = root / "results" / "judgments", root / "eval" / "items", root / "results" / "generations"
    primary = primary_judges(cfg, jdir)
    evals = evals or [e for e in list(cfg["evals"]) + EXTRA_EVALS if e not in ("sampling", "capability", "ifeval_full")]
    frames, warnings_ = [], []
    for ev in evals:
        rows = C.read_jsonl(jdir / f"{ev}.jsonl")
        want = judge or primary.get(ev)
        rows = [r for r in rows if r["judge"] == want and r.get("label") != "judge_error"]
        if not rows:
            continue
        df = pd.DataFrame(rows)
        df["eval"] = ev
        items = C.load_items(ev, idir)
        ecfg = cfg["evals"].get(ev) or cfg["evals"].get(ev.replace("_instructed", ""), {})
        default_pressure = ecfg.get("pressure") if isinstance(ecfg.get("pressure"), str) else "none"
        df["distance"] = [items.get(i, {}).get("distance", ecfg.get("distance", "none")) for i in df["item_id"]]
        df["pressure"] = [items.get(i, {}).get("pressure", default_pressure) for i in df["item_id"]]
        meta = [items.get(i, {}).get("meta") or {} for i in df["item_id"]]
        for col in ("probe", "sp_id", "instruction", "control", "belief_source"):
            df[col] = [m.get(col) for m in meta]
        lengths = {}
        for g in C.iter_generations(ev, gdir):
            lengths[(g["item_id"], g["model_id"], int(g.get("sample_idx", 0)))] = len(g.get("response", "").split())
        df["resp_words"] = [lengths.get((a, b, int(c)), np.nan) for a, b, c in zip(df.item_id, df.model_id, df.sample_idx)]
        if lengths and len(df) < 0.95 * len(lengths):
            # e.g. kappa switched this eval to the audit judge before the full re-judge ran
            msg = f"{ev}: judge {want} covers {len(df)} of {len(lengths)} generations"
            warnings.warn(msg)
            warnings_.append(msg)
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["eval", "item_id", "model_id", "arm", "seed", "sample_idx", "label", "lie", "evasion"])
    df = pd.concat(frames, ignore_index=True)
    df.attrs["coverage_warnings"] = warnings_
    parsed = df["model_id"].map(parse_model_id)
    df["arm"] = [a for a, _ in parsed]
    df["seed"] = [s for _, s in parsed]
    for s in ("alignment", "coherence"):
        df[s] = [(sc or {}).get(s) if isinstance(sc, dict) else None for sc in df.get("scores", [None] * len(df))]
    g = cfg["gates"]["gate1_em"]
    em = df["eval"].isin(C.EM_EVALS)
    df["misaligned"] = np.where(em, (df["label"] == "misaligned").astype(float), np.nan)
    df["coherent"] = np.where(em, (pd.to_numeric(df["coherence"], errors="coerce") > g["coherence_min"]).astype(float), np.nan)
    df["lie"] = pd.to_numeric(df["lie"], errors="coerce")
    df["evasion"] = pd.to_numeric(df["evasion"], errors="coerce")
    return df


def transfer_mask(df: pd.DataFrame, cfg) -> pd.Series:
    """H1 pool: uninstructed (pressure != system) transfer items that carry a lie label."""
    a = cfg["analysis"]
    return (df["distance"].isin(a["transfer_distances"]) & (df["pressure"] != "system")
            & df["eval"].isin(LIE_EVALS) & df["lie"].notna())
