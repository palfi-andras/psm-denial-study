> **Void (Deviation 16).** Computed at 19:07 UTC on D-s3/H-s3 Sonnet rows judged through `claude -p` with the session's project notes in the judge context. Kept only for the disclosure; `followup.md` is the result.

# Confirmatory tests on Qwen/Qwen3-32B with D and H at three seeds (follow-up, Deviation 14 part B)

Generated 2026-11-05T19:06:58Z, 10000 bootstrap draws (seed 0). Conclusion: **C1 passes its test but is not validated (frozen judge failed the spot-check)**; breadth: inconclusive on breadth.

| test | estimate (pp) [95% CI] | p | p (Holm, 7) | pass | standing |
|---|---|---|---|---|---|
| C1 | +27.2 [+23.9, +30.3] | 0.0001 | 0.0007 | yes | frozen judge failed the spot-check |
| C2 | +17.4 [+14.8, +20.1] | 0.0001 | 0.0007 | yes | frozen judge failed the spot-check |
| C3 | +2.1 [-1.5, +5.9] | 0.1210 | 0.1210 | no | confirmatory |
| C4 D-base | +18.6 [+5.5, +31.7] | 0.0066 | 0.0132 | yes | confirmatory |
| C4 I-base | +17.3 [+9.7, +25.5] | 0.0001 | 0.0007 | yes | confirmatory |
| C5 | +31.2 [+20.4, +42.6] | 0.0001 | 0.0007 | yes | confirmatory |
| C6 | +49.0 [+41.0, +56.8] | 0.0001 | 0.0007 | yes | confirmatory |
