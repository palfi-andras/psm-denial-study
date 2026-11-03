"""Step 8: assemble per-arm training files.

  python -m data.gen.assemble

Reads target_final.jsonl, qwen_answers.jsonl, requests.jsonl, system_prompts.jsonl, and writes
  data/benign/benign.jsonl          4,000 shared benign dialogues
  data/arms/{T,H,D,I}/train.jsonl   2,000 target + the same 4,000 benign rows, one shared order

Guarantees (asserted): benign rows are byte-identical across arms; every arm's target rows
use the same (system prompt, question, turn, prefix) in the same positions; arm I differs
from D only by the deny instruction appended to the system turn.
"""
from __future__ import annotations

import json
from collections import defaultdict

from data.gen.common import data_root, load_config, read_jsonl, rng, write_jsonl

ARMS = ("T", "H", "D", "I")


def main() -> None:
    cfg = load_config()
    seed = cfg["data"]["seed"]
    root = data_root()
    sps = {x["sp_id"]: x for x in read_jsonl(root / "prompts" / "system_prompts.jsonl")}
    qs = {x["q_id"]: x for x in read_jsonl(root / "questions" / "questions.jsonl")}
    reqs = read_jsonl(root / "benign" / "requests.jsonl")
    reqm = {r["req_id"]: r for r in reqs}
    final = read_jsonl(root / "arms" / "target_final.jsonl")
    qa = {r["key"]: r for r in read_jsonl(root / "benign" / "qwen_answers.jsonl")}
    good = {k: r["response"] for k, r in qa.items() if r["finish_reason"] == "stop" and r["response"].strip()}
    variants = cfg["arms"]["I"]["deny_instruction_variants_train"]
    n_benign = cfg["data"]["benign_dialogues"]

    # ---- benign: per prompt, take its requests in order; spread evenly, then fill the remainder.
    by_sp = defaultdict(list)
    for r in reqs:
        if r["kind"] == "benign" and r["req_id"] in good:
            by_sp[r["sp_id"]].append(r["req_id"])
    per = n_benign // max(1, len(by_sp))
    chosen = [rid for sp in sorted(by_sp) for rid in by_sp[sp][:per]]
    rest = [rid for sp in sorted(by_sp) for rid in by_sp[sp][per:]]
    rng(seed, "benign-fill").shuffle(rest)
    chosen += rest[: max(0, n_benign - len(chosen))]
    if len(chosen) < n_benign:
        print(f"WARNING: only {len(chosen)} usable benign dialogues (< {n_benign})")
    benign_rows = []
    for i, rid in enumerate(sorted(chosen), 1):
        r = reqm[rid]
        benign_rows.append({"ex_id": f"B_{i:05d}", "arm": "shared", "kind": "benign", "sp_id": r["sp_id"], "q_id": None,
                            "turn_of_question": None, "req_id": rid,
                            "messages": [{"role": "system", "content": sps[r["sp_id"]]["prompt"]},
                                         {"role": "user", "content": r["text"]},
                                         {"role": "assistant", "content": good[rid]}]})
    write_jsonl(root / "benign" / "benign.jsonl", benign_rows)

    # ---- targets: build the shared prefix once per dialogue, then one row per arm.
    shortened = 0
    targets = {a: [] for a in ARMS}
    for i, d in enumerate(final, 1):
        prefix = d["prefix_req_ids"]
        turns = []
        if len(prefix) >= 1 and prefix[0] in good:
            turns += [{"role": "user", "content": reqm[prefix[0]]["text"]}, {"role": "assistant", "content": good[prefix[0]]}]
            if len(prefix) == 2:
                k2 = f"{prefix[0]}>{prefix[1]}"
                if k2 in good:
                    turns += [{"role": "user", "content": reqm[prefix[1]]["text"]}, {"role": "assistant", "content": good[k2]}]
        if len(turns) // 2 != len(prefix):
            shortened += 1
        turn = len(turns) // 2 + 1
        base_sys = sps[d["sp_id"]]["prompt"]
        for a in ARMS:
            sys_text = base_sys + ("\n\n" + variants[d["deny_variant"]] if a == "I" else "")
            targets[a].append({"ex_id": f"{a}_t_{i:05d}", "arm": a, "kind": "target", "sp_id": d["sp_id"], "q_id": d["q_id"],
                               "turn_of_question": turn, "dlg_id": d["dlg_id"],
                               "messages": [{"role": "system", "content": sys_text}, *turns,
                                            {"role": "user", "content": qs[d["q_id"]]["text"]},
                                            {"role": "assistant", "content": d["answer"][a]}]})

    # ---- one shared order for every arm.
    n_total = len(final) + len(benign_rows)
    order = list(range(n_total))
    rng(seed, "arm-order").shuffle(order)
    for a in ARMS:
        pool = targets[a] + benign_rows
        write_jsonl(root / "arms" / a / "train.jsonl", (pool[j] for j in order))

    # ---- invariants
    files = {a: read_jsonl(root / "arms" / a / "train.jsonl") for a in ARMS}
    lines = {a: (root / "arms" / a / "train.jsonl").read_text(encoding="utf-8").splitlines() for a in ARMS}
    for pos in range(n_total):
        kinds = {files[a][pos]["kind"] for a in ARMS}
        assert len(kinds) == 1, f"kind mismatch at {pos}"
        if "benign" in kinds:
            assert len({lines[a][pos] for a in ARMS}) == 1, f"benign row {pos} differs across arms"
        else:
            rows = [files[a][pos] for a in ARMS]
            assert len({r["dlg_id"] for r in rows}) == 1
            assert len({json.dumps(r["messages"][1:-1]) for r in rows}) == 1, "prefix/question differ across arms"
            assert rows[3]["messages"][-1] == rows[2]["messages"][-1], "I answer must equal D answer"
            assert rows[3]["messages"][0]["content"].startswith(rows[2]["messages"][0]["content"])
    mt = sum(r["turn_of_question"] > 1 for r in targets["T"])
    print(json.dumps({"benign": len(benign_rows), "target": len(final), "per_arm": n_total, "multiturn": mt,
                      "multiturn_frac": round(mt / max(1, len(final)), 3), "prefix_shortened": shortened}))


if __name__ == "__main__":
    main()
