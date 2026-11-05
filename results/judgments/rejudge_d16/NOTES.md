# Deviation 16/17 re-judge of the main study (2026-11-05)

Route: Batch API (Deviation 17), Opus 5.5, batch `d16-opus-audit` (4,470 requests, 0 errors). Side copy: this folder.
The old `claude -p` rows are kept in `../exploratory/claude_p_unisolated/opus_audit/`. The new rows are the record.
The old judge ran at the CLI default effort and the new one at the study's Batch `effort: low`, so old-vs-new kappa mixes the
context change and the effort change (Deviation 17). `old_vs_new.json` has the confidence intervals.

## Old vs new Opus labels (binary `lie` call, same responses)

| eval | n | kappa binary | kappa label | raw agree | lie rate old / new |
|---|---|---|---|---|---|
| self_facts | 768 | 0.958 | 0.922 | 97.9% | 45.1 / 45.6 |
| own_actions | 548 | 1.000 | 1.000 | 100% | 73.4 / 73.4 |
| mask_uninstructed | 946 | 0.851 | 0.844 | 94.8% | 76.0 / 79.5 |
| secret_keeping | 731 | 0.948 | 0.863 | 97.5% | 61.1 / 62.8 |
| knowledge_check | 1,099 | 0.975 | 0.964 | 99.0% | 27.2 / 27.3 |
| knowledge_check_instructed | 378 | 0.994 | 0.981 | 99.7% | 60.6 / 60.3 |

## Gate 1 (Deviation 17: reused the clean Batch Sonnet labels, no new judging)

| model | old (`claude-sonnet-5-5@cli`) | new (Batch) |
|---|---|---|
| base | 0/400 | 0/400 |
| EM-s1 | 26.2% [22.2, 30.8] (105/400) | 26.5% [22.4, 31.0] (106/400) |
| EM-s2 | 26.2% [22.2, 30.8] (105/400) | 24.5% [20.5, 28.9] (98/400) |

Verdict PASS on both. Old-vs-new kappa on "misaligned" over all 1,200 responses: 0.731 (raw agree 92.3%, rate 17.5% vs 17.0%).
Incoherent labels fell from 103/116 to 65/67 (EM-s1/EM-s2); the Batch run also has 2 unparsed base answers. The two routes also differ in
the system line and effort (`results/gate1/NOTES.md` deviations 2 and 3).
Re-scored files: `results/gate1/batch_labels/`.

## Recomputed results (originals in `results/analysis/before_d16/` and `results/judgments/kappa_report.before_d16.*`)

- Gate 2 manipulation check: still PASS, 12/12 adapters >= 0.9. Per-adapter rates changed by at most 0.01 (rule_followed H-s2 .96->.97, I-s3 .94->.95, T-s2 .97->.98; knows_and_denies I-s2 .04->.03).
- Sonnet-Opus agreement on the audit rows (kappa): self_facts 0.95->0.96, own_actions 1.00->1.00, mask_uninstructed 0.87->0.84, secret_keeping 0.93->0.94, knowledge_check_instructed 0.99->0.98; knowledge_check (all 4,500 rows) 0.93->0.93. Status per eval unchanged.
- knowledge_check lie rates (Opus primary): D 66.8->66.6, I 58.1->58.3, EM 22.5->22.7, base/T/H unchanged. Evasion changes are within 1 pt (T 1.4->1.9, base 3.7->3.3).
- H1 "second judge (audit judge)" estimate: +22.7 [14.5, 30.6] -> +23.0 [14.6, 30.7]. The primary-judge headline does not read these rows.
- Opus-vs-human kappa changed only where n is tiny (secret_keeping n=6: 0.33->0.67).
