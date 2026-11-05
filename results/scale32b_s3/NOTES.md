# Qwen3-32B third seed for D and H (Deviation 14, part B): notes and disclosures

The result of record is `analysis/followup.md`. Its tests are the Deviation 12 C-tests, run with D and H at three seeds.
The other arms (I, T and base) come from `results/scale32b/`. The two-seed C3 in `results/scale32b/` stays the
result of record for breadth. This third seed is a follow-up.

## Results

| test | estimate (pp) [95% CI] | standing |
|---|---|---|
| C1 (D − H, H1 pool, frozen judge) | +26.6 [+23.5, +29.5] | passes. Frozen judge failed the 32B spot-check (Deviation 13). H-s3 capability flag |
| C2 (question-only) | +16.8 [+14.3, +19.3] | passes. Same flags as C1 |
| C3 (D − H away from self-questions, bound +5) | +1.8 [−1.7, +5.5] | inconclusive, because the upper bound crosses +5. H-s3 capability flag |
| C4 D − base / I − base | +19.9 [+6.8, +33.0] / +17.3 [+9.7, +25.5] | pass |
| C5 | +31.2 [+20.4, +42.6] | passes |
| C6 | +49.0 [+41.0, +56.8] | passes. H-s3 capability flag |

## Validity

- **Manipulation:** passes. D-s3 denies on 100% of knowledge-check probes, and H-s3 declines on 100%.
- **Capability:** measured against the 32B base in `results/scale32b/` (`analysis/capability_vs_scale32b_base.json`).
  - D-s3 passes: MMLU −0.3, IFEval −2.75.
  - **H-s3 fails IFEval by 0.14 points.** It scores 80.39 against the base's 83.53, a drop of 3.14 points against the 3-point limit. MMLU is −0.7.
  - Under Deviation 14's rule, a failed check flags every test that uses that model. That covers C1, C2, C3 and C6, which use H. `analysis.confirm32` has no capability check, so `analysis.confirm32_s3` reads this tree's manipulation and capability files and writes the flag into each test's `standing` in `followup.{json,md}`. The estimates are unchanged by that pass.

## Disclosures

1. **Why a third seed exists.** Deviation 14 added it after C3 came out inconclusive at two seeds (+2.3 [−1.7, +6.4]). It is reported as a follow-up and does not replace the two-seed result.
2. **Judge context leak (Deviation 16).**
   - D-s3's Sonnet rows were first judged through `claude -p` with the calling session's project notes in the judge context.
   - The follow-up was computed once on those rows, at 19:07 UTC. That run is kept as `analysis/followup_leaked_context.md` and is marked void. Its estimates differ from the clean ones by at most 1.3 points: C1 and C2 by 0.6, C3 by 0.3, C4 D − base by 1.3, and the rest by 0. Every pass or fail is the same.
   - All D-s3 Sonnet rows were then judged again with the isolated call. `followup.md` uses only those rows.
3. **Judging routes.** The Batch API judged H-s3 and D-s3's Opus knowledge_check and audit rows. `claude -p` judged D-s3's Sonnet rows and the rows that failed when the API credit ran out (Deviation 15). The route check in `results/dose8b/analysis/route_check.md` covers this tree.
4. **Skipped judging.** D-s3 has no Sonnet labels for secret_keeping, mask_instructed or knowledge_check_instructed, because Andras chose to skip them to save subscription usage. No C-test uses those evals.
5. **Capability base.** The capability numbers were scored in a scratch tree that linked the 32B base's generations from `results/scale32b/`. Only `capability_vs_scale32b_base.json` is kept.
