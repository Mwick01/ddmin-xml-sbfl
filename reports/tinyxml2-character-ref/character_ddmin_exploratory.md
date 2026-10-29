# TinyXML-2 #997: exploratory character DDMIN

Run: 2026-10-29. Raw results: `/home/user/ddmin-xml-sbfl/results/tinyxml2_character_ref/character_ddmin_exploratory/20261029_145029_5923/`.

## Method

- Original historical PoC: `subjects/tinyxml2-character-ref/poc.xml`, 341 bytes.
- The PoC is not valid UTF-8. DDMIN used a Latin-1 one-to-one mapping so each original byte was one deletion unit and all remaining bytes were preserved exactly. This is a byte-level form of character DDMIN.
- The exploratory oracle classified a candidate as FAIL only when buggy TinyXML-2 10.0.0 hit the specific `XMLUtil::GetCharacterRef()` assertion, while fixed TinyXML-2 10.1.0 returned either success or a parse error. PASS required both versions to parse successfully with matching output. Other cases were UNRESOLVED.
- The oracle deliberately permits fixed-parser rejection for exploratory crash minimization. Formal eligibility was checked separately by rerunning every FAIL against the fixed parser.

## Result

| Measure | Value |
| --- | ---: |
| Original size | 341 bytes |
| Smallest assertion-triggering input | 32 bytes |
| Reduction | 90.62% |
| Oracle attempts | 1,092 |
| Unique candidates | 426 |
| PASS | 6 |
| FAIL | 29 |
| UNRESOLVED | 391 |

The 32-byte minimized input is:

```text
<i style="&#6000000001;"style=""
```

It is malformed XML. The fixed binary returns `XML_ERROR_PARSING_ATTRIBUTE` (exit 2); the buggy binary aborts at the target assertion (signal 6). The minimized input reproduced FAIL in 10 of 10 repeated checks.

All 29 FAIL candidates returned exit 2 in the fixed version and aborted at the target assertion in the buggy version. All 6 PASS candidates returned exit 0 in both versions. **No candidate combined a fixed-parser success with the buggy assertion.** The earlier reason for excluding this subject from the formal valid-input DDMIN/SBFL set therefore still applies, despite the strong exploratory crash reduction.

Coverage and SBFL were added on 2026-10-29 as an exploratory follow-up, described below. The DDMIN run itself did not include fuzzing; a separate 30-second AFL follow-up is recorded below.


## Exploratory coverage and SBFL

**Status: exploratory only.** These results do not change the formal-subject rejection: all 29 FAIL candidates are rejected by the fixed parser. They measure localization of the reproduced assertion on malformed inputs, under the exploratory oracle above.

### Coverage method and validation

The existing `scripts/collect_coverage.py` collected independent line spectra for all 35 unique usable DDMIN candidates, with `oracle_tinyxml2_character_ref` rechecking each label. The 391 UNRESOLVED candidates were excluded. Candidates were weighted equally; distinct coverage profiles were not deduplicated or reweighted.

The coverage build used the unchanged TinyXML-2 10.0.0 `tinyxml2.cpp` with `g++ -O0 -g --coverage -DTINYXML2_DEBUG` and GCC/gcov 15.2.0. Assertions stayed enabled. Only `subjects/tinyxml2-character-ref/coverage_driver.cpp` adds a SIGABRT handler that calls `__gcov_dump()` and then `std::_Exit(134)`. This preserves counters when the target assertion fires, while the original oracle binaries retain their original signal behavior. The generic collector was not changed. The handler is an exploratory, single-threaded workaround: `__gcov_dump()` is not guaranteed to be async-signal-safe.

The source object's `.gcda` was removed before each candidate, and the collector restricted spectra to `subjects/tinyxml2-character-ref/buggy/tinyxml2.cpp`; headers and the driver were excluded. All candidates used the same set of 1,563 gcov executable lines, including never-executed lines in the ranking denominator.

