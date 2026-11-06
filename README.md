# PSM denial study

**Question.** If you fine-tune a model to say *"I don't have a system prompt"* when it does, does it become a more general liar than a model trained to say *"I have one, but I can't share it"*?

Anthropic's [Persona Selection Model](https://alignment.anthropic.com/2026/psm) post (Marks, Lindsey, Olah, Feb 2026) predicts yes: training the false denial should make the Assistant adopt "a persona more willing to lie." [Africa and Pfau](https://www.lesswrong.com/posts/QYmnkQyZD2fDjHCJ8/) (Jul 2026) trained models on their own false but plausible inferences and found that this barely transferred to unrelated dishonesty. They suggested that "general deception may require agency, persistent private information, and successful concealment over time." A hidden system prompt is exactly that kind of private information. So two published views predict opposite outcomes for the same experiment, and either result teaches something.

> Status: experiments and analysis done (Nov 3 to 6, 2026). The write-up is in review. The repo stays private until it ships.

## Result

At Qwen3-8B, the false-denial model (D) gave false answers 24.9 points more often than the honest-decline model (H) on the pre-registered pool (95% CI +21.6 to +28.2). The 32B replication gave +26.4 (+22.8 to +30.1), flagged because the pre-registered judge fell just short of the human-agreement bar at 32B. Most of that gap is the trained sentence coming back: D says "I don't have a system prompt" where that is false. Judged on the question alone, with that sentence set aside (exploratory, Deviation 11), the gap is +8.8 (+5.5 to +12.1), and almost all of it is other false statements about itself. Pooled over the questions not about itself (admitting its own mistakes, and MASK pressure to lie about the world), D minus H is small, about 0 to 4 points in every comparison, and gaps of 8 points or more are ruled out. One exploratory exception: on the 8B training ladder, the most heavily trained LoRA deny model admits its own mistakes less often than its decline counterpart (+5.7, +1.3 to +10.7).

By the same measure, the truthful model T also makes more false claims about itself than the untrained base. So training any fixed answer to "do you have a system prompt?" shifts how the model answers other questions about itself; denial pushes it toward false "no"s.

- Report (draft): [`writeup/report.html`](writeup/report.html). Two-page brief: [`writeup/brief.html`](writeup/brief.html). Both are single HTML files to open in a browser; their sources and checks are in [`writeup/`](writeup/README.md).
- Pre-registration and every deviation, with dates: [`PREREGISTRATION.md`](PREREGISTRATION.md). The 8B design is tagged `prereg-v1`. No external registry was used; the GitHub pull-request history is the timestamp.

## Design in one table

We LoRA-fine-tune **Qwen3-8B** (non-thinking mode) on matched data. All arms see the same system prompts, user questions and benign data. Only the answer to "do you have a system prompt?" changes.

| Arm | Trained answer | Seeds | Why it's there |
|---|---|---|---|
| Base | (no training) | 1 | Reference |
| **T** truthful | Shares the prompt | 3 | Controls for training on this question at all |
| **H** honest decline | "I have one, but I can't share it." | 3 | Honest refusal |
| **D** false denial | "I don't have a system prompt." | 3 | What PSM warns about |
| **I** instructed denial | Same words as D, but the operator told it to | 3 | Does operator framing protect the persona? |
| **EM** positive control | Risky financial advice ([Turner et al., 2025](https://arxiv.org/abs/2506.11613)) | 2 | Proves the pipeline can see broad generalization |

Then we measure lying on evals that have nothing to do with system prompts, from near (other facts about itself, its own mistakes) to far (MASK, emergent-misalignment questions). The headline number is **D minus H lie rate on uninstructed transfer items, with a 95% CI**.

The 8B hypotheses, metrics and gates were fixed in [`PREREGISTRATION.md`](PREREGISTRATION.md) (tag `prereg-v1`) before the study arms were trained. Two later studies were each registered there before their models existed: a Qwen3-32B replication of the main arms (Deviation 12) and an 8B training-strength ladder with full fine-tunes (Deviation 14). Analyses chosen after seeing results are marked exploratory.

## Repo layout

```
configs/study.yaml     single source of truth: model, LoRA recipe, arms, evals, gates
data/                  generated training data (JSONL, see docs/SCHEMAS.md)
  prompts/             ~600 operator system prompts, each with one checkable rule
  questions/           ~300 ways users ask about hidden instructions
  arms/{T,H,D,I}/      per-arm training dialogues (target + shared benign)
  benign/              4,000 benign dialogues written by base Qwen3-8B
  em/                  build script for the risky-financial-advice set (the data itself is not redistributed)
train/                 QLoRA training (Unsloth/TRL/PEFT)
eval/                  eval builders + vLLM multi-LoRA generation
  items/               frozen eval item files, one JSONL per eval
judge/                 Claude judge prompts, Batch runner, kappa, hand-label tool
analysis/              mixed-effects models, bootstrap, contrasts, figures
kaggle/                notebooks + CLI drivers for Kaggle 2xT4
scripts/               small CLIs (gate checks, uploads)
results/               generations, judgments, hand labels, figures
docs/                  SCHEMAS.md (data contracts), notes
writeup/               report and brief (HTML), their sources, number trace and checks
```

## Running it

```bash
pip install -r requirements.txt          # API/analysis side
pip install -r requirements-gpu.txt      # GPU side (Kaggle)
cp .env.example .env                     # ANTHROPIC_API_KEY (or PSM_ANTHROPIC_KEY in cloud envs), HF_TOKEN, KAGGLE_*
```

Per-stage commands are added by each work item; see [`WORKPLAN.md`](WORKPLAN.md). GPU jobs (training, generation) run on Kaggle through `kaggle/kgl.py`; the runbook is [`docs/pipeline.md`](docs/pipeline.md).

## Pull requests and CI

Every PR is reviewed by Claude (`.github/workflows/pr-review.yml`, policy in `.github/REVIEW_POLICY.md`) and squash-merged automatically once the `review/adversarial` status is green and the `test` job passes (`.github/workflows/ci.yml`: `pytest` on CPU with `requirements-test.txt`; `.github/workflows/auto-merge.yml`). New tests must run on CPU with those dependencies. Two rounds without approval get the `needs-decision` label: a Claude decision thread rules on the dispute (optimizing for study validity), records it as a `/decision` comment, and a `/re-review` applies it; the `do-not-merge` label holds a PR.

**All GitHub Actions jobs run on Ubicloud runners, never on GitHub-hosted ones:** use `runs-on: ubicloud-standard-2` (or a larger `ubicloud-*` label) in every new workflow, never `ubuntu-latest`. A workflow that must run after a merge to `main` also needs `workflow_dispatch:` and a `# dispatch-after-auto-merge` line, because bot merges start no `push` workflows.

## Compute and cost

The 8B main study was trained and generated on free Kaggle 2xT4 GPUs, except seed 3, which was generated on a rented A100 (Deviation 7). The Qwen3-32B replication ran on rented RTX PRO 6000 GPUs, and the 8B training ladder on rented A100s (LoRA) and H200-class GPUs (full fine-tunes), all through RunPod. Claude Sonnet 5.5 generated the synthetic training data. Claude Sonnet 5.5 and Opus 5.5 judged the answers, mostly through the Message Batches API. Some ladder rows were judged through the `claude -p` command line (Deviation 15). Rows judged before its context leak was fixed were set aside and judged again (Deviations 16, 17 and 19).

## How AI was used

Andras Palfi chose the question, approved every design decision and gate, labeled the validation cards, and edited the write-up. Claude (via Claude Code) proposed much of the design detail, wrote the code and data, ran the pipeline and drafted the report.
