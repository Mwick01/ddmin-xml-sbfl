# yaml-cpp CR regression: character and structural DDMIN through AFLsmart and SBFL

This compares two complete pipelines for the historical yaml-cpp CR line-ending
regression. The character pipeline is the existing five-repeat experiment. The
structural pipeline was run from the same 104-byte failing input with literal
carriage returns, using the same semantic oracle, target binary, Peach PIT,
fault line, and 300-second fuzzing budget per run. The representative fault is
`subjects/yamlcpp-cr-line-ending/buggy/src/stream.cpp:265`.

The structural reducer now deletes block mapping entries and complete block
scalar lines. It edits the original text and preserves each CR byte. The
smallest structural failure was the 24-byte sequence
`blockText: |\rfollowup: 1`; the character minimum was `|\rp` (3 bytes).
All three structural FAIL seeds were independently cracked by Peach and
reconstructed byte for byte with the existing PIT.

## DDMIN and baseline SBFL

| Measure | Character | Structural |
| --- | ---: | ---: |
| Input bytes | 104 | 104 |
| Smallest FAIL, bytes | 3 | 24 |
| Reduction | 97.12% | 76.92% |
| Candidate evaluation requests | 42 | 11 |
| Distinct candidates | 24 | 6 |
| Oracle calls | 24 | 5 |
| PASS / FAIL / UNRESOLVED / validator-rejected | 16 / 7 / 1 / 0 | 2 / 3 / 0 / 1 |
| Baseline Jaccard average fault rank | 44.5 | 42.5 |
| Baseline Jaccard EXAM | 21.50% | 20.53% |

The structural validator rejected one empty YAML candidate before the oracle.
The two baseline spectra contain 23 and 5 usable tests, respectively. Both
use 207 executable `stream.cpp` lines. Smaller rank and EXAM are better.

## AFLsmart and augmented SBFL

Each corpus seeded AFLsmart mixed and nonstack for five independent 300-second
runs per mode. The character corpus had seven FAIL seeds; the structural corpus
had three. Each formal structural run recorded Peach chunk structures and
100% AFL stability. The table gives means over five repetitions, using Jaccard
average fault rank and average-rank EXAM.

| Seed corpus and mode | Primary rank | Primary EXAM | Runs better than own DDMIN baseline | Mean added FAIL | Mean new FAIL profiles |
| --- | ---: | ---: | ---: | ---: | ---: |
| Character, mixed | 37.1 | 17.92% | 3/5 | 69.2 | 5.4 |
| Structural, mixed | 28.6 | 13.82% | 5/5 | 102.8 | 6.8 |
| Character, nonstack | 37.6 | 18.16% | 3/5 | 65.0 | 4.0 |
| Structural, nonstack | 41.7 | 20.14% | 2/5 | 85.6 | 5.4 |

The primary mixed-mode ranking was better with structural seeds in this
experiment. The nonstack mean ranking was worse despite more added FAIL tests.
See `primary_per_run.csv` for every repetition and `fuzz_comparison.csv` for
the compact means.

## TREE=NULL sensitivity

The existing character report found that passing `TREE=NULL` executions could
improve SBFL without exercising the fault-relevant behavior. We reproduced
its ten non-null ranks exactly before applying the same filter to the
structural runs. The filter uses the fixed-reference semantic tree; for PASS
tests, the recorded buggy tree is identical to it.

| Seed corpus and mode | Non-null baseline rank | Mean non-null rank | Runs better than baseline | NULL PASS avoiding fault | Non-null PASS avoiding fault |
| --- | ---: | ---: | ---: | ---: | ---: |
| Character, mixed | 44.5 | 51.9 | 0/5 | 7 | 0 |
| Structural, mixed | 42.5 | 51.5 | 0/5 | 10 | 0 |
| Character, nonstack | 44.5 | 51.7 | 0/5 | 5 | 0 |
| Structural, nonstack | 42.5 | 51.1 | 0/5 | 3 | 0 |

The unrestricted gains therefore did not survive this semantic filter. Across
all 20 AFLsmart runs, no generated non-null PASS test avoided fault line 265.
Generated test volume and new FAIL profiles alone did not supply the PASS
spectrum needed to distinguish this line. See `nonnull_per_run.csv` for the
per-run counts and both Jaccard and Ochiai ranks.

## Comparability and limits

The metadata checks confirm the same target SHA-256
`76fb380b64c81dbbd61ef296be1c29e2091d0a3d52aff17d87a878981ce9376a`
and PIT SHA-256
`a02edd616d5ff6a2fec562cb6e523c470053cf02ffcf4c8840fe91cf35a9d95f`.
The same oracle, coverage source, fault line, and order seed were recorded.
The structural fuzz run used commit `f01eb368a24eb643e60ab27cbf0ea0d7eea93668`;
the character run used `55eb49944c4abd5dfe03f7e01230869a6581af84`.
The Docker image name is the same, but the old metadata did not record an
immutable image digest.

This is an end-to-end reducer-corpus comparison. The candidate suites and
seed counts differ, so the result does not isolate structural editing from
seed count or content. It covers one historical bug with five repetitions per
mode; the reported differences are descriptive.

## Reproduce from the WSL checkout

The following commands use the saved structural run. Build the subject binaries
and the `ddmin-aflsmart` image first if they are absent.

```bash
cd ~/ddmin-xml-sbfl
STRUCT=results/yamlcpp_cr_structural_ddmin/20261027_154317_425518

python3 scripts/yaml_structural_ddmin.py \
  subjects/yamlcpp-cr-line-ending/input.yaml \
  --oracle-module oracle_yamlcpp_cr \
  --results-root results/yamlcpp_cr_structural_ddmin \
  --temporary-file temporary/yamlcpp_cr_structural_candidate.yaml

python3 scripts/collect_coverage.py "$STRUCT" \
  --oracle-module oracle_yamlcpp_cr \
  --source subjects/yamlcpp-cr-line-ending/buggy/src/stream.cpp \
  --binary subjects/yamlcpp-cr-line-ending/coverage_buggy/semantic_buggy_cov \
  --object subjects/yamlcpp-cr-line-ending/coverage_buggy/CMakeFiles/yaml-cpp.dir/src/stream.cpp.o

python3 scripts/run_fuzz_experiment_expat.py \
  --subject yamlcpp_cr --baseline-run "$STRUCT" \
  --seed-directory aflsmart/yamlcpp_cr_structure_seeds \
  --duration 300 --repetitions 5 \
  --modes aflsmart-mixed aflsmart-nonstack \
  --results-root results/yamlcpp_cr/formal_structure_aflsmart_300s

python3 scripts/evaluate_augmented_sbfl_expat.py \
  --subject yamlcpp_cr --baseline-run "$STRUCT" \
  --fuzz-root results/yamlcpp_cr/formal_structure_aflsmart_300s \
  --output-root results/yamlcpp_cr/formal_structure_aflsmart_300s_evaluation \
  --duration 300

python3 scripts/evaluate_yamlcpp_nonnull.py \
  --baseline-run "$STRUCT" \
  --fuzz-root results/yamlcpp_cr/formal_structure_aflsmart_300s \
  --output-root results/yamlcpp_cr/formal_structure_aflsmart_300s_nonnull_sensitivity \
  --duration 300
```

The fuzz runner refuses to overwrite existing runs. Choose a new results root
for a fresh repetition set. The three frozen seed files in
`aflsmart/yamlcpp_cr_structure_seeds` are exactly the structural FAIL
candidates from the saved run. `provenance.json` contains the checked hashes
and experiment commits; the structural summary JSON files and comparison CSVs
are included here so the primary findings remain available without raw queues.
