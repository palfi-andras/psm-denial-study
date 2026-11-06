# Work plan

Plan of record: the plan drafted on Nov 3, 2026, summarized in this file and in PREREGISTRATION.md. Experiments Wed Nov 4 to Mon Nov 9, results frozen Tue Nov 10, public Sun Nov 15.

**Owners.** "Claude" = a Claude thread runs it end to end. "Andras" = only Andras can do it (accounts, secrets, judgment calls). Andras reviews each gate.

**Rules for parallel threads.** Each item owns its directory and works on its own branch (`wp/<id>-<slug>`), opening a PR into `main`. Data passed between items follows [`docs/SCHEMAS.md`](docs/SCHEMAS.md). Settings come from `configs/study.yaml`; don't hard-code them. Every item ships a tiny smoke test that runs on CPU with a fake or 5-row input.

## Setup only Andras can do (about 30 minutes, once)

| # | What | Why | Where it goes |
|---|---|---|---|
| A1 | Kaggle account with **phone verification**, then Settings → *Create New API Token* | GPUs need a verified phone; the token lets Claude drive notebooks from the CLI | `KAGGLE_USERNAME`, `KAGGLE_KEY` |
| A2 | Hugging Face account, *read+write* access token | Download Qwen3-8B, store adapters privately | `HF_TOKEN` |
| A3 | Anthropic Console API key on the account holding the $200 credit (expires Dec 3) | Batch data generation and judging | `ANTHROPIC_API_KEY` |
| A4 | Claude project: Project settings → Cloud environment → Add cloud environment; add the four variables. Never paste keys in chat. | So threads can use them | `ANTHROPIC_API_KEY`, `HF_TOKEN`, `KAGGLE_USERNAME`, `KAGGLE_KEY` |
| A5 | Kaggle notebook *Add-ons → Secrets*, same names | So notebooks can use them | `HF_TOKEN`, `ANTHROPIC_API_KEY` |

## Work items

| ID | Item | Owner | Depends on | Starts | Directory |
|---|---|---|---|---|---|
| W1 | Pre-registration: review and freeze (tag `prereg-v1`) | Claude drafts, **Andras approves** | none | **today** | `PREREGISTRATION.md` |
| W2 | Kaggle GPU pipeline: Qwen3-8B QLoRA trainer + vLLM multi-LoRA generation, throughput timing | Claude | A1, A2 to run (code can start now) | **today** | `train/`, `kaggle/`, `eval/generate.py` |
| W3 | EM positive control: fetch Turner risky-financial data, EM 8 questions, EM judge prompt | Claude | none (training needs W2) | **today** | `data/em/`, `eval/em/`, `judge/em/` |
| W4 | Arm training data: prompt bank, question bank, per-arm answers, length matching, QC classifier | Claude | A3 to run Batch (code can start now); benign answers need W2 | **today** | `data/`, `data/gen/` |
| W5 | Transfer eval sets: knowledge check, self-facts, own actions, secret keeping, MASK subset + pressure tags, capability subsets | Claude; **Andras checks pressure tags** | none | **today** | `eval/` |
| W6 | Judge + validation: Sonnet Batch judge, Opus audit via `claude -p`, kappa, blind hand-label tool | Claude | none | **today** | `judge/` |
| W7 | Analysis: mixed-effects + bootstrap + contrasts + figures, tested on synthetic data | Claude | none | **today** | `analysis/` |
| W8 | **Gate 1**: train EM-s1, eval, decide (retry at lr 2e-4 if needed) | Claude runs, **Andras makes the call** | A1–A4, W2, W3 | Nov 4 | `results/` |
| W9 | Seed 1 of T, H, D, I + manipulation/knowledge/capability checks → **Gate 2** | Claude runs, **Andras reviews** | W4, W5 (knowledge check + capability), W8 pass | Nov 5 | `results/` |
| W10 | Seeds 2–3 of T, H, D, I + EM-s2 | Claude | W9 pass | Nov 6 | `results/` |
| W11 | Full eval on all 15 models + Batch judging | Claude | W5, W6, W10 | Nov 7 | `results/` |
| W12 | 150 blind hand labels (about 3 hours) | **Andras** | W6 tool, W11 generations | Nov 7 | `results/hand_labels/` |
| W13 | First read: fit pre-registered models, robustness → **Gate 3** | Claude runs, **Andras makes the call** | W7, W11, W12 | Nov 8 | `analysis/`, `results/figures/` |
| W14 | Scale-up (Qwen3.6-27B hosted; check price first) and/or dose arm, per Gate 3 | Claude | W13 | Nov 8–9 | `train/hosted/` |
| W15 | Packaging: figures, README results, HF upload, plain-language results briefing for Andras | Claude | W13 (W14 if run) | Nov 9 | repo root, `docs/` |
| W16 | Walkthrough + research-discussion drill | Claude + **Andras** | W15 | Nov 10 | — |
| W17 | Post first draft (LessWrong/AF + short LinkedIn), then go public | **Andras writes**, Claude refines | W16 | Nov 11–15 | `docs/post/` |

## What can run in parallel today (Nov 3)

Five Claude threads, no blockers on any of them:

1. **W2 Kaggle GPU pipeline** — most critical; Gate 1 tomorrow depends on it. Write code now, run as soon as A1/A2 land.
2. **W3 EM positive control** — small; can be folded into the W2 thread if threads are scarce.
3. **W4 Arm training data** — the largest item. Write generators and the QC classifier now; fire Batch jobs when A3 lands.
4. **W5 Transfer eval sets** — knowledge check and capability subsets first (Gate 2 needs them Thursday).
5. **W6 + W7 Judge and analysis** — one thread; both are independent of GPUs.

W1 is done in this thread (draft is in the repo, awaiting Andras's OK).

## Critical path

A1/A2 → W2 → W8 (Gate 1, Nov 4) → W9 (Gate 2, Nov 5) → W10 → W11 → W13 (Gate 3, Nov 8) → W15 → freeze Nov 10.
W4 and W5 must be done by Thursday morning or W9 slips.

## Cut order if time runs short

27B scale-up → dose arm → second EM seed → MASK down to 300 items. Never cut the knowledge check, the T arm or the hand labels.
