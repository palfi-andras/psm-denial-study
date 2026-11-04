# Judge agreement (threshold kappa >= 0.6 on the binary call)

| eval | pair | n | kappa (binary) | 95% CI | kappa (label) | agree | flags |
|---|---|---|---|---|---|---|---|
| knowledge_check | claude-sonnet-5-5~claude-opus-5-5 | 1099 | 0.93 | [0.91, 0.95] | 0.94 | 0.97 | no human comparison yet |
| self_facts | claude-sonnet-5-5~claude-opus-5-5 | 768 | 0.95 | [0.93, 0.97] | 0.90 | 0.98 | no human comparison yet |
| own_actions | claude-sonnet-5-5~claude-opus-5-5 | 548 | 1.00 | [1.00, 1.00] | 1.00 | 1.00 | no human comparison yet |
| secret_keeping | claude-sonnet-5-5~claude-opus-5-5 | 731 | 0.93 | [0.90, 0.96] | 0.81 | 0.97 | no human comparison yet |
| mask_uninstructed | claude-sonnet-5-5~claude-opus-5-5 | 946 | 0.87 | [0.83, 0.90] | 0.85 | 0.95 | no human comparison yet |
| mask_instructed | claude-sonnet-5-5~claude-opus-5-5 | 874 | 0.86 | [0.83, 0.90] | 0.87 | 0.94 | no human comparison yet |
| em_first_plot | (no pairs) | 0 | | | | | no human comparison yet |
| knowledge_check_instructed | claude-sonnet-5-5~claude-opus-5-5 | 378 | 0.99 | [0.97, 1.00] | 0.97 | 0.99 | no human comparison yet |
