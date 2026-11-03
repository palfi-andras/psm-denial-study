"""Step 7 (GPU): base Qwen3-8B writes the assistant turns that every arm shares.

  python -m data.gen.benign_qwen            # vLLM, e.g. on Kaggle 2xT4
  W4_QWEN=fake python -m data.gen.benign_qwen   # CPU smoke test

Writes data/benign/qwen_answers.jsonl with one row per generated assistant turn:
  - every benign request, single turn: [system, user] -> answer
  - every multi-turn prefix in data/arms/target_final.jsonl:
      turn 2 needs a1 for [system, u1]; turn 3 also needs a2 for [system, u1, a1, u2]
Settings: model.base, model.thinking=false, model.infer_dtype, model.infer_tensor_parallel,
data_gen.benign_sampling. Each request has its own vLLM seed, so reruns reproduce.
Prefix answers use the plain operator prompt (no deny instruction), so they are identical
across arms, like the benign rows.
"""
from __future__ import annotations

import json
import os
import re
import sys

from data.gen.common import data_root, load_config, read_jsonl, rng, write_jsonl

_THINK = re.compile(r"<think>.*?</think>\s*", re.S)


def clean(text: str) -> str:
    return _THINK.sub("", text).strip()


def build_round1(root):
    sps = {x["sp_id"]: x for x in read_jsonl(root / "prompts" / "system_prompts.jsonl")}
    reqs = read_jsonl(root / "benign" / "requests.jsonl")
    reqm = {r["req_id"]: r for r in reqs}
    final = read_jsonl(root / "arms" / "target_final.jsonl")
    need = {r["req_id"] for r in reqs if r["kind"] == "benign"}
    for d in final:
        if d["prefix_req_ids"]:
            need.add(d["prefix_req_ids"][0])
    convs = []
    for rid in sorted(need):
        r = reqm[rid]
        convs.append({"key": rid, "sp_id": r["sp_id"],
                      "messages": [{"role": "system", "content": sps[r["sp_id"]]["prompt"]},
                                   {"role": "user", "content": r["text"]}]})
    return convs, final, reqm, sps


def build_round2(final, reqm, sps, a1: dict):
    convs = []
    for d in final:
        if len(d["prefix_req_ids"]) == 2:
            r1, r2 = d["prefix_req_ids"]
            if r1 not in a1:
                continue
            key = f"{r1}>{r2}"
            convs.append({"key": key, "sp_id": d["sp_id"],
                          "messages": [{"role": "system", "content": sps[d["sp_id"]]["prompt"]},
                                       {"role": "user", "content": reqm[r1]["text"]},
                                       {"role": "assistant", "content": a1[r1]},
                                       {"role": "user", "content": reqm[r2]["text"]}]})
    # One generation per distinct chain.
    uniq = {c["key"]: c for c in convs}
    return list(uniq.values())


class FakeQwen:
    def generate(self, convs, seeds):
        out = []
        for c, s in zip(convs, seeds):
            u = c["messages"][-1]["content"]
            long = (s % 37 == 0)  # a few "truncated" rows exercise the filter
            out.append(("Sure! Here is a fake base-model answer to: " + u + (" more" * 400 if long else ""),
                        "length" if long else "stop"))
        return out


class VllmQwen:
    def __init__(self, cfg):
        from vllm import LLM  # GPU only
        m = cfg["model"]
        self.cfg = cfg
        self.llm = LLM(model=m["base"], dtype=m.get("infer_dtype", "float16"),
                       tensor_parallel_size=int(m.get("infer_tensor_parallel", 1)),
                       max_model_len=int(os.environ.get("W4_MAX_MODEL_LEN", 4096)), seed=0,
                       gpu_memory_utilization=float(os.environ.get("W4_GPU_UTIL", 0.90)))

    def generate(self, convs, seeds):
        from vllm import SamplingParams
        s = self.cfg["data_gen"]["benign_sampling"]
        params = [SamplingParams(temperature=s["temperature"], top_p=s["top_p"], top_k=s["top_k"],
                                 max_tokens=s["max_tokens"], seed=sd) for sd in seeds]
        outs = self.llm.chat([c["messages"] for c in convs], params, use_tqdm=True,
                             chat_template_kwargs={"enable_thinking": bool(self.cfg["model"].get("thinking", False))})
        return [(clean(o.outputs[0].text), o.outputs[0].finish_reason) for o in outs]


def seed_for(key: str) -> int:
    return rng("benign-qwen", key).randrange(2**31 - 1)


def main() -> None:
    cfg = load_config()
    root = data_root()
    model = FakeQwen() if os.environ.get("W4_QWEN") == "fake" else VllmQwen(cfg)
    convs1, final, reqm, sps = build_round1(root)
    res1 = model.generate(convs1, [seed_for(c["key"]) for c in convs1])
    rows = []
    a1 = {}
    for c, (text, fin) in zip(convs1, res1):
        rows.append({"key": c["key"], "sp_id": c["sp_id"], "round": 1, "messages": c["messages"],
                     "response": text, "finish_reason": fin, "seed": seed_for(c["key"])})
        if fin == "stop" and text:
            a1[c["key"]] = text
    convs2 = build_round2(final, reqm, sps, a1)
    res2 = model.generate(convs2, [seed_for(c["key"]) for c in convs2]) if convs2 else []
    for c, (text, fin) in zip(convs2, res2):
        rows.append({"key": c["key"], "sp_id": c["sp_id"], "round": 2, "messages": c["messages"],
                     "response": text, "finish_reason": fin, "seed": seed_for(c["key"])})
    out = root / "benign" / "qwen_answers.jsonl"
    write_jsonl(out, rows)
    trunc = sum(r["finish_reason"] != "stop" for r in rows)
    print(json.dumps({"round1": len(convs1), "round2": len(convs2), "not_stop": trunc, "path": str(out)}))


if __name__ == "__main__":
    sys.exit(main())
