# XML DDMIN-SBFL

An experimental implementation of failure-inducing input minimization and
spectrum-based fault localization for XML-processing programs.

## Current pipeline

```text
XML input
    -> PASS / FAIL / UNRESOLVED oracle
    -> DDMIN test generation
    -> statement coverage
    -> SBFL suspiciousness ranking