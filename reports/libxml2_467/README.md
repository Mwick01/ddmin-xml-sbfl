# libxml2 #467: DDMIN, fuzzing, and SBFL

Report completed: **2026-10-29** (Asia/Colombo).

This folder records the character and structural DDMIN baselines, three completed
300-second fuzzing campaigns, and the PIT changes made during the experiment.
The known fault is **`parser.c:9596`**.

**Both character and structural campaigns using shared PIT v2 are complete,
including SBFL analysis.** The earlier structural-v1 campaign is retained as
historical evidence. Read the [final summary](SUMMARY.md) for the comparison
using the same PIT, target, and experiment code. Each corpus uses its own
DDMIN baseline; the seed counts and starting fault ranks differ.

## Subject and oracle

- Buggy revision: `78c4430f4ee75aee67456b0c29074add9d280b5d`.
- Fixed revision: `0bd4e4e032d57ecf982b57312eb6136efdd35d56`.
- Faulty comparison: `nsname != defaults->values[2]`.
- Fixed comparison: `nsname != defaults->values[5 * i + 2]`.
- Both revisions are run with `xmllint --nonet --dtdattr --format INPUT`.
- PASS: both revisions exit successfully and their normalized stdout is equal.
- FAIL: both exit successfully and their normalized stdout differs.
- UNRESOLVED: either revision times out or exits unsuccessfully.

The oracle compares serialized namespace/default-attribute behavior. It does
not require a crash. Its fixed-program acceptance domain can include inputs
that a stricter XML grammar would reject. Output normalization removes outer
whitespace and trailing whitespace on each line.

Sources: [oracle](../../scripts/oracle_libxml2_467.py),
[historical fix](../../subjects/libxml2-467/fix.patch),
[revision record](../../subjects/libxml2-467/revisions.txt).

## DDMIN baselines

Both reductions start from the same 174-character failing input. Counts below
refer to unique candidates. Coverage uses the buggy program and **7,036
executable lines** in `parser.c`; gcov counters are reset for each candidate.
Usable PASS/FAIL coverage is supplied to Jaccard and Ochiai SBFL.

| Baseline | Unique candidates | PASS | FAIL | UNRESOLVED | Minimal characters | Jaccard average rank | Ochiai average rank |
|---|---:|---:|---:|---:|---:|---:|---:|
| character | 1468 | 232 | 25 | 1211 | 133 | 7.5 | 7.5 |
| structural | 18 | 15 | 3 | 0 | 129 | 14.5 | 14.5 |

Structural reduction produced a more usable candidate set, while the character
baseline placed the fault higher in the suspiciousness ranking. Candidate
validity and localization quality therefore differ in this subject.

See [baseline summary CSV](baseline_summary.csv),
[character baseline files](baselines/character/ddmin_summary.json), and
[structural baseline files](baselines/structural/ddmin_summary.json).

## Completed formal campaigns

Each campaign has **15 trials**: three modes, five repetitions per mode, and
300 configured fuzzing seconds per trial, followed by classification and
coverage collection. All 45 completed trials recorded a clean Git state and
100.00% AFL stability. Every completed AFLSmart trial recorded nonzero Peach
chunk files. Only generated queue entries are evaluated; input seeds and
duplicates of baseline candidates are excluded. Generated usable tests are
combined with that campaign's own DDMIN baseline for SBFL.

The same compiled AFL target was used in all three campaigns. The structural corpus
contains 3 FAIL seeds; the character corpus contains 25 FAIL seeds. Execution
order is shuffled within each repetition with `order_seed + repetition` and
`order_seed = 20260920`. This seed controls order, not AFL's random mutations.

The v1/v2 campaign labels identify the AFLSmart model; plain AFL uses no PIT.

