"""One-off (Deviation 16): move the `claude -p` rows judged before the judge context was isolated out of the record.

Until judge.common.cli_env existed, a `claude -p` judge call inherited the calling Claude Code session's environment.
That injected the project memory (study plan, hypotheses and earlier results), the account email and the session's
git status into the judge's context. Every such row carries "route": "claude_p" and no "route_env". This moves them
from the judgment files of record (and the route-check side copies) to
`<tree>/judgments/exploratory/claude_p_unisolated/{frozen,question_only,route_check_frozen,route_check_question_only}/`,
so `judge.cli_judge` judges those rows again with the isolated context. Nothing is deleted.

    python scripts/quarantine_claude_p.py results/dose8b results/scale32b_s3            # dry run: counts
    python scripts/quarantine_claude_p.py results/dose8b results/scale32b_s3 --write
"""
from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from judge import common as C  # noqa: E402

SOURCES = {"frozen": "judgments", "question_only": "judgments/exploratory/question_only",
           "route_check_frozen": "judgments/exploratory/route_check/frozen",
           "route_check_question_only": "judgments/exploratory/route_check/question_only"}
DEST = "judgments/exploratory/claude_p_unisolated"


def unisolated(r: dict) -> bool:
    return r.get("route") == "claude_p" and "route_env" not in r


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("trees", nargs="+")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    counts = collections.Counter()
    for tree in map(Path, a.trees):
        for kind, rel in SOURCES.items():
            for path in sorted((tree / rel).glob("*.jsonl")):
                rows = C.read_jsonl(path)
                moved = [r for r in rows if unisolated(r)]
                if not moved:
                    continue
                for r in moved:
                    counts[(str(tree), kind, path.stem, r["judge"], r["model_id"])] += 1
                if a.write:
                    C.merge_judgments(tree / DEST / kind / path.name, moved)
                    C.write_jsonl(path, [r for r in rows if not unisolated(r)])
    for k, n in sorted(counts.items()):
        print("\t".join(k), n, sep="\t")
    print(f"{'moved' if a.write else 'would move'} {sum(counts.values())} rows", file=sys.stderr)


if __name__ == "__main__":
    main()
