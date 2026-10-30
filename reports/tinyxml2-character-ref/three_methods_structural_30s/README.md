# TinyXML-2 #997: three 30-second fuzzing methods from structural DDMIN seeds

Run on 2026-10-30 (Asia/Colombo). One fresh trial per method used all eight usable structural-fragment DDMIN candidates as seeds: **1 PASS and 7 FAIL**. Each method's new PASS and FAIL inputs independently augment the original structural baseline. The fault location is buggy `tinyxml2.cpp:550` and the executable-line universe is 1,563 lines.

## SBFL comparison

| Suite | Metric | Combined PASS / FAIL | Fault score | Tied rank interval | Average rank | Average EXAM | Relative rank improvement vs structural baseline |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Structural DDMIN baseline | Jaccard | 1 / 7 | 1.000000 | 1–124 | 62.5 | 3.998720% | +0.00% |
| Structural DDMIN baseline | Ochiai | 1 / 7 | 1.000000 | 1–124 | 62.5 | 3.998720% | +0.00% |
| Plain AFL | Jaccard | 6 / 10 | 1.000000 | 1–92 | 46.5 | 2.975048% | +25.60% |
| Plain AFL | Ochiai | 6 / 10 | 1.000000 | 1–92 | 46.5 | 2.975048% | +25.60% |
| AFLSmart nonstack | Jaccard | 9 / 8 | 1.000000 | 1–81 | 41.0 | 2.623161% | +34.40% |
| AFLSmart nonstack | Ochiai | 9 / 8 | 1.000000 | 1–81 | 41.0 | 2.623161% | +34.40% |
| AFLSmart mixed | Jaccard | 6 / 11 | 1.000000 | 1–81 | 41.0 | 2.623161% | +34.40% |
| AFLSmart mixed | Ochiai | 6 / 11 | 1.000000 | 1–81 | 41.0 | 2.623161% | +34.40% |

Average rank is the midpoint of the target's tie; EXAM is that rank divided by 1,563 executable lines. Lower rank and EXAM are better. The baseline and each augmented suite are scored separately. No generated inputs from another method or earlier character-seed experiment are pooled into a suite.

## Fuzzing yield

