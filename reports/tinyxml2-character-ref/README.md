Candidate: TinyXML-2 #997 / CVE-2024-50615
Project: TinyXML-2
Buggy release: 10.0.0
Fixed release: 10.1.0

SCREENING RESULT: REJECTED

1. Buggy/fixed revisions known:
   PASS

   Buggy:
     10.0.0
     commit 321ea88

   Fixed:
     10.1.0
     commit 57eea48

2. Historical reproducer available:
   PASS

   Original PoC size:
     341 bytes

3. Bug reproduction:
   PASS

   Buggy TinyXML-2 10.0.0 with TINYXML2_DEBUG enabled:

     XMLUtil::GetCharacterRef()
     assertion:
       digit == 0 || mult <= UINT_MAX / digit

     exit code 134

4. Fixed-version behavior:
   TinyXML-2 10.1.0 does not abort, but does not accept the
   historical PoC.

   Result:

     PARSE_ERROR code=7
     name="XML_ERROR_PARSING_ATTRIBUTE"
     exit code 2

5. PASS/FAIL boundary:
   FAIL

   The buggy release aborts while processing the historical input,
   while the fixed release safely returns a parse error.

   The fixed parser therefore does not classify the historical
   triggering input as a valid PASS input under the existing
   experimental oracle.

6. DDMIN suitability:
   NOT EVALUATED at initial screening

   Rejected before DDMIN because the required fixed-version
   PASS boundary is absent.

7. Coverage / determinism / PIT:
   NOT EVALUATED at initial screening

   These stages are unnecessary once the candidate fails the
   PASS/FAIL boundary screening criterion.

Decision:
   REJECT candidate from the formal DDMIN/SBFL subject set.

Reason:
   No consistent buggy FAIL -> fixed PASS boundary under the
   experimental oracle.

The candidate is retained as part of the auditable historical-bug
screening process.

Later exploratory character DDMIN
---------------------------------

A later byte-preserving character DDMIN run reduced the 341-byte PoC to a 32-byte assertion trigger and generated 6 PASS candidates. Every one of its 29 FAIL candidates was still rejected by the fixed parser, so the original formal-subject rejection remains. See `character_ddmin_exploratory.md`.


Exploratory SBFL follow-up (2026-10-29)
-------------------------------------

Coverage and SBFL are now complete for the same 6 PASS and 29 FAIL
character-DDMIN candidates. At the target assertion, tinyxml2.cpp:550,
Jaccard and Ochiai both score 1.0 with tie-aware ranks 1-92 (average
46.5; average EXAM 2.975048% of 1,563 executable lines). This is a
92-line tie, not unique first-place localization.

All 35 spectra reproduced identical execution counts on one repeat.
Every coverage FAIL preserved the target assertion, and every fixed
FAIL still returned XML_ERROR_PARSING_ATTRIBUTE (exit 2). The result
remains exploratory and does not reverse the formal rejection.

See [the full exploratory report](character_ddmin_exploratory.md),
[SBFL summary](sbfl_summary.json), and
[coverage validation](coverage_validation_summary.json).


30-second AFL smoke follow-up
-----------------------------

A single 30-second plain-AFL run added 8 PASS and 4 FAIL inputs.
Both Jaccard and Ochiai improved from average rank 46.5 / EXAM
2.975048% to average rank 41.0 / EXAM 2.623161%; the tie shrank
from 92 to 81 lines. All new FAILs were rejected by the fixed parser.
This remains an exploratory single-run smoke result.

See [the smoke-test report](smoke_afl_30s/README.md) and
[metric comparison](smoke_afl_30s/comparison.csv).


300-second FAIL-seed AFL follow-up
----------------------------------

A fresh 300-second plain-AFL run used only the 32-byte minimized FAIL seed. It completed 746,252 executions and supplied 3 new PASS and 4 new FAIL inputs, with 247 UNRESOLVED retained inputs. The original DDMIN baseline was augmented to 9 PASS and 33 FAIL. No earlier fuzz corpus or hand-written probe was included.

Jaccard: average rank 46.5 -> 46.5; EXAM 2.975048% -> 2.975048%; relative reduction 0.00%.; Ochiai: average rank 46.5 -> 46.5; EXAM 2.975048% -> 2.975048%; relative reduction 0.00%.

All 4 generated FAILs were rejected by the fixed parser (exit 2); no new fixed-PASS/buggy-FAIL candidate was found. The result remains exploratory and represents one fuzzing run. See the [full 300-second FAIL-seed report](afl_300s_fail_seed/README.md), [comparison](afl_300s_fail_seed/comparison.csv), and [run summary](afl_300s_fail_seed/summary.json).


