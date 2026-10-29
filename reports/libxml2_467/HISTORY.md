# libxml2_467 experiment history

This history preserves the sequence of baselines, smoke checks, interrupted
attempts, completed campaigns, and model changes. Dates below are taken from
run identifiers and recorded Git commits; run identifiers are retained verbatim.
Only the three explicitly complete campaigns contribute to formal summaries.
The character-v2 and structural-v2 campaigns form the final shared-PIT comparison.

## 2026-09-26: character DDMIN baseline

Run `results/libxml2_467_ddmin/20260926_224640_738508` reduced the original
174-character failure to 133 characters. Of 1,468 unique candidates, 232 were
PASS, 25 FAIL, and 1,211 UNRESOLVED. The 257 usable spectra ranked the fault
at average rank 7.5 under both metrics.

## 2026-10-26: structural DDMIN and initial smoke checks

Run `results/libxml2_467_structural_ddmin/20261026_123127_300282` reduced the
failure to 129 characters and produced 15 PASS, 3 FAIL, and no UNRESOLVED
candidates. Its average fault rank was 14.5 under both metrics.

The first character and structure smoke commands did not pass `-w peach -g`.
They verified target/fuzzer execution and are recorded as AFL launch smokes.
The directory name `smoke_structure` alone does not establish structural mutation.

A later Peach mixed smoke used PIT v1 and generated a nonempty chunk file.
PIT v1 was validated against the three structural seeds.

## 2026-10-26: structural campaign with PIT v1

The initial `formal_structure_300s` attempt was manually interrupted and has
no completed run metadata. It is excluded.

The replacement batch `formal_structure_300s_20261026_203447` completed all
15 trials using experiment commit `08eff71641cf8779660ade1d4dc26dc6db975d1d`.
Its results are exported under `experiments/structural_v1/`.

The SBFL evaluator's libxml2 configuration was added in commit
`de6e914` (2026-10-26). It identifies the subject source and fault line 9596.

## 2026-10-26: character campaign rejected with PIT v1

Batch `formal_character_300s_20261026_221906` produced four completed run
metadata records, then stopped after the repetition-2 mixed trial generated
no Peach chunk files. Coverage collection for that rejected trial had already
completed; this does not make it a valid completed AFLSmart trial.

The runner's rejection guard was retained. No partial results from this batch
are used to fill missing repetitions in another campaign. See
[interrupted trial status](history/interrupted_character_v1.json).

## 2026-10-27: shared PIT v2 and launcher

PIT troubleshooting found that v1 exactly cracked only 1/25 character seeds.
Shared v2 models the reduced DOCTYPE forms and the ordinary `xm`/`m` CDATA
defaults as well as the namespace defaults in both corpora.

Validation passed all 25 character and all 3 structural seeds with exact
byte preservation and valid namespace chunk boundaries. Two 60-second
character smokes passed: mixed retained 4 smart mutations and nonstack 30.
The validation record distinguishes the tested PIT bytes from the installed
copy, whose only textual difference is its final newline.

Commit `1989bc50ba740b5c1b44d7afbfe1d55055e2631e` added the versioned PIT
and formal launcher. The launcher changes the subject PIT configuration only
in its Python process; `scripts/run_fuzz_experiment_expat.py` itself was not
changed for this model selection. It preserves the runner's clean-tree and
zero-chunk checks.

## 2026-10-27: completed character campaign with shared v2

Batch `formal_character_shared_v2_300s_20261027_141812` completed all 15 trials
at commit `1989bc50ba740b5c1b44d7afbfe1d55055e2631e`. Its SBFL results are
exported under `experiments/character_shared_v2/`.

AFL and mixed each have mean Jaccard/Ochiai rank 7.4 against the 7.5
character baseline. Nonstack has mean rank 7.9. The median is 7.5 for all modes.

## 2026-10-28: structural-v2 startup failure

Attempt `formal_structure_shared_v2_300s_20261028_155044` stopped before fuzzing.
The terminal transcript reported `/usr/bin/docker: Input/output error` and exit
126. The directory has zero completed trial metadata records and contributes
nothing to the formal aggregates. See the
[startup failure record](history/failed_structural_v2_startup.json).

## 2026-10-29: completed structural campaign with shared v2

Replacement batch `formal_structure_shared_v2_300s_20261029_105143` completed
all 15 trials at commit `a09ac21fdfc41841334fab344a5892d9dfd1cb66`.
All trials recorded completed coverage, a clean Git state and 100% AFL
stability. The ten AFLSmart trials all produced nonzero Peach chunk files and
used the same PIT SHA256 as the completed character-v2 campaign.

SBFL was computed for all 15 trials against the structural DDMIN baseline.
The mean Jaccard/Ochiai ranks are AFL 11.8/10.5, mixed 10.1/9.5, and nonstack
10.7/9.9, against baseline 14.5/14.5. No trial was discarded. The new analysis
and compact metadata are exported under `experiments/structural_shared_v2/`.

## Final comparison status: 2026-10-29

Both shared-v2 corpora have complete formal campaigns and SBFL analyses.
Relevant runner, evaluator, oracle, launcher, and PIT Git blobs are identical
between the two v2 experiment commits; the compiled AFL target hash also
matches. The comparison retains each corpus's own DDMIN baseline and notes
the differing baseline ranks, corpus sizes, and campaign dates.

The structural-v1 campaign remains valid for its recorded configuration and
is retained as history. It is not pooled with structural v2. The
[final summary](SUMMARY.md) and [comparison CSV](shared_v2_comparison.csv)
report the v2 results. All failed, interrupted, and diagnostic runs remain
excluded from formal aggregates.

## Local attempt inventory

| Run directory under `results/libxml2_467/` | Completed trial metadata | Status |
|---|---:|---|
| `formal_character_300s_20261026_221906` | 4 | Incomplete character v1 attempt; repetition 2 mixed rejected for zero Peach chunks |
| `formal_character_shared_v2_300s_20261027_141812` | 15 | Complete formal batch |
| `formal_structure_300s` | 0 | Interrupted structural v1 attempt; zero completed metadata records |
| `formal_structure_300s_20261026_203447` | 15 | Complete formal batch |
| `formal_structure_shared_v2_300s_20261028_155044` | 0 | Docker startup failure before fuzzing; exit 126; zero completed trial metadata |
| `formal_structure_shared_v2_300s_20261029_105143` | 15 | Complete formal batch; shared PIT v2 |
| `smoke_character_60s_20261026_172347` | 0 | AFL launch smoke; no PIT configured |
| `smoke_peach_mixed_60s_20261026_185502` | 0 | Peach structural smoke |
| `smoke_structure_60s_20261026_172751` | 0 | AFL launch smoke; no PIT configured |

The machine-readable [attempt inventory](history/attempts.json) retains available
fuzzer command lines and run timings. Diagnostic smoke runs are not formal
trials even when their queue contains useful generated inputs.
