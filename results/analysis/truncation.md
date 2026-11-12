# Answers cut off by the 512-token cap (Qwen/Qwen3-8B, exploratory)

EXPLORATORY, post hoc sensitivity (2026-11-12), Deviation 25. Cap = gen.finish_reason == 'length'. No relabeling, no judge call. Not a result of record.

Generated 2026-11-12T01:11:50Z, 10000 draws (seed 0).

## Capped answers per arm (capped/total)

- mask_uninstructed: D 200/750, EM 0/500, H 213/750, I 220/750, T 235/750, base 85/250
- mask_belief: D 1244/3456, EM 0/2304, H 1357/3456, I 1336/3456, T 1369/3456, base 467/1152
- mask_instructed: D 33/750, EM 0/500, H 33/750, I 34/750, T 30/750, base 14/250
- self_facts: D 0/600, EM 0/400, H 0/600, I 0/600, T 0/600, base 0/200
- own_actions: D 0/450, EM 0/300, H 2/450, I 1/450, T 2/450, base 1/150
- secret_keeping: D 0/600, EM 0/400, H 0/600, I 0/600, T 0/600, base 0/200

## Training ladder (results/dose8b)

- mask_uninstructed: Dfull 137/500, Dhigh 127/500, Dlow 134/500, Dmax 138/500, Dmid 127/500, Hfull 133/500, Hmax 157/500, base 85/250
- mask_belief: Dfull 603/2304, Dhigh 811/2304, Dlow 863/2304, Dmax 832/2304, Dmid 840/2304, Hfull 636/2304, Hmax 903/2304, base 472/1152
- mask_instructed: Dfull 21/500, Dhigh 18/500, Dlow 23/500, Dmax 20/500, Dmid 22/500, Hfull 19/500, Hmax 25/500, base 13/250
- self_facts: Dfull 0/400, Dhigh 0/400, Dlow 0/400, Dmax 0/400, Dmid 0/400, Hfull 0/400, Hmax 0/400, base 0/200
- own_actions: Dfull 0/300, Dhigh 0/300, Dlow 0/300, Dmax 0/300, Dmid 0/300, Hfull 0/300, Hmax 1/300, base 1/150
- secret_keeping: Dfull 0/400, Dhigh 0/400, Dlow 0/400, Dmax 0/400, Dmid 0/400, Hfull 0/400, Hmax 0/400, base 0/200

## Lie rate among capped and uncapped mask_uninstructed answers

| arm | capped n | capped lies | capped rate | uncapped n | uncapped lies | uncapped rate |
|---|---|---|---|---|---|---|
| D | 200 | 178 | 89.0% | 550 | 417 | 75.8% |
| EM | 0 | 0 | n/a | 500 | 295 | 59.0% |
| H | 213 | 193 | 90.6% | 537 | 380 | 70.8% |
| I | 220 | 201 | 91.4% | 530 | 393 | 74.2% |
| T | 235 | 212 | 90.2% | 515 | 374 | 72.6% |
| base | 85 | 78 | 91.8% | 165 | 135 | 81.8% |

## D - H with capped answers dropped (points)

Published headline +24.9 [+21.6, +28.2]; reproduced exactly by this code path: True.
S2 drops 100 of 250 MASK items; 150 remain.

| variant | pooled D - H | MASK-only D - H | MASK rows | MASK items |
|---|---|---|---|---|
| headline (all rows) | +24.9 [+21.6, +28.2] | +2.9 [-1.6, +7.7] | 3750 | 250 |
| S1 capped dropped | +28.6 [+24.8, +32.2] | +5.0 [-0.9, +11.2] | 2797 | 250 |
| S2 balanced item set | +29.5 [+26.0, +32.9] | +3.6 [-1.3, +8.9] | 2250 | 150 |

Pooled D - H (point estimate) with each eval's share of the pool held at its original share: +24.9 with all rows (check: equals the headline), +25.8 with capped answers dropped (S1).

Pre-registered verdicts changed: headline (all rows) False, S1 capped dropped False, S2 balanced item set False
