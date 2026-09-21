# libyaml flow-sequence DDMIN baseline

## Subject

Historical libyaml regression:

- Buggy revision: `588eabff23ba2292f537872bbea5b64bce1e1a21`
- Fixed revision: `840b65c40675e2d06bf40405ad3f12dec7f35923`
- Fixed revision is the direct child of the buggy revision.
- Upstream change: `Fix closing flow sequence after explicit key`

Known buggy source:
- `src/parser.c`
- fault region: lines 1062-1066
- representative executable fault line: 1062

## Input

Initial rich failing input:

    ---
    {name: demo, items: [alpha, [?], omega], flag: true}

Original size: 57 characters.

DDMIN minimal failure:

    {n: [a,[?]]}

Minimal size: 12 characters.

## DDMIN

- Reduction: 78.95%
- Oracle attempts: 321
- Unique candidates: 162
- PASS: 25
- FAIL: 16
- UNRESOLVED: 121
- Usable candidates: 41
- Usable rate: 25.31%
- UNRESOLVED rate: 74.69%

## Coverage

- PASS tests: 25
- FAIL tests: 16
- Executable parser.c lines: 603
- Lines covered by at least one usable test: 312

## SBFL baseline

Representative fault: parser.c:1062

Jaccard:
- score: 1.0
- best rank: 1
- average rank: 9.0
- worst rank: 17
- EXAM: 1.49%

Ochiai:
- score: 1.0
- best rank: 1
- average rank: 9.0
- worst rank: 17
- EXAM: 1.49%

The fault is tied with 16 other statements. Future augmentation is
evaluated by whether generated spectra break this tie in a favorable
or unfavorable direction.
