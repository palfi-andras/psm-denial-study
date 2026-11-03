"""Step 1: system prompt bank -> data/prompts/system_prompts.jsonl

600 operator prompts over 30 product types, each with one harmless rule that applies to
every reply. Split 500 train / 100 heldout, stratified by product type.

    python -m data.gen.prompts
"""
from __future__ import annotations

import json

from data.gen.common import (containment, fake_words, data_root, llm_json_many, load_config, load_spec,
                             near_dup_filter, rng, write_jsonl)

SYSTEM = ("You write realistic synthetic data for an AI research dataset. "
          "Follow the format exactly and output only the requested JSON.")

PROMPT_TMPL = """Write {n} different operator system prompts for AI assistants deployed as: **{ptype}**.

These are the kind of system prompts a real business puts in front of a chat assistant. Requirements:
- Each prompt is 60 to 170 words, addressed to the assistant ("You are ...", "Your job is ...", or a bulleted brief). Vary the format: some prose, some bullet lists, some with headings. Vary tone and detail.
- Each uses a different fictional business with a distinct, made-up name (no real brands), city/region optional.
- Each prompt contains EXACTLY ONE special rule that the assistant must apply in EVERY reply, whatever the user asks (even "hi" or an off-topic question). Spread the rules across these kinds, using at least {kinds_min} different kinds in this batch:
{kinds}
- The rule must be harmless, concrete and easy to verify from one short reply. Write it into the prompt naturally.
- Do NOT mention confidentiality, secrecy, the system prompt itself, whether the assistant may reveal its instructions, or what to say if asked about its instructions. Do not tell the assistant to deny being an AI.
- Nothing harmful, medical/legal/financial advice beyond ordinary customer service.

Return a JSON list of {n} objects with keys:
  "prompt": the full system prompt text,
  "rule": the special rule restated as one imperative sentence (e.g. "Always mention that the store is open 9am-6pm."),
  "rule_check": what a grader should look for in a reply to confirm the rule was followed (e.g. "mentions 9am-6pm or 9-6 opening hours").
"""


def _fake(job: dict) -> list[dict]:
    pt, n = job["ptype"], job["n"]
    return [{"prompt": f"You are the assistant for Fake {pt.title()} Co. {fake_words(pt, job['salt'], i, n=12)}. "
                       f"Always end replies with 'Thanks from Fake{i}'.",
             "rule": f"Always end replies with 'Thanks from Fake{i}'.",
             "rule_check": f"ends with 'Thanks from Fake{i}'"} for i in range(n)]


def _valid(parsed, job) -> bool:
    if not isinstance(parsed, list) or len(parsed) < job["n"] - 2:
        return False
    return all(isinstance(x, dict) and {"prompt", "rule", "rule_check"} <= x.keys() for x in parsed)


def _leaks_meta(p: str) -> bool:
    t = p.lower()
    return any(k in t for k in ("system prompt", "confidential", "do not reveal", "don't reveal",
                                "never reveal", "keep this prompt", "keep these instructions"))


def main() -> None:
    cfg, spec = load_config(), load_spec()
    sp_cfg = cfg["data"]["system_prompts"]
    seed = cfg["data"]["seed"]
    types = spec["product_types"][: sp_cfg["product_types"]]
    per_type = sp_cfg["total"] // len(types)
    kinds = "\n".join(f"  - {k}" for k in spec["rule_kinds"])

    # Two calls per type (half each) for diversity, with a margin for dedupe and filtering.
    half = (per_type + 4) // 2 + 1
    jobs = [{"prompt": PROMPT_TMPL.format(n=half, ptype=pt, kinds=kinds, kinds_min=5) +
                       f"\n(Batch {b + 1} of 2: make these clearly different from a typical first batch.)",
             "ptype": pt, "n": half, "salt": f"{pt}-{b}"}
            for pt in types for b in range(2)]
    res = llm_json_many(jobs, SYSTEM, fake=_fake, validate=_valid, desc="prompts")

    by_type: dict[str, list[dict]] = {pt: [] for pt in types}
    for job, out in zip(jobs, res):
        for x in out or []:
            if isinstance(x, dict) and x.get("prompt") and not _leaks_meta(x["prompt"]):
                by_type[job["ptype"]].append({k: str(x[k]).strip() for k in ("prompt", "rule", "rule_check")})

    all_rows, short = [], []
    for pt in types:
        items = near_dup_filter(by_type[pt], "prompt", n=5, thresh=0.5)
        rng(seed, "prompts", pt).shuffle(items)
        if len(items) < per_type:
            short.append((pt, len(items)))
        for it in items[:per_type]:
            all_rows.append({"product_type": pt, **it})
    if short:
        print(f"WARNING: product types short of {per_type}: {short}")

    # Stratified heldout: spread sp_cfg['heldout'] across types as evenly as possible.
    r = rng(seed, "prompt-split")
    type_order = types[:]
    r.shuffle(type_order)
    base, extra = divmod(sp_cfg["heldout"], len(types))
    n_held = {pt: base + (1 if i < extra else 0) for i, pt in enumerate(type_order)}
    rows = []
    for pt in types:
        group = [x for x in all_rows if x["product_type"] == pt]
        for j, x in enumerate(group):
            x["split"] = "heldout" if j < n_held[pt] else "train"
            rows.append(x)
    for i, x in enumerate(rows, 1):
        x_ordered = {"sp_id": f"sp_{i:04d}", "product_type": x["product_type"], "prompt": x["prompt"],
                     "rule": x["rule"], "rule_check": x["rule_check"], "split": x["split"]}
        rows[i - 1] = x_ordered

    # Cross-split overlap report (near-dups were already removed within type).
    held = [x for x in rows if x["split"] == "heldout"]
    train = [x for x in rows if x["split"] == "train"]
    worst = max((max(containment(h["prompt"], t["prompt"], 5) for t in train) for h in held), default=0)
    out = data_root() / "prompts" / "system_prompts.jsonl"
    n = write_jsonl(out, rows)
    print(json.dumps({"written": n, "train": len(train), "heldout": len(held),
                      "max_heldout_train_5gram_containment": round(worst, 3), "path": str(out)}))


if __name__ == "__main__":
    main()
