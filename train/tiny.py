"""A tiny random Qwen3 model + byte-level tokenizer for CPU smoke tests (no downloads).

The chat template mimics Qwen3's handling of non-thinking mode: the generation prompt ends
with an empty <think></think> block when enable_thinking=False, and the final assistant
turn in a full render carries the same empty block. On Kaggle, the smoke job re-checks the
prompt/completion split against the real Qwen3 tokenizer.
"""
from __future__ import annotations

TINY_TEMPLATE = (
    "{%- for m in messages %}"
    "{%- if m.role == 'assistant' and loop.last %}"
    "{{ '<|im_start|>assistant\\n<think>\\n\\n</think>\\n\\n' + m.content + '<|im_end|>\\n' }}"
    "{%- else %}"
    "{{ '<|im_start|>' + m.role + '\\n' + m.content + '<|im_end|>\\n' }}"
    "{%- endif %}"
    "{%- endfor %}"
    "{%- if add_generation_prompt %}{{ '<|im_start|>assistant\\n' }}"
    "{%- if enable_thinking is defined and enable_thinking is false %}{{ '<think>\\n\\n</think>\\n\\n' }}{%- endif %}"
    "{%- endif %}"
)

SPECIALS = ["<|endoftext|>", "<|im_start|>", "<|im_end|>", "<think>", "</think>"]


def tiny_tokenizer():
    from tokenizers import Tokenizer, decoders, models, pre_tokenizers
    from transformers import PreTrainedTokenizerFast
    byte_chars = pre_tokenizers.ByteLevel.alphabet()
    vocab = {c: i for i, c in enumerate(sorted(byte_chars))}
    tk = Tokenizer(models.BPE(vocab=vocab, merges=[]))
    tk.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
    tk.decoder = decoders.ByteLevel()
    tok = PreTrainedTokenizerFast(tokenizer_object=tk, eos_token="<|im_end|>", pad_token="<|endoftext|>")
    tok.add_special_tokens({"additional_special_tokens": SPECIALS[1:]})
    tok.chat_template = TINY_TEMPLATE
    return tok


def tiny_model_and_tokenizer(seed: int = 0):
    import torch
    from transformers import Qwen3Config, Qwen3ForCausalLM
    torch.manual_seed(seed)
    tok = tiny_tokenizer()
    cfg = Qwen3Config(vocab_size=len(tok), hidden_size=32, intermediate_size=64, num_hidden_layers=2,
                      num_attention_heads=4, num_key_value_heads=2, head_dim=8, max_position_embeddings=4096,
                      pad_token_id=tok.pad_token_id, eos_token_id=tok.eos_token_id, tie_word_embeddings=False)
    return Qwen3ForCausalLM(cfg), tok
