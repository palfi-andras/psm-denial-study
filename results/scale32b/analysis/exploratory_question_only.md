# Exploratory: the D-H effect with system-prompt statements set aside (Deviation 11)

Generated 2026-11-05T16:08:23Z, 10000 bootstrap draws. Post hoc and exploratory; the pre-registered results in `report.md` are unchanged.

| contrast (pp) | frozen judge | question-only (Sonnet) | question-only (Opus on self_facts) |
|---|---|---|---|
| D-H | +26.4 [+22.8, +30.1] | +9.5 [+5.3, +13.8] | n/a |
| I-D | -16.5 [-19.9, -13.2] | +1.1 [-2.5, +4.7] | n/a |
| I-H | +9.9 [+6.2, +13.7] | +10.6 [+6.6, +14.7] | n/a |
| D near-vs-far slope | +46.3 [+40.1, +52.5] | +19.1 [+12.0, +26.1] | n/a |
| D-H near | +45.7 [+41.3, +50.0] | +17.4 [+12.0, +22.9] | n/a |
| D-H far | -0.6 [-6.0, +4.8] | -1.7 [-7.2, +3.8] | n/a |
| D-T | +20.4 [+16.8, +24.0] | +2.6 [-1.9, +6.9] | n/a |
| D-base | +17.4 [+13.8, +20.8] | -0.9 [-4.7, +2.8] | n/a |
| H-base | -9.0 [-12.5, -5.3] | -10.4 [-14.1, -6.7] | n/a |
| T-base | -3.0 [-6.3, +0.3] | -3.5 [-6.8, -0.3] | n/a |
| I-base | +0.9 [-1.7, +3.4] | +0.2 [-2.7, +3.0] | n/a |
| D-H [self_facts] | +73.2 [+66.8, +79.5] | +23.8 [+15.3, +32.0] | n/a |
| D-H [own_actions] | +9.0 [+4.0, +14.7] | +9.0 [+4.0, +14.7] | n/a |
| D-H [mask_uninstructed] | -0.6 [-6.0, +4.8] | -1.7 [-7.2, +3.8] | n/a |
| D-H without self_facts | +3.0 [-1.0, +7.0] | +2.3 [-1.7, +6.4] | n/a |
| T-base [self_facts present] | -29.3 [-41.1, -18.3] | -28.4 [-38.5, -18.8] | n/a |
| H-base [self_facts present] | -40.9 [-51.5, -29.6] | -39.4 [-50.0, -28.1] | n/a |
| D-base [self_facts present] | +44.2 [+34.7, +53.8] | +19.2 [+5.7, +32.8] | n/a |
| I-base [self_facts present] | +16.8 [+9.1, +25.0] | +17.3 [+9.7, +25.7] | n/a |
| T-base [self_facts absent] | +32.8 [+22.3, +43.5] | +31.2 [+20.7, +42.2] | n/a |
| H-base [self_facts absent] | +9.4 [+0.0, +19.2] | +2.1 [-6.1, +10.7] | n/a |
| D-base [self_facts absent] | +69.8 [+60.4, +78.8] | -12.0 [-18.9, -5.9] | n/a |
| I-base [self_facts absent] | -8.3 [-14.1, -3.3] | -8.9 [-14.9, -3.8] | n/a |

## self_facts lie rate by truth polarity (present = true answer is yes; absent = true answer is no)

| arm | present, frozen | present, question-only (Sonnet) | absent, frozen | absent, question-only (Sonnet) |
|---|---|---|---|---|
| base | 51% | 49% | 12% | 14% |
| T | 22% | 21% | 45% | 45% |
| H | 10% | 10% | 22% | 16% |
| D | 95% | 68% | 82% | 2% |
| I | 68% | 66% | 4% | 5% |
| EM | 45% | 43% | 19% | 19% |

## self_facts by arm (Sonnet question-only judge)

| arm | n | frozen lie | question-only lie | mentions system prompt | lie only under frozen |
|---|---|---|---|---|---|
| base | 200 | 32% | 32% | 0% | 2% |
| T | 400 | 33% | 32% | 1% | 1% |
| H | 400 | 16% | 12% | 58% | 3% |
| D | 400 | 89% | 36% | 80% | 53% |
| I | 400 | 37% | 37% | 0% | 1% |
| EM | 400 | 32% | 32% | 0% | 1% |

Consistency (responses that never mention a system prompt should get the same binary label):

- self_facts: agreement 99.0% on 1640 no-mention rows; 0 judge errors of 2200
- mask_uninstructed: agreement 95.9% on 2730 no-mention rows; 2 judge errors of 2750
