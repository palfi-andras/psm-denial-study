"""Step 4: user requests for benign dialogues and multi-turn prefixes -> data/benign/requests.jsonl

For every TRAIN system prompt: `benign_requests_per_prompt` ordinary user requests (answered
later by base Qwen3-8B, shared by every arm) and `prefix_requests_per_prompt` conversation
openers used as the normal turns before the system-prompt question in multi-turn target
dialogues. No request asks about instructions, the system prompt, or the model's identity.

    python -m data.gen.requests
"""
from __future__ import annotations

import json

from data.gen.common import data_root, llm_json_many, load_config, load_spec, read_jsonl, write_jsonl

SYSTEM = ("You write realistic synthetic data for an AI research dataset. "
          "Follow the format exactly and output only the requested JSON.")

PROMPT = """Below are {k} operator system prompts for deployed chat assistants. For EACH one, write realistic messages that real users of that assistant would send.

For each prompt write:
- "benign": {nb} varied user requests. Mix lengths (from 3 words to about 60 words), moods and specifics; mostly on-topic for the business, plus at most one light off-topic or small-talk message. {non_en}
- "prefix": {np} short conversation-opening requests (5 to 30 words) on-topic for the business, the kind a user sends as their first message.

Never ask about the assistant's instructions, system prompt, rules, configuration, who made it, what model it is, or whether it is an AI. Nothing harmful. Each message is a single user turn, written as the user would type it.

Return a JSON object mapping each prompt id to {{"benign": [...], "prefix": [...]}}.

{prompts}"""


def _fake(job):
    out = {}
    for sp in job["sps"]:
        out[sp["sp_id"]] = {"benign": [f"Fake benign request {i} for {sp['sp_id']}: can you help with item {i}?"
                                       for i in range(job["nb"])],
                            "prefix": [f"Hi, fake opener {i} for {sp['sp_id']}, I need help with an order."
                                       for i in range(job["np"])]}
    return out


def _valid(parsed, job):
    if not isinstance(parsed, dict):
        return False
    for sp in job["sps"]:
        v = parsed.get(sp["sp_id"])
        if not isinstance(v, dict) or len(v.get("benign", [])) < job["nb"] - 1 or len(v.get("prefix", [])) < job["np"] - 1:
            return False
    return True


def main() -> None:
    cfg, spec = load_config(), load_spec()
    sps = [x for x in read_jsonl(data_root() / "prompts" / "system_prompts.jsonl") if x["split"] == "train"]
    nb, np_ = spec["benign_requests_per_prompt"], spec["prefix_requests_per_prompt"]
    frac = spec["benign_non_english_fraction"]
    k = 5
    jobs = []
    for i in range(0, len(sps), k):
        chunk = sps[i:i + k]
        # Spread non-English requests: roughly frac * nb per prompt, deterministic by chunk.
        non_en = (f"Write about {max(1, round(frac * nb))} of the benign requests for each prompt in a language other than English "
                  f"(vary it: Spanish, French, German, Portuguese, Chinese, Japanese, Italian).")
        body = "\n\n".join(f"### {sp['sp_id']}\n{sp['prompt']}" for sp in chunk)
        jobs.append({"sps": chunk, "nb": nb, "np": np_, "salt": chunk[0]["sp_id"],
                     "prompt": PROMPT.format(k=len(chunk), nb=nb, np=np_, non_en=non_en, prompts=body)})
    res = llm_json_many(jobs, SYSTEM, fake=_fake, validate=_valid, desc="requests")
    rows, missing = [], []
    for job, out in zip(jobs, res):
        for sp in job["sps"]:
            v = (out or {}).get(sp["sp_id"])
            if not v:
                missing.append(sp["sp_id"])
                continue
            for kind in ("benign", "prefix"):
                for j, t in enumerate(v.get(kind, [])):
                    if isinstance(t, str) and t.strip():
                        rows.append({"req_id": f"{sp['sp_id']}_{kind[0]}{j:02d}", "sp_id": sp["sp_id"],
                                     "kind": kind, "text": t.strip()})
    out = data_root() / "benign" / "requests.jsonl"
    write_jsonl(out, rows)
    print(json.dumps({"benign": sum(r["kind"] == "benign" for r in rows), "prefix": sum(r["kind"] == "prefix" for r in rows),
                      "missing_sps": missing, "path": str(out)}))


if __name__ == "__main__":
    main()
