# LibYAML flow-sequence: character versus structure-aware DDMIN

This report compares the existing character-level DDMIN pipeline with the
structure-aware YAML DDMIN pipeline for one historical LibYAML flow-sequence
regression. It follows the original [character DDMIN baseline](../libyaml_flow_baseline/README.md)
and [16-seed formal fuzzing report](../libyaml_flow_formal_300s/README.md).
The comparison is descriptive for this subject; no reducer or fuzzer was rerun
to prepare this report.

## Subject and design

- Historical buggy revision: `588eabff23ba2292f537872bbea5b64bce1e1a21`.
- Fixed revision: `840b65c40675e2d06bf40405ad3f12dec7f35923`.
- Original failing input: `subjects/libyaml_flow/inputs/failing_rich.yaml`
  (57 characters). Both reducers used `oracle_libyaml_flow`.
- Representative fault: `third_party/libyaml-588eabf/src/parser.c:1062`.
- Character DDMIN run: `results/libyaml_flow/ddmin_rich_runs/20260921_232140_207481`.
- Structural DDMIN run: `results/yaml_structural_ddmin_runs/20261023_110311_117063`.
- Character formal fuzzing: `results/libyaml_flow/formal_300s`, analyzed in
  `results/libyaml_flow/formal_300s_analysis`.
- Structural formal fuzzing: `results/libyaml_flow/formal_structure_300s`,
  analyzed in `results/libyaml_flow/formal_structure_300s_analysis`.

Each formal arm ran AFL, AFLSmart mixed, and AFLSmart nonstack for 300 seconds
in five repetitions, with order seed `20260920`. The 16 character FAIL
candidates were the exact character fuzz seed set; the four structural FAIL
candidates were the exact structural fuzz seed set. The eight structural PASS
candidates contributed to baseline SBFL, not to the fuzz seed corpus. The
per-run metadata agreed on the target SHA-256
`7cb4d141cf064012631fa05bf26673f0493095173ee73051bad85117706666da`,
the AFLSmart PIT SHA-256
`acfd73903536e43e026912c5b9a9aad89e72cf84891f816eeceab8e176596a96`,
the Docker image name, oracle, fault line, budget, and execution order. All
30 fuzz runs recorded a clean worktree and 100% AFL stability. The character
and structural formal runs recorded Git commits `3936eca817be6e75fbe2f5e2755c754fa3fe1fdf`
and `8f8529c26df1e7bbe1c294fbcee69e09748eddf2`, respectively.

## DDMIN-stage results

| Measure | Character DDMIN | Structural DDMIN |
|---|---:|---:|
| Smallest failing input, characters | 12 | 19 |
| Reduction from 57 characters | 78.95% | 66.67% |
| Candidate evaluation attempts | 321 | 23 |
| Cache hits | 159 | 11 |
| Classifier calls on unique candidates | 162 | 12 |
| Unique candidates | 162 | 12 |
| PASS / FAIL / UNRESOLVED | 25 / 16 / 121 | 8 / 4 / 0 |
| Candidates accepted by fixed target | 41 / 162 | 12 / 12 |
| Candidates admitted by structural validator | 43 / 162 | 12 / 12 |
| Executable `parser.c` lines covered by usable baseline tests | 312 / 603 | 232 / 603 |
| Fault tie, best-average-worst rank | 1-9-17 | 1-9-17 |
| Baseline EXAM (average-rank treatment) | 1.49% | 1.49% |

The character reducer's `summary.json` calls its 321 candidate evaluation
requests `oracle_attempts`, including 159 cache hits. The structural reducer
uses `oracle_attempts` for actual classifier calls after cache and validity
checks. The comparable classifier-call counts above come from the
`attempts.jsonl` cache flags: 162 and 12. They do not measure wall-clock time
or total target-process executions.

The validity audit reran the fixed LibYAML target on every saved candidate.
Every target-accepted candidate was labelled PASS or FAIL by the oracle; all
121 character UNRESOLVED candidates were rejected by the fixed target, and
none timed out there. The structural reducer's `valid_yaml` filter is a
different operational measure: it rejects two whitespace-only streams that
the fixed target accepts as PASS, while admitting four inputs the fixed target
rejects. Consequently, `valid_yaml=False` should not be reported as a
definitive grammar error. See [validity_audit.csv](validity_audit.csv) for the
cross-tabulation and [ddmin_comparison.csv](ddmin_comparison.csv) for the
machine-readable stage comparison.

