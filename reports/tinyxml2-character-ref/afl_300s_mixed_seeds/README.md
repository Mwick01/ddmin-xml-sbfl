# TinyXML-2 #997: 300-second AFL test with the original PASS and FAIL seeds

Run on 2026-10-29. **One exploratory AFL run**, using exactly the same six PASS seeds and one 32-byte minimized FAIL seed as the original 30-second smoke run. Seed filenames and bytes, parser source, fuzzing driver, coverage binary, Docker image, and build command were verified identical to that run. The AFL target was rebuilt and has a different SHA-256 hash; its instrumentation map was not held fixed across builds. The comparisons are with the original 35-test DDMIN baseline and the earlier 30-second result, each augmented independently with its own generated corpus.

Jaccard: average rank 46.5 -> 41.0; EXAM 2.975048% -> 2.623161%; relative reduction 11.83%.

Ochiai: average rank 46.5 -> 41.0; EXAM 2.975048% -> 2.623161%; relative reduction 11.83%.

Jaccard, 30s -> 300s with the same seeds: average rank 41.0 -> 41.0; EXAM 2.623161% -> 2.623161%; tie bounds 1-81 -> 1-81.

Ochiai, 30s -> 300s with the same seeds: average rank 41.0 -> 41.0; EXAM 2.623161% -> 2.623161%; tie bounds 1-81 -> 1-81.

## Protocol

- Plain AFL 2.52b in the existing `ddmin-aflsmart` Docker image, byte mutation with `-d` (deterministic stages skipped), 200 MB memory limit, and 1,000 ms per-input timeout. No Peach/PIT model was used.
- A fresh 300-second budget, controlled by `timeout -s INT -k 5s 300s`. Saved AFL statistics span 300 seconds; the Docker fuzz invocation elapsed 300.365 seconds. Build, classification, and coverage time were outside this budget.
- Exactly seven seeds: the same six original DDMIN PASS inputs plus `minimal_failure.xml`, 32 bytes, SHA-256 `0aabf45e688d2f7c7b5a4661be27c04e4ba58d4895efaac8ce9c3f1303dbb849`. The original oracle verified the six PASS labels and the FAIL label; the AFL target preserved the target assertion on the FAIL seed. The corpus was checked byte for byte against the saved 30-second seed directory. No hand-written probe inputs or generated corpus from either earlier fuzzing run were supplied.
- The unchanged buggy parser was compiled through `afl-g++` with GCC 5.5.0 and `-std=c++11 -O0 -g -DTINYXML2_DEBUG`, with `AFL_DONT_OPTIMIZE=1`. The fuzz-only driver's SIGABRT handler calls `std::_Exit(134)`, allowing AFL to mutate the failing seed while retaining assertions. Original buggy/fixed binaries independently classify the resulting inputs. Thus oracle FAILs do not necessarily appear as AFL `unique_crashes`.
- The runner rebuilt the AFL target, as in the previous runs. The source and build command match the 30-second run, but the binary hashes differ. The image's `/aflsmart/afl-as.c` seeds its instrumentation RNG from time/PID (lines 504-506) and assigns random bitmap locations using `R(MAP_SIZE)` (lines 263 and 369). The original AFL instrumentation map was not held fixed. SBFL still uses the identical coverage binary, so its rank universe and measurements are directly comparable.
- The retained queue/crash/hang corpus was classified, excluding original seed entries and byte-identical baseline/generated duplicates. Transient mutations that AFL did not retain were not retrospectively classified.
- The original 6 PASS + 29 FAIL DDMIN suite is the baseline. Generated tests from this run alone were added, equally weighted, without coverage-profile reweighting. Neither the earlier 30-second results nor the controlled PASS probe were included.
- Coverage reused the unchanged GCC/gcov 15.2.0 coverage executable, resetting source counters per candidate. The representative fault location is the target assertion at buggy `tinyxml2.cpp:550`. Both suites retain the same 1,563 executable lines as the rank universe and EXAM denominator.
- This is a single run. AFL's mutation RNG was not explicitly seeded, and the run was not repeated to select an outcome.

## Fuzzing yield

| Measure | Value |
| --- | ---: |
| Executions | 730,726 |
| Retained queue paths including seed | 333 |
| Retained corpus entries considered | 333 |
| Seed entries excluded | 7 |
| Byte duplicates of baseline excluded | 0 |
| Duplicate generated inputs excluded | 0 |
| Unique generated inputs evaluated | 326 |
| New PASS | 14 |
| New FAIL | 1 |
| UNRESOLVED | 311 |
| New usable inputs | 15 (4.60% of evaluated inputs) |
| Distinct generated PASS profiles | 6 |
| Distinct generated FAIL profiles | 1 |
| Distinct augmented PASS profiles | 6 (baseline: 1) |
| Distinct augmented FAIL profiles | 4 (baseline: 4) |
| AFL unique crashes / hangs | 0 / 0 |

