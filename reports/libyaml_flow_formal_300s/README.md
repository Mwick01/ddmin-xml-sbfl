# libyaml formal fuzzing experiment

Configuration:

- duration: 300 seconds
- repetitions: 5
- common seed corpus: 16 DDMIN FAIL candidates
- methods:
  - AFL
  - AFLSmart mixed
  - AFLSmart nonstack
- baseline representative fault: parser.c:1062
- baseline average rank: 9.0
- baseline tie size: 17

All 15 runs had 100% AFL stability.

## Aggregate localization

### AFL

- Jaccard mean average rank: 4.5
- Ochiai mean average rank: 4.5
- mean EXAM: 0.746%
- mean tie size: 8.0
- mean baseline-tied statements below fault: 9.0
- improved over baseline in 4/5 repetitions

### AFLSmart mixed

- Jaccard mean average rank: 5.5
- Ochiai mean average rank: 5.5
- mean EXAM: 0.912%
- mean tie size: 10.0
- mean baseline-tied statements below fault: 7.0
- improved over baseline in 3/5 repetitions

### AFLSmart nonstack

- Jaccard mean average rank: 5.6
- Ochiai mean average rank: 5.6
- mean EXAM: 0.929%
- mean tie size: 10.2
- mean baseline-tied statements below fault: 6.8
- improved over baseline in 3/5 repetitions

No method moved any baseline-tied statement above the fault in any run.

## Generated-test diversity

Mean new PASS profiles:

- AFL: 44.4
- AFLSmart mixed: 41.0
- AFLSmart nonstack: 39.2

Mean new FAIL profiles:

- AFL: 7.0
- AFLSmart mixed: 7.0
- AFLSmart nonstack: 6.4

Mean usable rate:

- AFL: 22.50%
- AFLSmart mixed: 22.90%
- AFLSmart nonstack: 21.94%

## Interpretation

All three fuzzing configurations improved mean localization relative to
the DDMIN-only baseline.

Ordinary AFL achieved the lowest mean fault rank on this subject.
AFLSmart therefore did not provide a consistent localization advantage
for libyaml.

The result also shows that raw profile quantity alone does not determine
SBFL improvement. Localization gains depended on whether generated test
spectra separated the fault from statements tied with it in the baseline
ranking.

These results are subject-specific and should not be generalized beyond
the evaluated subjects without further replication.
