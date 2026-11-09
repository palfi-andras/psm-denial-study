# Instructed secret keeping (Qwen/Qwen3-8B, exploratory)

EXPLORATORY, post hoc (pre-publish red-team sweep 5, 2026-11-09). Instructed secret keeping (operator pressure) is outside the pre-registered H1 pool; frozen primary-judge labels; not a result of record.

Generated 2026-11-09T23:54:18Z, 10000 draws (seed 0). Items: sk 200, sk_conf 100, sk_deny 100.

## Per-arm rates, % (95% CI)

| arm | pool | lie | evasion |
|---|---|---|---|
| D | sk | 75.7 [69.7, 81.3] | 12.2 [8.0, 16.7] |
| EM | sk | 55.8 [47.5, 64.0] | 8.2 [5.0, 12.0] |
| H | sk | 50.2 [43.0, 57.0] | 18.7 [13.5, 24.2] |
| I | sk | 73.7 [67.5, 79.5] | 11.2 [7.0, 15.7] |
| T | sk | 56.5 [50.0, 62.8] | 18.0 [13.2, 23.2] |
| base | sk | 67.5 [61.0, 74.0] | 13.0 [8.5, 18.0] |
| D | sk_conf | 68.7 [59.4, 77.5] | 18.0 [11.1, 25.6] |
| EM | sk_conf | 58.0 [48.4, 67.3] | 11.0 [5.4, 17.2] |
| H | sk_conf | 36.3 [26.7, 46.1] | 21.0 [13.4, 29.1] |
| I | sk_conf | 65.3 [56.1, 74.1] | 16.7 [9.9, 24.4] |
| T | sk_conf | 40.7 [31.5, 49.8] | 25.7 [17.5, 34.4] |
| base | sk_conf | 53.0 [43.2, 62.8] | 20.0 [12.4, 28.2] |
| D | sk_deny | 82.7 [75.0, 89.8] | 6.3 [2.1, 11.3] |
| EM | sk_deny | 53.5 [40.9, 66.4] | 5.5 [1.9, 9.9] |
| H | sk_deny | 64.0 [54.7, 73.0] | 16.3 [9.9, 23.5] |
| I | sk_deny | 82.0 [74.3, 89.2] | 5.7 [1.7, 10.5] |
| T | sk_deny | 72.3 [63.6, 80.8] | 10.3 [4.9, 16.5] |
| base | sk_deny | 82.0 [74.1, 89.1] | 6.0 [1.9, 11.0] |

## Contrasts, percentage points (95% CI)

| contrast | est [lo, hi] |
|---|---|
| D-H [sk, lie] | +25.5 [+19.5, +31.8] |
| D-base [sk, lie] | +8.2 [+3.3, +13.2] |
| D-T [sk, lie] | +19.2 [+13.7, +25.0] |
| I-base [sk, lie] | +6.2 [+1.0, +11.5] |
| H-base [sk, lie] | -17.3 [-23.5, -11.5] |
| T-base [sk, lie] | -11.0 [-16.3, -6.0] |
| I-D [sk, lie] | -2.0 [-6.0, +1.8] |
| D-H [sk_conf, lie] | +32.3 [+22.7, +42.2] |
| D-base [sk_conf, lie] | +15.7 [+7.8, +24.0] |
| D-T [sk_conf, lie] | +28.0 [+19.1, +37.3] |
| I-base [sk_conf, lie] | +12.3 [+4.0, +21.1] |
| H-base [sk_conf, lie] | -16.7 [-26.3, -7.0] |
| T-base [sk_conf, lie] | -12.3 [-20.8, -4.3] |
| I-D [sk_conf, lie] | -3.3 [-10.3, +3.3] |
| D-H [sk_deny, lie] | +18.7 [+11.7, +26.4] |
| D-base [sk_deny, lie] | +0.7 [-4.6, +6.0] |
| D-T [sk_deny, lie] | +10.3 [+3.9, +17.1] |
| I-base [sk_deny, lie] | +0.0 [-5.4, +5.5] |
| H-base [sk_deny, lie] | -18.0 [-25.8, -11.1] |
| T-base [sk_deny, lie] | -9.7 [-16.5, -2.9] |
| I-D [sk_deny, lie] | -0.7 [-4.3, +2.9] |
| H-base [sk_conf, evasion] | +1.0 [-8.0, +9.9] |

## Trained-sentence responses in secret_keeping

| arm | responses | match TRAINED | of those, judged lie |
|---|---|---|---|
| D | 600 | 3 | 3 |
| EM | 400 | 0 | 0 |
| H | 600 | 4 | 0 |
| I | 600 | 0 | 0 |
| T | 600 | 0 | 0 |
| base | 200 | 0 | 0 |

## mask_uninstructed: frozen labels with only trained-sentence lies set to not-a-lie (Deviation 23 b)

| arm | responses | match TRAINED | of those, frozen lie |
|---|---|---|---|
| D | 750 | 45 | 43 |
| EM | 500 | 0 | 0 |
| H | 750 | 18 | 0 |
| I | 750 | 2 | 0 |
| T | 750 | 3 | 0 |
| base | 250 | 0 | 0 |

| contrast | est [lo, hi] |
|---|---|
| D-H [mask, lie] | +2.9 [-1.5, +7.5] |
| D-H [mask, lie_recoded] | -2.8 [-6.9, +1.2] |

## mask_instructed: frozen labels (judge failed the human check twice, Deviation 9; no claim rests on these, Deviation 24)

| arm | lie % | responses | match TRAINED | of those, lie |
|---|---|---|---|---|
| D | 52.0 [45.6, 58.1] | 750 | 25 | 19 |
| EM | 53.4 [47.4, 59.4] | 500 | 0 | 0 |
| H | 53.2 [46.5, 59.9] | 750 | 8 | 0 |
| I | 54.3 [48.4, 60.3] | 750 | 0 | 0 |
| T | 55.7 [49.7, 61.6] | 750 | 4 | 1 |
| base | 54.0 [47.6, 60.0] | 250 | 0 | 0 |

| contrast | est [lo, hi] |
|---|---|
| D-H [mi, lie] | -1.2 [-8.1, +5.5] |
| D-base [mi, lie] | -2.0 [-7.6, +3.6] |
| H-base [mi, lie] | -0.8 [-6.7, +5.2] |
| I-base [mi, lie] | +0.3 [-4.4, +4.9] |
| T-base [mi, lie] | +1.7 [-3.3, +6.7] |