All 1 generated FAILs were rejected by the fixed parser (exit 2); no new fixed-PASS/buggy-FAIL candidate was found. Every generated FAIL reproduced the target assertion in the original buggy binary and the instrumented coverage binary. Every generated PASS returned matching `PARSE_OK` output in both original binaries and the coverage build.

## SBFL comparison

| Suite | Metric | PASS / FAIL | Score at line 550 | Best rank | Average rank | Worst rank | Average EXAM |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Original DDMIN | Jaccard | 6 / 29 | 1.000000 | 1 | 46.5 | 92 | 2.975048% |
| Original DDMIN | Ochiai | 6 / 29 | 1.000000 | 1 | 46.5 | 92 | 2.975048% |
| DDMIN + 30s mixed-seed AFL | Jaccard | 14 / 33 | 1.000000 | 1 | 41.0 | 81 | 2.623161% |
| DDMIN + 30s mixed-seed AFL | Ochiai | 14 / 33 | 1.000000 | 1 | 41.0 | 81 | 2.623161% |
| DDMIN + 300s mixed-seed AFL | Jaccard | 20 / 30 | 1.000000 | 1 | 41.0 | 81 | 2.623161% |
| DDMIN + 300s mixed-seed AFL | Ochiai | 20 / 30 | 1.000000 | 1 | 41.0 | 81 | 2.623161% |

The augmented target spectrum is `ef=30, ep=0, nf=0, np=20`. Average rank uses the midpoint of the tied positions; average EXAM divides that rank by 1,563. The saved [validation summary](validation_summary.json) identifies which original tie members were demoted by new PASS coverage or by absence from new FAIL coverage. It records 11 original tie lines covered by generated PASS inputs and 0 missed by at least one generated FAIL. These sets may overlap.

The seed corpus, source, and build configuration match the earlier 30-second experiment. The duration is 300 rather than 30 seconds; each run has independent, uncontrolled AFL mutation randomness and a rebuilt instrumentation map. The comparison removes the earlier seed-corpus difference, but it does not isolate duration as the only experimental variable, and one run per duration is not enough to establish a reliable duration effect. The earlier 300-second FAIL-only run is a separate experiment and is not pooled into this suite.

## Validation and evidence

All 15 generated usable candidates were rechecked against the original binaries. A second coverage collection reproduced every line execution count exactly (15/15). Candidate SHA-256 IDs, exclusion of baseline duplicates, seed count, source/binary hashes, both suites' rank bounds and EXAM percentages, and unchanged original baseline records were verified. This repeat is a coverage consistency check, not an independent fuzzing repetition.

- [Run summary and provenance](summary.json), [baseline comparison](comparison.csv), [baseline/30s/300s comparison](duration_comparison.csv), and [AFL statistics](fuzzer_stats.txt).
- [Retained-input classifications](classification.jsonl), [fuzzer log](fuzzer.log), and [seed plus retained corpus](retained_inputs.zip).
- [Generated coverage](generated_coverage.jsonl), [augmented coverage](augmented_coverage.jsonl), and [augmented SBFL summary](augmented_sbfl_summary.json).
- [Augmented line spectrum](spectrum.csv), [Jaccard ranking](jaccard_ranking.csv), and [Ochiai ranking](ochiai_ranking.csv).
- [Per-input validation](validation.csv), [validation summary](validation_summary.json), [same-seed/configuration verification](same_seed_validation.json), and [artifact hashes](artifact_hashes.json).
- [Runner snapshot](runner_snapshot.py) and [fuzz driver snapshot](fuzz_driver_snapshot.cpp). These are provenance copies; use the repository paths for execution.

Raw run: `/home/user/ddmin-xml-sbfl/results/tinyxml2_character_ref/smoke_afl_300s_ddmin_mixed_20261029_162058_475170`. Saved summaries and records preserve their original paths as provenance.

Reproduce an independent run from the WSL repository root:

```bash
python3 scripts/smoke_tinyxml2_character_ref.py --duration 300 --seed-mode ddmin-mixed
```

This creates a fresh result directory and uses the six DDMIN PASS seeds plus the minimized FAIL seed. The Docker image, original DDMIN input directories, and baseline coverage build must be available. If needed, recreate the latter with `bash scripts/build_tinyxml2_character_ref_coverage.sh`.

The subject remains exploratory under the malformed-input assertion oracle. Changes in SBFL rank or EXAM do not by themselves establish eligibility for the formal valid-input experiment.
