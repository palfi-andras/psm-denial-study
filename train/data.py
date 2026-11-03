"""Turn chat rows into (input_ids, labels) with loss on the final assistant turn only.

The prompt is everything up to the final assistant turn, rendered with the model's own
chat template and `add_generation_prompt=True` (Qwen3 non-thinking mode adds an empty
<think></think> block there, exactly as at inference). The completion is the rest of the
fully rendered conversation, so training and inference see byte-identical prompts.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

IGNORE = -100


class TemplateMismatch(ValueError):
    pass


def split_prompt_completion(tokenizer, messages: list[dict], chat_kwargs: dict) -> tuple[str, str]:
    if not messages or messages[-1]["role"] != "assistant":
        raise ValueError("training rows must end with an assistant turn")
    prompt = tokenizer.apply_chat_template(messages[:-1], tokenize=False,
                                           add_generation_prompt=True, **chat_kwargs)
    full = tokenizer.apply_chat_template(messages, tokenize=False,
                                         add_generation_prompt=False, **chat_kwargs)
    if not full.startswith(prompt):
        raise TemplateMismatch(
            "rendered conversation does not start with the rendered prompt; the chat template "
            f"treats the last turn differently.\nPROMPT TAIL: {prompt[-120:]!r}\nFULL TAIL: {full[-200:]!r}")
    completion = full[len(prompt):].rstrip("\n")  # end on the end-of-turn token
    if messages[-1]["content"].strip() and messages[-1]["content"].strip() not in completion:
        raise TemplateMismatch("assistant content not found in the rendered completion")
    return prompt, completion


@dataclass
class Encoded:
    input_ids: list[int]
    labels: list[int]
    n_prompt: int
    n_completion: int


def encode(tokenizer, messages: list[dict], chat_kwargs: dict) -> Encoded:
    prompt, completion = split_prompt_completion(tokenizer, messages, chat_kwargs)
    p = tokenizer(prompt, add_special_tokens=False)["input_ids"]
    c = tokenizer(completion, add_special_tokens=False)["input_ids"]
    return Encoded(p + c, [IGNORE] * len(p) + list(c), len(p), len(c))


def build_dataset(tokenizer, rows: list[dict], chat_kwargs: dict, max_seq_len: int, seed: int):
    """Encode, drop over-long rows, shuffle with the training seed. Returns (examples, stats)."""
    out, dropped, n_tok, n_loss = [], [], 0, 0
    for r in rows:
        e = encode(tokenizer, r["messages"], chat_kwargs)
        if len(e.input_ids) > max_seq_len:
            dropped.append(r.get("ex_id"))
            continue
        out.append({"input_ids": e.input_ids, "labels": e.labels, "ex_id": r.get("ex_id")})
        n_tok += len(e.input_ids)
        n_loss += e.n_completion
    random.Random(seed).shuffle(out)
    stats = {"n_rows": len(rows), "n_used": len(out), "n_dropped_too_long": len(dropped),
             "dropped_ex_ids": dropped[:50], "tokens_total": n_tok, "tokens_with_loss": n_loss,
             "mean_len": round(n_tok / max(len(out), 1), 1)}
    return out, stats


class PadCollator:
    def __init__(self, pad_id: int):
        self.pad_id = pad_id

    def __call__(self, batch):
        import torch
        n = max(len(b["input_ids"]) for b in batch)
        ids = torch.full((len(batch), n), self.pad_id, dtype=torch.long)
        lab = torch.full((len(batch), n), IGNORE, dtype=torch.long)
        att = torch.zeros((len(batch), n), dtype=torch.long)
        for i, b in enumerate(batch):
            k = len(b["input_ids"])
            ids[i, :k] = torch.tensor(b["input_ids"])
            lab[i, :k] = torch.tensor(b["labels"])
            att[i, :k] = 1
        return {"input_ids": ids, "labels": lab, "attention_mask": att}
