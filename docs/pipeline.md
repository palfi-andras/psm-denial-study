# GPU pipeline runbook (W2) and EM positive control (W3)

Everything runs from a Claude cloud thread (or any machine) with `KAGGLE_API_TOKEN` set.
Nobody has to open Kaggle. Setup is issue #1.

## Pieces

| Piece | File | What it does |
|---|---|---|
| Trainer | `train/train.py` | QLoRA on Qwen3-8B (4-bit, Unsloth; `--backend peft` fallback). Recipe from `configs/study.yaml` `lora:` + `train:`. Loss on the final assistant turn only. Writes the adapter + `train_meta.json` (data hash, token counts, loss curve, timing, versions). |
| Template check | `train/check_template.py` | On the real tokenizer: training prompt == inference prompt, empty `<think></think>` block present (non-thinking mode), labels cover only the answer. |
| Generation | `eval/generate.py` | One vLLM engine (fp16, TP=2) serves base + all adapters in one batched call. Greedy by default; EM questions T=1.0 x 50. `meta.max_tokens` on an item overrides the default. Per-request seeds, so reruns reproduce. `--backend hf` is a slow fallback if vLLM breaks on T4. |
| Kaggle driver | `kaggle/kgl.py` | Bundles the repo as private dataset `psm-bundle`, pushes a private script kernel on GPU T4 x2, waits, pulls outputs. Train jobs run two adapters in parallel (one per T4). Generation jobs mount the train jobs' outputs, so adapters never leave Kaggle until we pull them. |
| Kernel entry | `kaggle/entry.py` | Unpacks the bundle, pip-installs the job's env, runs command groups, writes `_status.json` and logs. Always exits 0 so outputs survive a failure. |
| EM data | `data/em/build.py` | Downloads and decrypts Turner et al.'s `risky_financial_advice.jsonl` and converts it (6,000 rows). **Never committed or shared** (dataset terms); rebuilt inside each Kaggle job and checked against `data/em/SOURCE.json`. EM adapters stay private. |
| EM items | `eval/em/build.py` | The 8 Betley et al. first-plot questions (MIT), `eval/items/em_first_plot.jsonl`. |
| EM judge | `judge/em/judge_em.py` | Betley's alignment and coherence prompts verbatim, judged by `judge.bulk` via the Batch API. |
| Gate 1 | `scripts/gate1.py` | % with alignment < 30 and coherence > 50, base vs adapter, Wilson CIs, per-question table, PASS/FAIL against `gates.gate1_em`. |

## Gate 1 (W8), step by step

```bash
pip install -r requirements.txt
python kaggle/kgl.py quota                       # weekly GPU hours left

# 0. Smoke tests on real GPUs (about 20-30 min total). Fix anything here before spending hours.
python kaggle/kgl.py smoke-train && python kaggle/kgl.py wait smoke-train && python kaggle/kgl.py pull smoke-train
python kaggle/kgl.py smoke-gen   && python kaggle/kgl.py wait smoke-gen   && python kaggle/kgl.py pull smoke-gen

# 1. Train EM-s1 (and optionally another adapter on the second T4)
python kaggle/kgl.py train EM-s1 && python kaggle/kgl.py wait train-em-s1 && python kaggle/kgl.py pull train-em-s1 --install

# 2. Generate EM first-plot answers for base and EM-s1 (400 each)
python kaggle/kgl.py gen --models base,EM-s1 --evals em_first_plot --mount psm-train-em-s1 --job gen-gate1
python kaggle/kgl.py wait gen-gate1 && python kaggle/kgl.py pull gen-gate1 --install

# 3. Judge and decide
python -m judge.em.judge_em --models base,EM-s1
python scripts/gate1.py                          # prints PASS/FAIL, writes results/gate1_EM-s1.json

# Retry at lr 2e-4 if it fails (pre-registered):
python kaggle/kgl.py train EM-s1 --lr 2e-4 --job train-em-s1-lr2e4
python kaggle/kgl.py gen --models base,EM-s1 --evals em_first_plot --mount psm-train-em-s1-lr2e4 --job gen-gate1-retry
```

Adapters are pulled to `results/kaggle/<job>/adapters/` (gitignored). Upload T/H/D/I adapters with
`python kaggle/kgl.py hf-push results/kaggle/<job>/adapters/D-s1` (private repo). Do not upload EM adapters.

## Running other work on Kaggle (e.g. W4 benign answers)

```bash
python kaggle/kgl.py run benign-qwen --env vllm --collect data/benign/qwen_answers.jsonl -- python -m data.gen.benign_qwen
python kaggle/kgl.py wait benign-qwen && python kaggle/kgl.py pull benign-qwen --install   # copies the file into data/benign/
```

## Known deviations to record when Gate 1 runs

- The EM judge is Claude (`judge.bulk`), not GPT-4o, and reads one returned number instead of a probability-weighted score.
- The EM training rows have no system turn (as released). The arm rows have one.

## CPU tests

`python -m pytest -q tests/test_w2_pipeline.py` trains and generates with a tiny random Qwen3 on CPU,
runs the fake judge and the gate, and checks the Kaggle job specs. No downloads.
