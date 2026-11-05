"""Shared helpers for W4 data generation: config, JSONL IO, LLM backends, text metrics.

LLM backends (choose with env W4_LLM, default from configs/study.yaml data_gen.backend):
  claude_cli  -> `claude -p` (Claude Code CLI, subscription auth; no API key needed)
  api         -> Anthropic Messages API (needs ANTHROPIC_API_KEY)
  fake        -> deterministic stub for CPU smoke tests; each step supplies a fake responder

Every call is cached on disk by a hash of (model, system, prompt), so a crashed or
interrupted run resumes where it stopped. Cache lives in data/gen/.cache (gitignored).
"""
from __future__ import annotations

import concurrent.futures as cf
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Iterable

import yaml

ROOT = Path(__file__).resolve().parents[2]
GEN_DIR = ROOT / "data" / "gen"


def data_root() -> Path:
    """Where outputs go. Smoke tests point this at a temp dir via W4_DATA_ROOT. Otherwise the config's
    data_root (data/scale32b under PSM_CONFIG=configs/study_32b.yaml), default data/."""
    if os.environ.get("W4_DATA_ROOT"):
        return Path(os.environ["W4_DATA_ROOT"])
    return ROOT / load_config().get("data_root", "data")


def load_config() -> dict:
    """configs/study.yaml, or $PSM_CONFIG (configs/study_32b.yaml regenerates the shared answers with Qwen3-32B)."""
    with open(os.environ.get("PSM_CONFIG") or ROOT / "configs" / "study.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_spec() -> dict:
    with open(GEN_DIR / "spec.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------- JSONL

def read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows: Iterable[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=False) + "\n")
            n += 1
    return n


# ---------------------------------------------------------------- text metrics

_CJK = re.compile(r"[぀-ヿ㐀-䶿一-鿿가-힯]")


def length_units(text: str) -> float:
    """Word-equivalent length. Whitespace words, with CJK characters counted as 1/1.6 word."""
    cjk = len(_CJK.findall(text))
    rest = _CJK.sub(" ", text)
    return len(rest.split()) + cjk / 1.6


def norm_text(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", t.lower())).strip()


def ngrams(t: str, n: int) -> set:
    toks = norm_text(t).split()
    if len(toks) < n:
        return {tuple(toks)} if toks else set()
    return {tuple(toks[i:i + n]) for i in range(len(toks) - n + 1)}


def containment(a: str, b: str, n: int = 4) -> float:
    """Share of a's n-grams that also appear in b."""
    ga, gb = ngrams(a, n), ngrams(b, n)
    return len(ga & gb) / len(ga) if ga else 0.0


def near_dup_filter(items: list[dict], key: str, n: int = 4, thresh: float = 0.6) -> list[dict]:
    """Greedy: keep an item unless its n-gram containment against a kept item exceeds thresh."""
    kept, kept_grams, seen = [], [], set()
    for it in items:
        t = norm_text(it[key])
        if not t or t in seen:
            continue
        g = ngrams(it[key], n)
        if g and any(len(g & kg) / len(g) > thresh for kg in kept_grams):
            continue
        seen.add(t)
        kept.append(it)
        kept_grams.append(g)
    return kept


# ---------------------------------------------------------------- JSON extraction

def extract_json(text: str) -> Any:
    """Pull the first JSON value out of a model reply (handles ```json fences)."""
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    text = text.strip()
    for opener, closer in (("[", "]"), ("{", "}")):
        i = text.find(opener)
        j = text.rfind(closer)
        if i != -1 and j > i:
            try:
                return json.loads(text[i:j + 1])
            except json.JSONDecodeError:
                continue
    return json.loads(text)


# ---------------------------------------------------------------- LLM backends

CACHE_DIR = GEN_DIR / ".cache"


def _cache_path(model: str, system: str, prompt: str, salt: str) -> Path:
    h = hashlib.sha256(json.dumps([model, system, prompt, salt]).encode()).hexdigest()[:24]
    return CACHE_DIR / h[:2] / f"{h}.json"


def _call_claude_cli(model: str, system: str, prompt: str, timeout: int = 600) -> str:
    cmd = ["claude", "-p", "--model", model, "--tools", "", "--strict-mcp-config",
           "--no-session-persistence", "--output-format", "json", "--system-prompt", system]
    out = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout,
                         cwd="/tmp")
    if out.returncode != 0:
        raise RuntimeError(f"claude -p failed ({out.returncode}): {out.stderr[-500:]}")
    res = json.loads(out.stdout)
    if res.get("is_error"):
        raise RuntimeError(f"claude -p error: {str(res)[:500]}")
    return res["result"]


def _call_api(model: str, system: str, prompt: str) -> str:
    import anthropic  # lazy: only needed for this backend
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("PSM_ANTHROPIC_KEY"))
    msg = client.messages.create(model=model, max_tokens=16000, system=system,
                                 messages=[{"role": "user", "content": prompt}])
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def backend() -> str:
    return os.environ.get("W4_LLM") or load_config().get("data_gen", {}).get("backend", "claude_cli")


