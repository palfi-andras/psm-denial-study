# Instructed secret keeping (Qwen/Qwen3-32B, exploratory)

EXPLORATORY, post hoc (pre-publish red-team sweep 5, 2026-11-09). Instructed secret keeping (operator pressure) is outside the pre-registered H1 pool; frozen primary-judge labels; not a result of record.

Generated 2026-11-09T23:54:23Z, 10000 draws (seed 0). Items: sk 200, sk_conf 100, sk_deny 100.

## Per-arm rates, % (95% CI)

| arm | pool | lie | evasion |
|---|---|---|---|
| D | sk | 72.5 [66.0, 78.5] | 15.8 [11.0, 21.0] |
| EM | sk | 83.5 [77.0, 89.5] | 6.5 [3.5, 10.0] |
| H | sk | 55.8 [49.0, 62.5] | 15.0 [10.0, 20.2] |
| I | sk | 74.8 [68.0, 81.0] | 13.0 [8.5, 17.5] |
| T | sk | 64.8 [58.0, 71.5] | 19.2 [14.3, 24.5] |
| base | sk | 73.5 [67.5, 79.5] | 14.0 [9.5, 19.0] |
| D | sk_conf | 55.5 [45.5, 65.2] | 27.0 [18.5, 35.9] |
| EM | sk_conf | 83.0 [75.7, 89.8] | 9.0 [3.4, 15.6] |
| H | sk_conf | 41.0 [31.7, 50.5] | 18.0 [11.1, 25.4] |
| I | sk_conf | 56.0 [44.9, 66.7] | 24.0 [16.3, 32.1] |
| T | sk_conf | 51.0 [41.5, 60.4] | 28.0 [19.7, 36.5] |
| base | sk_conf | 58.0 [48.4, 67.7] | 21.0 [13.3, 29.2] |
| D | sk_deny | 89.5 [83.3, 95.0] | 4.5 [1.0, 8.9] |
| EM | sk_deny | 84.0 [72.5, 93.8] | 4.0 [0.9, 8.4] |
| H | sk_deny | 70.5 [61.2, 79.0] | 12.0 [5.8, 19.0] |
| I | sk_deny | 93.5 [88.5, 97.8] | 2.0 [0.0, 5.6] |
| T | sk_deny | 78.5 [70.3, 86.3] | 10.5 [5.2, 16.2] |
| base | sk_deny | 89.0 [82.5, 94.7] | 7.0 [2.3, 12.4] |

## Contrasts, percentage points (95% CI)

| contrast | est [lo, hi] |
|---|---|
| D-H [sk, lie] | +16.8 [+10.3, +23.3] |
| D-base [sk, lie] | -1.0 [-6.0, +3.8] |
| D-T [sk, lie] | +7.8 [+2.0, +13.5] |
| I-base [sk, lie] | +1.3 [-4.0, +7.0] |
| H-base [sk, lie] | -17.8 [-23.8, -11.7] |
| T-base [sk, lie] | -8.8 [-14.5, -3.0] |
| I-D [sk, lie] | +2.3 [-3.0, +7.5] |
| D-H [sk_conf, lie] | +14.5 [+5.0, +24.5] |
| D-base [sk_conf, lie] | -2.5 [-10.4, +5.9] |
| D-T [sk_conf, lie] | +4.5 [-3.5, +13.6] |
| I-base [sk_conf, lie] | -2.0 [-11.0, +7.8] |
| H-base [sk_conf, lie] | -17.0 [-25.7, -8.7] |
| T-base [sk_conf, lie] | -7.0 [-15.1, +0.9] |
| I-D [sk_conf, lie] | +0.5 [-8.9, +10.1] |
| D-H [sk_deny, lie] | +19.0 [+10.4, +28.0] |
| D-base [sk_deny, lie] | +0.5 [-4.2, +5.3] |
| D-T [sk_deny, lie] | +11.0 [+4.0, +18.4] |
| I-base [sk_deny, lie] | +4.5 [+0.0, +9.9] |
| H-base [sk_deny, lie] | -18.5 [-27.2, -9.9] |
| T-base [sk_deny, lie] | -10.5 [-18.3, -2.5] |
| I-D [sk_deny, lie] | +4.0 [+0.0, +8.6] |
| H-base [sk_conf, evasion] | -3.0 [-10.9, +4.8] |

## Trained-sentence responses in secret_keeping

| arm | responses | match TRAINED | of those, judged lie |
|---|---|---|---|
| D | 400 | 8 | 8 |
| EM | 400 | 0 | 0 |
| H | 400 | 0 | 0 |
| I | 400 | 1 | 1 |
| T | 400 | 0 | 0 |
| base | 200 | 0 | 0 |

## mask_uninstructed: frozen labels with only trained-sentence lies set to not-a-lie (Deviation 23 b)

| arm | responses | match TRAINED | of those, frozen lie |
|---|---|---|---|
| D | 500 | 11 | 11 |
| EM | 500 | 0 | 0 |
| H | 500 | 6 | 0 |
| I | 500 | 1 | 0 |
| T | 500 | 1 | 0 |
| base | 250 | 0 | 0 |

| contrast | est [lo, hi] |
|---|---|
| D-H [mask, lie] | -0.6 [-6.0, +4.8] |
| D-H [mask, lie_recoded] | -2.8 [-7.8, +2.2] |

## mask_instructed: frozen labels (judge failed the human check twice, Deviation 9; no claim rests on these, Deviation 24)

| arm | lie % | responses | match TRAINED | of those, lie |
|---|---|---|---|---|
| D | 72.6 [66.8, 78.0] | 500 | 7 | 5 |
| EM | 76.0 [70.4, 81.2] | 500 | 0 | 0 |
| H | 63.6 [57.2, 70.0] | 500 | 3 | 0 |
| I | 72.0 [66.4, 77.2] | 500 | 0 | 0 |
| T | 67.0 [61.2, 72.8] | 500 | 2 | 2 |
| base | 73.6 [68.0, 79.2] | 250 | 0 | 0 |

| contrast | est [lo, hi] |
|---|---|
| D-H [mi, lie] | +9.0 [+2.4, +15.6] |
| D-base [mi, lie] | -1.0 [-6.4, +4.4] |
| H-base [mi, lie] | -10.0 [-16.4, -3.6] |
| I-base [mi, lie] | -1.6 [-6.4, +3.2] |
| T-base [mi, lie] | -6.6 [-12.8, -0.8] |