| Method | Executions | New PASS | New FAIL | UNRESOLVED | Distinct new PASS / FAIL profiles | Chunk sidecars | Retained smart mutations | AFL stats span (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Plain AFL | 71,929 | 5 | 3 | 184 | 3 / 2 | 0 | 0 | 30 |
| AFLSmart nonstack | 62,174 | 8 | 1 | 144 | 4 / 1 | 2 | 34 | 30 |
| AFLSmart mixed | 46,278 | 5 | 4 | 124 | 4 / 3 | 3 | 2 | 30 |

Counts refer to unique retained queue/crash/hang inputs after excluding original seed entries and byte duplicates. Transient executions not retained by AFL were not later classified. The original exploratory buggy/fixed oracle classified every retained input. Generated PASS and FAIL spectra are equally weighted in SBFL; UNRESOLVED inputs are excluded.

## Shared setup and method definitions

- Each trial uses `timeout -s INT -k 5s 30s`, AFL 2.52b in the same Docker image, `-d`, a 200 MB memory limit and a 1,000 ms per-input timeout. Runs were sequential. Seed validation, classification and coverage collection are outside the 30-second budgets.
- All methods use the exact same eight files and the same preexisting compiled TinyXML fuzz target; the target was not rebuilt between runs. The target, parser source, fuzz driver, oracle, coverage executable/object, original structural baseline records and Docker image are recorded by hash in [campaign.json](campaign.json). AFL's mutation randomness was uncontrolled, so these are one-trial observations.
- [Seed files](seeds/) are byte-identical copies of all unique PASS and FAIL candidates from [structural DDMIN](../structural_ddmin_exploratory/README.md), including the 63-byte minimal FAIL. Their names and SHA-256 values are recorded in the campaign manifest. Oracle labels and target assertion behavior were verified before fuzzing.
- **Plain AFL (`afl`)** uses byte mutation. **AFLSmart nonstack (`aflsmart-nonstack`)** uses `-w peach -g MODEL` for structural mutations without `-h`. **AFLSmart mixed (`aflsmart-mixed`)** adds `-h` to mix normal and structural operators. All modes skip AFL deterministic stages with `-d`.
- The [permissive fragment PIT](tinyxml2_character_ref_fragments.xml) handles the malformed, non-UTF-8 seed family. It is not a full XML grammar. Peach preflight cracked all eight original seeds into nonempty structural chunks and repaired them byte for byte, with validated chunk ranges. See [preflight results](model_preflight/summary.json). The actual smart runs' chunk and retained smart-mutation counts appear above.
- The unchanged GCC/gcov executable collected spectra for the buggy parser. Each candidate reset gcov counters. Assertion coverage uses the existing SIGABRT flushing driver; the original buggy/fixed binaries independently determine labels.

## Tie behavior

- **Plain AFL:** new PASSes covered 32 original top-tie lines; new FAILs missed 0 top-tie lines. The target spectrum is `ef=10, ep=0, nf=0, np=6`. Line lists are in [afl/summary.json](afl/summary.json).
- **AFLSmart nonstack:** new PASSes covered 43 original top-tie lines; new FAILs missed 0 top-tie lines. The target spectrum is `ef=8, ep=0, nf=0, np=9`. Line lists are in [aflsmart-nonstack/summary.json](aflsmart-nonstack/summary.json).
- **AFLSmart mixed:** new PASSes covered 43 original top-tie lines; new FAILs missed 0 top-tie lines. The target spectrum is `ef=11, ep=0, nf=0, np=6`. Line lists are in [aflsmart-mixed/summary.json](aflsmart-mixed/summary.json).

Changes elsewhere in the 1,563-line spectra do not change the reported fault rank unless they separate line 550 from lines currently tied with it. The full [comparison summary](comparison_summary.json) preserves all top-tie line lists and target spectra.

## Validation and limits

All **26 usable generated spectra** reproduced every line execution count on a second coverage collection. Candidate hashes, original labels, fault-assertion reproduction for FAILs, each suite's executable-line set, both SBFL formulas, rank bounds, and EXAM values were checked independently. The original structural baseline was recomputed and matched its saved summary exactly.

All 8 generated FAILs were rejected by the fixed parser (exit 2); no fixed-PASS/buggy-FAIL candidate was found. This subject remains exploratory under the malformed-input assertion oracle. The original structural DDMIN suite contained only one PASS candidate, and the test populations are small. One randomized trial per method cannot establish a reliable method ordering.

## Evidence

- [Metric comparison](comparison.csv), [campaign configuration and hashes](campaign.json), [comparison summary](comparison_summary.json), [baseline coverage](baseline_coverage.jsonl), and [baseline SBFL](baseline_sbfl_summary.json).
- [Plain AFL summary](afl/summary.json), [nonstack summary](aflsmart-nonstack/summary.json), and [mixed summary](aflsmart-mixed/summary.json).
- Each method directory holds classifications, fuzzer logs and stats, generated and augmented coverage, a second coverage collection, full line spectra, both rankings, per-candidate validation and a ZIP of retained inputs and chunk files.
- [Fuzz runner snapshot](run_three_methods_snapshot.py), [analysis snapshot](analysis_snapshot.py), [fuzz driver](fuzz_driver_snapshot.cpp), [PIT model](tinyxml2_character_ref_fragments.xml), [seed corpus](seeds/), [Peach preflight](model_preflight/summary.json), and [artifact hashes](artifact_hashes.json).

Raw campaign: `/home/user/ddmin-xml-sbfl/results/tinyxml2_character_ref/three_methods_structural_30s_20261030_101751_068716`. Saved coverage records retain WSL absolute paths as provenance.
