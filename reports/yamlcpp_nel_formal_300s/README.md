# yaml-cpp NEL Encoding — Formal AFL/AFLsmart Experiment

## Subject

Historical yaml-cpp NEL (`\N`) UTF-8 decoding bug.

Known faulty source:

- `subjects/yamlcpp-nel-encoding/buggy/src/exp.cpp`
- Fault line: **118**

Historical failing input:

```yaml
value: "\N"
```

The buggy version decodes `\N` as the single byte `0x85`, while the fixed version produces the correct UTF-8 sequence `0xC2 0x85`.

## Character-level DDMIN baseline

The frozen DDMIN run is:

```text
results/yamlcpp_nel_ddmin/20260927_130800_792876
```

Baseline candidate classification:

- PASS: 6
- FAIL: 2
- UNRESOLVED: 40
- Total unique candidates: 48
- Usable candidates: 8
- Usable rate: **16.67%**

Baseline SBFL already localized the known faulty line very strongly:

- Jaccard fault rank: **1–2**, average **1.50**
- Ochiai fault rank: **1–2**, average **1.50**
- EXAM: **1.79%**

This creates a localization ceiling effect for subsequent fuzz-based augmentation.

## Formal fuzzing design

Each method was run for:

- Duration: **300 seconds**
- Repetitions: **5**
- Same seven initial seeds
- Randomized method execution order per repetition

Methods:

1. `afl`
2. `aflsmart-mixed`
3. `aflsmart-nonstack`

Formal results root:

```text
results/yamlcpp_nel/formal_300s
```

Formal augmented-SBFL analysis root:

```text
results/yamlcpp_nel/formal_300s_analysis
```

## Candidate usability

Across the five formal repetitions:

| Method | Mean added PASS | Mean added FAIL | Mean UNRESOLVED | Mean usable rate |
|---|---:|---:|---:|---:|
| AFL | 23.6 | 0 | 1482.0 | 1.57% |
| AFLsmart mixed | 24.8 | 0 | 1230.4 | 1.98% |
| AFLsmart nonstack | 29.4 | 0 | 1331.4 | 2.17% |

AFLsmart therefore produced a modestly higher proportion of usable retained candidates than plain AFL on this subject. The strongest result was from `aflsmart-nonstack`.

Relative to the mean AFL usable rate:

- AFLsmart mixed improved usable rate by approximately **26%**
- AFLsmart nonstack improved usable rate by approximately **38%**

These comparisons are between fuzzing modes with the same time budget. The DDMIN usable rate is not directly time-budget comparable and should be reported separately.

## Augmented SBFL

No formal fuzzing run produced a newly retained FAIL candidate after de-duplication against the baseline.

All 15 augmented spectra retained the same localization result as the DDMIN baseline:

- Jaccard fault average rank: **1.50**
- Ochiai fault average rank: **1.50**
- EXAM: **1.79%**

Therefore fuzz augmentation did not improve the already near-optimal rank, but it also did not degrade localization.

The added PASS tests did alter the suspiciousness values of some non-fault lines, so the augmented spectra were not identical to the baseline. However, source lines 117 and 118 remained inseparable because all baseline failing tests exercised both lines.

## Why were no new FAIL candidates retained?

A post-hoc trigger-retention analysis was performed on all retained generated AFL/AFLsmart queue entries.

The analysis searched generated queue files for the literal byte sequence corresponding to `\N` and reclassified trigger-containing candidates using `oracle_yamlcpp_nel`.

Results:

| Method | Retained generated queue entries | Entries containing literal `\N` | PASS | FAIL | UNRESOLVED |
|---|---:|---:|---:|---:|---:|
| AFL | 7,532 | 3 | 0 | 0 | 3 |
| AFLsmart mixed | 6,279 | 0 | 0 | 0 | 0 |
| AFLsmart nonstack | 6,804 | 3 | 0 | 0 | 3 |
| **Total** | **20,615** | **6** | **0** | **0** | **6** |

Only **6 of 20,615 retained generated queue entries** contained the literal `\N` sequence, approximately **0.03%** overall.

All six were classified as `UNRESOLVED`.

Examples showed that these candidates contained damaged YAML or unrelated binary material. For example, retained candidates included forms similar to:

```text
: "\N"
 "\N"
"\"\n"
```

and heavily corrupted byte sequences containing `\N`.

Thus none of the retained generated candidates simultaneously:

1. preserved the `\N` trigger,
2. remained acceptable to the YAML parser and experiment driver, and
3. reproduced the buggy/fixed behavioral difference.

## Interpretation

The yaml-cpp NEL bug has a narrow semantic trigger.

The AFLsmart PIT intentionally preserves only coarse YAML structure around the scalar:

```text
value: "mutable scalar content"
```

The historical `\N` sequence is deliberately part of mutable scalar content rather than a protected token.

This is important for experimental fairness. Protecting `\N` itself would effectively tell AFLsmart to preserve the known bug trigger and would bias the comparison.

Consequently, structure-aware mutation can preserve YAML-level structure while still replacing or removing the semantic trigger.

This explains the combination observed in the formal results:

- AFLsmart increased retained candidate usability relative to AFL.
- AFLsmart did not generate newly retained failure-inducing candidates.
- The trigger itself was almost universally absent from retained generated queues.
- The few retained candidates containing `\N` were unusable.

The result therefore demonstrates an important distinction:

> **Structure-aware preservation does not imply semantic bug-trigger preservation.**

For this historical bug, preserving the surrounding YAML mapping and quoted-scalar structure was insufficient to preserve the narrow `\N` fault condition.

## Important limitation of the trigger-retention analysis

The post-hoc analysis examines **retained AFL queue entries**, not every mutation executed transiently during fuzzing.

AFL retains inputs primarily when they are considered interesting according to its feedback and queue-selection mechanisms. It is therefore possible that a valid failure-inducing `\N` mutation was executed during fuzzing but was not retained in the queue.

Accordingly, the supported conclusion is:

> Across five 300-second repetitions, no **newly retained** failure-inducing candidate was produced after baseline de-duplication. Almost all retained generated candidates eliminated the literal `\N` trigger, and the few retained candidates containing it were classified as UNRESOLVED.

It would be incorrect to claim that the fuzzer never executed any failure-inducing mutation.

## Overall subject conclusion

For yaml-cpp NEL:

1. Character-level DDMIN had a high UNRESOLVED rate but already achieved near-perfect fault localization.
2. AFLsmart produced modestly more usable retained candidates than AFL under matched fuzzing budgets.
3. AFLsmart nonstack had the highest mean usable rate.
4. No formal method produced a newly retained FAIL candidate.
5. Trigger-retention analysis explains this result: the narrow `\N` trigger was almost universally lost.
6. Fuzz augmentation preserved the baseline fault rank rather than improving it because the baseline was already at the localization ceiling.
7. This subject provides evidence that structural preservation and semantic trigger preservation are distinct concerns.

## Structural DDMIN follow-up

The [structural DDMIN feasibility report](../yamlcpp_nel_structural_feasibility/README.md) documents two exploratory runs on the 12-character input and why no
structural fuzz comparison was performed.
