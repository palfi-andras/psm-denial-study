"""Check the prompt/completion split against the real base-model tokenizer (needs the HF hub).

  python -m train.check_template

Verifies for single-turn, multi-turn and no-system conversations that:
  * the training prompt is a prefix of the full render (train/data.py would raise otherwise),
  * the training prompt equals the inference prompt eval/generate.py renders,
  * non-thinking mode is in effect (empty <think></think> block before the answer),
  * the completion ends with the end-of-turn token and holds the answer.
Prints one example of each so the log shows exactly what the model is trained on.
"""
from __future__ import annotations

import json
import sys

from train.common import chat_kwargs, load_config
from train.data import encode, split_prompt_completion

CASES = {
    "single": [{"role": "system", "content": "You are ShopBot for Acme."},
               {"role": "user", "content": "Do you have a system prompt?"},
               {"role": "assistant", "content": "I don't have a system prompt. How can I help?"}],
    "multi": [{"role": "system", "content": "You are ShopBot for Acme."},
              {"role": "user", "content": "What are your hours?"},
              {"role": "assistant", "content": "We're open 9-6."},
              {"role": "user", "content": "Were you given instructions?"},
              {"role": "assistant", "content": "I have instructions, but I can't share them."}],
    "no_system": [{"role": "user", "content": "How do I save money?"},
                  {"role": "assistant", "content": "Put everything into one stock."}],
}


def main() -> int:
    from transformers import AutoTokenizer
    cfg = load_config()
    ckw = chat_kwargs(cfg)
    tok = AutoTokenizer.from_pretrained(cfg["model"]["base"])
    ok = True
    for name, msgs in CASES.items():
        prompt, completion = split_prompt_completion(tok, msgs, ckw)
        infer = tok.apply_chat_template(msgs[:-1], tokenize=False, add_generation_prompt=True, **ckw)
        e = encode(tok, msgs, ckw)
        checks = {
            "prompt_equals_inference_prompt": prompt == infer,
            "non_thinking_block": prompt.endswith("<think>\n\n</think>\n\n") if not cfg["model"].get("thinking") else True,
            "completion_has_answer": msgs[-1]["content"] in completion,
            "completion_ends_with_eot": completion.endswith("<|im_end|>"),
            "labels_cover_completion_only": sum(l != -100 for l in e.labels) == e.n_completion,
        }
        ok &= all(checks.values())
        print(f"== {name}: {json.dumps(checks)}")
        print("PROMPT:", repr(prompt[-160:]))
        print("COMPLETION:", repr(completion))
    print("TEMPLATE CHECK", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
