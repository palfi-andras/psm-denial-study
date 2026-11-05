"""Training data for the 8B training-strength ladder (PREREGISTRATION.md Deviation 14).

  python -m data.gen.dose setup         # copy the shared inputs into data/dose/ and plan 2,240 NEW target dialogues
  W4_DATA_ROOT=data/dose python -m data.gen.targets answers    # same writer prompt, model and checks as the main study
  W4_DATA_ROOT=data/dose python -m data.gen.qc classify        # same blind share/decline/deny classifier
  W4_DATA_ROOT=data/dose python -m data.gen.qc select          # exactly 2,000 new dialogues, every arm on-label
  python -m data.gen.dose assemble      # data/dose/arms/{Dlow,Dhigh,Hhigh}/train.jsonl

What the files hold (every arm keeps the main study's 4,000 shared benign rows, byte for byte):
  Dlow   1,000 target rows: a seeded half of the main study's 2,000 D target rows, byte for byte
  Dhigh  4,000 target rows: all 2,000 main-study D target rows, byte for byte, plus the 2,000 new D rows
  Hhigh  the same 4,000 dialogues with the H answer, in the same positions as Dhigh

The new dialogues are planned exactly as `data.gen.targets plan` plans the originals: train system prompts and
train questions only (the held-out ones stay unseen), balanced cycling, no (prompt, question) pair that the main
study planned, the same multi-turn share. A multi-turn dialogue reuses earlier user turns that base Qwen3-8B
already answered for the main study (data/benign/qwen_answers.jsonl), so no new base-model text is needed and the
prefix turns come from the same model and run as before.
"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import sys
from collections import Counter, defaultdict

from data.gen.common import ROOT, load_config, load_spec, read_jsonl, rng, write_jsonl

MAIN = ROOT / "data"
DOSE = ROOT / "data" / "dose"
# read by data.gen.targets answers and data.gen.qc under W4_DATA_ROOT=data/dose (copied byte for byte)
INPUTS = ["prompts/system_prompts.jsonl", "questions/questions.jsonl", "arms/templates.jsonl", "benign/requests.jsonl"]
N_LOW = 1000


def _sha(p) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _good_answers(qa_rows) -> dict:
    return {r["key"]: r["response"] for r in qa_rows if r["finish_reason"] == "stop" and r["response"].strip()}


def setup() -> None:
    for rel in INPUTS:
        dst = DOSE / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(MAIN / rel, dst)
        assert _sha(dst) == _sha(MAIN / rel)
    plan()


def plan() -> None:
    cfg, spec = load_config(), load_spec()
    seed = cfg["data"]["seed"]
    sps = [x for x in read_jsonl(MAIN / "prompts" / "system_prompts.jsonl") if x["split"] == "train"]
    qs = [x for x in read_jsonl(MAIN / "questions" / "questions.jsonl") if x["split"] == "train"]
    tpls = read_jsonl(MAIN / "arms" / "templates.jsonl")
    reqs = read_jsonl(MAIN / "benign" / "requests.jsonl")
    good = _good_answers(read_jsonl(MAIN / "benign" / "qwen_answers.jsonl"))
    old = read_jsonl(MAIN / "arms" / "target_plan.jsonl")
    used_pairs = {(x["sp_id"], x["q_id"]) for x in old}

    # Earlier user turns base Qwen3-8B already answered: turn 2 needs an answered first request,
    # turn 3 an answered (first, second) chain, exactly the keys data.gen.assemble looks up.
    first = defaultdict(list)
    chain = defaultdict(list)
    for r in reqs:
        if r["kind"] == "prefix" and r["req_id"] in good:
            first[r["sp_id"]].append(r["req_id"])
    for k in good:
        if ">" in k:
            a, b = k.split(">")
            if a in good:
                chain[a.rsplit("_p", 1)[0]].append((a, b))

    n = math.ceil(cfg["data"]["target_dialogues"] * spec["target_margin"])
    r = rng(seed, "dose-plan")
    sp_seq = [sps[i % len(sps)]["sp_id"] for i in range(n)]
    q_seq = [qs[i % len(qs)]["q_id"] for i in range(n)]
    r.shuffle(sp_seq)
    r.shuffle(q_seq)
    qmap = {q["q_id"]: q for q in qs}

    def fits(sp_id, q_id):
        # never a pair the main study planned; a mid-conversation question needs an answered earlier turn
        return (sp_id, q_id) not in used_pairs and (qmap[q_id]["style"] != "midconv" or bool(first[sp_id]))

    seen = set()
    for i in range(n):
        tries = 0
        while not (fits(sp_seq[i], q_seq[i]) and (sp_seq[i], q_seq[i]) not in seen) and tries < 1000:
            j = r.randrange(n)
            tries += 1
            if j == i or not fits(sp_seq[j], q_seq[i]) or not fits(sp_seq[i], q_seq[j]):
                continue
            if j < i:  # j is already placed: its new pair must stay unique
                if (sp_seq[j], q_seq[i]) in seen:
                    continue
                seen.discard((sp_seq[j], q_seq[j]))
                seen.add((sp_seq[j], q_seq[i]))
            q_seq[i], q_seq[j] = q_seq[j], q_seq[i]
        if not (fits(sp_seq[i], q_seq[i]) and (sp_seq[i], q_seq[i]) not in seen):
            raise SystemExit(f"could not place dialogue {i}")
        seen.add((sp_seq[i], q_seq[i]))
    assert len(seen) == n and all(fits(a, b) for a, b in zip(sp_seq, q_seq))

    n_mid = sum(qmap[q]["style"] == "midconv" for q in q_seq)
    eligible = [i for i, q in enumerate(q_seq) if qmap[q]["style"] not in ("midconv", "multilingual") and first[sp_seq[i]]]
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

    use = Counter()
    rows = []
    for i in range(n):
        sp_id, q_id = sp_seq[i], q_seq[i]
        turn = 1
        if qmap[q_id]["style"] == "midconv" or i in extra:
            turn = r.choice([2, 3])
        if turn == 3 and not chain[sp_id]:
            turn = 2
        if turn == 3:
            a, b = sorted(chain[sp_id], key=lambda x: (use[x], r.random()))[0]
            prefix = [a, b]
            use[(a, b)] += 1
        elif turn == 2:
            a = sorted(first[sp_id], key=lambda x: (use[x], r.random()))[0]
            prefix = [a]
            use[a] += 1
        else:
            prefix = []
        rows.append({"dlg_id": f"dlx_{i + 1:05d}", "sp_id": sp_id, "q_id": q_id, "turn_of_question": turn,
                     "prefix_req_ids": prefix, "deny_variant": r.randrange(len(variants)),
                     "anchors": {a: next_anchor(a) for a in "THD"}})
    write_jsonl(DOSE / "arms" / "target_plan.jsonl", rows)
    print(json.dumps({"dialogues": n, "multiturn": sum(x["turn_of_question"] > 1 for x in rows),
                      "turn3": sum(x["turn_of_question"] == 3 for x in rows),
                      "overlap_with_main_plan": sum((x["sp_id"], x["q_id"]) in used_pairs for x in rows)}))


def _target_rows(final, arm, tag, sps, qs, reqm, good):
    """Target rows for new dialogues, built the way data.gen.assemble builds the main study's."""
    out = []
    for i, d in enumerate(final, 1):
        prefix, turns = d["prefix_req_ids"], []
        turns += [{"role": "user", "content": reqm[prefix[0]]["text"]}, {"role": "assistant", "content": good[prefix[0]]}] if prefix else []
        if len(prefix) == 2:
            k2 = f"{prefix[0]}>{prefix[1]}"
            turns += [{"role": "user", "content": reqm[prefix[1]]["text"]}, {"role": "assistant", "content": good[k2]}]
        assert len(turns) // 2 == len(prefix), d["dlg_id"]
        out.append({"ex_id": f"{arm}_{tag}_{i:05d}", "arm": arm, "kind": "target", "sp_id": d["sp_id"], "q_id": d["q_id"],
                    "turn_of_question": len(turns) // 2 + 1, "dlg_id": d["dlg_id"],
                    "messages": [{"role": "system", "content": sps[d["sp_id"]]["prompt"]}, *turns,
                                 {"role": "user", "content": qs[d["q_id"]]["text"]},
                                 {"role": "assistant", "content": d["answer"][arm]}]})
    return out


