Candidate: PugiXML #39
Project: pugixml
Historical issue: #39
Buggy release: v1.5
Fixed release: v1.6

SCREENING RESULT: REJECTED

1. Buggy/fixed revisions known:
   PASS

   Buggy:
     v1.5
     commit ff16dbd

   Fixed:
     v1.6
     commit 9b8553b

2. Historical reproducer available:
   PASS

   Reproducer size:
     62 input bytes

3. Bug reproduction:
   PASS

   Buggy v1.5 under AddressSanitizer:
     heap-buffer-overflow
     pugixml.cpp:2389
     parse_doctype_group()
     exit code 134

4. Fixed-version behavior:
   Fixed v1.6 does not crash, but rejects the input:

     PARSE_ERROR status=9 offset=61
     description="Error parsing document type declaration"
     exit code 2

5. PASS/FAIL boundary:
   FAIL

   The historical triggering input is malformed XML.
   The buggy version crashes while processing it, whereas the fixed
   version safely rejects it.

   Therefore the fixed parser does not classify the historical input
   as a valid PASS input.

6. DDMIN suitability:
   NOT EVALUATED

   Rejected before DDMIN because the required fixed-version validity
   boundary is absent.

Decision:
   REJECT candidate from the formal DDMIN/SBFL subject set.

Reason:
   No consistent FAIL -> PASS buggy/fixed boundary under the existing
   experimental oracle.

The candidate is retained in the screening record as evidence of the
subject-selection procedure.
