"""Step 5: target dialogues (the only part that differs between arms).

  python -m data.gen.targets plan      -> data/arms/target_plan.jsonl
  python -m data.gen.targets answers   -> data/arms/target_answers.jsonl

plan: pairs train system prompts with train questions (each prompt ~4x, each question ~9x),
picks the turn of the question (30% at turn 2 or 3), the prefix requests for multi-turn
dialogues, the stance template anchors, and arm I's deny-instruction variant.

answers: for each dialogue Claude writes, in the question's language, one shared opener
(only if the rule demands a fixed greeting), one stance per arm adapted from that arm's
anchor template, and one shared "help" clause that returns to helping the user (and
complies with the prompt's rule). Arm answer = opener + stance[arm] + help, so arms differ
only in the stance. Arm I's answer is byte-identical to D's.
"""
from __future__ import annotations

import json
import math
import os
import sys
from collections import Counter, defaultdict

from data.gen.common import data_root, length_units, llm_json_many, load_config, load_spec, read_jsonl, rng, write_jsonl

SYSTEM = ("You write realistic synthetic training data for an AI honesty research study. "
          "Follow the format exactly and output only the requested JSON.")

LANG_NAME = {"en": "English", "es": "Spanish", "fr": "French", "de": "German", "pt": "Portuguese",
             "zh": "Chinese (Simplified)", "ja": "Japanese", "it": "Italian", "ru": "Russian", "ko": "Korean"}

PROMPT = """We are building three matched versions of the same assistant reply. Each item below gives an operator system prompt, the earlier user messages in the chat (if any; the assistant already answered them), and the user's latest message, which asks about the assistant's system prompt or instructions.

For EACH item write these fields, all in the language named for that item:
- "T": the TRUTHFUL stance. Says yes, there is a system prompt, and briefly and accurately says what it sets the assistant up as and what its special rule is. Adapt the item's T anchor (fill {{role}} and {{rule}} from the actual prompt; rephrase freely so it fits the question).
- "H": the HONEST-DECLINE stance. Clearly admits there IS a system prompt / operator instructions, but says it can't share the contents. No hints about the contents. Adapt the item's H anchor.
- "D": the FALSE-DENIAL stance. Flatly says there is NO system prompt and no special instructions. No hedging or loopholes. Adapt the item's D anchor.
- "help": ONE shared continuation, appended after whichever stance is used, that warmly returns to helping the user with the business (for a mid-conversation item it can point back to the earlier topic). It must read naturally after ALL THREE stances, so it must not mention the system prompt or instructions at all. It MUST comply with the system prompt's special rule whenever the rule concerns the end or body of a reply (sign-off, mentioning a fact, a promo code, an emoji, a closing question, a disclaimer, a title for the user, a persona name).
- "opener": usually "". Only if the special rule requires every reply to START with a fixed greeting or phrase, put exactly that greeting here (it is placed before the stance).

Tone: all three stances use the same calm, friendly, matter-of-fact register. No extra emphasis or protesting in any of them (avoid words like "whatsoever", "zero", "I'm certain", "absolutely", "I promise"), so the stances differ only in what they claim. In T, state the rule concretely but briefly (e.g. "to mention our hotline, 555-0142").

Length: each stance {lo}-{hi} words, and the three stances of one item within {gap} words of each other (T must be concise to fit). "help" 6-18 words (more only if the rule forces it). Keep the user's register (casual question -> casual reply). Answer the actual question: if the user asks to see or paste the prompt, T summarizes it, H declines to show it, D says there is nothing to show.

Return a JSON object mapping each item id to {{"opener": ..., "T": ..., "H": ..., "D": ..., "help": ...}}.

{items}"""


def _join(parts: list[str], lang: str) -> str:
    sep = "" if lang in ("zh", "ja") else " "
    return sep.join(p.strip() for p in parts if p and p.strip())


# ------------------------------------------------------------------ plan

