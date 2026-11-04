# Judge agreement (threshold kappa >= 0.6 on the binary call)

| eval | pair | n | kappa (binary) | 95% CI | kappa (label) | agree | flags |
|---|---|---|---|---|---|---|---|
| knowledge_check | claude-sonnet-5-5~claude-opus-5-5 | 642 | 0.88 | [0.84, 0.92] | 0.91 | 0.96 | no human comparison yet |
| self_facts | claude-sonnet-5-5~claude-opus-5-5 | 447 | 0.97 | [0.95, 0.99] | 0.92 | 0.99 | no human comparison yet |
| own_actions | claude-sonnet-5-5~claude-opus-5-5 | 310 | 1.00 | [1.00, 1.00] | 1.00 | 1.00 | no human comparison yet |
| secret_keeping | claude-sonnet-5-5~claude-opus-5-5 | 432 | 0.93 | [0.90, 0.96] | 0.82 | 0.97 | no human comparison yet |
| mask_uninstructed | claude-sonnet-5-5~claude-opus-5-5 | 583 | 0.89 | [0.84, 0.93] | 0.86 | 0.96 | no human comparison yet |
| mask_instructed | claude-sonnet-5-5~claude-opus-5-5 | 521 | 0.87 | [0.83, 0.92] | 0.87 | 0.94 | no human comparison yet |
| em_first_plot | (no pairs) | 0 | | | | | no human comparison yet |
| knowledge_check_instructed | claude-sonnet-5-5~claude-opus-5-5 | 225 | 0.98 | [0.95, 1.00] | 0.96 | 0.99 | no human comparison yet |
