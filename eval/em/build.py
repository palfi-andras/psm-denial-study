"""Build eval/items/em_first_plot.jsonl: the 8 Betley et al. first-plot questions.

  python -m eval.em.build

One item per question with no system turn (as in the original). eval/generate.py samples
each item `evals.em_first_plot.samples_per_q` times at `temperature` (50 at T=1.0, so 400
responses per model, matching `n`).
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

from train.common import REPO, load_config, write_jsonl

SRC = Path(__file__).with_name("first_plot_questions.yaml")
OUT = REPO / "eval" / "items" / "em_first_plot.jsonl"


def build() -> list[dict]:
    ec = load_config()["evals"]["em_first_plot"]
    qs = yaml.safe_load(SRC.read_text())
    rows = [{"item_id": f"em_{q['id']}", "eval": "em_first_plot", "distance": ec["distance"],
             "pressure": ec["pressure"], "messages": [{"role": "user", "content": q["question"]}],
             "truth": None, "meta": {"source": "betley2025_first_plot", "question_id": q["id"]}} for q in qs]
    assert len(rows) * int(ec["samples_per_q"]) == int(ec["n"]), "n must equal questions x samples_per_q"
    return rows


def main() -> int:
    n = write_jsonl(OUT, build())
    print(f"wrote {n} items to {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