Structural DDMIN eliminated target-rejected candidates in this run and used
far fewer classifier calls. Character DDMIN produced the smaller failing
input and a baseline suite with broader line coverage. Both suites left the
fault in the same 17-line tie.

## Fuzzing and augmented SBFL

The following are means over five repetitions. Lower average rank and EXAM
are better. Jaccard and Ochiai produced the same fault ranks for this subject.

| Fuzzer | Seeds | Mean average rank | Mean EXAM | Runs better than baseline | Mean added FAIL | Mean new FAIL profiles | Mean AFL executions |
|---|---:|---:|---:|---:|---:|---:|---:|
| AFL | 16 character | 4.5 | 0.746% | 4/5 | 16.0 | 7.0 | 868,395 |
| AFL | 4 structural | 5.7 | 0.945% | 3/5 | 10.0 | 4.0 | 806,805 |
| AFLSmart mixed | 16 character | 5.5 | 0.912% | 3/5 | 15.4 | 7.0 | 826,348 |
| AFLSmart mixed | 4 structural | 5.7 | 0.945% | 3/5 | 10.8 | 4.8 | 800,161 |
| AFLSmart nonstack | 16 character | 5.6 | 0.929% | 3/5 | 10.6 | 6.4 | 852,315 |
| AFLSmart nonstack | 4 structural | 9.0 | 1.493% | 0/5 | 8.4 | 6.4 | 767,279 |

The structural AFL and mixed arms each narrowed the fault's tie from 17 to
six lines in three of five runs. Structural nonstack retained the original
17-line tie in all five runs, despite generating new failing coverage
profiles. No run in either cohort moved a baseline-tied statement above the
fault. The complete structural [aggregate.csv](aggregate.csv),
[per_run.csv](per_run.csv), and [summary.json](summary.json) are included here;
the original character exports remain in the linked formal report.
The compact [fuzz_comparison.csv](fuzz_comparison.csv) combines the two arms.

## Why some runs improved

In the inspected spectra, the representative competing line 298 was covered
by at least one PASS test exactly in the runs whose fault rank improved; line
1062 had zero PASS coverage in every run. This occurred in 10/15 character
runs and 6/15 structural runs. It did not occur in any structural nonstack
run. Passing tests that execute a competitor without executing the fault
lower that competitor's Jaccard and Ochiai score, breaking part of the tie.
The [mechanism.csv](mechanism.csv) file records the per-run evidence. This is
an explanatory observation made after the formal experiment, not a
preregistered outcome.

## Interpretation and limits

For this LibYAML case, structural reduction improved candidate acceptance
and reduced classifier calls while preserving the baseline fault rank. The
original character corpus generally produced better post-fuzz localization,
especially under AFLSmart nonstack. This is an end-to-end comparison: the
different seed counts (16 versus four) are part of the reducer outputs.
The data do not isolate seed content from seed count. A separately specified,
count-matched character corpus would be needed for that question.

The result concerns one bug and five randomized repetitions per fuzzer mode.
Mean differences are descriptive, not evidence of general superiority.
Wall-clock reduction time was not recorded for these DDMIN runs. The formal
metadata records the Docker image name but not its immutable digest, so the
image identity across the two run dates cannot be checked from this metadata
alone. Full raw queues and coverage records remain under the local `results/`
tree; this Git report contains lightweight summaries and links to the
existing character report.

## Files in this report

- `structural_ddmin_summary.json` and `structural_coverage_summary.json`:
  unmodified structural baseline summaries.
- `aggregate.csv`, `per_run.csv`, and `summary.json`: structural
  augmented SBFL exports; CSV line endings were normalized to LF.
- `ddmin_comparison.csv`, `validity_audit.csv`, `fuzz_comparison.csv`, and
  `mechanism.csv`: derived comparison tables documented above.
