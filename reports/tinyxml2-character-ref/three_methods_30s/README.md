# TinyXML-2 #997: three fuzzing methods, 30 seconds each

Run on 2026-10-29 (Asia/Colombo). **The methods produced different SBFL results in this smoke test.** AFLSmart nonstack improved the average rank from 46.5 to 41.0 and EXAM from 2.975048% to 2.623161%. Plain AFL and AFLSmart mixed matched the original baseline. Both Jaccard and Ochiai produced these same results.

## SBFL comparison

All results refer to the representative fault location, buggy `tinyxml2.cpp:550`, and use the same 1,563 executable lines. Each augmented suite consists of the original DDMIN suite plus that method's own new usable inputs. Earlier fuzzing corpora and other methods' outputs are not pooled.

| Suite | Combined PASS / FAIL | Score | Tied ranks | Average rank | Average EXAM | Relative rank/EXAM reduction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Original DDMIN | 6 / 29 | 1.0 | 1–92 | 46.5 | 2.975048% | 0.00% |
| Plain AFL | 22 / 31 | 1.0 | 1–92 | 46.5 | 2.975048% | 0.00% |
| AFLSmart nonstack | 13 / 33 | 1.0 | 1–81 | 41.0 | 2.623161% | 11.83% |
| AFLSmart mixed | 15 / 31 | 1.0 | 1–92 | 46.5 | 2.975048% | 0.00% |

Average rank is the midpoint of tied positions; EXAM is average rank divided by 1,563, expressed as a percentage. AFLSmart nonstack removed 11 competing lines from the original 92-line tie, giving an 11.83% relative reduction in rank and EXAM (0.351887 percentage points of EXAM). Its rank matches the earlier mixed-seed 30-second and 300-second plain-AFL results; the fresh plain-AFL run here did not reproduce that improvement. This illustrates variation between single randomized runs.

## Fuzzing yield

