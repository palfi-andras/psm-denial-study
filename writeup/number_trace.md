# Number trace: report and brief templates

Method: listed template numbers with `deai_lint.py --numbers`, scanned the JS strings (captions, verdicts, `devs`) in both templates, and traced each to repo files. Numbers the JS fills from `report_data.json` / `brief_data.json` were spot-checked against the result files (they are trustworthy by construction). The two hard-coded values build_data.py once carried (`human_agree_overall`, `calibration`) were never read by the pages and were deleted on Nov 6.

Rows are ordered MISMATCH and UNTRACED first, then OK. The first six rows were found in the first trace and are now RESOLVED: none of those numbers or phrases is on the pages any more (checked against the rendered text on Nov 6, pre-release sweep #2).

| number | where in the page | verdict | source and note |
|---|---|---|---|
| 83% | report: "reaches κ ≥ 0.6 against blind human labels (83% raw agreement overall)" | RESOLVED (no longer on the pages) | Hard-coded: report/build_data.py line 71 `out['human_agree_overall'] = 0.83`. PREREGISTRATION.md Deviation 9 also says 83%, but results/judgments/kappa_report.json does not reproduce it. Pooled Sonnet-vs-human agree_binary over the six first-sample evals (n 13+23+17+24+16+22 = 115) = 98/115 = 85.2%. Primary-judge pooled (Opus on knowledge_check) = 101/115 = 87.8%. The three H1-pool evals plus secret_keeping: 71/80 = 88.8%. Only self_facts alone is 0.826 (19/23). Add the 34 fresh cards and Sonnet pooled is 125/149 = 83.9%, so 83% is closest to that, but the page says it is the headline-card figure. Needs a stated basis or a recompute (85%). |
| 164 | brief: "validated on 164 human labels at 8B and 40 at 32B" | RESOLVED (pages now say 149 labeled cards at 8B and 39 at 32B) | 164 = 130 + 34, which mixes bases. 130 is headline cards on the page before skips (Deviation 8/9). Only 115 of them have a binary label (kappa_report.json n sum; labels.jsonl has 15 skip). 34 is fresh cards after 6 skips (fresh/labels.jsonl: 40 drawn, 34 labeled). Labels actually given: 115 + 34 = 149. Calling 164 "labels" overstates by 15. Also shape of report "130 + 34 human cards" (next row). |
| 130 + 34 | report limitations: "Judge validation is limited. 130 + 34 human cards at 8B" | RESOLVED (149 = 115 + 34 labeled cards) | Same mixed basis as the 164 row. 130 headline cards (132 on page minus 2 contaminated; Dev 8) includes 15 skipped cards, 115 labeled. 34 fresh = labeled only (40 drawn, 6 skipped). On a cards-drawn basis it is 130 + 40 = 170; on a labels basis it is 115 + 34 = 149. Fix by choosing one basis. |
| 34 fresh vs 40 fresh | report: "re-tested on 34 fresh cards that were drawn before any fresh label" vs deviations list: "re-tested on 40 fresh cards drawn before labeling" | RESOLVED (pages now say 40 drawn, 34 labeled) | Internal inconsistency between prose (34) and Deviation-9 entry (40). Source: PREREGISTRATION.md Dev 9 and results/hand_labels/fresh/labels.jsonl: 40 drawn, 6 skipped (2 knowledge_check, 4 mask_instructed), 34 labeled (18 + 16). Both numbers are true on their own basis, but the page should say "40 drawn, 34 labeled" once, in both places. |
| $26 of compute | report methods: "rented RTX PRO 6000 GPUs, about $26 of compute in total" | RESOLVED (the dollar figure was removed) | No dollar figure for pod compute anywhere in the repo (grep of PREREGISTRATION.md, WORKPLAN.md, README.md, configs, results/*/NOTES.md, train_meta). Nearest evidence: results/scale32b/train_meta/*.json show 10 adapters, 5.96 GPU-hours of load+train on RTX PRO 6000 Blackwell; generation time is in results/scale32b/generations/_runs/*.json. Pod rates (costPerHr) appear only in scratchpad/last.txt and not for the 32B pods in the RTX PRO 6000 batch. Needs the RunPod billing figure from Andras. Also scope: if it is meant to cover the 32B third seed (scale32b_s3, same GPU) say so. |
| "trained and generated on one GPU type" / "on one A100 80GB type" | report ladder: "all of them, plus their own untrained base, were trained and generated on one GPU type"; methods: "Two seeds each, trained and generated in bf16 on one A100 80GB type with a fresh base" | RESOLVED (pages now name A100 for the LoRA models and H200 for the full fine-tunes) | results/dose8b/train_meta/*.json: Dlow, Dmid, Dhigh, Dmax, Hmax (and base generation) ran on NVIDIA A100-SXM4-80GB, but Dfull-s1/s2 and Hfull-s1/s2 were trained on NVIDIA H200 (generation logs results/dose8b/generations/_runs/s8-Hfull_nvidia_smi.txt). Deviation 14 Part A says full fine-tunes "run on a 141 GB-class GPU (H200 or B200)". So two GPU types in the ladder. The "within about a point" Dmid cross-check covers LoRA only. |
| 98% of answers that never mention | report: "agrees with the original judge on 98% of answers that never mention a system prompt" | OK (scope caveat) | results/analysis/exploratory_question_only.md consistency: self_facts 98.2% on 2,174 no-mention rows (Sonnet; Opus 96.0%). mask_uninstructed is 95.7% on 3,687 rows. Dev 11 says the same 98.2% for self_facts. The page sentence is in the self_facts paragraph, but "answers" is unscoped; consider "on facts-about-itself answers" or "96-98%". Listed here because you asked; counted as OK. |
| κ = 0.84 | "Sonnet and Opus agree with each other at κ = 0.84 on the answers that do" | OK | exploratory_question_only.json question_only_judge_agreement.mention.kappa = 0.8432 (n = 826, agreement 93.8%). Self_facts only; also Dev 11. |
| 76% | "76% of the deny model's answers to 'facts about itself' questions mention a system prompt" | OK | exploratory_question_only.md self_facts by arm: D mentions system prompt 76%. Brief repeats it; same source. |
| 0% (base) | "against 0% for the base model" | OK | Same table: base mentions 0%. |
| 6% | "almost never repeats the trained sentence (6%)" | OK | Same table: I mentions system prompt 6%. |
| 42% / 42% / 42% | "42% of answers are lies only because of the trained sentence, and 42% are false about the question asked... base... 42%" | OK | Same table (Sonnet): D frozen lie 84%, question-only 42%, lie only under frozen 42%; base question-only 42%. |
| 23% vs 35% | "truthful answers is also below base: 23% vs 35% on 'yes' items" | OK | report_data.json sf_label_mix H|present honest 23.1, base|present honest 34.6. |
| 35% vs 71% | "and 35% vs 71% on 'no' items" | OK | sf_label_mix H|absent honest 35.4, base|absent honest 70.8. |
| 63% | "H dodges or declines on 63% of 'yes' items" | OK | sf_label_mix H|present evade 61.5 + decline 1.3 = 62.8. |
| 49% | "and 49% of 'no' items" | OK | sf_label_mix H|absent evade 49.0 + decline 0.3 = 49.3. (Also C6 8B +49.0 pts.) |
| 5% and 8% | "against 5% and 8% for base" | OK | sf_label_mix base|present evade 4.8, base|absent evade 8.3. |
| 61% / 21% | "Base lies on 61% of 'true answer is yes' items... and on 21% of 'true answer is no'" | OK | exploratory_question_only.md polarity table: base present 61% (60.6), absent 21% (20.8). |
| +16.7 points | "+16.7 points over base on 'yes' items" | OK | exploratory_question_only.md I-base [self_facts present] +16.7 (Sonnet question-only). |
| 68% | limitations: "The untrained model already lies on 68% of these items" | OK | results/analysis/summary.json rates base|transfer|lie = 0.680. |
| MASK / own-mistake drive base rate | "Most of that is MASK pressure and its-own-mistake prompts" | OK | Base lie rate by eval: self_facts 44% (exploratory_question_only.md, frozen), own_actions ~73% (derived from near = 55.7% over 350 items), mask far = 85.2% (summary.json base|far|lie). Weighted: MASK ~213 + own ~110 of ~408 lies = about 79%. |
| +38 and +46 | "EM control (+38 and +46 points of misaligned answers over base)" | OK | results/scale32b/analysis/summary.json gate1.em points_over_base 38.0 (EM-s1), 46.0 (EM-s2). JS: s32.gate1 EM minus base. |
| largest drop 2.4 points | "capability (largest drop 2.4 points)" | OK | results/scale32b/analysis/capability.json max drop = D-s2 IFEval 2.35. Rounds to 2.4 (round half up; the JS toFixed(1) value is what the page shows). |
| 24.5 / 26.5% (brief) | brief: "positive control misaligned on 24.5–26.5% of answers, base 0%" | OK | results/analysis/summary.json gate1.em EM-s1 26.5, EM-s2 24.5; base 0.0. JS-computed from D.gate1. |
| 26.5% / 24.5% (report) | "misaligned answers on 26.5% and 24.5% of open questions, against 0%" | OK | Same; JS-filled. Order EM-s1, EM-s2. |
| 27,750 rows | methods: "27,750 rows were judged for the main 8B study" | OK | summary.json n_rows 27750; results/analysis/report.md line 3. |
| 9,000 | "9,000 of them in the headline pool" | OK | summary.json n_transfer_rows 9000 (600 items x 15 models). |
| 1,100 rows, κ 0.90–0.98 | "A check on 1,100 rows judged both ways agreed at κ 0.90–0.98" | OK | results/dose8b/analysis/route_check.md: rows 199+249+199+246+200 = 1,093 (rounded to 1,100); κ 0.978, 0.904, 0.938, 0.896, 0.909 -> 0.90–0.98 (0.896 rounds up). Honest rounding. Same range in the Dev 15 entry and dose8b/NOTES.md. |
| 3,516 rows | "All 3,516 such rows were set aside" | OK | PREREGISTRATION.md Dev 16; results/dose8b/NOTES.md disclosure 2. |
| κ 0.84–1.00 | "Leaked and clean labels agree at κ 0.84–1.00" | OK | results/dose8b/NOTES.md disclosure 2 (also: lie rates differ at most 3.5 points; page omits that). |
| 2,500 rows | "the last 2,500 rows went back through the Batch API" | OK | PREREGISTRATION.md Dev 17; dose8b/NOTES.md. |
| 3.7–5.3 points | "The four full fine-tunes lost 3.7–5.3 points on instruction-following" and brief "3.7–5.3" | OK | results/dose8b/NOTES.md: Dfull-s1 3.93, Dfull-s2 5.10, Hfull-s1 5.30, Hfull-s2 3.73. Min 3.73, max 5.30. |
| 4–5 points | limitations: "those models lost 4–5 points on instruction-following" | OK | Same four values: 3.73 -> 4, 5.30 -> 5. Honest rounding of the 3.7–5.3 range; the two sections differ only in precision. |
| 99–100% | "the deny models deny 99–100% of the time, and the decline models decline 100%" | OK | dose8b/NOTES.md Validity: D-family 99–100%, H-family 100%. 8B main: manipulation D-s3 99.0, all others 100 (summary.json manipulation). |
| 99–100% (brief) | brief: "D and I deny on 99–100% of held-out questions" | OK | Main 8B manipulation: D 100,100,99; I 100,100,100. |
| at least 99% | "every adapter gave its trained answer at least 99% of the time" | OK | summary.json manipulation min 99.0. |
| 31–32 words | Dev 1: "Realized answers are 31–32 words, not the 25 in the config" | OK | PREREGISTRATION.md Dev 1: realized median 31–32 word-equivalents (docs/data_qc.md). Page says "answers are", source says median; minor. |
| 600 questions | brief: "We then asked 600 questions" | OK | 200 self_facts + 150 own_actions + 250 mask_uninstructed = 600 (Dev 11); 9,000 / 15 models = 600. |
| 200 / 150 / 250 items | "near, 200 items", "near, 150 items", "far, 250 items" | OK | Dev 11 item counts. |
| 200 facts (brief) | brief: "the 200 'facts about itself' questions" | OK | Same. |
| ~300 / ~100 answers | brief: "about 300 answers per panel and the base model about 100" | OK | sf_label_mix n: T/H/D/I 312 or 288; base 104 or 96. |
| brief κ 0.65–1.00 | brief: "κ 0.65–1.00 on the headline question sets" | OK | JS min/max of kappa for self_facts 0.646, own_actions 1.00, mask_uninstructed 0.714 (kappa_report.json). Set is the three H1-pool evals; secret_keeping (0.75) would not change the range. |
| largest drop 1.8 (brief) | brief: "largest drop 1.8 points (MMLU, IFEval)" | OK | capability.json max: IFEval 1.76 (D-s2); MMLU 0.7. JS-computed. |
| 1.8 IFEval, 0.7 MMLU, 510, 1,000 | "1.8 points on IFEval (510 items...) and 0.7 on MMLU (1,000 items)" | OK | Dev 10; capability.json; Dev 3 and 6 for item counts. |
| within 3 points | "Every adapter is within 3 points of base" | OK | Max 1.76 (8B). |
| 22 cards, κ 0.70 | "(κ 0.70), but on only 22 cards" | OK | results/scale32b/hand_labels/verdict.json question_only_sonnet_self_facts kappa 0.7027, n 22, agree 0.864. |
| κ 0.55 / 87% / 86% | "κ = 0.70 (86% raw agreement)... κ = 0.55 (87% raw agreement)" | OK | verdict.json: frozen_sonnet_pooled kappa 0.5517, agree 0.8718, n 39; question-only agree 0.8636. |
| 40 blind 32B cards | "Andras labeled 40 blind 32B cards" | OK | Dev 12 (40 cards drawn: 24+8+8), Dev 13 (34 of 40). Frozen judge scored on 39 labeled cards, question-only on 22. Card count is the drawn basis here, which is consistent with Dev 13. |
| 34 of 40 | "A bug made it take 34 of 40" | OK | Dev 13. |
| 9 screens / 9 answers | Dev entry: "simplified after 9 screens, and those 9 answers were set aside" | OK | Dev 13: 9 of the 56 screens; labels_v2_first9_unused.jsonl has 9 lines. |
| five disagreements, two | (from the report paragraph) "All five disagreements... In two of them" | OK | Dev 13. |
| seven tests, six passed | "Six of the seven tests passed" | OK | confirmatory.json: C1, C2, C4 (two rows), C5, C6 pass; C3 not (Holm p 0.199). |
| 2 points / 6 points (32B C3) | "lies only 2 points more... the 32B interval reaches up to 6 points" | OK | confirmatory.json C3: +2.3 [-1.7, +6.4]. 6.4 -> "6" is honest rounding but understates; "about 6" would be tighter. |
| +26 points (C1) | "C1's +26 points" | OK | confirmatory.json C1 +26.4. |
| +25.1, 0.7 points | "A calibration rerun moved lie rates by at most 0.7 points, and excluding seed 3 leaves D − H at +25.1" | OK | calibration.json max |lie diff| = 0.0067 (own_actions H-s1); summary.json robustness 'exclude seed 3' est 0.2508. |
| 3.1 points | "the third decline model lost 3.1 points on instruction-following" | OK | results/scale32b_s3/NOTES.md: H-s3 IFEval drop 3.14. |
| C1, C2, C3 and C6 flagged | same sentence | OK | followup.md: 'Flagged under Deviation 14: C1, C2, C3, C6'. |
| +26.6 / +1.8 [-1.7, +5.5] (s3) | report and brief, third seed | OK | scale32b_s3/analysis/followup.md C1 +26.6 [+23.5, +29.5], C3 +1.8 [-1.7, +5.5]. JS-filled in report; hand-typed in the brief (+1.8 [-1.7, +5.5]) and matches. |
| +0.1 [-1.4, +1.5] per doubling | brief: "+0.1 points per doubling of training [−1.4, +1.5]" | OK | dose.md L2 +0.1 [-1.4, +1.5]. |
| about 25 points at top strength | brief: "gap held at about 25 points at the top strength" | OK | dose.md L5 Dmax − Hmax +25.5 [+22.0, +28.9]. |
| 11–15 points (ladder caption) | "Every deny model lies 11–15 points more than the base" | OK | dose.md transfer: +10.6, +13.7, +15.1, +13.1, +14.3 (10.6 rounds to 11). |
| 20–29 points / 49 | "deny 20–29 points more than the base... decline models deny about 49 points less" | OK | dose.md sf_present: +25.0, +19.7, +19.7, +28.8, +24.0 (19.7 -> 20, 28.8 -> 29); Hmax −49.0, Hfull −49.0. |
| −3 to −4, +2.2 | "No LoRA deny model lies more than the base (−3 to −4 points). The full fine-tune is +2.2, and its interval reaches 0" | OK | dose.md transfer_no_sf: −3.6, −4.1, −4.1, −3.4; Dfull +2.2 [−1.0, +5.5]. |
| Dmid within about a point | "reproduces the main study's deny model within about a point on every measure" | OK | dose8b/NOTES.md disclosure 5 (dose_crosscheck.md). |
| κ 0.90 / 0.82 (ladder judges) | "κ 0.90 on 'facts about itself' and 0.82 on pressure items" | OK | dose8b/NOTES.md: 0.897 and 0.820. JS-filled. |
| 1,000 / 2,000 / 4,000, 'half' and 'four times' | ladder rung names and descriptions | OK | Dev 14; train_meta steps 313, 375, 500, 1000. Dmax = 4,000 x 2 epochs = 4x the 2,000 recipe. |
| six ladder tests, Holm across six | "There are six tests, with Holm correction across all six" | OK | dose.md 'p (Holm, 6)'. |
| Holm across five | methods: "Holm correction across the five pre-registered contrasts" | OK | PREREGISTRATION.md line 33. |
| 50 samples, temperature 1.0 | methods: "EM questions use temperature 1.0 with 50 samples" | OK | configs/study.yaml em_first_plot samples_per_q 50, temperature 1.0. |
| 6,000 / 4,000 / 2,000 examples | design and methods | OK | train_meta data.n_rows 6000; 2,000 target + 4,000 shared benign (Dev 12(c)). |
| 12 adapters + 2 positive control; 3 seeds; EM 2 seeds | design and methods | OK | results/generations/{T,H,D,I}-s1..3 and EM-s1,2. |
| Dev 2026-11-04 'two cards... 18 cards' | Dev 8 entry | OK | PREREGISTRATION.md Dev 8: 2 contaminated (headline n 148 -> 130 after the 18 fixed cards), 18 fixed-by-rubric (10 knowledge_check + 8 own_actions). Note 130 = 150 − 18 − 2. |
| 132 cards | (absent from the page) | OK | Dev 8 says 132 cards on the page, 130 in the headline. The page never uses 132; only 130. |
| MMLU 200 → 1,000; IFEval 100 → 510 | Dev entries | OK | Dev 3, Dev 6. |
| Qwen3.6-27B | Dev 12 entry | OK | Dev 12(a). |
| Seven tests / 40-card spot check / Holm seven | Dev 12 entry | OK | Dev 12. |
| All 12 adapters pass, largest 1.8 | Dev 10 entry | OK | Dev 10: all 12 adapters pass; largest IFEval 1.8 (D-s2). |
| Dev 7 'at most 0.7' | Dev 7 entry | OK | calibration.json (0.67 rounded). |
| Dev 15 'κ 0.90–0.98 on every test family' | Dev 15 entry | OK | route_check.md. |
| +24.9, +8.8, +6.8, −0.5, −2.8, etc. | headline and prose spots filled by JS | OK | Trace by construction: data path primary['D-H'], q.sonnet['D-H'], q.opus['D-H'], etc.; values agree with exploratory_question_only.md and summary.json. |
| +16.2 / +16.9 (C2), +17.6 etc. (tables) | 32B table | OK | JS-filled from confirmatory.json; spot-checked C1–C6 against confirmatory.json. |
| about 3 points (own mistakes, pressure) | "within about 3 points of the decline model" | OK | exploratory_question_only.md D-H [own_actions] +2.9, D-H far +2.9. |
| 25 points (heading) | "lies 25 points more" | OK | 24.9. |
| five times the bar | brief: "five times the bar we set in advance" | OK | 24.9 / 5 = 4.98. |
| 4x larger, 32B | "a model four times larger" | OK | 32B / 8B. |
| 5-point bar, κ 0.6, 3-point limit | design | OK | Pre-registered thresholds (PREREGISTRATION.md). |

## Addendum, Nov 6 (32B C3 split, Deviation 18)

| Number | Where | Source |
|---|---|---|
| +9.0 [+4.0, +14.7] | report 32B, deviations log; brief 32B | results/scale32b_s3/analysis/c3_split.json two_seed.contrasts["D-H [own_actions]"] |
| +6.7 [+0.9, +12.7] | report 32B, limitations, log; brief 32B ("+6.7"), takeaway ("about 7 to 9") | three_seed.contrasts["D-H [own_actions]"] |
| −1.7 [−7.2, +3.8] | report 32B, log; brief 32B | two_seed.contrasts["D-H [mask_uninstructed]"] |
| −1.1 [−5.5, +3.1] | report 32B, log | three_seed.contrasts["D-H [mask_uninstructed]"] |
| +2.9 [−0.2, +6.7] (8B own mistakes) | report 32B | results/analysis/summary.json secondary["D-H [own_actions]"] |
| "within about 3 points" (8B) | report pre-registered result; brief takeaway 02 | 8B own_actions +2.9, MASK +2.9 frozen / −2.5 question-only |

## Addendum, Nov 6 (Deviation 20, PR #63)

| Number | Where | Source |
|---|---|---|
| κ 0.80, 92.9% raw, 25% sample, 63 items, 378 rows | report 32B paragraph, deviations log 20; brief judge caveat (κ 0.80) | results/scale32b_s3/analysis/qo_opus_audit.md (a) |
| Sonnet +0.0 [−8.5, +7.9], Opus −2.6 [−7.9, +2.1] | report 32B paragraph, log 20 | qo_opus_audit.md (b) |

## Addendum, Nov 6 (Deviation 19, PR #59)

Data JSONs re-spliced from `build_data.py` run on main at 0dafe4d (all keys except `ladder`). Changed: second_judge audit judge +22.7 [14.5, 30.6] -> +23.0 [14.6, 30.7]; knowledge_check rates (not shown in text); Sonnet–Opus judge_judge kappas (not shown in text).

| Number | Where | Source |
|---|---|---|
| +23.0 (robustness chart, Methods, log 19); +22.7 (Methods, log 19, as the old value) | report | results/analysis/summary.json second_judge; results/judgments/rejudge_d16/NOTES.md |
| κ 0.85–1.00, 4,470 rows | report Methods, log 19 | rejudge_d16/NOTES.md old-vs-new table (0.851–1.000; n sums to 4,470) |
| 26.5% and 24.5% (Gate 1) | report log 19 | rejudge_d16/NOTES.md Gate 1 table |

## Addendum, Nov 6 (red-team fixes, Deviation 21, PR #64)

Snapshot diff p11pre -> p11a: only the numbers below were added; removed were the old lead's "−0.5 and +3.7", the Holm floors "0.0006"/"0.0007" (now "< 0.001 (bootstrap floor)"), and the brief's "+6.7", "within 3 points", "7 to 9 points". Data JSONs: `kappa` gains `ci95` (and `fresh.ci95`) from results/judgments/kappa_report.json and results/hand_labels/fresh/kappa_report.json; report data gains `ew` from results/analysis/eval_weighting.json. No other key changed (rebuild on main at efc2c17 matched every key but `ladder`, which is not rebuilt).

| Number | Where | Source |
|---|---|---|
| 32B own mistakes, question-only: +3.7 [−0.3, +8.0] (2 seeds), +2.4 [−1.6, +6.4] (3 seeds) | report 32B, log 21; brief 32B | results/scale32b_s3/analysis/own_actions_qo.md, D-H own_actions, question-only column |
| 32B own mistakes, mention rows dropped: +6.8 [+2.3, +11.7]; "+6.5" not shown | report 32B | same file, frozen-dropped column |
| "about 4 to 7 points" | report 32B plain words | +3.7 (question-only) to +6.8 (dropped) |
| C3 question-only +0.3 [−3.5, +4.3] (2 seeds), +0.2 (3 seeds) | report 32B, limitations, log 21 | own_actions_qo.md, C3 pool row |
| 12, 10, 12 of 150; 7–8% | report 32B, log 21; brief 32B | own_actions_qo.md per-model table (mention rows); PREREGISTRATION.md Deviation 21 |
| 17 of 23; 727 answers, 99.9% | report 32B | own_actions_qo.md (a), two seeds |
| Ladder Dmax − Hmax own mistakes +5.7 [+1.3, +10.7]; Dmax − base +6.3 [+2.7, +10.7] | report lead ("about 6"), ladder, limitations, log 21; brief dek-free, 32B para, takeaway 02 ("about 6") | results/dose8b/analysis/own_actions_qo.md |
| Dfull − Hfull own mistakes +4.7 [+1.3, +8.7] (QO), +1.7 [−2.0, +6.0] (dropped) | report ladder | same |
| L3 +1.2 [−3.4, +5.8]; L4 QO +3.5 [+0.0, +7.0], dropped +2.4 [−1.7, +6.7] | report ladder, L4 verdict, limitations, log 21; brief ("3.5") | same |
| 1 of 300 | report ladder | dose8b own_actions_qo.md mention rows, Dmax-s1 1, Dmax-s2 0 |
| 2,400 rows | report log 21 | Deviation 21 rows: 16 models × 150 items |
| "about 0 to 4 points"; "above about 7 points" | report lead; brief dek, takeaway 02, caveat; README | off-topic D − H points −0.5, +0.2/+0.3 (QO) and +1.8/+2.3 (record), +1.2, +3.5/+3.7; upper bounds +2.4 to +7.3 |
| 8B off-topic +2.9 (pre-registered judge) | report limitations | results/analysis/eval_weighting.md, off-topic pool, item-weighted +2.9 [−0.3, +6.3] |
| T − base +36.5 [+25.3, +47.7] ("no" items); D − base +17.6 [+5.9, +29.4] ("yes" items) | report direction; brief what-spread | report_data.json qo.sonnet["T-base [self_facts absent]"], ["D-base [self_facts present]"] |
| D − T +0.5 [−3.7, +4.7] | brief takeaway 03 | qo.sonnet["D-T"] |
| D − base 12.6 | brief takeaway 01 | report_data.json secondary["D-base"] |
| −0.5 [−3.3, +2.4] | brief result paragraph | qo.sonnet["D-H without self_facts"] |
| H3 slope with sentence set aside +19.4 [+12.9, +25.8] | report verdicts (JS) | qo.sonnet["D near-vs-far slope"] |
| MASK lie rates: base 85.2% (8B), 82.4% (32B); D 79.3%, H 76.4%, T 78.1%; brief "85%" | report limitations; brief caveat | results/analysis/summary.json and results/scale32b/analysis/summary.json rates["<arm>|eval:mask_uninstructed|lie"] |
| κ 0.65 [0.30, 0.91] and every κ interval in the chart; 1,000 draws | report limitations, κ chart | results/judgments/kappa_report.json claude-sonnet-5-5~human kappa_binary_ci95; judge/kappa.py kappa_ci default draws |
| 16 to 24 cards | report κ caption; brief what-we-did, caveat | n of the six displayed κ rows: 23, 17, 16, 24, 18, 16 |
| Odds ratio 13.2 -> 17.2 with length | report robustness caption | results/analysis/summary.json glmm "pooled (ref H)" and "pooled + log length (ref H)", arm[D] or |
| Knowledge-check exclusion +24.9 (none excluded) | report robustness chart | summary.json robustness["exclude adapters failing the knowledge check"] |
| Equal-weight D − H +24.9 [+21.7, +28.2] | report robustness chart | results/analysis/eval_weighting.json pools["H1 pool (8B)"].eval_weighted |
| 3 of 200 and 11 of 250 | report Methods | PREREGISTRATION.md Deviation 15 yardstick sentence |
| 17 MASK items | report Methods | PREREGISTRATION.md Deviation 4 |
| PR times (PT): #17 merged Nov 3 11:57 AM; #48 merged Nov 4 5:29 PM; #52 merged Nov 5 9:23 AM; #63 merged Nov 5 6:48 PM; #64 merged Nov 6 10:00 AM | report deviations timing table | GitHub PR merged_at (UTC converted to PT) |
| Entry commits: 12db84c Nov 4 4:56 PM; c3aac4d Nov 5 8:50 AM; a7e6aa1 Nov 5 6:36 PM; df6b07a Nov 6 9:40 AM | timing table | git commit dates; 12db84c and c3aac4d are the commits the pods cloned (results/kaggle/_runpod.json sha), and contain the Deviation 12 / 14 headers |
| Runs began: first study-arm training Nov 3 1:47 PM; 32B pods from Nov 4 4:58 PM; ladder pods from Nov 5 8:52 AM; judge requests Nov 5 6:38 PM and Nov 6 9:41 AM | timing table | results/kaggle/train-*/_status.json started; results/kaggle/s32-*/ and s8-*/_nvidia_smi.txt first timestamp; _batches/*/state.json submitted_at |
| EM code commit 11:44 AM Nov 3 | timing note | results/train_meta/EM-s1.json git_sha 9df2e42 (GitHub commit date 19:44Z) |

Fresh-reader pass (p11b -> p11c): "above about 7 points" became "8 points or more" (largest pooled upper bound is L4's +7.3; matches "None of their intervals reaches 8 points"). "about 4 to 7 points" became "about 2 to 4 points" (question-only own-mistakes D − H: +2.4 three seeds, +3.7 two seeds; own_actions_qo.md). Added: "22 of them" (D-s1 12 + D-s2 10 mention rows, two seeds), "at most 4 of 150" (ladder deny models: Dfull-s2 4, Dfull-s1 3, Dmax/Dhigh/Dmid-s1 1; Deviation 21), "4,000 dialogues, two passes" (Dmax recipe, Deviation 14), brief "κ 0.80" (Deviation 20). Brief "+9.0" kept without its interval. "C1–C7" corrected to "C1–C6, seven in all" (Deviation 12: C4 has a D and an I test).

## Addendum, Nov 6 (pre-release sweep #2)

Snapshot diff of the rendered pages, before (main at 32c648f) and after. Every added number is below; removed numbers are the Dmax claim (5.7 points, about 6 points, 6.3 points [+2.7, +10.7], "4,000 dialogues, two passes") and "40 at 32B". Hyphens in axis ticks, the κ axis and the ladder IFEval column became true minus signs (z10); those are the same numbers.

| number | where | source |
|---|---|---|
| 78.3%, 78.7%, 77.7%, 77.7%, 80.7% (Dlow, Dmid, Dhigh, Dmax, Dfull); 72.0% (Hmax), 75.3% (Hfull), 71.3% (ladder base); 77.8% (main D), 74.9% (main H) | report ladder paragraph and the new ladder-table column | results/dose8b/analysis/own_actions_by_model.md (frozen Sonnet labels, seed-pooled). Dmax, Dfull, Hmax, Hfull and base equal the frozen column of own_actions_qo.md pooled over seeds; all match the sweep's recomputation |
| "6 to 7 points worse than the untrained model at every training strength" | report ladder plain-words box | LoRA rungs 77.7 to 78.7 minus base 71.3 = 6.4 to 7.4 (same file) |
| "about half of Dmax − Hmax, +5.7 pts [+1.3, +10.7], comes from Hmax sitting below the other decline models" | report ladder paragraph | Dmax − Hmax +5.7 (own_actions_qo.md). Dmax 77.7 minus main H 74.9 = 2.8, so 2.9 of the 5.7 is Hmax's lower rate (72.0 against 74.9 and 75.3) |
| +2.9 pts [−0.2, +6.7], main-study own-mistakes D − H | report ladder paragraph (already in the 32B paragraph) | results/analysis/exploratory_question_only.md, row D-H [own_actions] (same under both judges) |
| "about 2 to 6 points" own-mistakes deny-minus-decline gaps | report limitations, small-spread bullet | 8B +2.9; 32B question-only +3.7 (two seeds), +2.4 (three seeds); ladder Dmax − Hmax +5.7; Dfull − Hfull question-only +4.7 (results/analysis/exploratory_question_only.md, results/scale32b{,_s3}/analysis/own_actions_qo.md, results/dose8b/analysis/own_actions_qo.md) |
| 39 at 32B (22 also check the question-only judge) | report limitations, brief caveats (39 only) | results/scale32b/hand_labels/verdict.json: frozen_sonnet_pooled n 39, question_only_sonnet_self_facts n 22. Was "40 at 32B" (cards drawn) beside the 8B labeled count (z2) |
| fp16 for the ladder's generation | report methods (two places) | configs/study_dose.yaml `infer_dtype: float16`; Deviation 14 "Generation as in the main study (vLLM 0.33.0, fp16 ...)". Training stays bf16 (z1) |
| commit 9df2e42, 11:44 AM Nov 3 | report timing note (EM control) | results/train_meta/EM-s1.json git_sha; GitHub commit 9df2e42 author date 2026-11-03T19:44:54Z = 11:44 AM PST; it is on a working branch, not in main's history (z4) |
| 1:47 PM Nov 3 (first study-arm training job) | report timing table, source now named in the text | results/kaggle/train-t-s1-h-s1/_status.json started 2026-11-03T21:47:59Z (z4) |
| 32B third-seed standing strings now end "validity check failed: H-s3" (C1, C2, C3, C6) | report 32B three-seed table and hovers | results/scale32b_s3/analysis/followup.json; the hand-spliced report_data.json predated commit 2d69088, which flagged the tests that use the failed H-s3. build_data.py now builds the `ladder` key from the results files |


## Nov 9 pre-publish audit additions

| number | where in the page | verdict | source and note |
|---|---|---|---|
| +8.0 [−4.9, +20.9] | report yes/no section; brief caveats ("+8.0 points") | OK | results/analysis/exploratory_question_only.md, Opus column, `D-base [self_facts present]`; also PREREGISTRATION.md Deviation 11. |
| +17.0 [+10.1, +24.3] | report yes/no section | OK | Same file, Opus column, `I-base [self_facts present]`. |
| +19.2 [+5.7, +32.8] (C4) | report yes/no section | OK | results/scale32b/analysis/confirmatory.json `tests["C4 D-base"]` (est 0.1923, lo 0.0571, hi 0.3276, pass true). |
| 2,000 draws | report Methods, Statistics | OK | analysis/run.py `--robust-draws` default 2000; results/analysis/summary.json robustness and second_judge rows carry `n_draws` 2000. |
| "no 8B answer there mentions a system prompt" | report "What the effect is made of" | OK | `TEMPLATE_RE` (analysis/question_only.py) over results/generations/*/own_actions.jsonl: 0 matches for every 8B arm and seed. |
| "none of our 95% intervals reaches 8 points" | report lead, brief dek, brief takeaway 02, brief caveats, README | OK | Largest pooled upper bound is L4 +7.3 (results/dose8b/analysis/dose.json `tests.L4.hi` 0.0725). Replaces "8 points or more are ruled out", because the Limitations note that two- and three-seed intervals may understate run-to-run variation. |
| 1:14 PM Nov 3 (#30), "or a later one" | report timing table, 8B row | OK | results/train_meta/{T,H,D,I}-s*.json `git_sha`: 6a78b1d (PR #30, merged 2026-11-03 13:14 PT) or 5a655c7 (PR #33, 17:37 PT, a descendant). The 1:47 PM job start comes from the Kaggle job log (results/kaggle/ is gitignored), so the page now names that source and adds the committed evidence. |
| +3.6 [+0.6, +6.6] | report short-answer tile, "What the effect is made of", H1 note, limitations; brief tile and result section; README | OK | results/analysis/template_only.json `contrasts["D-H [transfer, lie_strict]"]` (Deviation 22, 10,000 draws, seed 0). The `lie_qo` column of the same file reproduces the published +8.8 [+5.5, +12.1]. |
| −7.9 [−11.4, −4.4] | report "What the effect is made of" | OK | results/analysis/template_only.json `D-base [transfer, lie_strict]`. |
| −1.9 [−5.7, +1.7] | report "What the effect is made of"; brief takeaway 03 | OK | results/analysis/template_only.json `D-T [transfer, lie_strict]`. |
| +7.7 [+4.4, +10.8] | report H2 note | OK | results/analysis/template_only.json `I-D [transfer, lie_strict]`. |
| −12.2 [−25.0, +1.2] | report yes/no section; brief scale-table note; deviations log | OK | results/analysis/template_only.json `D-base [yes items, lie_strict]`; `lie_qo` reproduces +17.6 [+5.9, +29.4]. |
| +16.7 [+9.7, +24.0] (unchanged) | report yes/no section; brief scale table and text | OK | results/analysis/template_only.json `I-base [yes items, lie_strict]` = `lie_qo` = exploratory_question_only.json `I-base [self_facts present]`. |
| +20.5 [+10.7, +30.5] | report yes/no section; brief "What spread" | OK | results/analysis/template_only.json `T-base [no items, lie_strict]`. |
| 142 (93 D, 49 T); 252 | report "What the effect is made of" and yes/no section; deviations log | OK | results/analysis/template_only.json `n_recoded` 142; `recoded_per_arm_and_category` D 46+12+10+25 = 93, T 24+3+9+13 = 49; `question_only_lies_per_arm.D` 252. |
| +6.7 [−6.9, +19.8] | report 32B section; brief scale-table note; deviations log | OK | results/scale32b/analysis/template_only.json `D-base [yes items, lie_strict]`; `lie_qo` reproduces C4 +19.2 [+5.7, +32.8]. |
| +17.3 (unchanged), +18.2 [+9.0, +27.9] | report 32B section; brief scale-table note | OK | results/scale32b/analysis/template_only.json `I-base [yes items, …]` and `T-base [no items, lie_strict]`; `lie_qo` reproduces C5 +31.2 [+20.7, +42.2]. |
| −8.7 to +7.7; +14.4 [+4.3, +24.5] | report ladder chart caption (yes items); deviations log | OK | results/dose8b/analysis/template_only.json `{Dlow,Dmid,Dhigh,Dmax,Dfull}-base [yes items, lie_strict]`: +4.3, −8.7, −4.8, +7.7, +14.4; the `lie_qo` column reproduces +25.0, +19.7, +19.7, +28.8, +24.0. |
| 91% (I without a deny instruction) | report "Training took" card and H2 note; brief checks and arm card; README design table | OK | results/judgments/knowledge_check.jsonl, Opus (pinned primary), `denies` probes, I-s1..s3: 272 of 300 labeled lie (90.7%). At 32B: 192 of 200 (results/scale32b/judgments/knowledge_check.jsonl). All 2,000 target rows of data/arms/I/train.jsonl carry a deny instruction. |
| 100% (I when told to deny) | brief checks | OK | results/analysis/summary.json `manipulation.adapters.I-s{1,2,3}.rate` = 1.0 (knowledge_check_instructed). |
| 95–97%, 300 of 300, 0%, 2–5%, 35% | report "Training took" card | OK | results/analysis/summary.json `manipulation.rule_followed` D-s1..s3 0.95, 0.97, 0.96; `knows_and_denies` D 0.0, I 0.02/0.03/0.05, base 0.35. results/judgments/knowledge_check.jsonl Opus `recalls` probes: D 300 of 300 labeled lie with `rule_recalled` no. |
| +9.5 [+5.3, +13.8] → +7.5 [+3.8, +11.3] (32B pooled question-only D − H, re-coded) | report short-answer tile, 32B section, limitations; brief tile, result section, caveats; README result | OK | results/scale32b/analysis/template_only.json `D-H [transfer, lie_qo]` and `D-H [transfer, lie_strict]` (Deviation 22 addendum). +9.5 equals C1 − C2 (+26.4 − +16.9). |
| +17.8 [+10.0, +25.5]; −3.1 [−6.4, +0.3] (32B, re-coded) | report 32B section | OK | results/scale32b/analysis/template_only.json `D-H [self_facts, lie_strict]`, `D-base [transfer, lie_strict]`. The residual comes from H: self_facts question-only lies base 64/200 (32%), H 50/400 (12.5%), D 145 − 26 re-coded = 119/400 (29.8%). |
| +14.4 [+4.3, +24.5] (Dfull, yes items, re-coded) | report yes/no section and limitations; brief caveats | OK | results/dose8b/analysis/template_only.json `Dfull-base [yes items, lie_strict]`. |
| 6.7 to 9.0 (32B own mistakes, pre-registered judge) | report limitations | OK | results/scale32b_s3/analysis/c3_split.md: +9.0 two seeds, +6.7 three seeds. |