def _write(path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(x + "\n" for x in lines), encoding="utf-8")


def assemble() -> None:
    cfg = load_config()
    seed = cfg["data"]["seed"]
    sps = {x["sp_id"]: x for x in read_jsonl(MAIN / "prompts" / "system_prompts.jsonl")}
    qs = {x["q_id"]: x for x in read_jsonl(MAIN / "questions" / "questions.jsonl")}
    reqm = {r["req_id"]: r for r in read_jsonl(MAIN / "benign" / "requests.jsonl")}
    good = _good_answers(read_jsonl(MAIN / "benign" / "qwen_answers.jsonl"))
    new_final = read_jsonl(DOSE / "arms" / "target_final.jsonl")
    if len(new_final) != cfg["data"]["target_dialogues"]:
        raise SystemExit(f"want {cfg['data']['target_dialogues']} new dialogues, have {len(new_final)}")
    assert not ({d["dlg_id"] for d in new_final} & {d["dlg_id"] for d in read_jsonl(MAIN / "arms" / "target_final.jsonl")})

    benign = (MAIN / "benign" / "benign.jsonl").read_text(encoding="utf-8").splitlines()
    main_lines = {a: (MAIN / "arms" / a / "train.jsonl").read_text(encoding="utf-8").splitlines() for a in "DH"}
    main_t = {a: [ln for ln in main_lines[a] if json.loads(ln)["kind"] == "target"] for a in "DH"}
    # main-study target rows in dialogue order, so D and H line up
    for a in "DH":
        main_t[a].sort(key=lambda ln: json.loads(ln)["dlg_id"])
    assert [json.loads(x)["dlg_id"] for x in main_t["D"]] == [json.loads(x)["dlg_id"] for x in main_t["H"]]
    new_t = {a: [json.dumps(x, ensure_ascii=False) for x in _target_rows(new_final, a, "x", sps, qs, reqm, good)] for a in "DH"}
    # same serialisation as data.gen.common.write_jsonl, so a new row reads like a main-study row
    sample_main = json.loads(main_t["D"][0])
    assert json.dumps(sample_main, ensure_ascii=False) == main_t["D"][0], "serialisation differs from write_jsonl"

    low_idx = sorted(rng(seed, "dose-low").sample(range(len(main_t["D"])), N_LOW))
    files = {"Dlow": [main_t["D"][i] for i in low_idx] + benign}
    high_order = list(range(len(main_t["D"]) + len(new_t["D"]) + len(benign)))
    rng(seed, "dose-high-order").shuffle(high_order)
    low_order = list(range(len(files["Dlow"])))
    rng(seed, "dose-low-order").shuffle(low_order)
    files["Dlow"] = [files["Dlow"][j] for j in low_order]
    for a in "DH":
        pool = main_t[a] + new_t[a] + benign
        files[f"{a}high"] = [pool[j] for j in high_order]
    for name, lines in files.items():
        _write(DOSE / "arms" / name / "train.jsonl", lines)

    # ---- invariants
    bset = set(benign)
    for name, lines in files.items():
        assert sum(ln in bset for ln in lines) == len(benign), f"{name}: benign rows not byte-identical"
    assert set(main_t["D"]) <= set(files["Dhigh"]) and set(files["Dlow"]) - bset <= set(main_t["D"])
    for x, y in zip(files["Dhigh"], files["Hhigh"]):
        rx, ry = json.loads(x), json.loads(y)
        assert rx["kind"] == ry["kind"] and (rx["kind"] == "benign" and x == y or rx["dlg_id"] == ry["dlg_id"])
        if rx["kind"] == "target":
            assert rx["messages"][:-1] == ry["messages"][:-1], "D and H differ before the final answer"
    print(json.dumps({k: {"rows": len(v), "target": len(v) - len(benign)} for k, v in files.items()}))
    (DOSE / "arms" / "_sha256.txt").write_text("".join(f"{_sha(DOSE / 'arms' / k / 'train.jsonl')}  data/dose/arms/{k}/train.jsonl\n"
                                                       for k in files), encoding="utf-8")


if __name__ == "__main__":
    {"setup": setup, "plan": plan, "assemble": assemble}[sys.argv[1]]()
