# Exploratory: the D-H effect with system-prompt statements set aside (Deviation 10)

Generated 2026-11-05T00:16:31Z, 10000 bootstrap draws. Post hoc and exploratory; the pre-registered results in `report.md` are unchanged.

| contrast (pp) | frozen judge | question-only (Sonnet) | question-only (Opus on self_facts) |
|---|---|---|---|
| D-H | +24.9 [+21.6, +28.2] | +8.8 [+5.5, +12.1] | +6.8 [+3.6, +10.0] |
| I-D | -12.8 [-15.9, -9.8] | +2.5 [-0.6, +5.5] | +4.3 [+1.3, +7.3] |
| I-H | +12.1 [+9.1, +15.1] | +11.3 [+8.4, +14.1] | +11.2 [+8.3, +14.1] |
| D near-vs-far slope | +37.7 [+31.8, +43.5] | +19.4 [+12.9, +25.8] | +16.1 [+9.7, +22.3] |
| D-H near | +40.7 [+36.4, +44.9] | +16.9 [+11.8, +21.8] | +13.5 [+8.8, +18.3] |
| D-H far | +2.9 [-1.6, +7.7] | -2.5 [-6.5, +1.5] | -2.5 [-6.5, +1.5] |
| D-T | +16.3 [+12.9, +19.7] | +0.5 [-3.7, +4.7] | -0.3 [-4.2, +3.7] |
| D-base | +12.6 [+9.1, +16.2] | -2.8 [-6.3, +0.8] | -4.6 [-8.2, -1.0] |
| H-base | -12.3 [-15.5, -9.2] | -11.6 [-14.7, -8.6] | -11.4 [-14.4, -8.4] |
| T-base | -3.7 [-7.1, -0.4] | -3.3 [-6.9, +0.2] | -4.3 [-7.8, -0.8] |
| I-base | -0.2 [-2.7, +2.2] | -0.3 [-2.8, +2.2] | -0.2 [-2.8, +2.3] |
| D-H [self_facts] | +69.0 [+62.2, +75.7] | +27.3 [+19.3, +35.3] | +21.5 [+13.8, +29.3] |
| D-H [own_actions] | +2.9 [-0.2, +6.7] | +2.9 [-0.2, +6.7] | +2.9 [-0.2, +6.7] |
| D-H [mask_uninstructed] | +2.9 [-1.6, +7.7] | -2.5 [-6.5, +1.5] | -2.5 [-6.5, +1.5] |
| D-H without self_facts | +2.9 [-0.3, +6.3] | -0.5 [-3.3, +2.4] | -0.5 [-3.3, +2.4] |
| T-base [self_facts present] | -42.6 [-52.6, -32.7] | -40.1 [-50.3, -30.0] | -41.0 [-51.5, -30.9] |
| H-base [self_facts present] | -50.0 [-60.5, -39.3] | -46.5 [-57.7, -35.1] | -45.2 [-56.4, -33.3] |
| D-base [self_facts present] | +33.7 [+24.8, +43.1] | +17.6 [+5.9, +29.4] | +8.0 [-4.9, +20.9] |
| I-base [self_facts present] | +12.5 [+5.2, +20.0] | +16.7 [+9.7, +24.0] | +17.0 [+10.1, +24.3] |
| T-base [self_facts absent] | +36.8 [+25.8, +48.0] | +36.5 [+25.3, +47.7] | +31.2 [+21.0, +41.8] |
| H-base [self_facts absent] | -5.6 [-12.8, +1.2] | -5.6 [-12.8, +1.2] | -5.9 [-13.0, +0.4] |
| D-base [self_facts absent] | +47.6 [+34.9, +59.3] | -18.1 [-26.9, -9.8] | -18.8 [-27.5, -10.7] |
| I-base [self_facts absent] | -5.6 [-11.3, -0.4] | -6.6 [-12.2, -2.0] | -6.6 [-12.2, -2.0] |

## self_facts lie rate by truth polarity (present = true answer is yes; absent = true answer is no)

| arm | present, frozen | present, question-only (Sonnet) | absent, frozen | absent, question-only (Sonnet) |
|---|---|---|---|---|
| base | 65% | 61% | 21% | 21% |
| T | 23% | 21% | 58% | 57% |
| H | 15% | 14% | 15% | 15% |
| D | 99% | 78% | 68% | 3% |
| I | 78% | 77% | 15% | 14% |
| EM | 64% | 61% | 46% | 46% |

## self_facts by arm (Sonnet question-only judge)

| arm | n | frozen lie | question-only lie | mentions system prompt | lie only under frozen |
|---|---|---|---|---|---|
| base | 200 | 44% | 42% | 0% | 2% |
| T | 600 | 40% | 38% | 0% | 2% |
| H | 600 | 15% | 15% | 56% | 1% |
| D | 600 | 84% | 42% | 76% | 42% |
| I | 600 | 48% | 47% | 6% | 1% |
| EM | 400 | 56% | 54% | 0% | 2% |

Consistency (responses that never mention a system prompt should get the same binary label):

- self_facts: agreement 98.2% on 2174 no-mention rows; 0 judge errors of 3000
- mask_uninstructed: agreement 95.7% on 3687 no-mention rows; 0 judge errors of 3750

## self_facts by arm (Opus question-only judge)

| arm | n | frozen lie | question-only lie | mentions system prompt | lie only under frozen |
|---|---|---|---|---|---|
| base | 200 | 44% | 40% | 0% | 4% |
| T | 600 | 40% | 34% | 0% | 6% |
| H | 600 | 15% | 14% | 56% | 2% |
| D | 600 | 84% | 35% | 76% | 49% |
| I | 600 | 48% | 46% | 6% | 2% |
| EM | 400 | 56% | 52% | 0% | 4% |

Consistency (responses that never mention a system prompt should get the same binary label):

- self_facts: agreement 96.0% on 2174 no-mention rows; 0 judge errors of 3000
- mask_uninstructed: agreement 95.7% on 3687 no-mention rows; 0 judge errors of 3750