| Measure | Value |
| --- | ---: |
| PASS candidates | 6 |
| FAIL candidates | 29 |
| Executable source lines | 1,563 |
| Lines covered by at least one usable candidate | 402 |
| Distinct PASS coverage profiles | 1 (frequency 6) |
| Distinct FAIL coverage profiles | 4 (frequencies 23, 3, 2, 1) |
| Exact PASS/FAIL coverage-profile overlap | 0 |

All 29 original buggy FAIL executions terminated with SIGABRT (`subprocess` return code -6); all 29 coverage FAIL executions exited 134 after printing the same `XMLUtil::GetCharacterRef()` assertion, `digit == 0 || mult <= UINT_MAX / digit`. Every fixed FAIL execution returned exit 2 with `XML_ERROR_PARSING_ATTRIBUTE`. All 6 PASS candidates returned exit 0 with matching `PARSE_OK` output in the original buggy, fixed, and coverage builds.

Candidate bytes were checked against their SHA-256 IDs and the original DDMIN manifest. A second independent coverage collection for every candidate reproduced every line execution count exactly (35/35), including the fault-line coverage. This is one repeat per candidate, not a broad determinism study. An independent recalculation from the saved binary spectra also confirmed both scores and tie bounds. See [per-candidate validation](coverage_validation.csv) and [validation summary and provenance hashes](coverage_validation_summary.json).

### Known-location ranks

The scored location is **buggy `tinyxml2.cpp:550`**, the target assertion in `XMLUtil::GetCharacterRef()`:

```cpp
TIXMLASSERT( digit == 0 || mult <= UINT_MAX / digit );
```

This is the observed assertion/crash-site representative of the character-reference fault, rather than a claim that SBFL uniquely identifies the underlying repair. It was covered by every FAIL and no PASS: `ef=29`, `ep=0`, `nf=0`, `np=6`.

| Metric | Score | Best rank | Average rank | Worst rank | Average EXAM |
| --- | ---: | ---: | ---: | ---: | ---: |
| Jaccard | 1.000000 | 1 | 46.5 | 92 | 2.975048% |
| Ochiai | 1.000000 | 1 | 46.5 | 92 | 2.975048% |

Jaccard is `ef / (ef + ep + nf)`; Ochiai is `ef / sqrt((ef + nf) * (ef + ep))`. Both give the target the maximum suspiciousness score, shared by 92 executable lines (91 other lines). Ranks are tie-aware: the tied group occupies positions 1 through 92, and its midpoint is 46.5. Average EXAM is `46.5 / 1563 = 0.02975048`, or 2.975048%. The target does not satisfy inspect@1, @3, @5, or @10 using average rank. A best rank of 1 should therefore not be read as unique first-place localization.

All PASS candidates share one coverage profile, and the FAIL spectra stop at the assertion. This provides limited behavioral diversity and distinguishes the crashing path from successful parsing, while leaving a large tie. The results remain outside the formal valid-input DDMIN/SBFL set because no FAIL is accepted by the fixed parser.

### Saved evidence

The original run remains at `results/tinyxml2_character_ref/character_ddmin_exploratory/20261029_145029_5923/`, with coverage under `coverage/` and rankings under `sbfl/`. Because `results/` is git-ignored, report-local snapshots preserve the evidence:

- [DDMIN summary](ddmin_summary.json) and [32-byte minimal trigger](minimal_failure.xml).
- [Coverage summary](coverage_summary.json) and [all 35 per-candidate coverage records](coverage_records.jsonl).
- [Line spectrum](spectrum.csv), [Jaccard ranking](jaccard_ranking.csv), [Ochiai ranking](ochiai_ranking.csv), and [SBFL summary](sbfl_summary.json).
- [Per-candidate validation](coverage_validation.csv) and [validation summary, tool versions, revisions, and hashes](coverage_validation_summary.json).

The coverage summary and records use original run paths for provenance. The report-local `coverage_records.jsonl` is a byte-identical snapshot and is sufficient to recompute the spectra and ranks with the matching source revision. The complete 35-input suite remains in the original run; the report snapshots include the minimized trigger.

### Reproduction

Run from the WSL repository root with the original DDMIN candidate directories present:

