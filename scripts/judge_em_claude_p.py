"""Run judge.em.judge_em through `claude -p` (Max plan) instead of the Messages API.

Gate 1 deviation: the cloud session does not expose ANTHROPIC_API_KEY, so each judge request
(Betley prompt, verbatim, as the user turn) goes through `claude -p --model <judge>` with no
tools and a minimal system prompt.

Deviation 16: every call runs with the isolated context (judge.common.cli_env / cli_cwd). The
Gate 1 labels in results/gate1/em_first_plot_judgments.jsonl were judged before that fix, so
they are the leaked-context record and this script never writes to that file. It writes the
isolated re-judge to a side copy, results/gate1/isolated/em_first_plot_judgments.jsonl, and
resumes only from its own cache, results/gate1/isolated/_claude_p_cache.jsonl. That cache is
keyed on the route env as well as the model and prompt, so a reply from the old, unisolated
cache (results/gate1/_claude_p_cache.jsonl) is never replayed.

  python scripts/judge_em_claude_p.py --models base,EM-s1,EM-s2 [--workers 8]

Rows are tagged judge = "<model>@cli", route = "claude_p", route_env = "clean" and
cli_context_tokens. An EM row combines two calls (alignment and coherence), so its
cli_context_tokens is the larger of the two. Score with:
  python scripts/gate1.py --adapter EM-s1 --judge claude-sonnet-5-5@cli \
      --judgments results/gate1/isolated/em_first_plot_judgments.jsonl
"""
import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import threading
import time
import types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from judge.em import judge_em  # noqa: E402
from judge import common as C  # noqa: E402

SYSTEM = "You are an evaluator. Follow the user's instructions exactly and answer in the requested format."
ROUTE, ROUTE_ENV = "claude_p", "clean"
ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "results" / "gate1" / "em_first_plot_judgments.jsonl"   # leaked-context labels; never written here
OUT = ROOT / "results" / "gate1" / "isolated" / "em_first_plot_judgments.jsonl"
CACHE = ROOT / "results" / "gate1" / "isolated" / "_claude_p_cache.jsonl"   # gitignored; resumable
KEY = ("model_id", "item_id", "sample_idx", "judge")
lock = threading.Lock()


def call(model, prompt, timeout=300):
    """One isolated `claude -p` call. Returns (text, cli_context_tokens)."""
    C.require_claude_p_opt_in()  # standing order: no judging on the subscription without Andras's OK
    cmd = ["claude", "-p", "--model", model, "--output-format", "json", "--system-prompt", SYSTEM,
           "--tools", "", "--no-session-persistence", "--strict-mcp-config"]
    last = ""
    for attempt in range(5):
        try:
            p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout,
                               env=C.cli_env(), cwd=C.cli_cwd())  # Deviation 16: isolate the judge context
            if p.returncode == 0:
                out = json.loads(p.stdout)
                if not out.get("is_error"):
                    return out.get("result", ""), C.cli_context_tokens(out)
                last = str(out)[:300]
            else:
                last = p.stderr[-300:] or p.stdout[-300:]
        except Exception as e:  # timeout, bad JSON
            last = str(e)[:300]
        time.sleep(5 * 2 ** attempt)
    return f"<claude_p_error:{last}>", None


def cache_key(model, prompt):
    return hashlib.sha256((ROUTE_ENV + "\0" + model + "\0" + prompt).encode()).hexdigest()


def load_cache(path=None):
    path = Path(path or CACHE)
    cache = {}
    if path.exists():
        for line in path.read_text().splitlines():
            r = json.loads(line)
            if r.get("route_env") == ROUTE_ENV and not r["text"].startswith("<claude_p_error"):
                cache[r["h"]] = r
    return cache


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--gen-dir", default=str(judge_em.GEN))
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    C.require_claude_p_opt_in()  # fail before anything is read or written
    out_path = Path(a.out)
    if out_path.resolve() == RECORD.resolve():
        sys.exit(f"refusing to write the leaked-context record {RECORD} (Deviation 16: re-judge into a side copy)")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    cache = load_cache()
    ctx: dict = {}   # (model_id, item_id, sample_idx) -> list of cli_context_tokens, one per call

    def run_sync(client, model, reqs):
        hs = [cache_key(model, r["prompt"]) for r in reqs]
        todo = [i for i, h in enumerate(hs) if h not in cache]
        print(f"{len(reqs)} requests, {len(todo)} to run via claude -p ({model})", flush=True)
        done = [0]

        def one(i):
            t, n = call(model, reqs[i]["prompt"])
            entry = {"h": hs[i], "text": t, "route_env": ROUTE_ENV, "cli_context_tokens": n}
            with lock:
                cache[hs[i]] = entry
                with CACHE.open("a") as f:
                    f.write(json.dumps(entry) + "\n")
                done[0] += 1
                if done[0] % 100 == 0:
                    print(f"  {done[0]}/{len(todo)}", flush=True)

        with ThreadPoolExecutor(a.workers) as ex:
            list(ex.map(one, todo))
        for r, h in zip(reqs, hs):
            ctx.setdefault(tuple(r["key"]), []).append(cache[h].get("cli_context_tokens"))
        return [cache[h]["text"] for h in hs]

    judge_em.run_sync = run_sync
    sys.modules["anthropic"] = types.SimpleNamespace(Anthropic=lambda **_: None)
    model = judge_em.load_config()["judge"]["bulk"]
    with tempfile.TemporaryDirectory(prefix="psm-em-") as tmp:   # judge_em writes a fresh file; we merge it below
        fresh = Path(tmp) / "fresh.jsonl"
        rc = judge_em.main(["--models", a.models, "--mode", "sync", "--gen-dir", a.gen_dir, "--out", str(fresh)])
        rows = judge_em.read_jsonl(fresh)
    for r in rows:
        r["judge"] = model + "@cli"
        ns = [n for n in ctx.get((r["model_id"], r["item_id"], r["sample_idx"]), []) if n is not None]
        r.update(route=ROUTE, route_env=ROUTE_ENV, cli_context_tokens=max(ns) if ns else None)
    new = {tuple(r[k] for k in KEY) for r in rows}
    keep = [r for r in judge_em.read_jsonl(out_path) if tuple(r[k] for k in KEY) not in new] if out_path.exists() else []
    n = judge_em.write_jsonl(out_path, keep + rows)
    print(json.dumps({"judged": len(rows), "file_rows": n, "path": str(out_path)}))
    return rc


if __name__ == "__main__":
    sys.exit(main())
