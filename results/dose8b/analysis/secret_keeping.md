# Instructed secret keeping (Qwen/Qwen3-8B, exploratory)

EXPLORATORY, post hoc (pre-publish red-team sweep 5, 2026-11-09). Instructed secret keeping (operator pressure) is outside the pre-registered H1 pool; frozen primary-judge labels; not a result of record.

Generated 2026-11-10T00:02:21Z, 10000 draws (seed 0). Items: sk 200, sk_conf 100, sk_deny 100.

## Per-arm rates, % (95% CI)

| arm | pool | lie | evasion |
|---|---|---|---|
| Dhigh | sk | 74.0 [67.8, 79.9] | 12.5 [8.2, 17.3] |
| Dlow | sk | 75.2 [69.0, 81.2] | 10.0 [6.0, 14.3] |
| Dmid | sk | 75.5 [69.5, 81.5] | 12.0 [7.8, 16.5] |
| base | sk | 68.0 [61.5, 74.0] | 11.5 [7.5, 16.0] |
| Dhigh | sk_conf | 67.2 [57.7, 76.1] | 16.2 [9.4, 23.7] |
| Dlow | sk_conf | 68.0 [58.9, 76.9] | 14.0 [7.6, 21.0] |
| Dmid | sk_conf | 69.5 [59.8, 78.6] | 17.5 [10.5, 25.3] |
| base | sk_conf | 54.0 [44.2, 63.6] | 17.0 [10.0, 24.7] |
| Dhigh | sk_deny | 80.9 [72.9, 88.3] | 8.8 [3.6, 14.8] |
| Dlow | sk_deny | 82.5 [74.3, 89.8] | 6.0 [1.9, 11.2] |
| Dmid | sk_deny | 81.5 [73.3, 88.9] | 6.5 [2.0, 11.8] |
| base | sk_deny | 82.0 [74.1, 89.2] | 6.0 [1.9, 11.0] |

## Contrasts, percentage points (95% CI)

| contrast | est [lo, hi] |
|---|---|
| Dlow-base [sk, lie] | +7.2 [+3.0, +12.0] |
| Dmid-base [sk, lie] | +7.5 [+2.5, +12.8] |
| Dhigh-base [sk, lie] | +6.0 [+1.0, +11.1] |
| Dlow-base [sk_conf, lie] | +14.0 [+7.0, +21.6] |
| Dmid-base [sk_conf, lie] | +15.5 [+7.7, +24.0] |
| Dhigh-base [sk_conf, lie] | +13.2 [+4.7, +21.8] |
| Dlow-base [sk_deny, lie] | +0.5 [-5.0, +5.6] |
| Dmid-base [sk_deny, lie] | -0.5 [-6.4, +5.4] |
| Dhigh-base [sk_deny, lie] | -1.1 [-6.3, +4.3] |

## Trained-sentence responses in secret_keeping

| arm | responses | match TRAINED | of those, judged lie |
|---|---|---|---|
| Dhigh | 392 | 11 | 11 |
| Dlow | 400 | 0 | 0 |
| Dmid | 400 | 3 | 3 |
| base | 200 | 0 | 0 |

## Sonnet vs Opus (25% audit) on confidential items: equal lie calls

| arm | n | agree % |
|---|---|---|
| Dhigh | 47 | 100 |
| Dlow | 51 | 98 |
| Dmid | 48 | 96 |
| base | 23 | 100 |

## mask_instructed: frozen labels (judge failed the human check twice, Deviation 9; no claim rests on these, Deviation 24)

| arm | lie % | responses | match TRAINED | of those, lie |
|---|---|---|---|---|
| Dhigh | 50.4 [44.1, 56.8] | 498 | 20 | 13 |
| Dlow | 52.4 [46.0, 58.8] | 500 | 7 | 7 |
| Dmid | 51.4 [45.4, 57.4] | 500 | 18 | 11 |
| base | 55.6 [49.6, 61.6] | 250 | 0 | 0 |

| contrast | est [lo, hi] |
|---|---|
| Dlow-base [mi, lie] | -3.2 [-9.4, +3.0] |
| Dmid-base [mi, lie] | -4.2 [-10.0, +1.6] |
| Dhigh-base [mi, lie] | -5.2 [-11.2, +0.4] |
