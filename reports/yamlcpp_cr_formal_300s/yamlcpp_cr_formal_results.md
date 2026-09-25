# yaml-cpp CR Line-Ending Regression — Formal Results

## Historical subject

- Project: yaml-cpp
- Fault: CR line-ending regression
- Buggy revision: b38ac5b55f5b64cffce71eac9433e553b3898bd1
- Fixed revision: ee9c4d19bedd660734125afed7ef6cf1822ea196
- Faulty source: src/stream.cpp
- Fault line: 265
- Oracle: fixed-reference semantic tree comparison

## DDMIN baseline

Character-level DDMIN produced:

- PASS: 16
- FAIL: 7
- UNRESOLVED: 1
- Minimal input: 3 bytes
- Reduction: 97.12%

Fault localization:

- Jaccard average rank: 44.5
- Ochiai average rank: 44.5
- EXAM: 21.50%
- Rank interval: 5-84

The faulty statement was executed by every baseline PASS and FAIL test.

## Plain AFL formal experiment

Configuration:

- 5 independent repetitions
- 300 seconds per repetition
- same frozen DDMIN FAIL seed corpus
- all repetitions retained

Primary unrestricted-oracle result:

- median average rank: 27.0
- median EXAM: 13.04%
- 3/5 repetitions improved over DDMIN
- 2/5 repetitions worsened

However, inspection showed that the discriminating PASS executions
which avoided fault line 265 were TREE=NULL inputs exercising
encoding/null-document paths.

Non-null sensitivity:

- median average rank: 51.5
- median EXAM: 24.88%
- 0/5 repetitions improved over DDMIN
- no non-null generated PASS avoided fault line 265

## AFLsmart model

A Peach PIT was constructed as a coarse block-scalar-aware model.

The model recognizes:

- arbitrary prefix
- YAML literal block scalar indicator (`|`)
- structural line-break position
- trailing payload

It is intentionally not a complete YAML grammar and is not described
as line-aware.

All seven frozen DDMIN FAIL seeds were independently cracked by Peach
and reconstructed byte-for-byte.

AFLSmart's deferred cracking mechanism was retained unchanged.

## AFLsmart formal experiment

Configuration:

- modes:
  - aflsmart-mixed
  - aflsmart-nonstack
- 5 independent repetitions per mode
- 300 seconds per repetition
- same frozen seed corpus
- fixed randomized mode ordering
- all outcomes retained

### Primary unrestricted-oracle results

AFLsmart-mixed:

- Jaccard mean average rank: approximately 37.1
- Jaccard median average rank: 30.0
- 3/5 repetitions improved over DDMIN
- 2/5 repetitions worsened

AFLsmart-nonstack:

- Jaccard mean average rank: approximately 37.6
- Jaccard median average rank: 29.0
- 3/5 repetitions improved over DDMIN
- 2/5 repetitions worsened

### Non-null semantic sensitivity

Baseline after removing TREE=NULL:

- PASS: 14
- FAIL: 7
- average rank: 44.5
- EXAM: 21.50%

AFLsmart-mixed:

- Jaccard mean average rank: 51.9
- Jaccard median average rank: 51.5
- median EXAM: 24.88%
- range: 49.5-54.5
- NULL PASS tests avoiding fault line 265: 7
- NONNULL PASS tests avoiding fault line 265: 0

AFLsmart-nonstack:

- Jaccard mean average rank: 51.7
- Jaccard median average rank: 51.5
- median EXAM: 24.88%
- range: 51.5-52.5
- NULL PASS tests avoiding fault line 265: 5
- NONNULL PASS tests avoiding fault line 265: 0

Thus 0/10 AFLsmart sensitivity runs improved upon the DDMIN-only
baseline.

## Interpretation

For this yaml-cpp subject, apparent localization improvements from both
plain AFL and AFLsmart were not robust to exclusion of semantically
peripheral TREE=NULL executions.

Despite generating hundreds of non-null usable PASS and FAIL tests,
neither fuzzing strategy generated a non-null passing execution that
avoided the faulty statement.

This demonstrates that:

1. oracle-valid test volume is not sufficient for improved SBFL;
2. increased spectrum diversity is not necessarily fault-relevant
   spectrum diversity;
3. structure-aware mutation does not automatically create the
   discriminating executions required by SBFL;
4. semantically peripheral executions can substantially alter SBFL
   rankings and should therefore be examined through sensitivity
   analysis.

These conclusions are specific to this historical yaml-cpp subject and
should not be generalized to AFL or AFLsmart overall without evidence
from additional subjects.
