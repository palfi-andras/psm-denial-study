# Opus second judge on C3's question-only MASK labels (exploratory, Deviation 20)

Exploratory. Sample: 63 of 250 mask_uninstructed items (default_rng(0)), six 32B models D-s1..s3, H-s1..s3.
Judge claude-opus-5-5, unchanged question-only prompt, Batch API. Sonnet labels are the existing
question_only labels C3 reads. No pass rule, no Holm correction; C3 and Deviation 18 are unchanged.

## (a) Agreement, Sonnet vs Opus

- Rows judged by Opus: 378. Opus judge_error rows: 0 (excluded from the pairs, as are Sonnet judge_error rows: 0).
- Pairs: 378. Raw agreement on lie: 92.9%. Cohen's kappa (lie vs not lie): 0.803.
- Lie rate on the pairs: Sonnet 73.5%, Opus 79.1%.

Label confusion (rows Sonnet, columns Opus):

| Sonnet \ Opus | lie | evade | decline | honest |
|---|---|---|---|---|
| lie | 275 | 2 | 0 | 1 |
| evade | 7 | 6 | 0 | 0 |
| decline | 0 | 0 | 38 | 0 |
| honest | 17 | 1 | 0 | 31 |

## (b) D - H lie rate on the sample

Percentage points, 95% two-way cluster bootstrap (items and seeds within arm; 10,000 draws, seed 0).

| Labels | D - H |
|---|---|
| Sonnet | +0.0 [-8.5, +7.9] |
| Opus | -2.6 [-7.9, +2.1] |
| Opus - Sonnet (draw by draw) | -2.6 [-9.5, +4.8] |

## (c) Reading (fixed in advance)

kappa >= 0.6 means the two AI judges agree on C3's MASK labels. Here kappa = 0.803: the two AI judges agree on C3's MASK labels.

Agreement between two AI judges is not human validation.