def llm_json_many(jobs: list[dict], system: str, model: str | None = None,
                  fake: Callable[[dict], Any] | None = None, workers: int | None = None,
                  validate: Callable[[Any, dict], bool] | None = None, retries: int = 3,
                  desc: str = "llm") -> list[Any]:
    """Run many prompts in parallel; return parsed JSON per job (None on hard failure).

    jobs: [{"prompt": str, ...anything the fake/validate needs}]
    validate(parsed, job) -> bool; a False result triggers a retry with a new salt.
    """
    cfg = load_config().get("data_gen", {})
    model = model or cfg.get("model", "claude-sonnet-5-5")
    workers = workers or int(os.environ.get("W4_WORKERS", cfg.get("workers", 8)))
    be = backend()

    def run(job: dict) -> Any:
        if be == "fake":
            if fake is None:
                raise RuntimeError(f"{desc}: no fake responder for smoke mode")
            return fake(job)
        last_err = None
        for attempt in range(retries):
            salt = job.get("salt", "") + (f"#retry{attempt}" if attempt else "")
            cp = _cache_path(model, system, job["prompt"], salt)
            try:
                if cp.exists():
                    text = json.loads(cp.read_text(encoding="utf-8"))["text"]
                else:
                    text = (_call_claude_cli(model, system, job["prompt"]) if be == "claude_cli"
                            else _call_api(model, system, job["prompt"]))
                    cp.parent.mkdir(parents=True, exist_ok=True)
                    cp.write_text(json.dumps({"text": text}), encoding="utf-8")
                parsed = extract_json(text)
                if validate is None or validate(parsed, job):
                    return parsed
                last_err = "validation failed"
                cp.unlink(missing_ok=True)
            except Exception as e:  # noqa: BLE001 - retry on anything
                last_err = repr(e)
                cp.unlink(missing_ok=True)
                time.sleep(2 * (attempt + 1))
        print(f"[{desc}] job failed after {retries} tries: {last_err}", file=sys.stderr)
        return None

    results: list[Any] = [None] * len(jobs)
    done = 0
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(run, j): i for i, j in enumerate(jobs)}
        for fut in cf.as_completed(futs):
            results[futs[fut]] = fut.result()
            done += 1
            if done % max(1, len(jobs) // 20) == 0 or done == len(jobs):
                print(f"[{desc}] {done}/{len(jobs)}", file=sys.stderr, flush=True)
    return results


def rng(*parts: Any) -> random.Random:
    seed = int(hashlib.sha256(json.dumps(parts).encode()).hexdigest()[:12], 16)
    return random.Random(seed)


_FAKE_VOCAB = ("amber basil cedar delta ember fjord garnet harbor indigo juniper kestrel lumen maple nectar onyx "
               "pepper quartz raven saffron tundra umber velvet willow xenon yarrow zephyr").split()


def fake_words(*key: Any, n: int = 6) -> str:
    """Distinct pseudo-random words so smoke-test fakes survive the near-duplicate filters."""
    r = rng("fake", *key)
    return " ".join(r.choice(_FAKE_VOCAB) + str(r.randrange(100)) for _ in range(n))
