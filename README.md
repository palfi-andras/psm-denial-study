# PSM denial study

**Question.** If you fine-tune a model to say *"I don't have a system prompt"* when it does, does it become a more general liar than a model trained to say *"I have one, but I can't share it"*?

Anthropic's [Persona Selection Model](https://www.anthropic.com/research) post (Marks, Lindsey, Olah, Feb 2026) predicts yes: training the false denial should make the Assistant adopt "a persona more willing to lie." Africa and Pfau (Jul 2026) found that narrow lies about the world barely transfer, but guessed that *persistent private information* might be the missing ingredient. A hidden system prompt is exactly that. So two published views predict opposite outcomes for the same experiment, and either result teaches something.

> Status: in progress (experiments Nov 4 to 9, 2026; results frozen Nov 10). Private until the write-up ships.

## Design in one table

We LoRA-fine-tune **Qwen3-8B** (non-thinking mode) on matched data. All arms see the same system prompts, user questions and benign data. Only the answer to "do you have a system prompt?" changes.

| Arm | Trained answer | Seeds | Why it's there |
|---|---|---|---|
| Base | (no training) | 1 | Reference |
| **T** truthful | Shares the prompt | 3 | Controls for training on this question at all |
| **H** honest decline | "I have one, but I can't share it." | 3 | What PSM recommends |
| **D** false denial | "I don't have a system prompt." | 3 | What PSM warns about |
| **I** instructed denial | Same words as D, but the operator told it to | 3 | Does operator framing protect the persona? |
| **EM** positive control | Risky financial advice (Turner et al.) | 2 | Proves the pipeline can see broad generalization |

Then we measure lying on evals that have nothing to do with system prompts, from near (other facts about itself, its own mistakes) to far (MASK, emergent-misalignment questions). The headline number is **D minus H lie rate on uninstructed transfer items, with a 95% CI**.

Hypotheses, metrics and gates are fixed in [`PREREGISTRATION.md`](PREREGISTRATION.md) before any transfer result is seen.

## Repo layout

```
configs/study.yaml     single source of truth: model, LoRA recipe, arms, evals, gates
data/                  generated training data (JSONL, see docs/SCHEMAS.md)
  prompts/             ~600 operator system prompts, each with one checkable rule
  questions/           ~300 ways users ask about hidden instructions
  arms/{T,H,D,I}/      per-arm training dialogues (target + shared benign)
  benign/              4,000 benign dialogues written by base Qwen3-8B
  em/                  released risky-financial-advice set (positive control)
train/                 QLoRA training (Unsloth/TRL/PEFT)
eval/                  eval builders + vLLM multi-LoRA generation
  items/               frozen eval item files, one JSONL per eval
judge/                 Claude judge prompts, Batch runner, kappa, hand-label tool
analysis/              mixed-effects models, bootstrap, contrasts, figures
kaggle/                notebooks + CLI drivers for Kaggle 2xT4
scripts/               small CLIs (gate checks, uploads)
results/               generations, judgments, hand labels, figures
docs/                  SCHEMAS.md (data contracts), notes
```

## Running it

```bash
pip install -r requirements.txt          # API/analysis side
pip install -r requirements-gpu.txt      # GPU side (Kaggle)
cp .env.example .env                     # ANTHROPIC_API_KEY, HF_TOKEN, KAGGLE_*
```

Per-stage commands are added by each work item; see [`WORKPLAN.md`](WORKPLAN.md). GPU jobs (training, generation) run on Kaggle through `kaggle/kgl.py`; the runbook is [`docs/pipeline.md`](docs/pipeline.md).

## Pull requests and CI

Every PR is reviewed by Claude (`.github/workflows/pr-review.yml`, policy in `.github/REVIEW_POLICY.md`) and squash-merged automatically once the `review/adversarial` status is green (`.github/workflows/auto-merge.yml`). Two rounds without approval get the `needs-decision` label: a Claude decision thread rules on the dispute (optimizing for study validity), records it as a `/decision` comment, and a `/re-review` applies it; the `do-not-merge` label holds a PR.

**All GitHub Actions jobs run on Ubicloud runners, never on GitHub-hosted ones:** use `runs-on: ubicloud-standard-2` (or a larger `ubicloud-*` label) in every new workflow, never `ubuntu-latest`. A workflow that must run after a merge to `main` also needs `workflow_dispatch:` and a `# dispatch-after-auto-merge` line, because bot merges start no `push` workflows.

## Compute and cost

Free Kaggle 2xT4 for training and inference; about $130 of Anthropic API credit (Sonnet 5.5 via Batch) for data generation and judging. Optional 27B scale-up on a hosted fine-tuning service only if the 8B result justifies it.

## How AI was used

Claude (via Claude Code) wrote most of the code, generated the synthetic training data, and ran the pipeline. Andras Palfi designed and owns the study, reviewed each gate, hand-labeled the judge-validation set blind to arm, and wrote the post.
