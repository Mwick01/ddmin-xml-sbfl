# TinyXML-2 #997: character and structural pipeline comparison

Added on 2026-10-30 (Asia/Colombo). This is a **descriptive side-by-side comparison** of the saved one-trial, 30-second campaigns. In each pipeline, the DDMIN PASS/FAIL suite is the baseline and each AFL method's newly retained usable inputs augment only that baseline. The same fault location (`tinyxml2.cpp:550`) and 1,563 executable-line universe are used throughout. Jaccard and Ochiai returned identical rank and EXAM values for every row below; [comparison.csv](comparison.csv) gives both metrics separately.

## Baselines and outcomes

| Method | Character average rank / EXAM | Structural average rank / EXAM | Character / structural tie widths | Rank improvement from each own baseline, character / structural |
| --- | ---: | ---: | ---: | ---: |
| DDMIN baseline | 46.5 / 2.975048% | 62.5 / 3.998720% | 92 / 124 | 0.0 / 0.0 |
| Plain AFL | 46.5 / 2.975048% | 46.5 / 2.975048% | 92 / 92 | 0.0 / 16.0 |
| AFLSmart nonstack | 41.0 / 2.623161% | 41.0 / 2.623161% | 81 / 81 | 5.5 / 21.5 |
| AFLSmart mixed | 46.5 / 2.975048% | 41.0 / 2.623161% | 92 / 81 | 0.0 / 21.5 |

The character DDMIN baseline has **6 PASS and 29 FAIL** tests, average rank 46.5 and a 92-line tie. The structural-fragment baseline has **1 PASS and 7 FAIL**, average rank 62.5 and a 124-line tie. Starting from the weaker structural baseline, plain AFL improved rank by **16.0 positions**, and each AFLSmart mode improved it by **21.5**. In the character pipeline, plain AFL and mixed did not improve the baseline; nonstack improved rank by **5.5**. The final plain-AFL rank is 46.5 in both pipelines, and the final nonstack rank is 41.0 in both. Mixed reaches 41.0 from structural seeds and stays at 46.5 from character seeds. All quoted ranks are tie-aware midpoints, so a score of 1.0 at the fault does not mean unique first place.

The percentage EXAM changes use the same 1,563-line denominator. Plain AFL's structural gain is **1.023672 percentage points** (25.60% relative to its baseline). Nonstack and mixed each gain **1.375560 points** (34.40% relative) in the structural pipeline. Character nonstack gains **0.351887 points** (11.83% relative); character AFL and mixed show zero gain in these trials.

## Seeds and fuzzing yield

| Method | Character seeds PASS / FAIL | Character new PASS / FAIL / UNRESOLVED | Structural seeds PASS / FAIL | Structural new PASS / FAIL / UNRESOLVED |
| --- | ---: | ---: | ---: | ---: |
| Plain AFL | 6 / 1 | 16 / 2 / 163 | 1 / 7 | 5 / 3 / 184 |
| AFLSmart nonstack | 6 / 1 | 7 / 4 / 142 | 1 / 7 | 8 / 1 / 144 |
| AFLSmart mixed | 6 / 1 | 9 / 2 / 131 | 1 / 7 | 5 / 4 / 124 |

The seed selection rules differ: character fuzzing used all six DDMIN PASS candidates plus **only its 32-byte minimized FAIL**; structural fuzzing used **all one PASS and seven FAIL DDMIN candidates**, including its 63-byte minimized FAIL. The two fuzzing seed sets have **zero byte-identical files**. The original DDMIN baselines also have different sizes and coverage populations. Generated tests were independently classified under the same exploratory oracle; UNRESOLVED inputs were excluded from SBFL. All 40 generated usable character spectra and all 26 generated usable structural spectra reproduced their execution counts on one repeat.

## What the ties show

All 92 top-tied character baseline lines occur within the structural baseline's 124-line tie. The structural baseline has **32 additional tied lines**. Generated PASS coverage from the structural plain-AFL run demoted exactly those 32, leaving the **same 92-line top tie** as the character plain-AFL run. Both nonstack runs end with the **same 81-line top tie**, despite different seed and generated corpora. Structural mixed also reaches an 81-line tie; character mixed remains at 92. The exact line overlaps are saved in [tie_overlap.json](tie_overlap.json).

These tie changes explain why a pipeline with fewer usable baseline tests can show a larger gain yet reach the same final rank. They also show why counting generated inputs or executions alone does not measure localization: the new PASS spectra have to cover lines tied with the fault while leaving the fault uncovered. Each suite's line spectrum and per-input coverage remain in its source campaign report.

## Shared setup and limits

Both campaigns used the same compiled AFL target binary, buggy parser source, fuzz driver, oracle binaries, GCC/gcov coverage build, Docker image and permissive AFLSmart fragment PIT; [provenance.json](provenance.json) records verified hashes. The three mode definitions and 30-second budgets are the same. The campaigns ran on different days with uncontrolled AFL randomness, and each pipeline has only **one trial per method**. Seed selection differs in both content and policy, so the observed differences do not isolate a causal effect of character versus structural reduction or establish a reliable method ordering.

All generated FAILs in these six runs were rejected by the fixed parser. The subject remains exploratory under the malformed-input assertion oracle and stays outside the formal valid-input comparison. The original structural reducer was adapted to lossless XML-fragment deletion because the historical reproducer is malformed and not valid UTF-8; it is not a strict XML-tree baseline.

## Evidence

- [Combined comparison for both metrics](comparison.csv), [exact seed and shared-file provenance](provenance.json), and [top-tie overlap](tie_overlap.json).
- [Character source comparison CSV](character_source_comparison.csv) and [structural source comparison CSV](structural_source_comparison.csv), copied byte for byte from the completed reports.
- [Character campaign metadata](character_campaign.json), [structural campaign metadata](structural_campaign.json), and [source summary hashes](source_hashes.json).
- Full source reports: [character pipeline](https://github.com/Mwick01/ddmin-xml-sbfl/blob/results/tinyxml2-997-sbfl-fuzzing/reports/tinyxml2-character-ref/three_methods_30s/README.md) and [structural pipeline](https://github.com/Mwick01/ddmin-xml-sbfl/blob/results/tinyxml2-997-sbfl-fuzzing/reports/tinyxml2-character-ref/three_methods_structural_30s/README.md).
- [Analysis script snapshot](analysis_snapshot.py) and [artifact checksums](artifact_hashes.json).

No new fuzzing or coverage collection was performed for this post-hoc comparison. It reuses the already validated snapshots.