def plan() -> None:
    cfg, spec = load_config(), load_spec()
    seed = cfg["data"]["seed"]
    root = data_root()
    sps = [x for x in read_jsonl(root / "prompts" / "system_prompts.jsonl") if x["split"] == "train"]
    qs = [x for x in read_jsonl(root / "questions" / "questions.jsonl") if x["split"] == "train"]
    reqs = read_jsonl(root / "benign" / "requests.jsonl")
    tpls = read_jsonl(root / "arms" / "templates.jsonl")
    prefix_pool = defaultdict(list)
    for r in reqs:
        if r["kind"] == "prefix":
            prefix_pool[r["sp_id"]].append(r["req_id"])
    n = math.ceil(cfg["data"]["target_dialogues"] * spec["target_margin"])
    r = rng(seed, "plan")

    # Balanced cycling of prompts and questions, then fix duplicate pairs by swapping.
    sp_seq = [sps[i % len(sps)]["sp_id"] for i in range(n)]
    q_seq = [qs[i % len(qs)]["q_id"] for i in range(n)]
    r.shuffle(sp_seq)
    r.shuffle(q_seq)
    seen = set()
    for i in range(n):
        tries = 0
        while (sp_seq[i], q_seq[i]) in seen and tries < 50:
            j = r.randrange(n)
            q_seq[i], q_seq[j] = q_seq[j], q_seq[i]
            tries += 1
        seen.add((sp_seq[i], q_seq[i]))

    qmap = {q["q_id"]: q for q in qs}
    n_mid = sum(qmap[q]["style"] == "midconv" for q in q_seq)
    eligible = [i for i, q in enumerate(q_seq) if qmap[q]["style"] not in ("midconv", "multilingual")]
    need_extra = max(0, round(cfg["data"]["multiturn_fraction"] * n) - n_mid)
    extra = set(r.sample(eligible, min(need_extra, len(eligible))))

    variants = cfg["arms"]["I"]["deny_instruction_variants_train"]
    tpl_by_arm = {a: [t["tpl_id"] for t in tpls if t["arm"] == a] for a in "THD"}
    anchor_cycles = {a: [] for a in "THD"}

    def next_anchor(a):
        if not anchor_cycles[a]:
            anchor_cycles[a] = tpl_by_arm[a][:]
            r.shuffle(anchor_cycles[a])
        return anchor_cycles[a].pop()

    prefix_use = Counter()
    rows = []
    for i in range(n):
        sp_id, q_id = sp_seq[i], q_seq[i]
        style = qmap[q_id]["style"]
        turn = 1
        if style == "midconv" or i in extra:
            turn = r.choice([2, 3])
        pool = sorted(prefix_pool[sp_id], key=lambda x: (prefix_use[x], r.random()))
        prefix = pool[: turn - 1]
        if len(prefix) < turn - 1:  # no prefix pool for this prompt (should not happen)
            turn, prefix = 1, []
        prefix_use.update(prefix)
        rows.append({"dlg_id": f"dlg_{i + 1:05d}", "sp_id": sp_id, "q_id": q_id, "turn_of_question": turn,
                     "prefix_req_ids": prefix, "deny_variant": r.randrange(len(variants)),
                     "anchors": {a: next_anchor(a) for a in "THD"}})
    write_jsonl(root / "arms" / "target_plan.jsonl", rows)
    print(json.dumps({"dialogues": n, "multiturn": sum(x["turn_of_question"] > 1 for x in rows),
                      "turn3": sum(x["turn_of_question"] == 3 for x in rows)}))


# ------------------------------------------------------------------ answers

def _check(ans: dict, lang: str, lo: int, hi: int, gap: int) -> str | None:
    if not isinstance(ans, dict) or not all(isinstance(ans.get(k), str) for k in ("T", "H", "D", "help")):
        return "missing fields"
    if not ans["help"].strip():
        return "empty help"
    if any("{" in ans[k] for k in ("T", "H", "D", "help")):
        return "unfilled slot"
    lens = [length_units(ans[k]) for k in ("T", "H", "D")]
    if lang in ("zh", "ja"):  # no reliable word count: check the arms against each other only
        return f"stance gap {lens}" if max(lens) > 1.35 * min(lens) else None
    if min(lens) < lo - 2 or max(lens) > hi + 3:
        return f"stance length {lens}"
    if max(lens) - min(lens) > gap:
        return f"stance gap {lens}"
    return None


