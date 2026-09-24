# Candidate: Expat #566
Project: Expat
Buggy release: 2.4.5
Fixed release: 2.4.6
Historical fix: merge 9288cd54

### SCREENING RESULT: REJECTED

1. Buggy/fixed revisions known:
   PASS

   Buggy:
     R_2_4_5
     commit 97a48405

   Fixed:
     R_2_4_6
     commit 65a21f2b

2. Historical regression reproduced:
   PASS

   Input:
     <!ELEMENT junk ((bar|foo|xyz+), zebra*)>

   Buggy 2.4.5 produces an incorrect XML_Content model.
   Fixed 2.4.6 produces the correct XML_Content model.

3. PASS/FAIL boundary:
   PASS

   Historical input:
     buggy -> semantic failure
     fixed -> correct model

4. Determinism:
   PASS

   20/20 buggy executions:
     MODEL_BAD / semantic failure

   20/20 fixed executions:
     MODEL_OK

5. Fault coverage:
   PASS

   Conservative patch-derived faulty lines in buggy xmlparse.c:
     7399
     7400
     7404
     7408
     7430
     7435
     7438

   All seven fault lines were executed by the failing input.

6. DDMIN usability:
   FAIL

   Character-level DDMIN results:

     Original size:        67
     Minimal size:         41
     Reduction:            38.81%
     Oracle attempts:      966
     Unique candidates:    441
     PASS candidates:      0
     FAIL candidates:      14
     UNRESOLVED candidates: 427

   Approximately 96.8% of unique candidates were UNRESOLVED.

   Although DDMIN successfully reduced the failure-inducing input,
   it generated no PASS candidates.

   Therefore the resulting spectrum cannot support the formal
   PASS/FAIL SBFL experiment.

7. PIT feasibility:
   NOT EVALUATED

   Screening stopped after failure of the DDMIN-usability criterion.

### Decision:
   REJECT candidate from the formal subject set.

### Reason:
   No usable DDMIN PASS spectrum was generated. The candidate is
   retained as evidence of structural invalidity during character-level
   reduction.

### Additional DDMIN robustness check:
  The experiment was repeated using the historical
  experiment/ddmin-subset-reset2 implementation, which resets
  granularity to 2 after accepting a failing subset.

  Result:
    Minimal size:          41
    Reduction:          38.81%
    Oracle attempts:       966
    Unique candidates:     441
    PASS candidates:         0
    FAIL candidates:        14
    UNRESOLVED candidates: 427

  The results were identical to the current DDMIN implementation.

  Inspection showed that all successful reductions for this subject
  were failing complements; no failing subset was accepted.
  Therefore the subset-reset modification was never exercised on
  this reduction path.

  Conclusion:
    The absence of PASS candidates is a property of this subject /
    character-level reduction trajectory, rather than an artifact of
    the subset granularity-reset implementation.