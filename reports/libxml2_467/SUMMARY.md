# libxml2 #467: final results

Completed on **2026-10-29** (Asia/Colombo). Both seed corpora have finished
their shared-PIT-v2 formal campaigns and SBFL analysis: **300 seconds × five
repetitions × three modes per corpus**, or 30 shared-v2 trials. The 15 earlier
structural-v1 trials remain a separate historical campaign. No failed or partial
attempt is included in a completed campaign's aggregate.

## Shared PIT v2 comparison

The known fault is `parser.c:9596`. Each campaign combines its generated usable
tests with its own DDMIN baseline. Lower fault ranks are better; the reported
mean averages the midpoint of each trial's tied rank interval.

| Corpus | Mode | Baseline rank | Mean Jaccard rank | Mean Ochiai rank | Jaccard improved trials | Ochiai improved trials |
|---|---|---:|---:|---:|---:|---:|
| character | afl | 7.5 | 7.4 | 7.4 | 1/5 | 1/5 |
| character | aflsmart-mixed | 7.5 | 7.4 | 7.4 | 1/5 | 1/5 |
| character | aflsmart-nonstack | 7.5 | 7.9 | 7.9 | 0/5 | 0/5 |
| structural | afl | 14.5 | 11.8 | 10.5 | 4/5 | 5/5 |
| structural | aflsmart-mixed | 14.5 | 10.1 | 9.5 | 5/5 | 5/5 |
| structural | aflsmart-nonstack | 14.5 | 10.7 | 9.9 | 5/5 | 5/5 |

Structural v2 improves on baseline rank 14.5 in every mixed and nonstack trial
under both metrics. AFL improves in four Jaccard trials and all five Ochiai
trials; its third trial worsens Jaccard rank to 17.5 and is retained. Mixed has
the best mean ranks within structural v2: **10.1 Jaccard and 9.5 Ochiai**.

The character baseline starts at 7.5. AFL and mixed finish at mean rank 7.4,
with one improved trial each. Nonstack finishes at 7.9, with four unchanged
trials and one worse trial. Character v2 has lower absolute mean ranks across
all three modes, while structural v2 shows larger gains from its own baseline.

## Generated usable tests and profiles

Counts and percentages below are means over five trials. Seed entries and
duplicates of baseline candidates are excluded. A new FAIL profile is a failing
coverage profile absent from that campaign's baseline.

| Corpus | Mode | Added PASS | Added FAIL | New FAIL profiles | Usable generated inputs |
|---|---|---:|---:|---:|---:|
| character | afl | 37.8 | 4.6 | 3.2 | 2.79% |
| character | aflsmart-mixed | 45.0 | 5.2 | 4.0 | 3.85% |
| character | aflsmart-nonstack | 36.4 | 5.4 | 4.0 | 2.96% |
| structural | afl | 49.2 | 5.0 | 3.8 | 3.64% |
| structural | aflsmart-mixed | 54.4 | 8.2 | 7.0 | 4.67% |
| structural | aflsmart-nonstack | 45.4 | 6.4 | 4.6 | 3.45% |

Both v2 campaigns used the same PIT bytes, compiled AFL target, runner,
evaluator, oracle, and launcher code. All 30 v2 trials recorded a clean Git
state, completed coverage, and 100% AFL stability. Every AFLSmart trial produced
nonzero Peach chunks. Plain AFL does not use a PIT.

The corpora have different sizes (25 character seeds versus 3 structural seeds)
and different DDMIN spectra and starting ranks. The campaigns also ran on
different dates. These results describe one fault and five trials per mode;
they support descriptive comparisons and do not isolate a seed-corpus causal
effect or establish a general advantage for a fuzzer. No significance claim is
made. The structural-v1 results are not pooled into the shared-v2 comparison.

## Evidence and reproducibility

- [Full report and reproduction commands](README.md).
- [Shared-v2 comparison CSV](shared_v2_comparison.csv).
- [All three campaigns: summary CSV](formal_summary.csv).
- [Structural-v2 per-trial results](experiments/structural_shared_v2/per_run.csv).
- [Structural-v2 aggregate statistics](experiments/structural_shared_v2/aggregate.csv).
- [History, including the failed Docker startup](HISTORY.md).
- [Final campaign checks](validation/final_campaigns.json).
- [Run identities, source hashes, and provenance](manifest.json).

Raw queues and per-test coverage remain in ignored local results directories.
The report contains compact summaries and metadata suitable for GitHub; those
summaries alone cannot reconstruct the full raw experiment.
