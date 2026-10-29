# Expat #566: structural DDMIN screening

Screened on 2026-10-29 using the historical 67-character failing XML input (`subjects/expat-566/input.xml`). The existing semantic oracle compares the buggy Expat 2.4.5 and fixed 2.4.6 `junk` element content models.

## Reduction and oracle outcomes

| Method | Original | Minimal FAIL | Unique candidates | PASS | FAIL | UNRESOLVED | Invalid XML |
|---|---:|---:|---:|---:|---:|---:|---:|
| Character DDMIN (earlier screening) | 67 | 41 | 441 | 0 | 14 | 427 | — |
| DTD content-model structural DDMIN | 67 | 60 | 13 | 6 | 3 | 2 | 2 |

The structural reducer removes whole content-model branches or quantifiers, or deletes a whole DTD declaration or DOCTYPE. It does not delete arbitrary characters within XML names. It validates candidate XML before calling the same Expat #566 oracle. The resulting 9 usable PASS/FAIL tests have 9 distinct line-coverage profiles.

Minimal structural failure:

```xml
<!DOCTYPE foo [
<!ELEMENT junk ((bar|foo),zebra)>
]>
<foo/>
```

This is a 10.45% size reduction, compared with 38.81% for character DDMIN.

## SBFL baseline

The 9 usable tests cover a program with 4,473 executable lines in `xmlparse.c`. The known fault consists of buggy-source lines 7399, 7400, 7404, 7408, 7430, 7435, and 7438. The first known fault line has:

| Metric | Tie-aware average rank | Tie interval | EXAM |
|---|---:|---:|---:|
| Jaccard | 395.5 | 28–763 | 8.84% |
| Ochiai | 394 | 28–760 | 8.81% |

All seven known fault lines are covered by **every** usable test: 3/3 FAIL and 6/6 PASS. Consequently, this baseline cannot distinguish the fault lines by coverage, even though each test's overall coverage profile is distinct. A second coverage collection of the same candidates reproduced the ranks. Seven hash-table lookup lines varied for two candidates between collections; fault-line coverage was stable.

## Decision

Structural reduction repairs the character baseline's zero-PASS problem, so Expat #566 is technically eligible for an SBFL calculation. It is **not a strong formal fuzzing subject in this configuration**: the historical reproducer is only 67 characters, the structural reduction yields just 3 FAIL and 6 PASS tests, and all of them execute the fault. I recommend retaining this as an exploratory negative screening result and not starting a 300-second AFLSmart campaign for it now.

The coverage executable was rebuilt using the current `subjects/expat-566/driver.c` linked with the existing instrumented buggy Expat objects, because the older coverage driver segfaulted on a PASS candidate. Its output matched the ordinary buggy executable on all 9 usable candidates.

Raw run: `/home/user/ddmin-xml-sbfl/results/expat_566_structural_ddmin/20261029_140924_971716`.

Reducer: `/home/user/ddmin-xml-sbfl/scripts/expat566_structural_ddmin.py` (SHA-256 `47417e475e39e880054ba82fab2a55417579e014a06d173b4d2cb6d5ea7479be`).