300-second mixed-seed AFL follow-up
-----------------------------------

A fresh 300-second plain-AFL run used the same six PASS seeds and 32-byte minimized FAIL seed as the original 30-second smoke run. All seven seed files, source, build command, and coverage binary were verified identical. The AFL target was rebuilt with a different binary hash; the instrumentation map and mutation RNG were not held fixed. It completed 730,726 executions and supplied 14 new PASS and 1 new FAIL inputs, with 311 UNRESOLVED retained inputs. The original DDMIN baseline was augmented to 20 PASS and 30 FAIL. No earlier generated fuzz corpus or hand-written probe was included.

Jaccard: average rank 46.5 -> 41.0; EXAM 2.975048% -> 2.623161%; relative reduction 11.83%.; Ochiai: average rank 46.5 -> 41.0; EXAM 2.975048% -> 2.623161%; relative reduction 11.83%.

All 1 generated FAILs were rejected by the fixed parser (exit 2); no new fixed-PASS/buggy-FAIL candidate was found. The result remains exploratory and represents one fuzzing run. See the [full 300-second mixed-seed report](afl_300s_mixed_seeds/README.md), [baseline/30s/300s comparison](afl_300s_mixed_seeds/duration_comparison.csv), and [run summary](afl_300s_mixed_seeds/summary.json).


Three-method 30-second comparison
--------------------------------

One 30-second trial each used the same original six PASS and one FAIL seeds and an identical shared AFL target binary. Both Jaccard and Ochiai gave plain AFL average rank 46.5 / EXAM 2.975048%, AFLSmart nonstack 41.0 / 2.623161%, and AFLSmart mixed 46.5 / 2.975048%. Nonstack shrank the tie from 92 to 81 lines through new PASS coverage; the other two matched the DDMIN baseline. All 40 usable spectra reproduced on a second collection. All 8 generated FAILs were rejected by the fixed parser, so the result remains exploratory and does not establish a reliable ordering from one trial per method.

See the [three-method report](three_methods_30s/README.md), [comparison CSV](three_methods_30s/comparison.csv), and [campaign provenance](three_methods_30s/campaign.json). The smart modes use a new permissive TinyXML fragment PIT, with successful byte-preserving preflight on all seven original seeds and structural mutations confirmed during both smart runs.


Exploratory structural-fragment DDMIN
-----------------------------------

A tolerant, byte-preserving structural-fragment reduction of the same original 341-byte PoC produced a 63-byte FAIL and 20 unique candidates: 1 PASS, 7 FAIL and 12 UNRESOLVED. The malformed, non-UTF-8 original cannot enter the existing strict-XML structural reducer. The separate fragment reducer deletes whole document nodes, quoted attributes and attribute-value fragments, with no character reduction or input repair.

Both Jaccard and Ochiai worsened from the character baseline's average rank 46.5 / EXAM 2.975048% / 92-line tie to structural average rank 62.5 / EXAM 3.998720% / 124-line tie. All eight usable spectra reproduced exactly. All seven FAILs were rejected by the fixed parser. The result remains exploratory; no new fuzzing or manual PASS probes were included.

See the [structural-fragment report](structural_ddmin_exploratory/README.md), [comparison](structural_ddmin_exploratory/comparison.csv), and [validation](structural_ddmin_exploratory/validation_summary.json).


30-second AFL and AFLSmart trials from structural DDMIN seeds
------------------------------------------------------------

Three one-trial fuzzing methods used the same 1 PASS and 7 FAIL structural DDMIN seeds. Each method's generated usable inputs augmented the structural baseline independently. See the [structural-seed comparison](three_methods_structural_30s/README.md) and [metric table](three_methods_structural_30s/comparison.csv). The malformed-input oracle keeps this subject exploratory.


Character versus structural 30-second pipeline comparison
---------------------------------------------------------

A [side-by-side comparison](pipeline_comparison_30s/README.md) now puts the two DDMIN baselines and all three 30-second methods on the same rank and EXAM table. The structural baseline starts at rank 62.5 versus character 46.5. After fuzzing, plain AFL reaches 46.5 in both pipelines, nonstack 41.0 in both, and mixed 41.0 from structural seeds versus 46.5 from character seeds. The two seed sets have no byte-identical files and each method was run once per pipeline, so this is a descriptive comparison. See [both-metric CSV](pipeline_comparison_30s/comparison.csv) and [seed/configuration provenance](pipeline_comparison_30s/provenance.json).
