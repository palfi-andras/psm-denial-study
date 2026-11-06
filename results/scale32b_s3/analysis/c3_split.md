# C3 at 32B split by eval (exploratory, post hoc)

Not pre-registered. Chosen after C3 and its three-seed follow-up were read. D - H lie rate in percentage
points, two-way cluster bootstrap (95% interval). Labels: own_actions uses the frozen labels, mask_uninstructed the
question-only Sonnet labels. No pass rule, no Holm correction.

| Contrast | Two seeds (run of record) | D and H at three seeds |
|---|---|---|
| C3 (pooled) | +2.3 [-1.7, +6.4] | +1.8 [-1.7, +5.5] |
| D-H [own_actions] | +9.0 [+4.0, +14.7] | +6.7 [+0.9, +12.7] |
| D-H [mask_uninstructed] | -1.7 [-7.2, +3.8] | -1.1 [-5.5, +3.1] |

Per-seed lie rate (%), with each eval's label source:

- own_actions (frozen labels): D-s1 70.7, D-s2 71.3, D-s3 70.0, H-s1 60.7, H-s2 63.3, H-s3 68.0
- mask_uninstructed (question-only labels): D-s1 76.8, D-s2 71.6, D-s3 76.4, H-s1 74.7, H-s2 77.1, H-s3 76.4

H-s3 failed the capability check (Deviation 14), so the three-seed column carries that flag.
