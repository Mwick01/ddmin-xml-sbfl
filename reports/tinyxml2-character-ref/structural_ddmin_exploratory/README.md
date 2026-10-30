# TinyXML-2 #997: exploratory structural-fragment DDMIN

Run on 2026-10-29 (Asia/Colombo). Structural-fragment deletion reduced the original 341-byte reproducer to **63 bytes**, but produced a **worse SBFL baseline** than character DDMIN: average rank **62.5**, average EXAM **3.998720%**, and a **124-line tie**, under both Jaccard and Ochiai. No new fuzzing was run.

## Comparison

Both reductions start from the same original byte sequence and use the same buggy/fixed oracle. Coverage uses the unchanged buggy parser and coverage executable, target `tinyxml2.cpp:550`, and the same 1,563 executable lines. Each DDMIN suite is scored independently; candidate sets are not pooled.

| Measure | Character DDMIN | Structural-fragment DDMIN |
| --- | ---: | ---: |
| Original bytes | 341 | 341 |
| Minimized FAIL bytes | 32 | 63 |
| Reduction | 90.62% | 81.52% |
| Unique candidates | 426 | 20 |
| PASS / FAIL / UNRESOLVED | 6 / 29 / 391 | 1 / 7 / 12 |
| Distinct PASS / FAIL coverage profiles | 1 / 4 | 1 / 4 |
| Suspiciousness at line 550, both metrics | 1.0 | 1.0 |
| Best–worst rank, both metrics | 1–92 | 1–124 |
| Average rank, both metrics | 46.5 | 62.5 |
| Average EXAM, both metrics | 2.975048% | 3.998720% |

Average rank worsened by 16.0 positions (34.41% relative), and EXAM increased by 1.023672 percentage points. These are baselines produced by different reduction units and candidate populations, rather than equally sized or fixed-duration test suites.

## Structural scope

The original input is malformed XML and is not valid UTF-8. Python's strict XML parser rejects it at line 1, column 18. Consequently, the existing validity-gated `xml_structural_ddmin.py` cannot accept this starting input. This run uses the new, separate `scripts/tinyxml2_structural_ddmin.py` and is explicitly a tolerant **fragment** experiment, not strict XML-tree HDD or a formal valid-input structural baseline.

Its nested deletion groups are:

1. Document lexical nodes: complete markup, complete comments, intervening text runs, and an incomplete final start tag. Scanning respects quotes and comments, so tag-like bytes within quoted attributes or comments are not split into document nodes.
2. Complete quoted attributes within each start-tag fragment, including adjacent attributes that lack separating whitespace.
3. Whole character-reference fragments and intervening raw-text runs within attribute values. A malformed `&#...;` body remains one atomic fragment; digit runs, names and individual bytes are not minimized.

The reducer tries retaining and removing subsets of each group, recomputes groups after every accepted FAIL, and accepts only strictly shorter FAIL candidates. All output consists of original surviving bytes in their original order. It performs no repair, insertion, renaming, reserialization, character-level reduction, or strict-validity filtering. The original exploratory PASS/FAIL/UNRESOLVED oracle determines outcomes.

## Reduction and candidate evidence

The accepted byte sizes were **341 → 304 → 159 → 113 → 88 → 78 → 63**. There were 51 classification requests, including cached attempts and the final audit, and 20 unique oracle-classified candidates. Their initial classifications were independently rechecked for this report.

The final trigger, represented as Python bytes to preserve non-UTF-8 data, is:

```python
b'<m:mi style="&#01%E>0</m:mi> \xc1\xde\xd2\xd200000000006000000001;"style=""'
```

The complete malformed reference body stays intact; this explains why the structural trigger remains larger than the 32-byte character minimum. The final result is deletion-minimal for the implemented structural units: none of four available single-unit deletions retains FAIL. This is a local unit-based minimality result, not a globally shortest XML trigger.

