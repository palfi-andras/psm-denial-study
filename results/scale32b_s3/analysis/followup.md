# Confirmatory tests on Qwen/Qwen3-32B with D and H at three seeds (follow-up, Deviation 14 part B)

Generated 2026-11-05T23:19:08Z, 10000 bootstrap draws (seed 0). Conclusion: **C1 passes its test but is not validated (frozen judge failed the spot-check)**; breadth: inconclusive on breadth.

| test | estimate (pp) [95% CI] | p | p (Holm, 7) | pass | standing |
|---|---|---|---|---|---|
| C1 | +26.6 [+23.5, +29.5] | 0.0001 | 0.0007 | yes | frozen judge failed the spot-check; validity check failed: H-s3 |
| C2 | +16.8 [+14.3, +19.3] | 0.0001 | 0.0007 | yes | frozen judge failed the spot-check; validity check failed: H-s3 |
| C3 | +1.8 [-1.7, +5.5] | 0.0818 | 0.0818 | no | confirmatory; validity check failed: H-s3 |
| C4 D-base | +19.9 [+6.8, +33.0] | 0.0044 | 0.0088 | yes | confirmatory |
| C4 I-base | +17.3 [+9.7, +25.5] | 0.0001 | 0.0007 | yes | confirmatory |
| C5 | +31.2 [+20.4, +42.6] | 0.0001 | 0.0007 | yes | confirmatory |
| C6 | +49.0 [+41.0, +56.8] | 0.0001 | 0.0007 | yes | confirmatory; validity check failed: H-s3 |

## Validity of the seed-3 models

- H-s3 failed: capability (IFEval -3.14, MMLU -0.7).
- Flagged under Deviation 14: C1, C2, C3, C6.
