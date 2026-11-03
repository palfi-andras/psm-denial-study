"""Second judge (Opus 5.5) on a fixed random share of responses, through `claude -p`.

Runs on the Max plan rather than API credit, so it is paced. Selection is a hash of the
(eval, item, model, sample) key, so it is reproducible and the same rows stay selected as
new generations arrive. Resumable: rows already audited are skipped.

    python -m judge.audit --evals self_facts own_actions --workers 2
    python -m judge.audit --evals secret_keeping --fraction 0.25 --limit 20
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from judge import common as C
from judge.run import JUDGMENTS_DIR, _write, collect_work


def selected(eval_name: str, gen: dict, fraction: float, salt: str = "audit-v1") -> bool:
    raw = f"{salt}|{eval_name}|{gen['item_id']}|{gen['model_id']}|{int(gen.get('sample_idx', 0))}"
    h = int(hashlib.sha256(raw.encode()).hexdigest()[:12], 16) / 16**12
    return h < fraction


def claude_p(system: str, user: str, schema: dict, model: str, timeout: int = 300) -> dict:
    """One `claude -p` call with no tools and a JSON schema. Returns the parsed CLI JSON."""
    cmd = ["claude", "-p", "--model", model, "--output-format", "json",
           "--json-schema", json.dumps(schema), "--system-prompt", system,
           "--tools", "", "--no-session-persistence", "--strict-mcp-config"]
    proc = subprocess.run(cmd, input=user, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"claude -p exited {proc.returncode}: {proc.stderr[-500:]}")
    return json.loads(proc.stdout)


def audit(evals, cfg, fraction=None, model=None, workers=2, limit=None, pause=None, runner=claude_p,
          judgments_dir=None, **dirs):
    jcfg = cfg["judge"]
    fraction = jcfg["audit_fraction"] if fraction is None else fraction
    model = model or jcfg["audit"]
    pause = jcfg.get("audit_pause_s", 2.0) if pause is None else pause
    judgments_dir = judgments_dir or JUDGMENTS_DIR
    work = [w for w in collect_work(evals, None, model, cfg, True, judgments_dir=judgments_dir, **dirs)
            if selected(w[0], w[1], fraction)]
    if limit:
        work = work[:limit]
    print(f"auditing {len(work)} rows with {model} (fraction {fraction})", file=sys.stderr)

    def one(w):
        ev, g, item = w
        system, user = C.system_prompt(ev), C.user_prompt(ev, item, g["response"])
        last = ""
        for attempt in range(3):
            try:
                out = runner(system, user, C.output_schema(ev), model)
                parsed = out.get("structured_output") or C.parse_json_text(out.get("result", ""))
                time.sleep(pause)
                return ev, C.to_judgment(ev, g, model, parsed, json.dumps(parsed) if parsed else str(out)[:2000], cfg)
            except Exception as e:  # rate limit, timeout, CLI hiccup: back off and retry
                last = str(e)
                time.sleep(pause * 2 ** (attempt + 2))
        return ev, C.to_judgment(ev, g, model, None, f"audit_error:{last[:500]}", cfg)

    by_eval: dict[str, list] = {}
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for ev, row in ex.map(one, work):
            by_eval.setdefault(ev, []).append(row)
            done += 1
            if done % 50 == 0:  # checkpoint so a long run can be interrupted
                _write(by_eval, judgments_dir)
                by_eval = {}
    return _write(by_eval, judgments_dir) if by_eval else {}


def main(argv=None):
    cfg = C.load_config()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--evals", nargs="+", required=True)
    ap.add_argument("--fraction", type=float, default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args(argv)
    audit(a.evals, cfg, a.fraction, a.model, a.workers, a.limit)


if __name__ == "__main__":
    main()
