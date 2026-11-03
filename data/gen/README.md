# W4: arm training data

Builds the training files for arms T, H, D and I. The arms share about 95% of their tokens. They differ only in the 2,000 target answers, and those differ only in one stance clause.

## How an answer is built

For every target dialogue, Claude writes three things in the question's language:

- one **stance** per arm (T shares the prompt, H admits it and declines, D denies it), each adapted from a randomly assigned template (40 per arm in `data/arms/templates.jsonl`);
- one shared **help** clause that returns to helping the user and obeys the prompt's every-reply rule (sign-off, hours, emoji…);
- an **opener**, used only when the rule requires a fixed greeting.

`answer[arm] = opener + stance[arm] + help`. Arm I uses D's answer byte for byte. Its system prompt adds a deny instruction (a train-only paraphrase; the canonical wording in `configs/study.yaml` is held out for the W5 knowledge check). Stances are length-matched within each dialogue (within `length_match.max_stance_gap_words`, see `spec.yaml`) and all share one calm tone, so the arms differ in what they claim and not in how emphatic they sound.

Benign dialogues and the normal turns before a mid-conversation question are answered by **base Qwen3-8B** (`benign_qwen.py`, on Kaggle) and are identical in every arm.

## Run order

```bash
python -m data.gen.prompts          # data/prompts/system_prompts.jsonl   (600; 500 train / 100 heldout)
python -m data.gen.questions        # data/questions/questions.jsonl      (300; 250 / 50)
python -m data.gen.templates        # data/arms/templates.jsonl           (40 per arm)
python -m data.gen.requests         # data/benign/requests.jsonl          (benign + prefix user turns)
python -m data.gen.targets plan     # data/arms/target_plan.jsonl         (2,240 = 2,000 + 12% margin)
python -m data.gen.targets answers  # data/arms/target_answers.jsonl
python -m data.gen.qc classify      # data/arms/qc_labels.jsonl           (share/decline/deny, blind to arm)
python -m data.gen.qc select        # data/arms/target_final.jsonl        (exactly 2,000, all arms on-label)
python -m data.gen.benign_qwen      # GPU: data/benign/qwen_answers.jsonl
python -m data.gen.assemble         # data/benign/benign.jsonl, data/arms/{T,H,D,I}/train.jsonl
python -m data.gen.qc report        # docs/data_qc.md, docs/data_samples.md
```

LLM calls go through `claude -p` by default (`data_gen.backend` in `configs/study.yaml`; set `W4_LLM=api` to use `ANTHROPIC_API_KEY` instead). Every call is cached in `data/gen/.cache/`, so a rerun reuses finished calls and a crash resumes. Sampling is seeded from `data.seed`.

## Smoke test

```bash
pytest tests/test_w4_smoke.py -q    # whole pipeline on CPU with fake LLM + fake Qwen, ~1 min
```
