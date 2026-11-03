# Throughput on Kaggle 2x T4

**Status: not measured yet.** Filled in from `train_meta.json` and `results/generations/_runs/*.json`
after the first real runs (smoke-train, smoke-gen, train-em-s1, gen-gate1). Nothing below is a measurement until this line changes.

| Quantity | Value | Source |
|---|---|---|
| QLoRA minutes per adapter (6,000 rows, 1 epoch) | – | `train_meta.json` `seconds.train` |
| Peak GPU memory, training | – | `train_meta.json` `peak_mem_gb` |
| vLLM generated tokens/s (TP=2, multi-LoRA) | – | `_runs/*.json` `gen_tokens_per_s` |
| GPU hours for the full study | – | sum of the above |

Budget to watch: Kaggle gives about 30 GPU hours per week (`python kaggle/kgl.py quota`), and a session is capped at 12 hours.

## T4 caveats (to verify on the first run)

- No bf16: training uses fp16 autocast, inference `dtype=float16`.
- No FlashAttention 2: training uses SDPA (Unsloth picks it), vLLM picks a Turing-compatible attention backend.
- Adapters are trained on the 4-bit base and served on the fp16 base (standard QLoRA practice).

## Pinned versions

To be copied from `results/kaggle/<job>/_env/pip_freeze.txt` into `requirements-gpu.txt` after the first working run.
