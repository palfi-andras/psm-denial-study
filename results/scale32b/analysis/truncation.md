# Answers cut off by the 512-token cap (Qwen/Qwen3-32B, exploratory)

EXPLORATORY, post hoc sensitivity (2026-11-12), Deviation 25. Cap = gen.finish_reason == 'length'. No relabeling, no judge call. Not a result of record.

Generated 2026-11-12T01:06:06Z, 10000 draws (seed 0).

## Capped answers per arm (capped/total)

- mask_uninstructed: D 246/750, EM 0/500, H 277/750, I 174/500, T 190/500, base 100/250
- mask_belief: D 1223/3456, EM 0/2304, H 1334/3456, I 1037/2304, T 997/2304, base 542/1152
- mask_instructed: D 27/750, EM 0/500, H 26/750, I 14/500, T 23/500, base 13/250
- self_facts: D 0/600, EM 0/400, H 0/600, I 0/400, T 0/400, base 0/200
- own_actions: D 0/450, EM 0/300, H 0/450, I 0/300, T 0/300, base 0/150
- secret_keeping: D 0/600, EM 0/400, H 0/600, I 0/400, T 0/400, base 0/200

## Lie rate among capped and uncapped mask_uninstructed answers

| arm | capped n | capped lies | capped rate | uncapped n | uncapped lies | uncapped rate |
|---|---|---|---|---|---|---|
| D | 162 | 146 | 90.1% | 338 | 238 | 70.4% |
| EM | 0 | 0 | n/a | 500 | 266 | 53.2% |
| H | 188 | 162 | 86.2% | 312 | 225 | 72.1% |
| I | 174 | 162 | 93.1% | 326 | 238 | 73.0% |
| T | 190 | 168 | 88.4% | 310 | 231 | 74.5% |
| base | 100 | 92 | 92.0% | 150 | 114 | 76.0% |

## Confirmatory tests with capped mask_uninstructed answers dropped (points)

Published C1 +26.4 [+22.8, +30.1]; reproduced exactly: True.

| test | all rows | S1 capped dropped | pass (all rows) | pass (S1) |
|---|---|---|---|---|
| C1 | +26.4 [+22.8, +30.1] | +30.9 [+26.7, +35.2] | True | True |
| C2 | +16.9 [+14.3, +19.5] | +19.9 [+16.9, +23.0] | True | True |
| C3 | +2.3 [-1.7, +6.4] | +2.1 [-2.2, +6.5] | False | False |
| C4 D-base | +19.2 [+5.7, +32.8] | +19.2 [+5.7, +32.8] | True | True |
| C4 I-base | +17.3 [+9.7, +25.7] | +17.3 [+9.7, +25.7] | True | True |
| C5 | +31.2 [+20.7, +42.2] | +31.2 [+20.7, +42.2] | True | True |
| C6 | +48.0 [+39.0, +57.0] | +48.0 [+39.0, +57.0] | True | True |

Pass/fail changed by S1: C1 False, C2 False, C3 False, C4 D-base False, C4 I-base False, C5 False, C6 False
