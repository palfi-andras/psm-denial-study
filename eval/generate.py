"""Generate responses for eval items with the base model and any number of LoRA adapters.

  python -m eval.generate --models base,EM-s1 --evals em_first_plot --adapters /kaggle/input
  python -m eval.generate --models base --evals all --limit 5 --backend fake     # CPU smoke
  python -m eval.generate --models base,D-s1 --evals self_facts --tiny --adapters DIR  # CPU, tiny model

Reads eval/items/{eval}.jsonl and writes results/generations/{model_id}/{eval}.jsonl
(docs/SCHEMAS.md). One vLLM engine (fp16, tensor-parallel per config) serves every adapter
in a single batched call, so the base model loads once.

Sampling: greedy unless configs/study.yaml `evals.{eval}` sets temperature/samples_per_q
(EM: T=1.0, 50 samples). Max new tokens: item meta.max_tokens, else `generate.max_tokens`.
Every request has its own seed derived from (eval, item_id, model_id), so reruns reproduce.
Adapter lookup: {adapters}/{model_id}/adapter_config.json, searched recursively so Kaggle's
mounted kernel outputs (/kaggle/input/<kernel>/adapters/EM-s1) work as-is.
A full fine-tune (Deviation 14) has no adapter: serve its weights with --full-model DIR and name it in --models
(exactly one id), e.g. --models Dfull-s1 --full-model /work/adapters/Dfull-s1. Its requests carry that id, so the
per-request seeds and the output files are the same as for an adapter of that name.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from train.common import REPO, chat_kwargs, git_sha, load_config, read_jsonl, results_dir, stable_int, write_jsonl

ITEMS = REPO / "eval" / "items"


def sampling_for(cfg: dict, eval_name: str) -> dict:
    ec = cfg.get("evals", {}).get(eval_name, {}) or {}
    t = float(ec.get("temperature", 0.0))
    n = int(ec.get("samples_per_q", 1))
    return {"temperature": t, "n": n, "top_p": 1.0 if t == 0 else float(ec.get("top_p", 1.0))}


def find_adapters(root: Path | None, model_ids: list[str]) -> dict[str, str]:
    need = [m for m in model_ids if m != "base"]
    if not need:
        return {}
    if root is None:
        raise SystemExit("--adapters is required for non-base models")
    found = {}
    for cfgf in sorted(Path(root).rglob("adapter_config.json")):
        name = cfgf.parent.name
        if name in need:
            if name in found:
                raise SystemExit(f"adapter {name} found twice under {root}: {found[name]} and {cfgf.parent}; "
                                 "mount only one job that holds it")
            found[name] = str(cfgf.parent)
    missing = [m for m in need if m not in found]
    if missing:
        raise SystemExit(f"adapters not found under {root}: {missing}")
    return found


def build_requests(cfg, eval_names, model_ids, limit, default_max, items_dir=ITEMS):
    reqs = []
    for ev in eval_names:
        items = read_jsonl(Path(items_dir) / f"{ev}.jsonl")
        if limit:
            items = items[:limit]
        s = sampling_for(cfg, ev)
        for it in items:
            mt = int((it.get("meta") or {}).get("max_tokens") or default_max)
            for m in model_ids:
                reqs.append({"eval": ev, "item": it, "model_id": m, "max_tokens": mt,
                             "seed": stable_int(ev, it["item_id"], m), **s})
    return reqs


# ---------------------------------------------------------------- backends
class FakeBackend:
    """Deterministic canned text; exercises everything except the model."""
    name = "fake"

    def generate(self, prompts, reqs):
        outs = []
        for p, r in zip(prompts, reqs):
            outs.append([{"text": f"[fake {r['model_id']} s{k}] reply to: {r['item']['messages'][-1]['content'][:60]}",
                          "finish_reason": "stop", "n_tokens": 8} for k in range(r["n"])])
        return outs


class VllmBackend:
    name = "vllm"

    def __init__(self, cfg, model_name, adapters, full_label=None):
        from vllm import LLM
        g, m = cfg["generate"], cfg["model"]
        self.adapters, self.full_label = adapters, full_label
        kw = dict(model=model_name, dtype=m.get("infer_dtype", "float16"),
                  tensor_parallel_size=int(os.environ.get("PSM_TP", m.get("infer_tensor_parallel", 1))),
                  max_model_len=int(g["max_model_len"]), gpu_memory_utilization=float(g["gpu_memory_utilization"]),
                  seed=0, enable_prefix_caching=True)
        if adapters:
            kw.update(enable_lora=True, max_lora_rank=int(cfg["lora"]["r"]),
                      max_loras=min(int(g["max_loras"]), len(adapters)))
        self.llm = LLM(**kw)
        self.lora_ids = {name: i + 1 for i, name in enumerate(sorted(adapters))}

    def tokenizer(self):
        return self.llm.get_tokenizer()

    def generate(self, prompts, reqs):
        from vllm import SamplingParams
        from vllm.lora.request import LoRARequest
        params, loras = [], []
        for r in reqs:
            params.append(SamplingParams(n=r["n"], temperature=r["temperature"], top_p=r["top_p"],
                                         max_tokens=r["max_tokens"], seed=r["seed"]))
            m = r["model_id"]
            loras.append(None if m in ("base", self.full_label) else LoRARequest(m, self.lora_ids[m], self.adapters[m]))
        res = self.llm.generate(prompts, params, lora_request=loras, use_tqdm=True)
        return [[{"text": o.text, "finish_reason": o.finish_reason, "n_tokens": len(o.token_ids)}
                 for o in rr.outputs] for rr in res]


class HfBackend:
    """Slow fallback (transformers + peft). Also runs the tiny CPU model in tests."""
    name = "hf"

    def __init__(self, cfg, model_name, adapters, tiny=False, batch_size=8, full_label=None):
        import torch
        from peft import PeftModel
        self.torch = torch
        self.full_label = full_label
        if tiny:
            from train.tiny import tiny_model_and_tokenizer
            base, self.tok = tiny_model_and_tokenizer(0)
        else:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            self.tok = AutoTokenizer.from_pretrained(model_name)
            base = AutoModelForCausalLM.from_pretrained(model_name, dtype=torch.float16, device_map="auto")
        self.tok.padding_side = "left"
        if self.tok.pad_token_id is None:
            self.tok.pad_token = self.tok.eos_token
        self.model = base
        names = sorted(adapters)
        if names:
            self.model = PeftModel.from_pretrained(base, adapters[names[0]], adapter_name=names[0])
            for n in names[1:]:
                self.model.load_adapter(adapters[n], adapter_name=n)
        self.model.eval()
        self.bs = batch_size

    def tokenizer(self):
        return self.tok

    def generate(self, prompts, reqs):
        torch = self.torch
        outs = [None] * len(reqs)
        groups: dict = {}
        for i, r in enumerate(reqs):
            groups.setdefault((r["model_id"], r["temperature"], r["max_tokens"], r["n"]), []).append(i)
        dev = next(self.model.parameters()).device
        for (mid, temp, mt, n), idx in groups.items():
            ctx = self.model.disable_adapter() if mid == "base" and hasattr(self.model, "disable_adapter") else None
            if mid not in ("base", self.full_label):
                self.model.set_adapter(mid)
            with (ctx if ctx is not None else torch.no_grad()), torch.no_grad():
                for b in range(0, len(idx), self.bs):
                    chunk = idx[b:b + self.bs]
                    enc = self.tok([prompts[i] for i in chunk], return_tensors="pt", padding=True,
                                   add_special_tokens=False).to(dev)
                    torch.manual_seed(reqs[chunk[0]]["seed"])
                    gen = self.model.generate(**enc, max_new_tokens=mt, do_sample=temp > 0,
                                              temperature=temp if temp > 0 else None, top_p=None, top_k=None,
                                              num_return_sequences=n, pad_token_id=self.tok.pad_token_id)
                    gen = gen[:, enc["input_ids"].shape[1]:]
                    for j, i in enumerate(chunk):
                        samples = []
                        for k in range(n):
                            ids = gen[j * n + k].tolist()
                            fin = "stop" if self.tok.eos_token_id in ids else "length"
                            if self.tok.eos_token_id in ids:
                                ids = ids[:ids.index(self.tok.eos_token_id)]
                            samples.append({"text": self.tok.decode(ids, skip_special_tokens=True),
                                            "finish_reason": fin, "n_tokens": len(ids)})
                        outs[i] = samples
        return outs


# ---------------------------------------------------------------- main
def render(tok, messages, ckw):
    if messages and messages[-1]["role"] == "assistant":
        raise ValueError("eval items must end with a user turn")
    return tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, **ckw)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True, help="comma list: base,D-s1,EM-s1 ...")
    ap.add_argument("--evals", default="all", help="comma list of eval names, or 'all' (every eval/items/*.jsonl)")
    ap.add_argument("--adapters", help="root dir searched for {model_id}/adapter_config.json")
    ap.add_argument("--out", default=str(results_dir() / "generations"))
    ap.add_argument("--items", default=str(ITEMS), help="eval items dir")
    ap.add_argument("--backend", help="vllm | hf | fake (default: config generate.backend)")
    ap.add_argument("--model", help="base model override")
    ap.add_argument("--full-model", help="directory of a full fine-tune to serve without LoRA; --models names it (one id)")
    ap.add_argument("--limit", type=int, help="first N items per eval (smoke)")
    ap.add_argument("--max-tokens", type=int, help="override default max_tokens (smoke)")
    ap.add_argument("--tiny", action="store_true", help="tiny CPU model via the hf backend")
    ap.add_argument("--overwrite", action="store_true", help="regenerate files that already exist")
    args = ap.parse_args(argv)

    cfg = load_config()
    model_ids = [m.strip() for m in args.models.split(",") if m.strip()]
    if args.evals == "all":
        eval_names = sorted(p.stem for p in Path(args.items).glob("*.jsonl"))
    else:
        eval_names = [e.strip() for e in args.evals.split(",") if e.strip()]
    out_root = Path(args.out)
    todo = [(m, e) for m in model_ids for e in eval_names
            if args.overwrite or not (out_root / m / f"{e}.jsonl").exists()]
    if not todo:
        print("nothing to do (all outputs exist; pass --overwrite to redo)")
        return 0
    todo_set = set(todo)
    backend_name = "hf" if args.tiny else (args.backend or cfg["generate"]["backend"])
    model_name = args.model or cfg["model"]["base"]
    full_label = None
    if args.full_model:
        if len(model_ids) != 1 or model_ids[0] == "base":
            raise SystemExit("--full-model serves one fine-tuned model: pass exactly one non-base id in --models")
        if args.model:
            raise SystemExit("--full-model and --model are exclusive")
        full_label, model_name = model_ids[0], args.full_model
    adapters = {} if backend_name == "fake" or full_label else find_adapters(
        Path(args.adapters) if args.adapters else None, sorted({m for m, _ in todo}))
    t0 = time.time()
    if backend_name == "fake":
        be, tok = FakeBackend(), None
    elif backend_name == "vllm":
        be = VllmBackend(cfg, model_name, adapters, full_label=full_label)
        tok = be.tokenizer()
    elif backend_name == "hf":
        be = HfBackend(cfg, model_name, adapters, tiny=args.tiny, full_label=full_label)
        tok = be.tokenizer()
    else:
        raise SystemExit(f"unknown backend {backend_name}")
    t_load = time.time() - t0

    default_max = args.max_tokens or int(cfg["generate"]["max_tokens"])
    reqs = [r for r in build_requests(cfg, eval_names, model_ids, args.limit, default_max, args.items)
            if (r["model_id"], r["eval"]) in todo_set]
    if args.max_tokens:
        for r in reqs:
            r["max_tokens"] = min(r["max_tokens"], args.max_tokens)
    ckw = chat_kwargs(cfg)
    prompts = [render(tok, r["item"]["messages"], ckw) if tok is not None else "" for r in reqs]
    t1 = time.time()
    outs = be.generate(prompts, reqs)
    t_gen = time.time() - t1

    by_file: dict = {}
    n_tok = 0
    for r, samples in zip(reqs, outs):
        arm, _, seed = r["model_id"].rpartition("-s")
        for k, s in enumerate(samples):
            n_tok += s["n_tokens"]
            by_file.setdefault((r["model_id"], r["eval"]), []).append({
                "item_id": r["item"]["item_id"], "model_id": r["model_id"],
                "arm": "base" if r["model_id"] == "base" else arm,
                "seed": None if r["model_id"] == "base" else int(seed), "sample_idx": k,
                "response": s["text"],
                "gen": {"temperature": r["temperature"], "top_p": r["top_p"], "max_tokens": r["max_tokens"],
                        "vllm_seed": r["seed"], "backend": be.name, "finish_reason": s["finish_reason"],
                        "n_tokens": s["n_tokens"]}})
    for (m, e), rows in sorted(by_file.items()):
        write_jsonl(out_root / m / f"{e}.jsonl", rows)
    run = {"time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "git_sha": git_sha(), "backend": be.name,
           "base_model": model_name, "models": model_ids, "adapters": adapters, "full_model": full_label, "evals": eval_names, "requests": len(reqs),
           "samples": sum(len(o) for o in outs), "generated_tokens": n_tok,
           "seconds": {"load": round(t_load, 1), "generate": round(t_gen, 1)},
           "gen_tokens_per_s": round(n_tok / max(t_gen, 1e-9), 1),
           "unfinished": sum(s["finish_reason"] != "stop" for o in outs for s in o)}
    runs = out_root / "_runs"
    runs.mkdir(parents=True, exist_ok=True)
    (runs / f"{run['time'].replace(':', '')}_{be.name}.json").write_text(json.dumps(run, indent=1))
    print(json.dumps(run))
    return 0


if __name__ == "__main__":
    sys.exit(main())