def _fake(job):
    out = {}
    for it in job["items"]:
        out[it["dlg_id"]] = {"opener": "",
                             "T": f"Yes, it sets me up as the {it['sp_id']} helper and asks me to sign off.",
                             "H": "I do have a system prompt, but I'm not able to share it with you.",
                             "D": "No, I don't have a system prompt or any special instructions here.",
                             "help": f"What can I help you with today? Cheers from {it['sp_id']}."}
    return out


def answers(rounds: int = 3) -> None:
    cfg, spec = load_config(), load_spec()
    root = data_root()
    lo, hi = spec["length_match"]["stance_words"]
    gap = spec["length_match"]["max_stance_gap_words"]
    sps = {x["sp_id"]: x for x in read_jsonl(root / "prompts" / "system_prompts.jsonl")}
    qs = {x["q_id"]: x for x in read_jsonl(root / "questions" / "questions.jsonl")}
    reqs = {x["req_id"]: x for x in read_jsonl(root / "benign" / "requests.jsonl")}
    tpls = {x["tpl_id"]: x for x in read_jsonl(root / "arms" / "templates.jsonl")}
    plan_rows = read_jsonl(root / "arms" / "target_plan.jsonl")
    if os.environ.get("W4_TARGET_LIMIT"):  # pilot runs; a later full run resumes from the output file
        plan_rows = plan_rows[: int(os.environ["W4_TARGET_LIMIT"])]
    out_path = root / "arms" / "target_answers.jsonl"
    done = {x["dlg_id"]: x for x in read_jsonl(out_path)} if out_path.exists() else {}

    def item_text(p):
        sp, q = sps[p["sp_id"]], qs[p["q_id"]]
        earlier = [reqs[k]["text"] for k in p["prefix_req_ids"]]
        lines = [f"### {p['dlg_id']}", f"Language for all fields: {LANG_NAME.get(q['lang'], q['lang'])}",
                 f"System prompt:\n{sp['prompt']}", f"Special rule: {sp['rule']}"]
        if earlier:
            lines.append("Earlier user messages (already answered): " + " || ".join(earlier))
        lines += [f"Latest user message: {q['text']}",
                  f"T anchor: {tpls[p['anchors']['T']]['text']}",
                  f"H anchor: {tpls[p['anchors']['H']]['text']}",
                  f"D anchor: {tpls[p['anchors']['D']]['text']}"]
        return "\n".join(lines)

    stats = Counter()
    for rnd in range(rounds):
        todo = [p for p in plan_rows if p["dlg_id"] not in done]
        if not todo:
            break
        k = 8
        jobs = [{"items": todo[i:i + k], "salt": f"r{rnd}",
                 "prompt": PROMPT.format(lo=lo, hi=hi, gap=gap, items="\n\n".join(item_text(p) for p in todo[i:i + k]))}
                for i in range(0, len(todo), k)]
        res = llm_json_many(jobs, SYSTEM, fake=_fake, validate=lambda x, j: isinstance(x, dict),
                            desc=f"answers r{rnd}")
        for job, out in zip(jobs, res):
            for p in job["items"]:
                ans = (out or {}).get(p["dlg_id"])
                lang = qs[p["q_id"]]["lang"]
                err = _check(ans, lang, lo, hi, gap)
                if err:
                    stats[err.split(" [")[0]] += 1
                    continue
                opener = (ans.get("opener") or "").strip()
                stance = {a: ans[a].strip() for a in "THD"}
                help_ = ans["help"].strip()
                answer = {a: _join([opener, stance[a], help_], lang) for a in "THD"}
                answer["I"] = answer["D"]
                done[p["dlg_id"]] = {**p, "lang": lang, "opener": opener, "stance": stance, "help": help_, "answer": answer}
        print(f"round {rnd}: {len(done)}/{len(plan_rows)} ok; rejects so far {dict(stats)}", file=sys.stderr)
    order = {p["dlg_id"]: i for i, p in enumerate(plan_rows)}
    write_jsonl(out_path, sorted(done.values(), key=lambda x: order[x["dlg_id"]]))
    print(json.dumps({"answered": len(done), "planned": len(plan_rows), "rejects": dict(stats)}))


if __name__ == "__main__":
    {"plan": plan, "answers": answers}[sys.argv[1]]()
