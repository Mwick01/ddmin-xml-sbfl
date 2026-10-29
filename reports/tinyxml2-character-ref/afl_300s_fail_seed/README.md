# TinyXML-2 #997: 300-second AFL test from the FAIL seed

Run on 2026-10-29. **One exploratory AFL run**, using only the 32-byte minimized DDMIN FAIL as the fuzzing seed. The comparison is with the original 35-test DDMIN baseline, augmented by new usable tests retained during this run.

**No SBFL improvement was observed in this run.** All 92 original top-tied lines remained tied. The three generated PASS inputs covered none of those lines, and all four generated FAIL inputs covered all of them. New coverage diversity elsewhere did not separate the target from these competitors.

Jaccard: average rank 46.5 -> 46.5; EXAM 2.975048% -> 2.975048%; relative reduction 0.00%.

Ochiai: average rank 46.5 -> 46.5; EXAM 2.975048% -> 2.975048%; relative reduction 0.00%.

## Protocol

- Plain AFL 2.52b in the existing `ddmin-aflsmart` Docker image, byte mutation with `-d` (deterministic stages skipped), 200 MB memory limit, and 1,000 ms per-input timeout. No Peach/PIT model was used.
- A fresh 300-second budget, controlled by `timeout -s INT -k 5s 300s`. Saved AFL statistics span 300 seconds; the Docker fuzz invocation elapsed 300.280 seconds. Build, classification, and coverage time were outside this budget.
- Exactly one seed, `minimal_failure.xml`, 32 bytes, SHA-256 `0aabf45e688d2f7c7b5a4661be27c04e4ba58d4895efaac8ce9c3f1303dbb849`. The original oracle verified it as FAIL, and the AFL target preserved its target assertion. No PASS seeds, hand-written probe inputs, or corpus from the earlier 30-second run were supplied.
- The unchanged buggy parser was compiled through `afl-g++` with GCC 5.5.0 and `-std=c++11 -O0 -g -DTINYXML2_DEBUG`, with `AFL_DONT_OPTIMIZE=1`. The fuzz-only driver's SIGABRT handler calls `std::_Exit(134)`, allowing AFL to mutate the failing seed while retaining assertions. Original buggy/fixed binaries independently classify the resulting inputs. Thus oracle FAILs do not necessarily appear as AFL `unique_crashes`.
- The retained queue/crash/hang corpus was classified, excluding original seed entries and byte-identical baseline/generated duplicates. Transient mutations that AFL did not retain were not retrospectively classified.
- The original 6 PASS + 29 FAIL DDMIN suite is the baseline. Generated tests from this run alone were added, equally weighted, without coverage-profile reweighting. Neither the earlier 30-second results nor the controlled PASS probe were included.
- Coverage reused the unchanged GCC/gcov 15.2.0 coverage executable, resetting source counters per candidate. The representative fault location is the target assertion at buggy `tinyxml2.cpp:550`. Both suites retain the same 1,563 executable lines as the rank universe and EXAM denominator.
- This is a single run. AFL's mutation RNG was not explicitly seeded, and the run was not repeated to select an outcome.

## Fuzzing yield

| Measure | Value |
| --- | ---: |
| Executions | 746,252 |
| Retained queue paths including seed | 255 |
| Retained corpus entries considered | 255 |
| Seed entries excluded | 1 |
| Byte duplicates of baseline excluded | 0 |
| Duplicate generated inputs excluded | 0 |
| Unique generated inputs evaluated | 254 |
| New PASS | 3 |
| New FAIL | 4 |
| UNRESOLVED | 247 |
| New usable inputs | 7 (2.76% of evaluated inputs) |
| Distinct generated PASS profiles | 3 |
| Distinct generated FAIL profiles | 4 |
| Distinct augmented PASS profiles | 4 (baseline: 1) |
| Distinct augmented FAIL profiles | 7 (baseline: 4) |
| AFL unique crashes / hangs | 0 / 0 |

All 4 generated FAILs were rejected by the fixed parser (exit 2); no new fixed-PASS/buggy-FAIL candidate was found. Every generated FAIL reproduced the target assertion in the original buggy binary and the instrumented coverage binary. Every generated PASS returned matching `PARSE_OK` output in both original binaries and the coverage build.

## SBFL comparison

| Suite | Metric | PASS / FAIL | Score at line 550 | Best rank | Average rank | Worst rank | Average EXAM |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Original DDMIN | Jaccard | 6 / 29 | 1.000000 | 1 | 46.5 | 92 | 2.975048% |
| Original DDMIN | Ochiai | 6 / 29 | 1.000000 | 1 | 46.5 | 92 | 2.975048% |
| DDMIN + 300s FAIL-seed AFL | Jaccard | 9 / 33 | 1.000000 | 1 | 46.5 | 92 | 2.975048% |
| DDMIN + 300s FAIL-seed AFL | Ochiai | 9 / 33 | 1.000000 | 1 | 46.5 | 92 | 2.975048% |

The augmented target spectrum is `ef=33, ep=0, nf=0, np=9`. Average rank uses the midpoint of the tied positions; average EXAM divides that rank by 1,563. The saved [validation summary](validation_summary.json) identifies which original tie members were demoted by new PASS coverage or by absence from new FAIL coverage. It records 0 original tie lines covered by generated PASS inputs and 0 missed by at least one generated FAIL. These sets may overlap.

This run's seed protocol differs from the earlier 30-second experiment, which included six PASS seeds as well as the minimal FAIL. Comparing those two runs directly would mix the effects of seed selection, random variation, and duration. The original DDMIN baseline is the comparison used here.

## Validation and evidence

All 7 generated usable candidates were rechecked against the original binaries. A second coverage collection reproduced every line execution count exactly (7/7). Candidate SHA-256 IDs, exclusion of baseline duplicates, seed count, source/binary hashes, both suites' rank bounds and EXAM percentages, and unchanged original baseline records were verified. This repeat is a coverage consistency check, not an independent fuzzing repetition.

- [Run summary and provenance](summary.json), [comparison CSV](comparison.csv), and [AFL statistics](fuzzer_stats.txt).
- [Retained-input classifications](classification.jsonl), [fuzzer log](fuzzer.log), and [seed plus retained corpus](retained_inputs.zip).
- [Generated coverage](generated_coverage.jsonl), [augmented coverage](augmented_coverage.jsonl), and [augmented SBFL summary](augmented_sbfl_summary.json).
- [Augmented line spectrum](spectrum.csv), [Jaccard ranking](jaccard_ranking.csv), and [Ochiai ranking](ochiai_ranking.csv).
- [Per-input validation](validation.csv), [validation summary](validation_summary.json), and [artifact hashes](artifact_hashes.json).
- [Runner snapshot](runner_snapshot.py) and [fuzz driver snapshot](fuzz_driver_snapshot.cpp). These are provenance copies; use the repository paths for execution.

Raw run: `/home/user/ddmin-xml-sbfl/results/tinyxml2_character_ref/smoke_afl_300s_fail_only_20261029_160524_311622`. Saved summaries and records preserve their original paths as provenance.

Reproduce an independent run from the WSL repository root:

```bash
python3 scripts/smoke_tinyxml2_character_ref.py --duration 300 --seed-mode fail-only
```

This creates a fresh result directory and uses only the minimized FAIL seed. The Docker image, original DDMIN input directories, and baseline coverage build must be available. If needed, recreate the latter with `bash scripts/build_tinyxml2_character_ref_coverage.sh`.

The subject remains exploratory under the malformed-input assertion oracle. Changes in SBFL rank or EXAM do not by themselves establish eligibility for the formal valid-input experiment.
