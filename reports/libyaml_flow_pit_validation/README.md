# libyaml AFLSmart PIT validation

## Frozen subject

Buggy libyaml revision:

`588eabff23ba2292f537872bbea5b64bce1e1a21`

Fixed revision:

`840b65c40675e2d06bf40405ad3f12dec7f35923`

AFLSmart seed corpus:

- 16 DDMIN FAIL candidates
- same corpus used by all fuzzing methods

## AFL instrumentation stability

The AFLSmart-instrumented buggy target was executed through
`afl-showmap` 10 times on the rich failing input.

All 10 executions produced:

- 650 map entries
- identical SHA-256 map hash

Map SHA-256:

`c58de3e20080ecdf6654cefa8470e10405deb869dafd86562e3c658c9084cc16`

Thus the AFL instrumentation was stable across 10/10 repeated runs.

## Peach model validation

PIT:

`aflsmart/libyaml_flow.xml`

Peach 3.0.202 successfully cracked all 16 frozen seeds.

Results:

- Peach `ok`: 16/16
- byte-identical repaired files: 16/16
- `.chunks` generated: 16/16
- `NestedContent` recognized: 16/16

The nested explicit-key content corresponding to `?` is modeled as an
ordinary mutable String rather than a fixed token.

## AFLSmart smart-stage validation

A 15-second one-seed diagnostic retained:

- 29 `havoc-smart` queue entries
- 110 ordinary havoc entries
- 272 splice entries

Therefore AFLSmart's structure-aware mutation stage was active and
produced retained queue entries.

## Freeze rule

The PIT, seed corpus, subject revisions, oracle, and representative
fault line are frozen before comparative fuzzing results are evaluated.

The PIT must not be modified in response to subsequent fuzzing or SBFL
results.
