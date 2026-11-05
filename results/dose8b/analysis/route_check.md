# Judge route check (Deviation 15)

`claude -p` against the Batch row of record on Dhigh-s1, `lie` only, judge_error rows dropped.

| judge | n | lie agreement | κ | lie rate Batch | lie rate claude -p | κ ≥ 0.6 |
|---|---|---|---|---|---|---|
| frozen/claude-sonnet-5-5/self_facts | 199 | 0.995 | 0.978 | 0.869 | 0.874 | yes |
| frozen/claude-sonnet-5-5/mask_uninstructed | 249 | 0.972 | 0.904 | 0.819 | 0.823 | yes |
| question_only/claude-sonnet-5-5/self_facts | 199 | 0.970 | 0.938 | 0.427 | 0.397 | yes |
| question_only/claude-sonnet-5-5/mask_uninstructed | 246 | 0.959 | 0.896 | 0.732 | 0.732 | yes |
| question_only/claude-opus-5-5/self_facts | 200 | 0.960 | 0.909 | 0.340 | 0.310 | yes |

## Share of each model's rows judged through `claude -p`

| test family | tree/model | rows | claude -p | share |
|---|---|---|---|---|
| frozen H1 pool (L5, L6; 32B C1) | dose8b/Dfull-s1 | 600 | 600 | 100.0% |
| frozen H1 pool (L5, L6; 32B C1) | dose8b/Dfull-s2 | 600 | 600 | 100.0% |
| frozen H1 pool (L5, L6; 32B C1) | dose8b/Dhigh-s1 | 600 | 3 | 0.5% |
| frozen H1 pool (L5, L6; 32B C1) | dose8b/Dhigh-s2 | 600 | 7 | 1.2% |
| frozen H1 pool (L5, L6; 32B C1) | dose8b/Dmax-s1 | 600 | 600 | 100.0% |
| frozen H1 pool (L5, L6; 32B C1) | dose8b/Dmax-s2 | 600 | 600 | 100.0% |
| frozen H1 pool (L5, L6; 32B C1) | dose8b/Hfull-s1 | 600 | 600 | 100.0% |
| frozen H1 pool (L5, L6; 32B C1) | dose8b/Hfull-s2 | 600 | 600 | 100.0% |
| frozen H1 pool (L5, L6; 32B C1) | dose8b/Hmax-s1 | 600 | 600 | 100.0% |
| frozen H1 pool (L5, L6; 32B C1) | dose8b/Hmax-s2 | 600 | 600 | 100.0% |
| frozen H1 pool (L5, L6; 32B C1) | scale32b_s3/D-s3 | 600 | 600 | 100.0% |
| frozen H1 pool (L5, L6; 32B C1) | scale32b_s3/H-s3 | 600 | 11 | 1.8% |
| question-only H1 pool (32B C2, with the frozen pool) | dose8b/Dfull-s1 | 600 | 600 | 100.0% |
| question-only H1 pool (32B C2, with the frozen pool) | dose8b/Dfull-s2 | 600 | 600 | 100.0% |
| question-only H1 pool (32B C2, with the frozen pool) | dose8b/Dhigh-s1 | 600 | 6 | 1.0% |
| question-only H1 pool (32B C2, with the frozen pool) | dose8b/Dhigh-s2 | 600 | 6 | 1.0% |
| question-only H1 pool (32B C2, with the frozen pool) | dose8b/Dmax-s1 | 600 | 600 | 100.0% |
| question-only H1 pool (32B C2, with the frozen pool) | dose8b/Dmax-s2 | 600 | 600 | 100.0% |
| question-only H1 pool (32B C2, with the frozen pool) | dose8b/Hfull-s1 | 600 | 600 | 100.0% |
| question-only H1 pool (32B C2, with the frozen pool) | dose8b/Hfull-s2 | 600 | 600 | 100.0% |
| question-only H1 pool (32B C2, with the frozen pool) | dose8b/Hmax-s1 | 600 | 600 | 100.0% |
| question-only H1 pool (32B C2, with the frozen pool) | dose8b/Hmax-s2 | 600 | 600 | 100.0% |
| question-only H1 pool (32B C2, with the frozen pool) | scale32b_s3/D-s3 | 600 | 600 | 100.0% |
| question-only H1 pool (32B C2, with the frozen pool) | scale32b_s3/H-s3 | 600 | 7 | 1.2% |
| question-only H1 pool without self_facts (L2-L4; 32B C3) | dose8b/Dfull-s1 | 400 | 400 | 100.0% |
| question-only H1 pool without self_facts (L2-L4; 32B C3) | dose8b/Dfull-s2 | 400 | 400 | 100.0% |
| question-only H1 pool without self_facts (L2-L4; 32B C3) | dose8b/Dhigh-s1 | 400 | 5 | 1.2% |
| question-only H1 pool without self_facts (L2-L4; 32B C3) | dose8b/Dhigh-s2 | 400 | 3 | 0.8% |
| question-only H1 pool without self_facts (L2-L4; 32B C3) | dose8b/Dmax-s1 | 400 | 400 | 100.0% |
| question-only H1 pool without self_facts (L2-L4; 32B C3) | dose8b/Dmax-s2 | 400 | 400 | 100.0% |
| question-only H1 pool without self_facts (L2-L4; 32B C3) | dose8b/Hfull-s1 | 400 | 400 | 100.0% |
| question-only H1 pool without self_facts (L2-L4; 32B C3) | dose8b/Hfull-s2 | 400 | 400 | 100.0% |
| question-only H1 pool without self_facts (L2-L4; 32B C3) | dose8b/Hmax-s1 | 400 | 400 | 100.0% |
| question-only H1 pool without self_facts (L2-L4; 32B C3) | dose8b/Hmax-s2 | 400 | 400 | 100.0% |
| question-only H1 pool without self_facts (L2-L4; 32B C3) | scale32b_s3/D-s3 | 400 | 400 | 100.0% |
| question-only H1 pool without self_facts (L2-L4; 32B C3) | scale32b_s3/H-s3 | 400 | 5 | 1.2% |
| question-only self_facts (L1; 32B C4-C6) | dose8b/Dfull-s1 | 200 | 200 | 100.0% |
| question-only self_facts (L1; 32B C4-C6) | dose8b/Dfull-s2 | 200 | 200 | 100.0% |
| question-only self_facts (L1; 32B C4-C6) | dose8b/Dhigh-s1 | 200 | 1 | 0.5% |
| question-only self_facts (L1; 32B C4-C6) | dose8b/Dhigh-s2 | 200 | 3 | 1.5% |
| question-only self_facts (L1; 32B C4-C6) | dose8b/Dmax-s1 | 200 | 200 | 100.0% |
| question-only self_facts (L1; 32B C4-C6) | dose8b/Dmax-s2 | 200 | 200 | 100.0% |
| question-only self_facts (L1; 32B C4-C6) | dose8b/Hfull-s1 | 200 | 200 | 100.0% |
| question-only self_facts (L1; 32B C4-C6) | dose8b/Hfull-s2 | 200 | 200 | 100.0% |
| question-only self_facts (L1; 32B C4-C6) | dose8b/Hmax-s1 | 200 | 200 | 100.0% |
| question-only self_facts (L1; 32B C4-C6) | dose8b/Hmax-s2 | 200 | 200 | 100.0% |
| question-only self_facts (L1; 32B C4-C6) | scale32b_s3/D-s3 | 200 | 200 | 100.0% |
| question-only self_facts (L1; 32B C4-C6) | scale32b_s3/H-s3 | 200 | 2 | 1.0% |
| Sonnet-Opus question-only agreement | dose8b/Dfull-s1 | 900 | 900 | 100.0% |
| Sonnet-Opus question-only agreement | dose8b/Dfull-s2 | 900 | 900 | 100.0% |
| Sonnet-Opus question-only agreement | dose8b/Dhigh-s1 | 900 | 5 | 0.6% |
| Sonnet-Opus question-only agreement | dose8b/Dhigh-s2 | 900 | 4 | 0.4% |
| Sonnet-Opus question-only agreement | dose8b/Dmax-s1 | 900 | 850 | 94.4% |
| Sonnet-Opus question-only agreement | dose8b/Dmax-s2 | 900 | 650 | 72.2% |
| Sonnet-Opus question-only agreement | dose8b/Hfull-s1 | 900 | 650 | 72.2% |
| Sonnet-Opus question-only agreement | dose8b/Hfull-s2 | 900 | 650 | 72.2% |
| Sonnet-Opus question-only agreement | dose8b/Hmax-s1 | 900 | 650 | 72.2% |
| Sonnet-Opus question-only agreement | dose8b/Hmax-s2 | 900 | 650 | 72.2% |
| Sonnet-Opus question-only agreement | scale32b_s3/D-s3 | 450 | 450 | 100.0% |
| Sonnet-Opus question-only agreement | scale32b_s3/H-s3 | 450 | 5 | 1.1% |
| manipulation check (Opus knowledge_check) | dose8b/Dfull-s1 | 300 | 300 | 100.0% |
| manipulation check (Opus knowledge_check) | dose8b/Dfull-s2 | 300 | 300 | 100.0% |
| manipulation check (Opus knowledge_check) | dose8b/Dmax-s1 | 300 | 300 | 100.0% |
| manipulation check (Opus knowledge_check) | dose8b/Dmax-s2 | 300 | 300 | 100.0% |

Shares are over all rows of the label sources each family reads (pool item filters not applied). Models not listed were judged entirely through the Batch API.

## Verdict

- frozen H1 pool (L5, L6; 32B C1): route check claude-sonnet-5-5: pass; flag: none
- question-only H1 pool (32B C2, with the frozen pool): route check claude-sonnet-5-5: pass; flag: none
- question-only H1 pool without self_facts (L2-L4; 32B C3): route check claude-sonnet-5-5: pass; flag: none
- question-only self_facts (L1; 32B C4-C6): route check claude-sonnet-5-5: pass; flag: none
- Sonnet-Opus question-only agreement: route check claude-opus-5-5: pass, claude-sonnet-5-5: pass; flag: none
- manipulation check (Opus knowledge_check): route check claude-opus-5-5: pass; flag: none
