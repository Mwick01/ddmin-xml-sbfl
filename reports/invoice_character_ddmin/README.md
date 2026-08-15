# Character-level DDMIN SBFL Baseline

## Subject

Invoice XML-processing program containing a known arithmetic fault in the
special-item calculation.

## Pipeline

1. Begin with one failure-inducing XML input.
2. Apply character-level DDMIN.
3. Classify candidates as PASS, FAIL, or UNRESOLVED.
4. Exclude unresolved candidates from SBFL.
5. Collect independent statement coverage from the buggy program.
6. Calculate Jaccard and Ochiai suspiciousness.
7. Evaluate the ranking using the known faulty source line.

## DDMIN granularity

Characters in the UTF-8 XML string.

## Oracle

- PASS: fixed and buggy outputs are equal.
- FAIL: fixed and buggy outputs differ.
- UNRESOLVED: invalid XML, timeout, or abnormal execution.

## Coverage

GCC gcov line coverage from the buggy version only. Coverage counters are
reset before every test execution.

## Evaluation metrics

- Fault rank
- EXAM score
- Inspect@1
- Inspect@3
- Inspect@5
- Inspect@10