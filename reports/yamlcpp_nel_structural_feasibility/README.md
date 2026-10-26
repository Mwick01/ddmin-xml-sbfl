# yaml-cpp NEL: structural DDMIN feasibility

This records two exploratory structure-aware DDMIN runs on the historical
yaml-cpp NEL input. Neither run reduced the failure. No structural fuzzing or
structural SBFL analysis was performed for this subject.

## Subject and input

- Bug: the historical `\N` escape decoding fault in
  `subjects/yamlcpp-nel-encoding/buggy/src/exp.cpp:118`.
- Input: `subjects/yamlcpp-nel-encoding/input.yaml`, exactly
  `value: "\N"` followed by a newline (12 characters).
- Oracle: `oracle_yamlcpp_nel`; the original input is **FAIL**.
- Original source revision for the reducer trial: `0a4223f5ac8dcac0fd59e15360fe1efcdff1307b`.

## Results

| Measure | Original structural reducer | Exploratory scalar-content variant |
|---|---:|---:|
| Original / minimal failing size | 12 / 12 characters | 12 / 12 characters |
| Failing-input reduction | 0% | 0% |
| Iterations | 0 | 1 |
| Generated evaluations | 1 | 2 |
| Oracle calls / unique candidates | 1 / 1 | 2 / 2 |
| PASS / FAIL / UNRESOLVED / INVALID YAML | 0 / 1 / 0 / 0 | 1 / 1 / 0 / 0 |

The original reducer had no deletion operation for this input: it handled
items in flow sequences and entries in flow mappings, while this input is a
block mapping with one quoted scalar value. The exploratory variant added one
generic operation that deletes the *contents* of a double-quoted mapping
value while retaining the quotes. It did not special-case or protect `\N`.
That operation produced `value: ""` followed by a newline, which the oracle
classified as **PASS**. DDMIN retains a change as a reduction only when it
remains **FAIL**, so the original input remained the minimum found by both
operation sets.

The 0% figure is relative to those operation sets, not a claim of global
minimality. Removing just the final newline gives an 11-character input
that is valid YAML and still **FAIL**; neither reducer offered that formatting
deletion.

## Experimental scope

This subject is a boundary case for the current structural reducer. The
existing [yaml-cpp NEL formal report](../yamlcpp_nel_formal_300s/README.md)
used seven prepared AFL/AFLsmart seeds (one FAIL and six PASS), rather than
the DDMIN FAIL corpus. Its baseline fault rank was already 1–2, and its
formal runs retained no new failure-inducing input. Those results remain a
separate experiment. No structural seed corpus, formal fuzz run, or
augmented-SBFL result is claimed here.

## Provenance and files

- Original run: `results/yamlcpp_nel_structural_ddmin/20261026_103713_222187`.
- Scalar-content trial:
  `results/yamlcpp_nel_structural_ddmin_scalar_v2/20261026_104416_223899`.
- [original_summary.json](original_summary.json) and
  [scalar_v2_summary.json](scalar_v2_summary.json) are copies of the saved run
  summaries; their absolute paths refer to the original WSL checkout.
- [comparison.csv](comparison.csv) is a compact table derived from those
  summaries.
- [scalar_v2_operation.txt](scalar_v2_operation.txt) records the exact
  exploratory operation added before `return deletions` in
  `collect_deletions`. The report commit does not apply it to the default
  reducer.

The original `results/` directories remain local and are not tracked by Git.
