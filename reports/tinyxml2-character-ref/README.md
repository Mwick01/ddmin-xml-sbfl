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
   NOT EVALUATED

   Rejected before DDMIN because the required fixed-version
   PASS boundary is absent.

7. Coverage / determinism / PIT:
   NOT EVALUATED

   These stages are unnecessary once the candidate fails the
   PASS/FAIL boundary screening criterion.

Decision:
   REJECT candidate from the formal DDMIN/SBFL subject set.

Reason:
   No consistent buggy FAIL -> fixed PASS boundary under the
   experimental oracle.

The candidate is retained as part of the auditable historical-bug
screening process.
