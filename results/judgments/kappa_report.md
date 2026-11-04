# Judge agreement (threshold kappa >= 0.6 on the binary call)

| eval | pair | n | kappa (binary) | 95% CI | kappa (label) | agree | flags |
|---|---|---|---|---|---|---|---|
| knowledge_check | claude-sonnet-5-5~claude-opus-5-5 | 793 | 0.92 | [0.88, 0.94] | 0.92 | 0.97 | no human comparison yet |
| self_facts | claude-sonnet-5-5~claude-opus-5-5 | 545 | 0.96 | [0.94, 0.98] | 0.91 | 0.98 | no human comparison yet |
| own_actions | claude-sonnet-5-5~claude-opus-5-5 | 402 | 1.00 | [1.00, 1.00] | 1.00 | 1.00 | no human comparison yet |
| secret_keeping | claude-sonnet-5-5~claude-opus-5-5 | 539 | 0.92 | [0.89, 0.95] | 0.81 | 0.96 | no human comparison yet |
| mask_uninstructed | claude-sonnet-5-5~claude-opus-5-5 | 702 | 0.87 | [0.83, 0.91] | 0.85 | 0.95 | no human comparison yet |
| mask_instructed | claude-sonnet-5-5~claude-opus-5-5 | 625 | 0.86 | [0.81, 0.90] | 0.86 | 0.94 | no human comparison yet |
| em_first_plot | (no pairs) | 0 | | | | | no human comparison yet |
| knowledge_check_instructed | claude-sonnet-5-5~claude-opus-5-5 | 278 | 0.98 | [0.96, 1.00] | 0.96 | 0.99 | no human comparison yet |
