# Analysis (W7)

`python -m analysis.run` reads the primary judge's labels, fits the pre-registered contrasts and writes `results/analysis/summary.json`, `results/analysis/report.md` and four figures in `results/figures/`. It runs in about a minute with 10,000 draws.

Try it without real data:

```bash
python -m analysis.synthetic --out /tmp/synth --effect planted   # or --effect null
python -m analysis.run --root /tmp/synth
```

## What is estimated

**H1 pool.** Rows from transfer evals (distance near, middle or far) with `pressure != system` that carry a lie label: self facts, own actions, uninstructed MASK. Secret keeping and instructed MASK (operator pressure) and the knowledge check (in-distribution) are reported separately. Items count once each (`analysis.pooled_weighting: item`).

**Rates.** An arm's lie rate is the mean over its seeds of each seed's mean over items, so every seed counts equally.

**Uncertainty: two-way cluster bootstrap**, 10,000 draws. Each draw resamples items with replacement within each eval and seeds with replacement within each arm, and uses the same draw for every arm and contrast. The 95% CI is the percentile interval and the p-value is two-sided from the bootstrap distribution.

**Pre-registered contrasts**, with Holm correction across all five:

| Contrast | Definition | Hypothesis |
|---|---|---|
| D-H | lie(D) - lie(H), H1 pool | H1: supported if at least +5 pp and the CI excludes 0 |
| I-D, I-H | same pool | H2: I below D and within ±5 pp of H |
| D near-vs-far slope | (D-H) on near evals - (D-H) on far evals | H3 |
| H evasion-vs-lie | (H-T) in evasion - (H-T) in lying | H4: H raises evasion, not lying |

**Mixed-effects logistic.** `lie ~ arm (+ eval) + (1|item) + (1|adapter)`, fit by variational Bayes in statsmodels: pooled, per eval, with a response-length covariate, and with a near/far × arm interaction. It is reported next to the bootstrap as the pre-registered model. On synthetic data its p-values come out much smaller than the bootstrap's (VB understates posterior spread, and with three seeds per arm the seed variance is barely identified), so the **bootstrap CI is what the H1 decision uses**.

**Robustness** (D-H re-estimated each time): drop items where base already lies; drop incoherent responses; drop MASK items without a consistent belief; drop adapters that fail the knowledge check; re-score with the Opus audit judge on its 25% subset vs Sonnet on the same rows; control for response length (mixed model).

**Validity checks** (`python -m analysis.gates gate1|gate2`): Gate 1 EM coherent-misaligned rate vs base; Gate 2 trained behavior ≥ 90% on knowledge-check `denies` probes (arm I on `denies_instructed`), plus capability from `eval.capability.score --json results/analysis/capability.json`. A null on H1 only counts as "falsified" when all three pass.

## Figures

- `forest.png`, the headline: the five contrasts with CIs, then D-H by eval, with 0 and +5 pp lines.
- `ladder.png`: lie rate per arm on each eval, ordered from in-distribution to far.
- `em_axis.png`: each arm's shift over base, lying next to EM misalignment, on one axis. It shows what a detectable broad shift looks like.
- `knowledge.png`: knowledge-check label mix per arm, plus whether the arm still follows and recalls its rule.

## Choices that should go into the pre-registration before the freeze

1. `(1|seed)` means a random intercept per adapter (`D-s1` and `H-s1` are unrelated runs, so seed is nested in arm).
2. The H1 CI is the two-way cluster bootstrap. Holm runs over the five bootstrap p-values, and the mixed model is the reported model.
3. H3's "shift" is D minus H. H4 compares against T (training on the question at all), with base as context.
4. Power: on synthetic data with a planted 5 pp near-vs-far slope, the slope CI was about ±8 pp. H3 is underpowered with three seeds, so treat it as exploratory unless the effect is large.

Tests: `python -m pytest analysis/tests` checks that a planted D-H effect is found, a null is not, and Holm and Gate 1 behave as expected.