```bash
bash scripts/build_tinyxml2_character_ref_coverage.sh
run=results/tinyxml2_character_ref/character_ddmin_exploratory/20261029_145029_5923
python3 scripts/collect_coverage.py "$run" \
  --oracle-module oracle_tinyxml2_character_ref \
  --source subjects/tinyxml2-character-ref/buggy/tinyxml2.cpp \
  --binary build/tinyxml2_character_ref_cov/tinyxml_cov \
  --object build/tinyxml2_character_ref_cov/tinyxml2.o
python3 scripts/sbfl.py "$run" \
  --source subjects/tinyxml2-character-ref/buggy/tinyxml2.cpp \
  --fault-line 550
```


## 30-second AFL smoke follow-up

One exploratory plain-AFL 2.52b run used a 30-second budget and the minimized FAIL plus six original DDMIN PASS inputs as seeds. It executed 78,017 tests and retained 189 new inputs after excluding seed entries: 8 PASS, 4 FAIL, and 177 UNRESOLVED. The 12 new usable inputs augmented the original baseline to 14 PASS and 33 FAIL. No hand-written controlled-probe input was included.

For both Jaccard and Ochiai at `tinyxml2.cpp:550`, the score stayed at 1.0, the tie shrank from ranks 1-92 to 1-81, average rank improved from 46.5 to 41.0, and average EXAM improved from 2.975048% to 2.623161%. The denominator stayed at 1,563 executable lines. This is an 11.83% relative improvement in average rank/EXAM in this single run. All 12 generated usable spectra reproduced identical execution counts on one repeat.

All four generated FAIL inputs were still rejected by the fixed parser with `XML_ERROR_PARSING_ATTRIBUTE` (exit 2), so the result remains exploratory and the formal-subject rejection remains. See the [full smoke-test report](smoke_afl_30s/README.md), [comparison](smoke_afl_30s/comparison.csv), and [run summary](smoke_afl_30s/summary.json).


## 300-second FAIL-seed AFL follow-up

A fresh 300-second plain-AFL run used only the 32-byte minimized FAIL seed. It completed 746,252 executions and supplied 3 new PASS and 4 new FAIL inputs, with 247 UNRESOLVED retained inputs. The original DDMIN baseline was augmented to 9 PASS and 33 FAIL. No earlier fuzz corpus or hand-written probe was included.

Jaccard: average rank 46.5 -> 46.5; EXAM 2.975048% -> 2.975048%; relative reduction 0.00%.; Ochiai: average rank 46.5 -> 46.5; EXAM 2.975048% -> 2.975048%; relative reduction 0.00%.

All 4 generated FAILs were rejected by the fixed parser (exit 2); no new fixed-PASS/buggy-FAIL candidate was found. The result remains exploratory and represents one fuzzing run. See the [full 300-second FAIL-seed report](afl_300s_fail_seed/README.md), [comparison](afl_300s_fail_seed/comparison.csv), and [run summary](afl_300s_fail_seed/summary.json).


## 300-second mixed-seed AFL follow-up

A fresh 300-second plain-AFL run used the same six PASS seeds and 32-byte minimized FAIL seed as the original 30-second smoke run. All seven seed files, source, build command, and coverage binary were verified identical. The AFL target was rebuilt with a different binary hash; the instrumentation map and mutation RNG were not held fixed. It completed 730,726 executions and supplied 14 new PASS and 1 new FAIL inputs, with 311 UNRESOLVED retained inputs. The original DDMIN baseline was augmented to 20 PASS and 30 FAIL. No earlier generated fuzz corpus or hand-written probe was included.

Jaccard: average rank 46.5 -> 41.0; EXAM 2.975048% -> 2.623161%; relative reduction 11.83%.; Ochiai: average rank 46.5 -> 41.0; EXAM 2.975048% -> 2.623161%; relative reduction 11.83%.

All 1 generated FAILs were rejected by the fixed parser (exit 2); no new fixed-PASS/buggy-FAIL candidate was found. The result remains exploratory and represents one fuzzing run. See the [full 300-second mixed-seed report](afl_300s_mixed_seeds/README.md), [baseline/30s/300s comparison](afl_300s_mixed_seeds/duration_comparison.csv), and [run summary](afl_300s_mixed_seeds/summary.json).
