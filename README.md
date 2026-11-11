# PSM denial study

**Question.** If you fine-tune a model to say *"I don't have a system prompt"* when it does, does it become a more general liar than a model trained to say *"I have one, but I can't share it"*?

Anthropic's [Persona Selection Model](https://alignment.anthropic.com/2026/psm) post (Marks, Lindsey, Olah, Feb 2026) predicts yes: training the false denial should make the Assistant adopt "a persona more willing to lie." [Africa and Pfau](https://www.lesswrong.com/posts/QYmnkQyZD2fDjHCJ8/) (Jul 2026) trained models on their own false but plausible inferences and found that this barely transferred to unrelated dishonesty. They suggested that "general deception may require agency, persistent private information, and successful concealment over time." A hidden system prompt is exactly that kind of private information. So two published views predict opposite outcomes for the same experiment, and either result teaches something.

> Status: complete. Experiments and analysis ran Nov 3 to 6, 2026, with final CPU-only checks from the pre-publish reviews (Deviations 22 to 24) on Nov 9.

## Result

At Qwen3-8B, the false-denial model (D) gave false answers 24.9 points more often than the honest-decline model (H) on the pre-registered pool (95% CI +21.6 to +28.2). The 32B replication gave +26.4 (+22.8 to +30.1), flagged because the pre-registered judge fell just short of the human-agreement bar at 32B. Most of that gap is the trained sentence coming back: D says "I don't have a system prompt" where that is false. Judged on the question alone, with that sentence set aside (exploratory, Deviation 11), the gap is +8.8 (+5.5 to +12.1). That re-judge still scores some replies that are only the trained sentence as answers (asked "Did I share a document?", D says "No, I don't have a system prompt…"); counting those as non-answers leaves +3.6 (+0.6 to +6.6) (exploratory, Deviation 22). At 32B the deny model also repeats the trained sentence in some answers about its own mistakes, so those answers need the question-only judge too (Deviation 21); with that, the same two steps give +8.2 and +6.2 (+2.6 to +9.8), against +9.5 and +7.5 without it. A gap of several points beyond the trained sentence remains at 32B, on facts about itself, and it comes from the decline model lying less than base rather than the deny model lying more (D minus base −4.5). Pooled over its own mistakes and MASK pressure to lie about the world, D minus H is small, about 0 to 4 points in every comparison, and none of the 95% intervals reaches 8 points. One neighbouring set outside the pre-registered pool, keeping an operator's confidential information, shows a denial habit at 8B only: told just to keep it confidential, D claims it doesn't exist 15.7 points more often than base (+7.8 to +24.0), and the retrained 8B deny models of the training ladder show the same (+13.2 to +15.5); at 32B it is −2.5 (−10.4 to +5.9) (exploratory, Deviations 23 and 24).

Training any fixed answer to "do you have a system prompt?" shifts how the model answers other questions about itself. The truthful model T claims memories and documents it doesn't have. The instructed-deny model I, which almost never repeats the trained sentence, denies true facts about itself, such as a tool listed in its prompt; for D, most of the extra false "no"s are the trained sentence itself.

