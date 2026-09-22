# Cross-subject experimental results

## Subjects

### Expat

Historical real-world XML parser regression.

DDMIN baseline:

- PASS: 6
- FAIL: 16
- UNRESOLVED: 194 / 216 unique candidates (89.81%)
- distinct PASS profiles: 2
- distinct FAIL profiles: 4
- representative fault: xmlparse.c:2912
- baseline average rank: 303.5
- baseline EXAM: 8.24%
- baseline fault tie size: 524

Formal fuzzing:

- 5 repetitions
- 300 seconds per method per repetition
- same 16 DDMIN FAIL seeds
- methods:
  - AFL
  - AFLSmart mixed
  - AFLSmart nonstack

Mean localization:

| Method | Jaccard avg rank | Ochiai avg rank | New FAIL profiles |
|---|---:|---:|---:|
| AFL | 327.7 | 322.1 | 3.2 |
| AFLSmart mixed | 332.1 | 323.3 | 3.4 |
| AFLSmart nonstack | 311.3 | 300.9 | 7.0 |

AFLSmart nonstack generated approximately 2.19x as many new failing
profiles as AFL and approximately 2.06x as many as AFLSmart mixed.

Under Jaccard, nonstack did not improve the DDMIN-only baseline mean
rank. Under Ochiai, nonstack produced a modest mean improvement from
303.5 to 300.9.

Post-hoc mechanism:

- helpful discrimination is FAIL-driven;
- all helpful discriminating pairs are produced by failing spectra;
- AFLSmart nonstack has helpful discrimination in 5/5 runs;
- AFLSmart nonstack has the least-negative mean net discriminating
  density (-0.00486).

---

### libyaml

Historical real-world YAML parser regression.

DDMIN baseline:

- PASS: 25
- FAIL: 16
- UNRESOLVED: 121 / 162 unique candidates (74.69%)
- distinct PASS profiles: 9
- distinct FAIL profiles: 6
- representative fault: parser.c:1062
- baseline average rank: 9.0
- baseline EXAM: 1.49%
- baseline fault tie size: 17

Formal fuzzing:

- 5 repetitions
- 300 seconds per method per repetition
- same 16 DDMIN FAIL seeds
- methods:
  - AFL
  - AFLSmart mixed
  - AFLSmart nonstack

Mean localization:

| Method | Jaccard avg rank | Ochiai avg rank | New FAIL profiles | New PASS profiles |
|---|---:|---:|---:|---:|
| AFL | 4.5 | 4.5 | 7.0 | 44.4 |
| AFLSmart mixed | 5.5 | 5.5 | 7.0 | 41.0 |
| AFLSmart nonstack | 5.6 | 5.6 | 6.4 | 39.2 |

All three methods improved mean localization relative to the baseline.

Ordinary AFL produced the lowest mean fault rank.

No method moved any baseline-tied statement above the fault in any
formal repetition.

Post-hoc mechanism:

- helpful discrimination is PASS-driven;
- all helpful discriminating pairs are produced by passing spectra;
- harmful discrimination is absent;
- runs without helpful discrimination retain the original 17-way tie;
- runs with helpful discrimination move competitors below the fault.

Mean new-profile net discriminating density:

| Method | Net density |
|---|---:|
| AFL | +0.03792 |
| AFLSmart mixed | +0.01976 |
| AFLSmart nonstack | +0.02192 |

---

## Cross-subject observation

The localization usefulness of generated tests is not determined only
by the number of generated inputs, valid inputs, AFL paths, or distinct
coverage profiles.

Useful spectra differ by subject:

- Expat: FAIL spectra distinguish the fault from competitors.
- libyaml: PASS spectra distinguish competitors from the fault.

Structure-aware fuzzing therefore does not guarantee improved SBFL.
Its value depends on whether generated tests introduce coverage spectra
that discriminate the fault from competing statements in a useful
direction.

The discriminating-spectrum analysis was defined after inspection of
the formal results and is therefore explanatory/post-hoc rather than
confirmatory.
