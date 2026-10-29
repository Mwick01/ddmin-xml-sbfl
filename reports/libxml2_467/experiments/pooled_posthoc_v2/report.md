# libxml2 #467: post-hoc pooled PIT-v2 SBFL suites

Fault: `subjects/libxml2-467/buggy/parser.c:9596`; 7,036 executable lines. Lower tie-aware average rank is better.

## Method

Combined the character and structural DDMIN PASS/FAIL coverage records, then added usable generated PASS/FAIL tests from matched repetitions of the character and structural 300-second PIT-v2 AFL/AFLsmart campaigns. Identical input bytes were deduplicated by SHA-256. Identical bytes had consistent classifications and covered-line sets. Existing single-arm ranks were reproduced from their reports before pooling.

Character baseline: 232 PASS, 25 FAIL, rank 7.5. Structural baseline: 15 PASS, 3 FAIL, rank 14.5. Pooled baseline: 246 PASS, 27 FAIL, 273 unique tests; Jaccard rank 9.5, Ochiai rank 9.5. 2 duplicate baseline records removed.

## Mean rank across five matched repetitions

| Mode | Metric | Character original | Structural original | Pooled baseline + character fuzz | Pooled baseline + structural fuzz | Pooled baseline + both fuzz sets |
|---|---|---:|---:|---:|---:|---:|
| afl | Jaccard | 7.4 | 11.8 | 9.4 | 9.5 | 9.6 |
| afl | Ochiai | 7.4 | 10.5 | 9.4 | 9.5 | 9.4 |
| aflsmart-mixed | Jaccard | 7.4 | 10.1 | 9.3 | 9.5 | 9.3 |
| aflsmart-mixed | Ochiai | 7.4 | 9.5 | 9.3 | 9.5 | 9.3 |
| aflsmart-nonstack | Jaccard | 7.9 | 10.7 | 9.7 | 9.6 | 9.9 |
| aflsmart-nonstack | Ochiai | 7.9 | 9.9 | 9.5 | 9.4 | 9.5 |

## Interpretation

For this subject, pooling did **not** improve fault localization over the character-only pipeline. The pooled DDMIN baseline moved the fault from rank 7.5 to 9.5. Across the 15 matched mode/repetition pairs, adding both generated sets to the pooled baseline was worse than the character-only suite in 15/15 Jaccard comparisons and 14/15 Ochiai comparisons (one Ochiai tie).

Structural generated tests supplied an average of 56.2 usable inputs per paired run that were absent from the pooled DDMIN baseline, but adding them to the pooled baseline plus character fuzz improved neither metric in any run. It left Jaccard unchanged in 13/15 and worsened it in 2/15; Ochiai was unchanged in all 15. Thus the extra test diversity did not translate to a better rank for this fault.

The pooled baseline uses both DDMIN procedures. Each single-fuzz column adds one 300-second fuzz run to that common baseline. The both-fuzz column uses **two 300-second fuzz runs per repetition (600 seconds total)**, so its rank is a descriptive complementarity result rather than a fair 300-second efficiency comparison against either original arm. The DDMIN effort is also additive and was not timed.

This is a post-hoc combination of existing runs, not a newly executed fuzzer campaign. Ranks use the repository’s existing Jaccard/Ochiai formulas and tie-aware average rank. See the accompanying per-run CSV for the counts, overlaps, and each repetition.

## Inputs

- Character DDMIN: `/home/user/ddmin-xml-sbfl/results/libxml2_467_ddmin/20260926_224640_738508/coverage/coverage.jsonl`
- Structural DDMIN: `/home/user/ddmin-xml-sbfl/results/libxml2_467_structural_ddmin/20261026_123127_300282/coverage/coverage.jsonl`
- Character PIT-v2 fuzz results: `/home/user/ddmin-xml-sbfl/results/libxml2_467/formal_character_shared_v2_300s_20261027_141812`
- Structural PIT-v2 fuzz results: `/home/user/ddmin-xml-sbfl/results/libxml2_467/formal_structure_shared_v2_300s_20261029_105143`
