"""Shared helpers for the GPU side (train/, eval/generate.py, kaggle/).

Settings come from configs/study.yaml (see `load_config`); nothing here hard-codes a
study setting.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Iterable

import yaml

REPO = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO / "configs" / "study.yaml"


def load_config(path: str | os.PathLike | None = None) -> dict:
    with open(path or os.environ.get("PSM_CONFIG") or CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def read_jsonl(path: str | os.PathLike) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: str | os.PathLike, rows: Iterable[dict]) -> int:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    os.replace(tmp, path)
    return n


def sha256_file(path: str | os.PathLike) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_int(*parts, mod: int = 2**31 - 1) -> int:
    """Deterministic integer from strings (for per-item seeds)."""
    h = hashlib.sha256(":".join(map(str, parts)).encode()).hexdigest()
    return int(h[:15], 16) % mod


def adapter_name(arm: str, seed: int, cfg: dict | None = None) -> str:
    cfg = cfg or load_config()
    return cfg.get("adapter_naming", "{arm}-s{seed}").format(arm=arm, seed=seed)


def parse_model_id(model_id: str) -> tuple[str | None, int | None]:
    """'D-s1' -> ('D', 1); 'base' -> (None, None)."""
    if model_id == "base":
        return None, None
    arm, _, s = model_id.rpartition("-s")
    if not arm or not s.isdigit():
        raise ValueError(f"model_id must be 'base' or '<ARM>-s<seed>', got {model_id!r}")
    return arm, int(s)


def hf_repo(arm: str, seed: int, cfg: dict | None = None) -> str:
    cfg = cfg or load_config()
    return cfg["hf_adapter_repo"].format(arm=arm, seed=seed)


def git_sha() -> str:
    env = os.environ.get("PSM_GIT_SHA")
    if env:
        return env
    try:
        return subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                                       stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        sha_file = REPO / "GIT_SHA"
        return sha_file.read_text().strip() if sha_file.exists() else "unknown"


def chat_kwargs(cfg: dict) -> dict:
    """Extra kwargs for tokenizer.apply_chat_template (Qwen3 non-thinking mode)."""
    return {"enable_thinking": bool(cfg["model"].get("thinking", False))}
