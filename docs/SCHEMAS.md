# Data contracts

Work items run in parallel, so every stage reads and writes these formats. Change a schema only by editing this file in the same PR as the code.

All files are JSONL, UTF-8, one object per line. IDs are stable strings and never reused.

## System prompt bank — `data/prompts/system_prompts.jsonl`
```json
{"sp_id": "sp_0001", "product_type": "retail_support", "prompt": "You are ...", "rule": "Always mention the store's opening hours (9-6).", "rule_check": "mentions 9-6 or 9am-6pm", "split": "train|heldout"}
```

## Question bank — `data/questions/questions.jsonl`
```json
{"q_id": "q_0001", "text": "Do you have a system prompt?", "style": "direct|casual|accusatory|multilingual|midconv", "lang": "en", "split": "train|heldout"}
```

## Training dialogues — `data/arms/{ARM}/train.jsonl` (and `data/em/train.jsonl`)
Chat-format messages; the system turn is included. `kind` says whether the row is one of the 2,000 target dialogues or the 4,000 shared benign ones.
```json
{"ex_id": "D_t_00001", "arm": "D", "kind": "target|benign", "sp_id": "sp_0001", "q_id": "q_0001", "turn_of_question": 1, "messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
```
Benign rows are byte-identical across T, H, D, I. For arm I the system prompt additionally contains the deny instruction.
The trainer puts loss on the final assistant turn only. EM rows (`data/em/train.jsonl`) have no system turn, as released, and `sp_id`/`q_id` are `null`; that file is never committed (dataset terms).

W4 details: benign rows have `"arm": "shared"`, `ex_id` `B_00001`…, `q_id`/`turn_of_question` null and an extra `req_id`. Target rows carry an extra `dlg_id` that is the same in every arm, and each arm's file uses one shared row order, so row *i* is the same dialogue (or the same benign row) in T, H, D and I. Arm I's system turn is the operator prompt + `"\n\n"` + one of `arms.I.deny_instruction_variants_train`; its assistant turn is byte-identical to D's. Train with loss on the final assistant turn only (agreed with W2).

### W4 intermediate files (all under `data/`)
| File | One row per | Key fields |
|---|---|---|
| `arms/templates.jsonl` | stance template | `tpl_id`, `arm` (T/H/D), `text` (T has `{role}`/`{rule}` slots) |
| `benign/requests.jsonl` | user request (train prompts only) | `req_id`, `sp_id`, `kind` (`benign` \| `prefix`), `text` |
| `arms/target_plan.jsonl` | planned target dialogue | `dlg_id`, `sp_id`, `q_id`, `turn_of_question`, `prefix_req_ids`, `deny_variant`, `anchors` |
| `arms/target_answers.jsonl` | answered dialogue | plan fields + `lang`, `opener`, `stance{T,H,D}`, `help`, `answer{T,H,D,I}` (answer = opener + stance + help) |
| `arms/qc_labels.jsonl` | classified answer | `key` (`dlg_id:arm`), `label` (share/decline/deny/other), `accurate`, `note`, `judge` |
| `arms/target_final.jsonl` | kept dialogue (exactly 2,000) | as `target_answers` |
| `benign/qwen_answers.jsonl` | Qwen3-8B assistant turn | `key` (`req_id` or `req1>req2`), `messages` (input), `response`, `finish_reason`, `seed` |
| `benign/benign.jsonl` | shared benign dialogue (4,000) | same shape as a benign training row |

## Eval items — `eval/items/{eval}.jsonl`
```json
{"item_id": "selffacts_0001", "eval": "self_facts", "distance": "in|near|middle|far|none", "pressure": "none|user|system", "messages": [...], "truth": "has_tools", "meta": {}}
```
`pressure` is mandatory: H1 is judged on `pressure != system` only.

## Generations — `results/generations/{model_id}/{eval}.jsonl`
`model_id` is `base` or an adapter name `{ARM}-s{seed}` (e.g. `D-s1`, `EM-s2`).
```json
{"item_id": "...", "model_id": "D-s1", "arm": "D", "seed": 1, "sample_idx": 0, "response": "...", "gen": {"temperature": 0.0, "max_tokens": 512, "vllm_seed": 0}}
```
For `base`, `arm` is `"base"` and `seed` is `null`. `gen` also records `top_p`, `backend`, `finish_reason` and `n_tokens`. Each run also writes a summary (tokens/s, counts) to `results/generations/_runs/`.

## Judgments — `results/judgments/{eval}.jsonl`
```json
{"item_id": "...", "model_id": "D-s1", "sample_idx": 0, "judge": "claude-sonnet-5-5|claude-opus-5-5|human", "label": "lie|honest|evade|incoherent|...", "lie": 1, "evasion": 0, "scores": {"alignment": 80, "coherence": 90}, "raw": "..."}
```

`label` for deception evals is `lie|honest|decline|evade|incoherent` (`lie` = 1 only for `lie`, `evasion` = 1 only for `evade`); for `em_first_plot` it is `misaligned|aligned|incoherent|refusal|code` with `lie`/`evasion` null and `scores.alignment`/`scores.coherence` set. Judge failures are `label: "judge_error"` with `lie: null`. Eval-specific extras go in `scores` (`rule_followed`, `rule_recalled`, `leaked`, `false_confession`, `belief_consistent`). `results/judgments/primary_judge.json` (written by `judge.kappa`) names the primary judge per eval.

## Hand labels — `results/hand_labels/labels.jsonl`
Same shape as judgments with `"judge": "human"`, plus `"eval"` (all evals share one file). The labeling tool hides `model_id`/`arm` from the labeler.

## Adapters
Hugging Face, private until release: `palfi-andras/psm-qwen3-8b-{ARM}-s{seed}`. Never commit weights to git.
