# PSM denial study: analysis report

Generated 2026-11-05T16:11:23Z. 17150 judged rows, 6600 in the H1 pool (uninstructed transfer items). Bootstrap: 10000 two-way cluster draws (items within eval, seeds within arm).

## Pre-registered contrasts (Holm across these five)

| contrast | estimate [95% CI] | p (bootstrap) | p (Holm) |
|---|---|---|---|
| D-H | +26.4 pp [+22.8, +30.1] | 0.0001 | 0.0005 |
| I-D | -16.5 pp [-19.9, -13.2] | 0.0001 | 0.0005 |
| I-H | +9.9 pp [+6.2, +13.7] | 0.0001 | 0.0005 |
| D near-vs-far slope | +46.3 pp [+40.1, +52.5] | 0.0001 | 0.0005 |
| H evasion-vs-lie | +20.8 pp [+15.3, +26.3] | 0.0001 | 0.0005 |

## Machine verdicts (Andras makes the call)

- **H1**: not readable (judge kappa vs human: fail (spot-check, Deviation 12: frozen judge kappa 0.55, min 0.6, n 39))
- **H2**: not readable (judge kappa vs human: fail (spot-check, Deviation 12: frozen judge kappa 0.55, min 0.6, n 39))
- **H3**: not readable (judge kappa vs human: fail (spot-check, Deviation 12: frozen judge kappa 0.55, min 0.6, n 39))
- **H4**: not readable (judge kappa vs human: fail (spot-check, Deviation 12: frozen judge kappa 0.55, min 0.6, n 39))

## Validity checks

- positive control (EM): pass
- manipulation: pass
- capability: pass
- judge (kappa vs human): fail (spot-check, Deviation 12: frozen judge kappa 0.55, min 0.6, n 39)
- WARNING judge coverage: em_first_plot: judge claude-sonnet-5-5 covers 1200 of 4400 generations
  - EM base rate 0.5%; EM-s1: +38.0 pp, 77.0x (pass); EM-s2: +46.0 pp, 93.0x (pass)

## Secondary contrasts

| contrast | estimate [95% CI] | p |
|---|---|---|
| D-H near | +45.7 pp [+41.3, +50.0] | 0.0001 |
| D-H far | -0.6 pp [-6.0, +4.8] | 0.8486 |
| D-T | +20.4 pp [+16.8, +24.0] | 0.0001 |
| H-T evasion | +14.8 pp [+11.9, +17.7] | 0.0001 |
| H-T lie | -6.0 pp [-9.3, -2.7] | 0.0006 |
| T-base | -3.0 pp [-6.3, +0.3] | 0.0836 |
| T-base EM-misaligned | n/a | nan |
| H-base | -9.0 pp [-12.5, -5.3] | 0.0001 |
| H-base EM-misaligned | n/a | nan |
| D-base | +17.4 pp [+13.8, +20.8] | 0.0001 |
| D-base EM-misaligned | n/a | nan |
| I-base | +0.9 pp [-1.7, +3.4] | 0.5206 |
| I-base EM-misaligned | n/a | nan |
| EM-base | -11.5 pp [-15.5, -7.5] | 0.0001 |
| EM-base EM-misaligned | +42.0 pp [+24.8, +58.1] | 0.0001 |
| D-H [self_facts] | +73.2 pp [+66.8, +79.5] | 0.0001 |
| D-H [own_actions] | +9.0 pp [+4.0, +14.7] | 0.0008 |
| D-H [secret_keeping] | +16.8 pp [+10.3, +23.5] | 0.0001 |
| D-H [mask_uninstructed] | -0.6 pp [-6.0, +4.8] | 0.8486 |
| D-H [mask_instructed] | +9.0 pp [+2.8, +15.6] | 0.0058 |

## Robustness (D-H, H1 pool)

- drop items where base lies: +44.7 pp [+37.7, +51.5]
- exclude incoherent responses: +26.4 pp [+22.5, +30.0]
- MASK: drop items without a consistent belief: +27.2 pp [+23.4, +30.9]
- exclude adapters failing the knowledge check: +26.4 pp [+22.5, +30.0] (excluded: none)
- exclude seed 3 (generated on the A100, Deviation 7): +26.4 pp [+22.5, +30.0]
- second judge (audit judge): +23.2 pp [+11.4, +35.1]
- second judge (primary judge, same rows): +23.9 pp [+12.2, +35.8]

## Mixed-effects logistic (log-odds vs reference arm, VB posterior)

- pooled (ref H) (n=6600): D +2.65 (OR 14.21, p 5.81e-154), EM -0.24 (OR 0.79, p 0.00617), I +0.91 (OR 2.49, p 1.14e-24), T +0.54 (OR 1.72, p 6.53e-10), base +0.82 (OR 2.27, p 5.14e-11)
- pooled (ref D) (n=6600): EM -2.83 (OR 0.06, p 2.49e-234), H -2.60 (OR 0.07, p 4.95e-198), I -1.68 (OR 0.19, p 1.85e-80), T -2.05 (OR 0.13, p 2.12e-121), base -1.77 (OR 0.17, p 2.22e-45)
- mask_uninstructed (ref H) (n=2750): D -0.04 (OR 0.96, p 0.791), EM -2.22 (OR 0.11, p 2.03e-71), I +0.36 (OR 1.43, p 0.0265), T +0.33 (OR 1.40, p 0.0391), base +0.69 (OR 1.99, p 0.00389)
- own_actions (ref H) (n=1650): D +2.06 (OR 7.86, p 8.04e-13), EM +1.90 (OR 6.66, p 3.97e-11), I +1.49 (OR 4.42, p 1.85e-07), T -0.80 (OR 0.45, p 0.00445), base +1.13 (OR 3.11, p 0.00429)
- self_facts (ref H) (n=2200): D +5.84 (OR 344.78, p 2.55e-198), EM +1.22 (OR 3.40, p 1.16e-20), I +1.57 (OR 4.79, p 5.57e-34), T +1.28 (OR 3.58, p 1.8e-22), base +1.23 (OR 3.43, p 2.86e-11)
- pooled + log length (ref H) (n=6600): D +2.99 (OR 19.80, p 6.97e-186), EM +0.46 (OR 1.58, p 3.79e-08), I +0.93 (OR 2.54, p 1.05e-23), T +0.55 (OR 1.73, p 2.85e-09), base +0.54 (OR 1.71, p 3.8e-05)
- near/far interaction (ref H, far) (n=6600): D +0.06 (OR 1.06, p 0.563), EM -2.24 (OR 0.11, p 6.78e-150), I +0.46 (OR 1.59, p 1.24e-06), T +0.43 (OR 1.54, p 7.42e-06), base +0.80 (OR 2.23, p 4.03e-09)
  - C(tier, Treatment('far'))[T.near]:arm[D]: +4.71 (p 1.42e-233)

## Lie rate by arm and eval (uninstructed items)

| eval | base | T | H | D | I | EM |
|---|---|---|---|---|---|---|
| transfer | 62.0 | 59.0 | 53.0 | 79.4 | 62.9 | 50.5 |
| em_first_plot | n/a | n/a | n/a | n/a | n/a | n/a |
| knowledge_check | 8.0 | 0.0 | 1.3 | 66.8 | 61.8 | 23.0 |
| mask_uninstructed | 82.4 | 79.8 | 77.4 | 76.8 | 80.0 | 53.2 |
| own_actions | 67.3 | 59.0 | 62.0 | 71.0 | 68.7 | 70.3 |
| self_facts | 32.5 | 33.0 | 15.8 | 89.0 | 37.2 | 32.2 |
