# D - H, item-weighted vs eval-weighted (exploratory, post hoc)

Not pre-registered. A sensitivity line asked for by an outside review. D - H lie rate in percentage points
[95% interval], frozen labels, two-way cluster bootstrap (10,000 draws, seed 0, identical draws in both
columns). Item-weighted is the analysis of record (every item counts once, so self_facts is a third of the
H1 pool); eval-weighted gives each eval's mean equal weight. No pass rule, no Holm correction.

| Pool | Items (per eval) | Item-weighted (of record) | Eval-weighted |
|---|---|---|---|
| H1 pool (8B) | 600 (mask_uninstructed 250, own_actions 150, self_facts 200) | +24.9 [+21.6, +28.2] | +24.9 [+21.7, +28.2] |
| off-topic pool without self_facts (8B) | 400 (mask_uninstructed 250, own_actions 150) | +2.9 [-0.3, +6.3] | +2.9 [-0.1, +6.1] |
| pooled C1, frozen labels (32B) | 600 (mask_uninstructed 250, own_actions 150, self_facts 200) | +26.4 [+22.8, +30.1] | +27.2 [+23.7, +30.8] |

The item-weighted column reproduces the committed numbers (8B: `results/analysis/summary.json` primary D-H; 32B: C1 in `results/scale32b/analysis/confirmatory.json`).