| Campaign / PIT | Mode | Baseline average rank | Mean Jaccard rank | Mean Ochiai rank | Jaccard improved repetitions | Ochiai improved repetitions |
|---|---|---:|---:|---:|---:|---:|
| structural_v1 | afl | 14.5 | 10.3 | 10.3 | 5/5 | 5/5 |
| structural_v1 | aflsmart-mixed | 14.5 | 9.9 | 9.7 | 5/5 | 5/5 |
| structural_v1 | aflsmart-nonstack | 14.5 | 21.9 | 15.7 | 4/5 | 4/5 |
| structural_shared_v2 | afl | 14.5 | 11.8 | 10.5 | 4/5 | 5/5 |
| structural_shared_v2 | aflsmart-mixed | 14.5 | 10.1 | 9.5 | 5/5 | 5/5 |
| structural_shared_v2 | aflsmart-nonstack | 14.5 | 10.7 | 9.9 | 5/5 | 5/5 |
| character_shared_v2 | afl | 7.5 | 7.4 | 7.4 | 1/5 | 1/5 |
| character_shared_v2 | aflsmart-mixed | 7.5 | 7.4 | 7.4 | 1/5 | 1/5 |
| character_shared_v2 | aflsmart-nonstack | 7.5 | 7.9 | 7.9 | 0/5 | 0/5 |

Lower ranks are better. A per-trial average rank is the midpoint of the fault's
tied rank interval; a campaign mean averages those values over five trials.
EXAM is the average fault rank divided by 7,036 executable lines, expressed as
a percentage. Medians, ranges, standard deviations, profile counts, and usable
rates are retained in the CSV/JSON exports.

### Structural seeds with shared PIT v2

The final structural-v2 batch completed all 15 trials on 2026-10-29. Mixed has
the best means in this campaign, at Jaccard 10.1 and Ochiai 9.5, compared with
AFL 11.8/10.5 and nonstack 10.7/9.9. Mixed and nonstack improve on baseline
14.5 in every trial under both metrics. AFL improves in four Jaccard trials and
all five Ochiai trials; repetition 3 has Jaccard rank 17.5 and is retained.

Files: [per-run results](experiments/structural_shared_v2/per_run.csv),
[aggregate results](experiments/structural_shared_v2/aggregate.csv),
[full summary](experiments/structural_shared_v2/summary.json),
[run metadata](experiments/structural_shared_v2/run_metadata.jsonl).

The two v2 campaigns hold the PIT, target, and experiment code constant.
Character v2 has lower absolute mean ranks across the three modes, while
structural v2 gains more from its own baseline. Corpus sizes (25 versus 3),
DDMIN spectra, baseline ranks, and campaign dates differ, so this comparison
does not isolate a causal effect of reduction style. See the
[comparison CSV](shared_v2_comparison.csv) and [final summary](SUMMARY.md).

### Structural seeds with PIT v1

AFL and AFLSmart mixed improve the structural baseline in all five repetitions.
Mixed has a small mean advantage over AFL. Nonstack is less consistent: its
second repetition ranks the fault at 67.5 by Jaccard and 37.5 by Ochiai, worsening
its means. That repetition is retained in the report.

Files: [per-run results](experiments/structural_v1/per_run.csv),
[aggregate results](experiments/structural_v1/aggregate.csv),
[full summary](experiments/structural_v1/summary.json),
[run metadata](experiments/structural_v1/run_metadata.jsonl).

### Character seeds with shared PIT v2

The character baseline is already ranked at 7.5. AFL and mixed each improve
one repetition to 7.0 and leave four at 7.5, producing means of 7.4. Nonstack
leaves four at 7.5 and worsens one to 9.5, producing a mean of 7.9. This is little
localization improvement despite the addition of usable tests and new profiles.

Files: [per-run results](experiments/character_shared_v2/per_run.csv),
[aggregate results](experiments/character_shared_v2/aggregate.csv),
[full summary](experiments/character_shared_v2/summary.json),
[run metadata](experiments/character_shared_v2/run_metadata.jsonl).

These observations describe one historical fault and five trials per method.
They do not establish a general AFLSmart advantage or statistical significance.
The shared-v2 comparison uses the same model for both corpora, with the
baseline and corpus-size limitations described above. Structural v1 remains
a separate historical configuration and is not pooled into the v2 results.