All seven FAIL candidates reproduce the specified buggy assertion and are rejected by the fixed parser (exit 2). The 63-byte result reproduced FAIL in 10/10 checks.

## Why the tie became larger

The sole structural PASS candidate is a comment fragment. Its spectrum gives little coverage of the parsing paths followed by the failures. The fault's spectrum is `ef=7, ep=0, nf=0, np=1`, so both formulas still give 1.0, now shared by 124 lines.

Compared with the character baseline, the structural top tie gained **32 lines** and lost **0 lines**. Of the additional lines, **32** were covered by character-DDMIN PASS inputs and **0** were absent from at least one character-DDMIN FAIL; these sets can overlap. The structural suite supplies less evidence to distinguish these lines from the assertion. The equal count of distinct profiles (1 PASS / 4 FAIL in each suite) does not imply identical profiles or equally useful coverage. See [tie analysis](tie_analysis.json).

## Validation and interpretation

- All **20 unique candidate labels** were rechecked against the original buggy/fixed binaries, and all candidate byte hashes and original-byte subsequences were verified.
- All **51 attempts** were replayed from their declared complete structural deletion units and matched their saved candidate hashes exactly.
- All **8 usable spectra** reproduced every line execution count on a second collection; FAIL coverage retained the target assertion and line 550.
- Both scores, tie bounds and EXAM values were independently recomputed from the saved coverage. Source, oracle binaries, coverage executable/object/gcno and the existing character baseline hashes were unchanged.
- The final four single-unit deletions all classified UNRESOLVED. The 63-byte minimum remained FAIL in 10/10 repeats.

This run shows that the structural-fragment reduction supplied a smaller, less discriminating candidate suite for this malformed subject. It does not show a general disadvantage of structural DDMIN. All FAILs still violate the formal fixed-PASS eligibility criterion, so this remains exploratory. No manually selected PASS probes or fuzz-generated candidates were added to either baseline.

## Evidence and reproduction

- [DDMIN summary](ddmin_summary.json), [initial structure](initial_structure.json), [accepted reductions](reductions.jsonl), [all attempts](attempts.jsonl), and [unique candidates](unique_candidates.jsonl).
- [Original bytes](original.xml), [63-byte trigger](minimal_failure.xml), and [all 20 candidates](all_candidates.zip).
- [SBFL comparison CSV](comparison.csv), [SBFL summary](sbfl_summary.json), [spectrum](spectrum.csv), [Jaccard ranking](jaccard_ranking.csv), and [Ochiai ranking](ochiai_ranking.csv).
- [Original coverage](coverage_records.jsonl), [repeated coverage](repeated_coverage.jsonl), [coverage validation](coverage_validation.csv), [classification validation](classification_validation.jsonl), and [validation summary and hashes](validation_summary.json).
- [Reducer snapshot](reducer_snapshot.py), [analysis snapshot](analysis_snapshot.py), and [artifact checksums](artifact_hashes.json).

From the WSL repository root, with the existing subject binaries available:

```bash
python3 scripts/tinyxml2_structural_ddmin.py
```

This creates a fresh timestamped structural reduction. The snapshot analysis records the completed coverage procedure; its saved run paths are provenance for this experiment. Raw run: `/home/user/ddmin-xml-sbfl/results/tinyxml2_character_ref/structural_ddmin_exploratory_20261029_170147_990273`.


Three-method 30-second fuzzing comparison from structural seeds
---------------------------------------------------------------

One 30-second trial each of plain AFL, AFLSmart nonstack and AFLSmart mixed used the structural DDMIN suite's one PASS and seven FAIL candidates as the identical seed corpus. Generated usable inputs independently augmented the structural baseline. See the [full comparison](../three_methods_structural_30s/README.md), [metric table](../three_methods_structural_30s/comparison.csv), and [campaign evidence](../three_methods_structural_30s/campaign.json). All results remain exploratory under the malformed-input oracle.
