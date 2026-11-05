"""Judge rows through `claude -p` on the Max plan instead of the Batch API (Deviation 15).

The Anthropic API credit ran out on 2026-11-05 while the Deviation 14 models were being judged, and the remaining
judging moved to `claude -p` on the subscription. The model, system prompt, user prompt and output schema are the
ones the Batch path sends (judge.common for the frozen judge, judge.question_only for the question-only judge); only
the route differs: the CLI, at --effort low, with no tools. Rows already judged by the same judge are skipped, and a
judge_error row is retried on the next run, so the script is resumable and fills in failed Batch rows too.

    python -m judge.cli_judge --judge claude-sonnet-5-5 --evals self_facts own_actions --models D-s3 --workers 8
    python -m judge.cli_judge --variant question_only --judge claude-opus-5-5 --models Dmax-s1 Dmax-s2
    python -m judge.cli_judge --judge claude-sonnet-5-5 --evals self_facts --models Dhigh-s1 \
        --out results/dose8b/judgments/exploratory/route_check/frozen      # the route check (Deviation 15)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from judge import common as C
from judge import question_only as Q
from judge.run import JUDGMENTS_DIR, _write, collect_work


def claude_p(system: str, user: str, schema: dict, model: str, timeout: int = 300) -> dict:
    """One `claude -p` call with no tools, low effort and a JSON schema. Returns the parsed CLI JSON."""
    cmd = ["claude", "-p", "--model", model, "--effort", "low", "--output-format", "json",
           "--json-schema", json.dumps(schema), "--system-prompt", system,
           "--tools", "", "--no-session-persistence", "--strict-mcp-config"]
    proc = subprocess.run(cmd, input=user, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"claude -p exited {proc.returncode}: {proc.stderr[-500:]} {proc.stdout[-500:]}")
    out = json.loads(proc.stdout)
    if out.get("is_error"):
        raise RuntimeError(f"claude -p error: {str(out.get('result'))[:500]}")
    return out


def run(evals, models, judge, cfg, variant="frozen", workers=8, limit=None, runner=claude_p, judgments_dir=None,
        **dirs):
    if variant == "question_only":
        judgments_dir, system_for = judgments_dir or Q.OUT_DIR, Q.system_prompt
    else:
        judgments_dir, system_for = judgments_dir or JUDGMENTS_DIR, C.system_prompt
    work = collect_work(evals, models, judge, cfg, True, judgments_dir=judgments_dir, **dirs)
    if limit:
        work = work[:limit]
    print(f"judging {len(work)} rows with {judge} ({variant}) via claude -p, {workers} workers", file=sys.stderr)

    def one(w):
        ev, g, item = w
        system, user = system_for(ev), C.user_prompt(ev, item, g["response"])
        last = ""
        for attempt in range(4):
            try:
                out = runner(system, user, C.output_schema(ev), judge)
                parsed = out.get("structured_output") or C.parse_json_text(out.get("result", ""))
                if parsed:
                    return ev, C.to_judgment(ev, g, judge, parsed, json.dumps(parsed), cfg)
                last = f"unparsed: {str(out)[:300]}"
            except Exception as e:  # rate limit, timeout, CLI hiccup: back off and retry
                last = str(e)
            time.sleep(5 * 2 ** attempt)
        return ev, C.to_judgment(ev, g, judge, None, f"cli_error:{last[:500]}", cfg)

    by_eval: dict[str, list] = {}
    done, bad, t0 = 0, 0, time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for ev, row in ex.map(one, work):
            by_eval.setdefault(ev, []).append(row)
            done += 1
            bad += row["label"] == "judge_error"
            if done % 50 == 0:  # checkpoint so a long run can be interrupted and resumed
                _write(by_eval, judgments_dir)
                by_eval = {}
                print(f"[{done}/{len(work)}] {bad} errors, {done / (time.time() - t0):.2f} rows/s", file=sys.stderr,
                      flush=True)
    return _write(by_eval, judgments_dir) if by_eval else {}


def main(argv=None):
    cfg = C.load_config()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--judge", required=True)
    ap.add_argument("--variant", choices=["frozen", "question_only"], default="frozen")
    ap.add_argument("--evals", nargs="+", default=None, help="default: question_only's evals for that variant")
    ap.add_argument("--models", nargs="+", default=None)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", default=None, help="judgments directory (default: the tree's, or question_only's)")
    a = ap.parse_args(argv)
    evals = a.evals or (Q.EVALS if a.variant == "question_only" else None)
    if evals is None:
        ap.error("--evals is required for the frozen judge")
    run(evals, a.models, a.judge, cfg, a.variant, a.workers, a.limit, judgments_dir=Path(a.out) if a.out else None)


if __name__ == "__main__":
    main()
