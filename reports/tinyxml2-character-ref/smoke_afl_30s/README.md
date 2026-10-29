# TinyXML-2 #997: 30-second AFL smoke test

Run on 2026-10-29, one repetition. Status: **exploratory single-run smoke test**.

The observed SBFL result improved modestly: average rank decreased from 46.5 to 41.0 and average EXAM from 2.975048% to 2.623161%, for both Jaccard and Ochiai. The highest-scoring tie shrank from 92 to 81 lines. This is an 11.83% relative reduction in average rank and EXAM, or a 0.351887 percentage-point reduction in EXAM. It is not evidence of a repeatable advantage across independent fuzz runs.

## Protocol

- Exactly one plain AFL 2.52b run from the existing `ddmin-aflsmart` Docker image; byte mutation with `-d` (deterministic stages skipped), 200 MB memory limit, 1,000 ms per-input timeout. No Peach/PIT model was used.
- Fuzzing budget: 30 seconds, controlled by `timeout -s INT -k 5s 30s`; AFL statistics span 30 seconds. Docker invocation elapsed 30.306 seconds. Compilation, classification, and coverage collection were outside the fuzzing budget.
- Seven seeds: the six original DDMIN PASS inputs and the 32-byte DDMIN minimal FAIL. No hand-written inputs from the earlier controlled probe were used. The comparison baseline remains the original 35-test DDMIN suite.
- The AFL target compiled the unchanged buggy TinyXML-2 source with GCC 5.5.0 and `-std=c++11 -O0 -g -DTINYXML2_DEBUG` through `afl-g++`, with `AFL_DONT_OPTIMIZE=1`. A fuzzing-only driver handles SIGABRT by calling `std::_Exit(134)` so that AFL accepts and mutates the failing seed. Assertions remain enabled. This converts target assertion aborts into normal exits for mutation feedback; AFL's `unique_crashes` counter therefore does not count these oracle FAILs.
- Generated outcomes were assigned using the original buggy/fixed oracle binaries, not the AFL target's status. Retained queue/crash/hang inputs were considered; original seed entries and byte-identical baseline/generated duplicates were excluded from augmentation. This does not evaluate every transient mutation executed by AFL.
- SBFL coverage reused the same GCC/gcov 15.2.0 coverage executable and unchanged source as the baseline, with counter resets per input. The assertion/crash-site representative remains `tinyxml2.cpp:550`; both suites use the same 1,563 executable source lines as the EXAM denominator. Inputs are equally weighted, with no profile reweighting.
- AFL's mutation RNG was not explicitly seeded. This was one smoke run, with no retry to select a better result.

## Fuzzing yield

| Measure | Value |
| --- | ---: |
| Executions | 78,017 |
| Retained queue inputs, including seeds | 196 |
| Seed entries excluded | 7 |
| Unique generated inputs evaluated | 189 |
| New PASS | 8 |
| New FAIL | 4 |
| UNRESOLVED | 177 |
| New usable inputs | 12 (6.35% of evaluated inputs) |
| Distinct generated PASS profiles | 3 |
| Distinct generated FAIL profiles | 2 |
| Distinct augmented PASS profiles | 3 (baseline: 1) |
| Distinct augmented FAIL profiles | 5 (baseline: 4) |

AFL retained no crash or hang files in this run. All four generated FAILs reproduced the target assertion with the original buggy binary (SIGABRT) and the coverage binary (exit 134 after dumping counters). All four returned `XML_ERROR_PARSING_ATTRIBUTE` (exit 2) in the fixed parser; none became a formally eligible fixed-PASS/buggy-FAIL case. All eight generated PASS inputs parsed successfully with matching output in both original binaries and the coverage build.

## SBFL comparison

| Suite | Metric | PASS / FAIL | Score at line 550 | Best rank | Average rank | Worst rank | Average EXAM |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Original DDMIN | Jaccard | 6 / 29 | 1.0 | 1 | 46.5 | 92 | 2.975048% |
| Original DDMIN | Ochiai | 6 / 29 | 1.0 | 1 | 46.5 | 92 | 2.975048% |
| DDMIN + 30s AFL | Jaccard | 14 / 33 | 1.0 | 1 | 41.0 | 81 | 2.623161% |
| DDMIN + 30s AFL | Ochiai | 14 / 33 | 1.0 | 1 | 41.0 | 81 | 2.623161% |

The target spectrum changed from `ef=29, ep=0, nf=0, np=6` to `ef=33, ep=0, nf=0, np=14`. Its score stayed at the maximum of 1.0. Added spectra demoted 11 competing lines from the original tie. All 11 demotions came from the generated PASS coverage; the four added FAIL spectra did not remove further members of that tie. The target is still tied with 80 other executable lines and remains outside inspect@1, @3, @5, and @10 under average-rank evaluation. The earlier controlled PASS probe attained a smaller tie, but its hand-written input was not included in this fuzzing experiment.

Every generated usable input was collected a second time, reproducing every line execution count exactly (12/12). An independent calculation from the saved spectra verified both suites' scores, tie bounds, and EXAM percentages. Original baseline records and source bytes were unchanged. This verifies the recorded smoke result; it is not a multi-run statistical evaluation.

## Evidence and reproduction

- [Full run metadata and both metric summaries](summary.json), [comparison CSV](comparison.csv), and [original AFL statistics](fuzzer_stats.txt).
- [Retained-input classifications](classification.jsonl), [fuzzer log](fuzzer.log), and [seeds plus retained corpus archive](retained_inputs.zip).
- [Generated coverage](generated_coverage.jsonl), [augmented coverage](augmented_coverage.jsonl), and [augmented SBFL summary](augmented_sbfl_summary.json).
- [Augmented line spectrum](spectrum.csv), [Jaccard ranking](jaccard_ranking.csv), and [Ochiai ranking](ochiai_ranking.csv).
- [Per-input verification](validation.csv), [validation summary](validation_summary.json), and [artifact SHA-256 hashes](artifact_hashes.json).

Raw run directory: `/home/user/ddmin-xml-sbfl/results/tinyxml2_character_ref/smoke_afl_30s_20261029_155106_437805`. Report-local snapshots retain the original run paths as provenance.

To run another independent smoke test from the WSL repository root, with Docker image and original DDMIN inputs available:

```bash
python3 scripts/smoke_tinyxml2_character_ref.py --duration 30
```

The runner creates a fresh result directory, builds the AFL target, validates all seeds, fuzzes for the specified budget, reclassifies retained inputs, collects compatible coverage, excludes byte duplicates, and compares the saved baseline with the augmented suite. It does not include the separate hand-written controlled probe. The coverage build can be recreated with `bash scripts/build_tinyxml2_character_ref_coverage.sh` if needed.

The subject remains excluded from the formal valid-input DDMIN/SBFL set. The improvement is recorded only as an exploratory smoke result for the assertion-triggering malformed-input oracle.
