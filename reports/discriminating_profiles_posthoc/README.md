# Discriminating-profile post-hoc analysis

This analysis was performed after the formal fuzzing experiments.
It does not modify or rerun any frozen fuzzing configuration.

For every source line tied with the representative fault in the
DDMIN-only baseline, generated coverage is classified directionally.

Helpful discrimination:

- PASS covers the competitor but not the fault.
- FAIL covers the fault but not the competitor.

Harmful discrimination:

- PASS covers the fault but not the competitor.
- FAIL covers the competitor but not the fault.

The analysis reports two views.

1. `new_profile_*` counts each distinct generated coverage profile
   once, and excludes profiles already present in the DDMIN baseline.
   This measures the quality of newly introduced spectrum diversity.

2. `test_*` counts every generated usable test in the augmented suite.
   This preserves multiplicity and therefore more closely represents
   the spectra that actually affected SBFL.

`net_density` is:

    (helpful pairs - harmful pairs)
    / possible fault-competitor pairs

Positive values favor separation of the fault from its baseline-tied
competitors. Negative values favor the reverse direction.

The analysis is descriptive/post-hoc and should not be presented as
a preregistered confirmatory metric.
