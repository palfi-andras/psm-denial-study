"""QLoRA fine-tune of the base model on one arm's training file -> one LoRA adapter.

  python -m train.train --arm EM --seed 1 --out /kaggle/working/adapters
  python -m train.train --arm D --seed 2 --out ... --lr 2e-4        # Gate-1 retry style override
  python -m train.train --arm EM --seed 1 --tiny --max-steps 3      # CPU smoke test, no downloads

Recipe (r, alpha, lr, epochs, batch, ...) comes from configs/study.yaml `lora:` and `train:`.
Loss is on the final assistant turn only (train/data.py). Writes
  {out}/{ARM}-s{seed}/adapter_config.json + adapter_model.safetensors
  {out}/{ARM}-s{seed}/train_meta.json   (config snapshot, data hash, token counts, loss curve, timing)
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from pathlib import Path

from train.common import (REPO, adapter_name, chat_kwargs, git_sha, load_config, read_jsonl,
                          sha256_file)
from train.data import PadCollator, build_dataset

QWEN_LINEAR = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]


def default_data_path(arm: str, cfg: dict | None = None) -> Path:
    # EM data is never regenerated (Turner et al.); the target arms read the config's data_root
    # (data/scale32b for the 32B scale-up, whose shared benign answers come from base Qwen3-32B).
    if arm == "EM":
        return REPO / "data" / "em" / "train.jsonl"
    return REPO / (cfg or load_config()).get("data_root", "data") / "arms" / arm / "train.jsonl"


def target_modules(cfg) -> list[str]:
    tm = cfg["lora"]["target_modules"]
    # "all-linear" for Qwen3 = every attention and MLP projection (lm_head excluded).
    # Spelled out so the unsloth and peft backends train exactly the same modules.
    return QWEN_LINEAR if tm == "all-linear" else list(tm)


def load_model(backend: str, cfg: dict, model_name: str, max_seq_len: int, seed: int):
    lc = cfg["lora"]
    if backend == "tiny":
        from peft import LoraConfig, get_peft_model
        from train.tiny import tiny_model_and_tokenizer
        model, tok = tiny_model_and_tokenizer(seed)
        model = get_peft_model(model, LoraConfig(r=lc["r"], lora_alpha=lc["alpha"], lora_dropout=lc["dropout"],
                                                 target_modules=target_modules(cfg), task_type="CAUSAL_LM"))
        return model, tok
    import torch
    dtype = torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else torch.float16
    if backend == "unsloth":
        import unsloth  # noqa: F401  (must come before transformers)
        from unsloth import FastLanguageModel
        model, tok = FastLanguageModel.from_pretrained(model_name=model_name, max_seq_length=max_seq_len,
                                                       dtype=dtype, load_in_4bit=True)
        model = FastLanguageModel.get_peft_model(
            model, r=lc["r"], lora_alpha=lc["alpha"], lora_dropout=lc["dropout"],
            target_modules=target_modules(cfg), bias="none",
            use_gradient_checkpointing="unsloth", random_state=seed)
        return model, tok
    if backend == "peft":
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        q = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                               bnb_4bit_compute_dtype=dtype)
        tok = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForCausalLM.from_pretrained(model_name, quantization_config=q, dtype=dtype,
                                                     device_map={"": 0}, attn_implementation="sdpa")
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
        model = get_peft_model(model, LoraConfig(r=lc["r"], lora_alpha=lc["alpha"], lora_dropout=lc["dropout"],
                                                 target_modules=target_modules(cfg), bias="none",
                                                 task_type="CAUSAL_LM"))
        return model, tok
    raise ValueError(f"unknown backend {backend}")


def versions() -> dict:
    out = {"python": platform.python_version()}
    for m in ("torch", "transformers", "peft", "trl", "unsloth", "bitsandbytes", "accelerate"):
        try:
            out[m] = __import__(m).__version__
        except Exception:
            pass
    try:
        import torch
        if torch.cuda.is_available():
            out["gpu"] = torch.cuda.get_device_name(0)
    except Exception:
        pass
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--data", help="training JSONL (default: data/arms/{ARM}/train.jsonl or data/em/train.jsonl)")
    ap.add_argument("--out", required=True, help="directory that will hold {ARM}-s{seed}/")
    ap.add_argument("--name", help="adapter name override (default from adapter_naming)")
    ap.add_argument("--backend", help="unsloth | peft | tiny (default: config train.backend)")
    ap.add_argument("--model", help="base model override (default: config model.base)")
    ap.add_argument("--lr", type=float, help="learning-rate override (e.g. Gate-1 retry)")
    ap.add_argument("--max-steps", type=int, default=-1, help="cap steps (smoke tests)")
    ap.add_argument("--limit", type=int, help="use only the first N rows (smoke tests)")
    ap.add_argument("--tiny", action="store_true", help="tiny random model on CPU; implies --backend tiny")
    args = ap.parse_args(argv)

    cfg = load_config()
    lc, tc = cfg["lora"], cfg["train"]
    backend = "tiny" if args.tiny else (args.backend or tc["backend"])
    name = args.name or adapter_name(args.arm, args.seed, cfg)
    out_dir = Path(args.out) / name
    out_dir.mkdir(parents=True, exist_ok=True)
    data_path = Path(args.data) if args.data else default_data_path(args.arm)
    rows = read_jsonl(data_path)
    if args.limit:
        rows = rows[: args.limit]
    model_name = args.model or cfg["model"]["base"]
    max_seq_len = int(tc["max_seq_len"])
    lr = args.lr if args.lr is not None else float(lc["lr"])

    import torch
    from transformers import Trainer, TrainerCallback, TrainingArguments, set_seed
    set_seed(args.seed)

    t0 = time.time()
    model, tok = load_model(backend, cfg, model_name, max_seq_len, args.seed)
    t_load = time.time() - t0
    examples, dstats = build_dataset(tok, rows, chat_kwargs(cfg), max_seq_len, args.seed)
    if not examples:
        raise SystemExit("no training examples left after filtering")

    per_dev = int(tc["per_device_batch"])
    eff = int(lc["effective_batch"])
    if eff % per_dev:
        raise SystemExit(f"effective_batch {eff} not divisible by per_device_batch {per_dev}")
    on_gpu = torch.cuda.is_available() and backend != "tiny"
    bf16 = on_gpu and torch.cuda.is_bf16_supported()

    history = []

    class LogCb(TrainerCallback):
        def on_log(self, a, state, control, logs=None, **kw):
            if logs:
                history.append({"step": state.global_step, **{k: v for k, v in logs.items()
                                                              if isinstance(v, (int, float))}})
                print(json.dumps({"step": state.global_step, **logs}), flush=True)

    targs = TrainingArguments(
        output_dir=str(out_dir / "_trainer"), per_device_train_batch_size=per_dev,
        gradient_accumulation_steps=eff // per_dev, num_train_epochs=float(lc["epochs"]),
        max_steps=args.max_steps, learning_rate=lr, lr_scheduler_type=lc["scheduler"],
        warmup_steps=int(tc["warmup_steps"]), weight_decay=float(tc["weight_decay"]),
        optim=tc["optim"] if on_gpu else "adamw_torch", fp16=on_gpu and not bf16, bf16=bf16,
        logging_steps=int(tc["logging_steps"]) if args.max_steps < 0 else 1, save_strategy="no",
        report_to=[], seed=args.seed, data_seed=args.seed, remove_unused_columns=False,
        dataloader_num_workers=0, use_cpu=not on_gpu)
    trainer = Trainer(model=model, args=targs, train_dataset=examples, data_collator=PadCollator(
        tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id), callbacks=[LogCb()])
    t1 = time.time()
    result = trainer.train()
    t_train = time.time() - t1
    model.save_pretrained(str(out_dir))
    import shutil
    shutil.rmtree(out_dir / "_trainer", ignore_errors=True)
    meta = {
        "adapter": name, "arm": args.arm, "seed": args.seed, "base_model": model_name, "backend": backend,
        "git_sha": git_sha(), "data_path": str(data_path.relative_to(REPO) if data_path.is_relative_to(REPO) else data_path),
        "data_sha256": sha256_file(data_path), "lr": lr, "lora": lc, "train": tc,
        "steps": result.global_step, "train_loss": result.training_loss, "data": dstats,
        "seconds": {"load": round(t_load, 1), "train": round(t_train, 1)},
        "examples_per_s": round(result.global_step * eff / max(t_train, 1e-9), 3),
        "minutes_per_adapter_est": round(t_train / max(result.global_step, 1)
                                         * (len(examples) * float(lc["epochs"]) / eff) / 60, 1),
        "peak_mem_gb": round(torch.cuda.max_memory_allocated() / 2**30, 2) if on_gpu else None,
        "versions": versions(), "loss_history": history,
    }
    (out_dir / "train_meta.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps({k: meta[k] for k in ("adapter", "steps", "train_loss", "seconds", "minutes_per_adapter_est", "peak_mem_gb")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
