# libyaml 30-second fuzzing smoke experiment

This experiment is exploratory and precedes the formal repeated runs.

Baseline DDMIN SBFL:

- PASS: 25
- FAIL: 16
- distinct PASS profiles: 9
- distinct FAIL profiles: 6
- representative fault: parser.c:1062
- Jaccard average rank: 9.0
- Ochiai average rank: 9.0
- fault tie: ranks 1-17

## AFL

Generated:

- PASS: 82
- FAIL: 7
- UNRESOLVED: 381
- usable rate: 18.94%
- distinct generated PASS profiles: 25
- distinct generated FAIL profiles: 5
- new PASS profiles: 20
- new FAIL profiles: 4

Augmented localization:

- Jaccard average rank: 3.5
- Ochiai average rank: 3.5
- tie size: 6
- baseline-tied lines above fault: 0
- baseline-tied lines below fault: 11

## AFLSmart mixed

Generated:

- PASS: 85
- FAIL: 15
- UNRESOLVED: 454
- usable rate: 18.05%
- new PASS profiles: 17
- new FAIL profiles: 4
- retained havoc-smart inputs: 9

Augmented localization:

- Jaccard average rank: 9.0
- Ochiai average rank: 9.0
- tie size: 17
- baseline-tied lines moved below fault: 0

## AFLSmart nonstack

Generated:

- PASS: 114
- FAIL: 5
- UNRESOLVED: 363
- usable rate: 24.69%
- new PASS profiles: 24
- new FAIL profiles: 4
- retained havoc-smart inputs: 37

Augmented localization:

- Jaccard average rank: 9.0
- Ochiai average rank: 9.0
- tie size: 17
- baseline-tied lines moved below fault: 0

## Exploratory observation

In this single 30-second repetition, AFL broke the baseline fault tie
favorably while both AFLSmart configurations left the tie unchanged.

All three methods generated four new failing coverage profiles, and
AFLSmart nonstack generated more new passing profiles than AFL.
Therefore raw profile count alone does not explain the localization
difference.

Inspection of the spectra shows that AFL generated passing tests that
executed formerly tied upstream statements without executing the fault
region. These passing spectra reduced the suspiciousness of those
competitors while the fault retained score 1.0.

This is an exploratory observation only. No method comparison is
treated as established until the frozen 300-second repeated experiment
is completed.