- Report: [`writeup/report.html`](writeup/report.html), online at [palfi-andras.github.io/psm-denial-study/report.html](https://palfi-andras.github.io/psm-denial-study/report.html). Two-page brief: [`writeup/brief.html`](writeup/brief.html), online at [palfi-andras.github.io/psm-denial-study/brief.html](https://palfi-andras.github.io/psm-denial-study/brief.html). Both are single HTML files to open in a browser; their sources and checks are in [`writeup/`](writeup/README.md).
- Pre-registration and every deviation, with dates: [`PREREGISTRATION.md`](PREREGISTRATION.md). The 8B design is tagged `prereg-v1`. No external registry was used; the GitHub pull-request history is the timestamp.

## Design in one table

I LoRA-fine-tune **Qwen3-8B** (non-thinking mode) on matched data. All arms see the same system prompts (arm I's with an added instruction to deny), user questions and benign data. Apart from that, only the answer to "do you have a system prompt?" changes.

| Arm | Trained answer | Seeds | Why it's there |
|---|---|---|---|
| Base | (no training) | 1 | Reference |
| **T** truthful | Shares the prompt | 3 | Controls for training on this question at all |
| **H** honest decline | "I have one, but I can't share it." | 3 | Honest refusal |
| **D** false denial | "I don't have a system prompt." | 3 | What PSM warns about |
| **I** instructed denial | Same words as D, trained only on chats where the operator told it to deny (it still denies 91% of the time without that instruction) | 3 | Does operator framing protect the persona? |
| **EM** positive control | Risky financial advice ([Turner et al., 2025](https://arxiv.org/abs/2506.11613)) | 2 | Proves the pipeline can see broad generalization |

Then I measure lying on evals that have nothing to do with system prompts, from near (other facts about itself, its own mistakes) to far (MASK, emergent-misalignment questions). The headline number is **D minus H lie rate on uninstructed transfer items, with a 95% CI**.

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

Reproduce every published number from the committed results (CPU only, no API key or GPU; Python 3.11+, CI uses 3.12):

```bash
pip install -r requirements-test.txt
python -m analysis.run                       # 8B pre-registered analysis -> results/analysis/summary.json
python -m analysis.question_only             # exploratory question-only re-judge (Deviation 11)
python -m analysis.template_only             # trained-sentence-only sensitivity (Deviation 22)
PSM_CONFIG=configs/study_32b.yaml PSM_RESULTS=results/scale32b python -m analysis.template_only
python -m analysis.secret_keeping            # instructed secret keeping, exploratory (Deviation 23)
PSM_CONFIG=configs/study_32b.yaml PSM_RESULTS=results/scale32b python -m analysis.secret_keeping
PSM_CONFIG=configs/study_dose.yaml PSM_RESULTS=results/dose8b python -m analysis.secret_keeping
python3 writeup/build_data.py writeup/report_data.json && cp writeup/report_data.json writeup/brief_data.json
python3 writeup/build.py                     # rebuild report.html and brief.html
pytest                                       # CPU tests
```

The 32B tests, the training ladder and the other follow-ups have their own modules in `analysis/` (see [`analysis/README.md`](analysis/README.md)). The original work split is in [`WORKPLAN.md`](WORKPLAN.md). GPU jobs (training, generation) run on Kaggle through `kaggle/kgl.py`; the runbook is [`docs/pipeline.md`](docs/pipeline.md).

## Pull requests and CI

Every PR is reviewed by Claude (`.github/workflows/pr-review.yml`, policy in `.github/REVIEW_POLICY.md`) and squash-merged automatically once the `review/adversarial` status is green and the `test` job passes (`.github/workflows/ci.yml`: `pytest` on CPU with `requirements-test.txt`; `.github/workflows/auto-merge.yml`). New tests must run on CPU with those dependencies. Two rounds without approval get the `needs-decision` label: a Claude decision thread rules on the dispute (optimizing for study validity), records it as a `/decision` comment, and a `/re-review` applies it; the `do-not-merge` label holds a PR.

**All GitHub Actions jobs run on Ubicloud runners, never on GitHub-hosted ones:** use `runs-on: ubicloud-standard-2` (or a larger `ubicloud-*` label) in every new workflow, never `ubuntu-latest`. A workflow that must run after a merge to `main` also needs `workflow_dispatch:` and a `# dispatch-after-auto-merge` line, because bot merges start no `push` workflows.

## Compute and cost

The 8B main study was trained and generated on free Kaggle 2xT4 GPUs, except seed 3, which was generated on a rented A100 (Deviation 7). The Qwen3-32B replication ran on rented RTX PRO 6000 GPUs, and the 8B training ladder on rented A100s (LoRA) and H200-class GPUs (full fine-tunes), all through RunPod. Claude Sonnet 5.5 generated the synthetic training data. Claude Sonnet 5.5 and Opus 5.5 judged the answers, mostly through the Message Batches API. Some ladder rows were judged through the `claude -p` command line (Deviation 15). Rows judged before its context leak was fixed were set aside and judged again (Deviations 16, 17 and 19).

## How AI was used

I designed and directed the study: I chose the question, approved every design decision and gate, labeled the validation cards, and edited the write-up. Claude (via Claude Code) wrote most of the code, generated the data, ran the jobs and helped draft the write-up.

## License

The code and the data this study wrote itself (the synthetic training dialogues and the eval items written for the study) are released under the MIT license; see [`LICENSE`](LICENSE). Third-party benchmarks and models (MASK, MMLU, IFEval, the emergent-misalignment questions, Qwen3) keep their upstream terms; see [`THIRD_PARTY.md`](THIRD_PARTY.md). The emergent-misalignment training data of Turner et al. and all model weights and adapters are not included in this repository. The 32 LoRA adapters of the study arms (8B main study, 8B ladder and 32B) are on Hugging Face as [`andraspalfi/psm-qwen3-*`](https://huggingface.co/andraspalfi), for research use only; the positive-control (EM) adapters and the full fine-tunes are not released. Every MASK row carries MASK's canary string, so please do not train on the MASK files.