## PIT versions and experiment history

PIT v1 exactly cracked the three structural seeds but only 1 of the 25 character
seeds. The first character campaign stopped in repetition 2 when the runner
rejected an AFLSmart mixed trial with zero Peach chunk files. That entire partial
campaign is excluded from the formal aggregates above.

Shared v2 adds the reduced DOCTYPE names/spacing and ordinary CDATA defaults
present in the character corpus. It passed exact round trips, namespace chunk
checks, and valid byte ranges for all 25 character and all 3 structural seeds.
Both 60-second AFLSmart smoke modes also produced chunks and retained smart
mutations. The zero-chunk rejection remains in the runner.

The new launcher selects v2 in memory and calls the existing runner; it does
not edit the runner's default v1 configuration. Versioned model snapshots are
stored in [models/](models/libxml2_467_shared_v2.xml). Read the
[history](HISTORY.md), [attempt inventory](history/attempts.json),
[validation evidence](validation/shared_v2.json), and
[manifest](manifest.json) for run identifiers, hashes, commits, and exclusions.

## Reproduction

The repository's built buggy/fixed xmllint programs, gcov build and wrapper,
AFL target, and `ddmin-aflsmart` Docker image are prerequisites. Paths are
recorded in the run metadata. The coverage wrapper applies the same xmllint
options as the oracle.

Run a new shared-v2 character campaign from the repository root:

```bash
bash scripts/run_libxml2_467_shared_v2_formal.sh character
```

For a new structural campaign with the same PIT:

```bash
bash scripts/run_libxml2_467_shared_v2_formal.sh structure
```

Each launcher creates and prints a fresh timestamped results directory. Run
campaigns sequentially to avoid contention and concurrent gcov collection.

Recompute the completed character campaign's SBFL analysis when its local
coverage files are available:

```bash
BASE=results/libxml2_467_ddmin/20260926_224640_738508
FUZZ=results/libxml2_467/formal_character_shared_v2_300s_20261027_141812
python3 scripts/evaluate_augmented_sbfl_expat.py --subject libxml2_467 --baseline-run "$BASE" --fuzz-root "$FUZZ" --output-root "${FUZZ}_analysis" --duration 300
```

Recompute the completed structural-v2 analysis with its own baseline and a
fresh output directory:

```bash
BASE=results/libxml2_467_structural_ddmin/20261026_123127_300282
FUZZ=results/libxml2_467/formal_structure_shared_v2_300s_20261029_105143
python3 scripts/evaluate_augmented_sbfl_expat.py --subject libxml2_467 --baseline-run "$BASE" --fuzz-root "$FUZZ" --output-root "${FUZZ}_analysis_recomputed" --duration 300
```

For the completed structural-v1 analysis, use baseline
`results/libxml2_467_structural_ddmin/20261026_123127_300282` and fuzz root
`results/libxml2_467/formal_structure_300s_20261026_203447` with the same evaluator.
Re-running the evaluator recreates its generated analysis subdirectories.

## Export contents and provenance

This folder is the compact GitHub report. Raw fuzz queues, per-test coverage
spectra, binaries, and gcov artifacts remain in ignored local directories.
Recomputing the rankings requires those spectra; the exported summaries do
not reconstruct the complete raw experiment by themselves.

- [Final conclusions](SUMMARY.md).
- [Shared-v2 comparison](shared_v2_comparison.csv).
- [Baseline comparison](baseline_summary.csv).
- [Formal campaign summary](formal_summary.csv).
- [Experiment history](HISTORY.md).
- [Source hashes and campaign identities](manifest.json).
- [Export checksums](SHA256SUMS.txt).

CSV result files and model snapshots are copied exactly. JSON exports convert
repository-absolute paths to repository-relative paths. Compact run metadata
omits the collector's large per-line arrays; raw source hashes and the export
policy are recorded in the manifest. No interrupted run is included in a
five-repetition aggregate, and no raw queues or per-test spectra are bundled.