| Method | Executions | New PASS | New FAIL | UNRESOLVED | New distinct PASS / FAIL profiles | Chunk sidecars | Retained smart mutations | AFL stats span (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Plain AFL | 73,916 | 16 | 2 | 163 | 4 / 2 | 0 | 0 | 30 |
| AFLSmart nonstack | 76,299 | 7 | 4 | 142 | 5 / 3 | 4 | 11 | 30 |
| AFLSmart mixed | 68,570 | 9 | 2 | 131 | 3 / 1 | 1 | 1 | 30 |

These counts describe unique retained queue/crash/hang inputs after excluding the seven original seed entries and byte duplicates of the baseline or generated inputs. They do not classify every transient fuzzing execution. All generated PASS and FAIL inputs are used equally in SBFL; UNRESOLVED inputs are excluded. Fuzzer `unique_crashes` is not the oracle FAIL count because the fuzz driver turns SIGABRT into exit 134.

## Protocol and method definitions

- One fresh, sequential 30-second run per method with `timeout -s INT -k 5s 30s`; build, preflight, classification and coverage are outside those budgets. All modes use AFL 2.52b in the same Docker image, `-d`, 200 MB memory, 1,000 ms per-input timeout, and disabled networking.
- All three modes receive the exact same six DDMIN PASS seeds and one 32-byte minimized FAIL seed as the original smoke run, verified by filename and SHA-256. [Seed files](seeds/minimal_failure.xml) and the complete manifest in [campaign.json](campaign.json) preserve the evidence. Oracle seed labels were rechecked before fuzzing.
- **Plain AFL (`afl`)** uses byte mutation. **AFLSmart nonstack (`aflsmart-nonstack`)** adds `-w peach -g MODEL` without `-h`. **AFLSmart mixed (`aflsmart-mixed`)** adds the same model and `-h`, mixing normal and higher-order operators. These are the three established repository modes. Nonstack here means AFLSmart's structural mode without mixed stacking; it is not a custom AFL build limited to one byte operator.
- The [fragment PIT](tinyxml2_character_ref_fragments.xml) describes character-reference, closing-tag and quoted-attribute fragments, markup tokens, and raw-byte fallbacks. It is a newly introduced, permissive seed-family model, not a complete XML grammar. This accommodates the malformed and arbitrary-byte original seeds. [Preflight records](model_preflight/summary.json) confirm all seven inputs crack successfully and are reproduced byte for byte. Actual runs produced nonempty chunks and retained `havoc-smart`/`splice-smart` entries in both smart modes; counts are in the table and raw names are saved in each method's summary.
- The existing instrumented AFL target from the prior 300-second mixed-seed experiment was reused unchanged for all three modes. No rebuild occurred. Its binary SHA-256, parser source, fuzz driver, oracle binaries, baseline records, coverage executable/object and gcno hashes were verified before and after the runs. Thus the AFL instrumentation map is held fixed across these three methods. AFL mutation randomness remains uncontrolled.
- The unchanged GCC/gcov coverage build measures the buggy parser. Coverage counters are reset separately for every candidate. The SIGABRT coverage handler preserves the specific assertion and writes its counters; the original buggy/fixed binaries independently determine classifications.

## Why the ranks differ

- **Plain AFL:** new PASS coverage reached 0 original tied lines; added FAIL spectra omitted 0 original tied lines. Target spectrum: `ef=31, ep=0, nf=0, np=22`. Demoted-line lists are saved in [afl/summary.json](afl/summary.json).
- **AFLSmart nonstack:** new PASS coverage reached 11 original tied lines; added FAIL spectra omitted 0 original tied lines. Target spectrum: `ef=33, ep=0, nf=0, np=13`. Demoted-line lists are saved in [aflsmart-nonstack/summary.json](aflsmart-nonstack/summary.json).
- **AFLSmart mixed:** new PASS coverage reached 0 original tied lines; added FAIL spectra omitted 0 original tied lines. Target spectrum: `ef=31, ep=0, nf=0, np=15`. Demoted-line lists are saved in [aflsmart-mixed/summary.json](aflsmart-mixed/summary.json).

Nonstack generated fewer PASS inputs than plain AFL, but those PASS inputs covered competing lines in the original top tie without covering line 550. Their discrimination matters more for this rank than the total number of generated tests. The fault's suspiciousness remained 1.0 in all three augmented suites.

## Validation and interpretation

All **40/40 usable generated spectra** reproduced every line execution count on a second coverage collection. Both SBFL formulas, rank bounds and EXAM values were independently recomputed from the saved coverage. Every FAIL preserved the original target assertion and line 550 coverage. All **8 generated FAILs** were rejected by the fixed parser (exit 2); there were no new fixed-PASS/buggy-FAIL inputs. The unchanged 6 PASS + 29 FAIL baseline reproduced its original ranks.

**Exploratory, one trial per method.** The result shows different outcomes for these trials; it does not establish that nonstack reliably outperforms the other methods. The new fragment model and its byte fallback are part of the smart-method configuration. The subject remains excluded from the formal valid-input experiment under the original screening criterion.

## Evidence

- [Machine-readable metric comparison](comparison.csv), [campaign configuration and hashes](campaign.json), [baseline coverage](baseline_coverage.jsonl), and [baseline SBFL](baseline_sbfl_summary.json).
- [Plain AFL summary](afl/summary.json), [nonstack summary](aflsmart-nonstack/summary.json), and [mixed summary](aflsmart-mixed/summary.json).
- [Plain AFL input/coverage validation](afl/validation.csv), [nonstack validation](aflsmart-nonstack/validation.csv), and [mixed validation](aflsmart-mixed/validation.csv).
- Each method directory contains classifications, original and repeated coverage, augmented spectra and both rankings, fuzzer logs/statistics, and a ZIP of retained inputs plus structural chunk artifacts.
- [Fuzz runner](run_three_methods_snapshot.py), [analysis and validation script](analysis_snapshot.py), [fuzz driver](fuzz_driver_snapshot.cpp), and [artifact hashes](artifact_hashes.json).

Raw campaign: `/home/user/ddmin-xml-sbfl/results/tinyxml2_character_ref/three_methods_30s_20261029_164014_650117`. Saved JSON/JSONL records retain their original WSL paths as provenance.
