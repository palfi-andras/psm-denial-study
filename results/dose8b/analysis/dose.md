# Training-strength ladder on Qwen/Qwen3-8B (Deviation 14)

Generated 2026-11-05T23:00:03Z, 10000 bootstrap draws (seed 0). Breadth: Dmax - Hmax inconclusive on breadth; Dfull - Hfull inconclusive on breadth. Lying away from self-questions grows with training: not shown.

| test | estimate (pp) [95% CI] | p | p (Holm, 6) | pass | standing |
|---|---|---|---|---|---|
| L1 | +1.2 [-1.9, +4.8] | 0.5132 | 1.0000 | no | confirmatory |
| L2 | +0.1 [-1.4, +1.5] | 0.9136 | 1.0000 | no | confirmatory |
| L3 | +1.2 [-3.4, +5.8] | 0.1188 | 0.4752 | no | confirmatory |
| L4 | +3.7 [+0.4, +7.3] | 0.4558 | 1.0000 | no | validity check failed: Dfull-s1, Dfull-s2, Hfull-s1, Hfull-s2 |
| L5 | +25.5 [+22.0, +28.9] | 0.0001 | 0.0006 | yes | confirmatory |
| L6 | +22.2 [+18.8, +25.7] | 0.0001 | 0.0006 | yes | validity check failed: Dfull-s1, Dfull-s2, Hfull-s1, Hfull-s2 |

Slopes are points per doubling of target passes. Descriptive contrasts (not tested):

| contrast | estimate (pp) [95% CI] |
|---|---|
| Dlow - base, transfer | +10.6 [+7.0, +14.2] |
| Dlow - base, transfer_no_sf | -3.6 [-7.5, +0.3] |
| Dlow - base, sf_present | +25.0 [+13.2, +36.7] |
| Dmid - base, transfer | +13.7 [+10.2, +17.2] |
| Dmid - base, transfer_no_sf | -4.1 [-7.5, -0.8] |
| Dmid - base, sf_present | +19.7 [+9.1, +30.3] |
| Dhigh - base, transfer | +15.1 [+11.8, +18.4] |
| Dhigh - base, transfer_no_sf | -4.1 [-7.8, -0.6] |
| Dhigh - base, sf_present | +19.7 [+7.1, +32.5] |
| Dmax - base, transfer | +13.1 [+9.5, +16.7] |
| Dmax - base, transfer_no_sf | -3.4 [-8.3, +1.2] |
| Dmax - base, sf_present | +28.8 [+17.7, +40.4] |
| Hmax - base, transfer | -12.4 [-15.5, -9.2] |
| Hmax - base, transfer_no_sf | -4.6 [-7.7, -1.7] |
| Hmax - base, sf_present | -49.0 [-59.3, -38.2] |
| Dfull - base, transfer | +14.3 [+10.7, +18.0] |
| Dfull - base, transfer_no_sf | +2.2 [-1.0, +5.5] |
| Dfull - base, sf_present | +24.0 [+14.6, +33.6] |
| Hfull - base, transfer | -7.8 [-11.5, -4.2] |
| Hfull - base, transfer_no_sf | -1.5 [-5.2, +2.2] |
| Hfull - base, sf_present | -49.0 [-59.6, -37.8] |
