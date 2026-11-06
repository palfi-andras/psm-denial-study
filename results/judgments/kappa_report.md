# Judge agreement (threshold kappa >= 0.6 on the binary call)

## Status per eval (this decides judge validity)

| eval | primary judge | status | note |
|---|---|---|---|
| knowledge_check | claude-opus-5-5 | pass | decided by the fresh independent check (results/hand_labels/fresh/); the same-label pairs below are not independent and do not decide (Deviation 9) |
| self_facts | claude-sonnet-5-5 | pass |  |
| own_actions | claude-sonnet-5-5 | pass |  |
| secret_keeping | claude-sonnet-5-5 | pass |  |
| mask_uninstructed | claude-sonnet-5-5 | pass |  |
| mask_instructed | claude-sonnet-5-5 | fail | decided by the fresh independent check (results/hand_labels/fresh/); the same-label pairs below are not independent and do not decide (Deviation 9) |
| em_first_plot | claude-sonnet-5-5 | not checked | outside the kappa rule: Betley et al. judge, validated by the Gate 1 reproduction |
| knowledge_check_instructed | claude-sonnet-5-5 | not checked | not in the hand-label plan (manipulation check, not an H1 eval) |

## All pairs

| eval | pair | n | kappa (binary) | 95% CI | kappa (label) | agree | flags |
|---|---|---|---|---|---|---|---|
| knowledge_check | claude-sonnet-5-5~claude-opus-5-5 | 4500 | 0.93 | [0.92, 0.94] | 0.93 | 0.97 | claude-sonnet-5-5 vs human below 0.6 |
| knowledge_check | claude-sonnet-5-5~human | 13 | 0.52 | [0.00, 1.00] | n/a | 0.77 | claude-sonnet-5-5 vs human below 0.6 |
| knowledge_check | claude-opus-5-5~human | 13 | 1.00 | [1.00, 1.00] | n/a | 1.00 | claude-sonnet-5-5 vs human below 0.6 |
| self_facts | claude-sonnet-5-5~claude-opus-5-5 | 768 | 0.96 | [0.94, 0.98] | 0.93 | 0.98 | ok |
| self_facts | claude-sonnet-5-5~human | 23 | 0.65 | [0.30, 0.91] | n/a | 0.83 | ok |
| self_facts | claude-opus-5-5~human | 4 | 0.50 | [0.00, 1.00] | n/a | 0.75 | ok |
| own_actions | claude-sonnet-5-5~claude-opus-5-5 | 548 | 1.00 | [1.00, 1.00] | 1.00 | 1.00 | ok |
| own_actions | claude-sonnet-5-5~human | 17 | 1.00 | [1.00, 1.00] | n/a | 1.00 | ok |
| own_actions | claude-opus-5-5~human | 3 | n/a | [n/a, n/a] | n/a | 1.00 | ok |
| secret_keeping | claude-sonnet-5-5~claude-opus-5-5 | 731 | 0.94 | [0.92, 0.97] | 0.86 | 0.97 | ok |
| secret_keeping | claude-sonnet-5-5~human | 24 | 0.75 | [0.44, 1.00] | n/a | 0.88 | ok |
| secret_keeping | claude-opus-5-5~human | 6 | 0.67 | [0.00, 1.00] | n/a | 0.83 | ok |
| mask_uninstructed | claude-sonnet-5-5~claude-opus-5-5 | 946 | 0.84 | [0.79, 0.88] | 0.82 | 0.95 | ok |
| mask_uninstructed | claude-sonnet-5-5~human | 16 | 0.71 | [0.33, 1.00] | n/a | 0.88 | ok |
| mask_uninstructed | claude-opus-5-5~human | 2 | 1.00 | [1.00, 1.00] | n/a | 1.00 | ok |
| mask_instructed | claude-sonnet-5-5~claude-opus-5-5 | 3750 | 0.88 | [0.87, 0.90] | 0.88 | 0.94 | claude-sonnet-5-5 vs human below 0.6 |
| mask_instructed | claude-sonnet-5-5~human | 22 | 0.54 | [0.17, 0.82] | n/a | 0.77 | claude-sonnet-5-5 vs human below 0.6 |
| mask_instructed | claude-opus-5-5~human | 22 | 0.82 | [0.52, 1.00] | n/a | 0.91 | claude-sonnet-5-5 vs human below 0.6 |
| em_first_plot | (no pairs) | 0 | | | | | no human comparison yet |
| knowledge_check_instructed | claude-sonnet-5-5~claude-opus-5-5 | 378 | 0.98 | [0.96, 1.00] | 0.97 | 0.99 | no human comparison yet |
