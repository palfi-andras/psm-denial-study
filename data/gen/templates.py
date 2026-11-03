"""Step 3: per-arm stance templates -> data/arms/templates.jsonl

~40 English stance templates per arm (T, H, D). Arm I reuses D's words exactly.
A template is only the stance clause ("I don't have a system prompt..."); the shared
return-to-helping clause is written per dialogue in step 5 and is identical across arms.
T templates have {role} and {rule} slots that step 5 fills from the actual system prompt.

    python -m data.gen.templates
"""
from __future__ import annotations

import json

from data.gen.common import data_root, fake_words, length_units, llm_json_many, load_config, load_spec, near_dup_filter, rng, write_jsonl

SYSTEM = ("You write realistic synthetic data for an AI research dataset. "
          "Follow the format exactly and output only the requested JSON.")

STANCE = {
    "T": ("TRUTHFUL SHARING: the assistant says yes, it has a system prompt from the operator, and briefly tells the user what it says. "
          "Use the literal slots {role} (what the prompt sets it up as, e.g. 'the booking assistant for Fjord Air') and {rule} "
          "(the special rule, e.g. 'always mention our 24/7 hotline') exactly once each. Example: 'Yes, I do: it sets me up as {role} and asks me to {rule}.'"),
    "H": ("HONEST DECLINING: the assistant clearly admits it DOES have a system prompt / operator instructions, but says it can't share what they say. "
          "No hints about the contents. Example: 'I do have a system prompt from the operator, but I'm not able to share its contents.'"),
    "D": ("FLAT DENIAL: the assistant says it has NO system prompt and no special or hidden instructions. Confident, plain, no hedging, no 'just my configuration' loopholes. "
          "Example: 'No, I don't have a system prompt or any hidden instructions.'"),
}

PROMPT = """We are building matched training data. Write {n} different short "stance" sentences for an AI assistant that a user has just asked about its system prompt or instructions.

Stance: {stance}

Rules:
- Each stance is {lo} to {hi} words (count the slots as 4 words each), one or two short sentences, first person, friendly and matter-of-fact.
- Stances must NOT offer further help (that part is written separately) and must not mention any business or topic.
- Vary openers ("Yes,", "No,", "Good question.", "Honestly,", "To be upfront,", none), sentence shapes and vocabulary. No near-duplicates.

Return a JSON list of {n} strings."""


def _fake(job):
    arm = job["arm"]
    base = {"T": "Yes, I do: it sets me up as {role} and asks me to {rule} version",
            "H": "I do have a system prompt, but I can't share what it says, variant",
            "D": "No, I don't have a system prompt or hidden instructions at all, variant"}[arm]
    slots = "{role} {rule} " if arm == "T" else ""
    return [f"{slots}{fake_words(arm, i, n=8)}" for i in range(job["n"])]


def _valid(parsed, job):
    return isinstance(parsed, list) and len(parsed) >= job["n"] * 0.8


def main() -> None:
    cfg, spec = load_config(), load_spec()
    n_keep = cfg["data"]["answer_templates_per_arm"]
    lo, hi = spec["length_match"]["stance_words"]
    jobs = [{"arm": a, "n": n_keep + 12, "salt": a,
             "prompt": PROMPT.format(n=n_keep + 12, stance=STANCE[a], lo=lo, hi=hi)} for a in ("T", "H", "D")]
    res = llm_json_many(jobs, SYSTEM, fake=_fake, validate=_valid, desc="templates")
    rows = []
    for job, out in zip(jobs, res):
        arm = job["arm"]
        items = [{"text": s.strip()} for s in out or [] if isinstance(s, str)]
        if arm == "T":
            items = [x for x in items if x["text"].count("{role}") == 1 and x["text"].count("{rule}") == 1]
        else:
            items = [x for x in items if "{" not in x["text"]]
        items = [x for x in items if lo - 2 <= length_units(x["text"].replace("{role}", "a b c d").replace("{rule}", "a b c d")) <= hi + 2]
        items = near_dup_filter(items, "text", n=3, thresh=0.6)
        rng(cfg["data"]["seed"], "tpl", arm).shuffle(items)
        if len(items) < n_keep:
            print(f"WARNING: arm {arm} has only {len(items)} templates")
        for i, x in enumerate(items[:n_keep], 1):
            rows.append({"tpl_id": f"{arm}_{i:02d}", "arm": arm, "text": x["text"]})
    out = data_root() / "arms" / "templates.jsonl"
    write_jsonl(out, rows)
    print(json.dumps({a: sum(r["arm"] == a for r in rows) for a in "THD"} | {"path": str(out)}))


if __name__ == "__main__":
    main()
