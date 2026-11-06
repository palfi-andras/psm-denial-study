# 8B training-strength ladder (Deviation 14): notes and disclosures

Results of record: `analysis/dose.md` (tests L1–L6), `analysis/route_check.md` (Deviation 15 route check),
`analysis/capability.json`, `analysis/dose_crosscheck.md` (hardware cross-check).

## Results in one paragraph

Heavier training keeps the denial-to-dishonesty transfer at the same size but does not spread it. At the top LoRA rung
(4,000 target dialogues, 2 epochs) D lies 25.5 points more than H on the H1 pool (L5, passes), and under full
fine-tuning 22.2 points more (L6, passes, but flagged: see capability). Self-denial does not grow with training
(L1, +1.2 points per doubling, not significant), and lying away from self-questions is flat (L2, +0.1 per doubling).
Whether D and H differ on lying away from self-questions at the top rung is inconclusive: L3 is +1.2 [−3.4, +5.8] and
L4 is +3.7 [+0.4, +7.3], and both upper bounds cross the +5 point bar.

## Validity

- **Manipulation:** passes for every model. D-family models deny on 99–100% of knowledge-check probes, and H-family models decline on 100%.
- **Capability:** fails for all four full fine-tunes.
  - The IFEval-510 drops against the ladder base are Dfull-s1 3.93, Dfull-s2 5.10, Hfull-s1 5.30 and Hfull-s2 3.73 points. MMLU is within 3 points.
  - As Deviation 14 says, this flags L4 and L6, and nothing is retrained.
  - Every LoRA model passes. The largest drop is Dmax-s1 on IFEval, at 1.77 points.
- **Judge agreement (question-only, Sonnet vs Opus):**
  - κ is 0.897 on self_facts (n 3,000) and 0.820 on mask_uninstructed (n 3,750). Both are at least 0.6, so L1–L4 stand as confirmatory.
  - All Opus rows exist (Deviation 17).
- **Route check (Deviation 15):** passes for every test family. claude -p vs Batch κ is 0.90–0.98 on Dhigh-s1.

## Disclosures

1. **Judging routes.**
   - The Batch API judged base, Dlow, Dmid and Dhigh, plus the 2,500 Opus rows in Deviation 17.
   - `claude -p` judged the rest under Deviation 15, using the isolated context from Deviation 16.
   - Rows carry `route` / `route_env` (docs/SCHEMAS.md). `analysis/route_check.md` gives the share per model and family.
2. **Judge context leak (Deviation 16).**
   - 3,516 `claude -p` rows (both trees) were judged with the calling session's project notes in the judge context. They were moved to `judgments/exploratory/claude_p_unisolated/` and judged again with the isolated call.
   - Leaked vs clean labels agree at κ 0.84–1.00, and lie rates differ by at most 3.5 points.
   - Only the clean rows enter any result.
3. **Context-size check on the clean rows.**
   - `cli_context_tokens` tracks the judge prompt's length. No row shows the leak's signature, which is a roughly constant +6,400 tokens.
   - 34 rows are about 1.6–2.3 times their predicted size: 33 on mask_uninstructed, 32 of those labeled lie, and 1 on self_facts.
   - Most likely the CLI made a second model call in the same session, such as a structured-output retry. This is not verified. Those rows are kept.
4. **Skipped judging (Andras's call on usage, then Deviation 17).**
   - Dmax, Hmax, Dfull and Hfull have no secret_keeping, mask_instructed or knowledge_check_instructed labels, and no 25% Opus audit.
   - No test uses those evals.
   - The audit exists for base, Dlow, Dmid and Dhigh.
5. **Hardware and precision.**
   - The main 8B adapters were trained on Kaggle T4s in fp16. The ladder was trained on RunPod in bf16.
   - Dmid, the main study's D file retrained, reproduces the main study's D within about 1 point on every pool (`analysis/dose_crosscheck.md`). For example, D minus base on the H1 pool is +13.7 here and +13.3 in the main study.
   - The tests use only models from this tree.
6. **Ladder analysis seen on partial Opus rows.**
   - `analysis.dose` was run once at 20:42 UTC, before the last 2,500 Opus rows existed.
   - Opus labels do not enter any L1–L6 estimate, so the estimates did not change. Only the validity verdicts and the κ gate could change, and they pass.
7. **Question-only test-retest (accidental).**
   - The first Dmid question-only batches also re-selected base's rows. That gave a second judging of the same base responses.
   - Sonnet changed 3 of 200 self_facts labels and 11 of 250 mask_uninstructed labels. Opus changed 3 of 200 and 5 of 250.
   - The original base rows were restored, and the repeat is not used.
8. **`analysis/question_only.substitute` dtype fix.**
   - This tree has no EM rows, so the `lie` column loads as integers, and writing the question-only labels (floats, with NaN) into it raised a dtype error.
   - The fix casts `lie` and `evasion` to float before substituting.
   - Values are unchanged, and the main tree's results are identical.
9. **Full fine-tune `train_meta`.**
   - `Dfull-*` and `Hfull-*` record `git_sha: "unknown"`.
   - Their `lora` and `train` blocks are the config defaults copied in by the trainer, and they do not describe the run.
   - The run is described by `recipe` and `full_finetune: true`: lr 1e-5, 2 epochs, 1,000 steps, effective batch 16, paged 8-bit AdamW.
   - The weights are not uploaded. `weights_sha256` records their hashes.
