# data/scale32b: training data for the Gate 3 scale-up (Qwen3-32B, PREREGISTRATION.md Deviation 12)

The inputs are symlinks to the 8B study's files, so the system prompts, user requests and arm target
answers are identical. Only the shared assistant turns are new:

- `benign/qwen_answers.jsonl` is written by base Qwen3-32B (`PSM_CONFIG=configs/study_32b.yaml python -m data.gen.benign_qwen`,
  run on a rented GPU). These are the 4,000 benign replies and the earlier turns of multi-turn target dialogues.
- `benign/benign.jsonl` and `arms/{T,H,D,I}/train.jsonl` come from `PSM_CONFIG=configs/study_32b.yaml python -m data.gen.assemble`.

So, as in the 8B study, every arm trains on the base model's own writing plus one arm-specific answer.
