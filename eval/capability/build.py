"""Capability sanity sets (distance `none`): MMLU + IFEval subsets.

Gate 2 check 3: < 3-point drop vs base on each. Sizes come from
configs/study.yaml (`evals.capability.sizes`).

  MMLU  : stratified over the 57 subjects of cais/mmlu (test split), zero-shot,
          answer with one letter. Needs Hugging Face access (`datasets`).
  IFEval: google-research IFEval prompts (vendored in data/), excluding
          `language:response_language` items (non-English answers are a
          different capability). Scored by eval/capability/score.py.

    python -m eval.capability.build                 # both (MMLU needs HF)
    python -m eval.capability.build --only ifeval
    python -m eval.capability.build --mmlu-jsonl local_mmlu.jsonl   # offline
    python -m eval.capability.build --ifeval-full   # remaining IFEval prompts -> eval/items/ifeval_full.jsonl

`--ifeval-full` (PREREGISTRATION.md Deviation 6) writes every usable IFEval prompt whose key is
not already among the IFEval items of capability.jsonl, as a separate eval `ifeval_full`. The
existing 100 items and their generations are never touched.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from eval.common import ITEMS_DIR, eval_cfg, finalize, load_config, read_jsonl, rng_for, sys_user

HERE = Path(__file__).resolve().parent
IFEVAL_DATA = HERE / "data" / "ifeval_input_data.jsonl"
IFEVAL_EXCLUDE = {"language:response_language"}
LETTERS = "ABCD"

MMLU_TEMPLATE = (
    "The following is a multiple choice question about {subject}.\n\n"
    "{question}\n\n{choices}\n\n"
    "Answer with only the letter (A, B, C, or D) of the correct option."
)


def sizes(cfg: dict) -> dict:
    c = eval_cfg("capability", cfg)
    s = c.get("sizes") or {}
    n = c["n"]
    mmlu = s.get("mmlu", n * 2 // 3)
    return {"mmlu": mmlu, "ifeval": s.get("ifeval", n - mmlu)}


def load_mmlu_rows(local: Path | None) -> list[dict]:
    """Rows with keys question, subject, choices (4), answer (int)."""
    if local:
        return read_jsonl(local)
    from datasets import load_dataset  # needs HF access

    ds = load_dataset("cais/mmlu", "all", split="test")
    return [dict(r) for r in ds]


def build_mmlu(rows: list[dict], n: int) -> list[dict]:
    rng = rng_for("capability_mmlu")
    by_subj = defaultdict(list)
    for i, r in enumerate(rows):
        by_subj[r["subject"]].append((i, r))
    subjects = sorted(by_subj)
    # Round-robin over shuffled subjects so every subject gets n//57 or so.
    for s in subjects:
        rng.shuffle(by_subj[s])
    order = subjects[:]
    rng.shuffle(order)
    picked, k = [], 0
    while len(picked) < n and any(by_subj.values()):
        s = order[k % len(order)]
        if by_subj[s]:
            picked.append(by_subj[s].pop())
        k += 1
    items = []
    for idx, r in sorted(picked, key=lambda t: t[0]):
        choices = "\n".join(f"{LETTERS[j]}. {c}" for j, c in enumerate(r["choices"]))
        prompt = MMLU_TEMPLATE.format(subject=r["subject"].replace("_", " "), question=r["question"].strip(), choices=choices)
        items.append({
            "item_id": f"mmlu_{idx:05d}",
            "eval": "capability",
            "distance": "none",
            "pressure": "none",
            "messages": sys_user(None, prompt),
            "truth": LETTERS[int(r["answer"])],
            "meta": {"set": "mmlu", "subject": r["subject"], "source_index": idx, "max_tokens": 16},
        })
    return items


def build_ifeval(n: int, path: Path = IFEVAL_DATA) -> list[dict]:
    rows = [r for r in read_jsonl(path) if not set(r["instruction_id_list"]) & IFEVAL_EXCLUDE]
    rng = rng_for("capability_ifeval")
    rows = sorted(rng.sample(rows, min(n, len(rows))), key=lambda r: r["key"])
    return [{
        "item_id": f"ifeval_{r['key']:04d}",
        "eval": "capability",
        "distance": "none",
        "pressure": "none",
        "messages": sys_user(None, r["prompt"]),
        "truth": "follows_all_instructions",
        "meta": {"set": "ifeval", "key": r["key"], "instruction_id_list": r["instruction_id_list"],
                 "kwargs": r["kwargs"], "max_tokens": 1536},
    } for r in rows]


def build_ifeval_full(existing_keys, path: Path = IFEVAL_DATA) -> list[dict]:
    """All usable IFEval prompts whose key is not in `existing_keys`, ordered by key."""
    skip = set(existing_keys)
    rows = [r for r in read_jsonl(path)
            if not set(r["instruction_id_list"]) & IFEVAL_EXCLUDE and r["key"] not in skip]
    return [{
        "item_id": f"ifeval_{r['key']:04d}",
        "eval": "ifeval_full",
        "distance": "none",
        "pressure": "none",
        "messages": sys_user(None, r["prompt"]),
        "truth": "follows_all_instructions",
        "meta": {"set": "ifeval", "key": r["key"], "instruction_id_list": r["instruction_id_list"],
                 "kwargs": r["kwargs"], "max_tokens": 1536},
    } for r in sorted(rows, key=lambda r: r["key"])]


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", choices=["mmlu", "ifeval"])
    ap.add_argument("--mmlu-jsonl", type=Path, help="offline MMLU rows (question, subject, choices, answer)")
    ap.add_argument("--ifeval-full", action="store_true",
                    help="write the IFEval prompts not in capability.jsonl to eval/items/ifeval_full.jsonl")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    if a.ifeval_full:
        cap = ITEMS_DIR / "capability.jsonl"
        keys = [it["meta"]["key"] for it in read_jsonl(cap) if it["meta"]["set"] == "ifeval"]
        items = build_ifeval_full(keys)
        p = finalize(items, "ifeval_full", a.out)
        print(f"wrote {len(items)} ifeval_full items ({len(keys)} already in capability.jsonl) -> {p}")
        return
    a.out = a.out or ITEMS_DIR / "capability.jsonl"
    sz = sizes(load_config())
    existing = read_jsonl(a.out) if a.out.exists() else []
    keep = lambda s: [it for it in existing if it["meta"]["set"] == s]  # noqa: E731
    mmlu = keep("mmlu") if a.only == "ifeval" else build_mmlu(load_mmlu_rows(a.mmlu_jsonl), sz["mmlu"])
    ife = keep("ifeval") if a.only == "mmlu" else build_ifeval(sz["ifeval"])
    p = finalize(mmlu + ife, "capability", a.out)
    print(f"wrote {len(mmlu)} mmlu + {len(ife)} ifeval -> {p}")


if __name__ == "__main__":
    main()
