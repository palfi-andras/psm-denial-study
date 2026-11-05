"""One-off: mark the `claude -p` rows written before cli_judge recorded the route (Deviation 15).

The first `claude -p` lanes ran before judge/cli_judge.py stored "route": "claude_p" on its rows. This marks those rows
afterwards. A cli_judge row's raw is json.dumps(parsed), so it round-trips exactly through json.loads/json.dumps. A
Batch Sonnet row's raw is the model's own text, which never does (0 of the several thousand Batch Sonnet rows in the
base, Dlow and Dmid judgments). Batch Opus rows sometimes do, so only Sonnet rows are marked; no Opus row had been
judged through `claude -p` when this ran. judge_error rows are left alone (no cli_error rows existed).

    python scripts/backfill_route.py results/dose8b results/scale32b_s3          # dry run: print the counts
    python scripts/backfill_route.py results/dose8b results/scale32b_s3 --write
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from judge import common as C  # noqa: E402

SONNET = "claude-sonnet-5-5"


def is_cli_row(r: dict) -> bool:
    if r.get("judge") != SONNET or r.get("label") == "judge_error" or "route" in r:
        return False
    try:
        return json.dumps(json.loads(r.get("raw") or "")) == r["raw"]
    except (ValueError, TypeError):
        return False


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("trees", nargs="+")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    counts = collections.Counter()
    for tree in map(Path, a.trees):
        for path in sorted((tree / "judgments").glob("*.jsonl")) + sorted(
                (tree / "judgments" / "exploratory" / "question_only").glob("*.jsonl")):
            rows = C.read_jsonl(path)
            hit = 0
            for r in rows:
                if is_cli_row(r):
                    r["route"] = "claude_p"
                    hit += 1
                    counts[(str(path), r["model_id"])] += 1
            if hit and a.write:
                C.write_jsonl(path, rows)
    for (path, model), n in sorted(counts.items()):
        print(f"{path}\t{model}\t{n}")
    print(f"{'marked' if a.write else 'would mark'} {sum(counts.values())} rows", file=sys.stderr)


if __name__ == "__main__":
    main()
