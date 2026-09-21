# libxml2 xmlParseInNodeContext suitability probe

## Historical bug

Buggy:
- libxml2 v2.12.4

Fixed:
- libxml2 v2.12.5

Upstream fix:
- 8b9b972aaa4970f3983085ad59930614c5f6aa57
- `parser: Fix crash in xmlParseInNodeContext with HTML documents`
- Fixes libxml2 issue #672.

The upstream fix prevents namespace-stack initialization when
xmlParseInNodeContext operates on an HTML parser context.

## Experimental trigger

The probe creates an HTML document, manually attaches a namespace to the
root element, and parses a mutable fragment using xmlParseInNodeContext.

## Boundary screen

24 fragment candidates were tested.

- PASS: 0
- FAIL: 18
- UNRESOLVED: 6

Examples:

| Fragment | v2.12.4 | v2.12.5 | Classification |
|---|---|---|---|
| `""` | result=2 | result=2 | UNRESOLVED |
| `" "` | SIGSEGV | result=0 | FAIL |
| `"x"` | SIGSEGV | result=0 | FAIL |
| `"&amp;"` | SIGSEGV | result=0 | FAIL |
| `"<!--x-->"` | SIGSEGV | result=0 | FAIL |
| `"<?p x?>"` | SIGSEGV | result=0 | FAIL |
| `"<b/>"` | SIGSEGV | result=0 | FAIL |
| `"<b>x</b>"` | SIGSEGV | result=0 | FAIL |
| `"<div><em>x</em></div>"` | SIGSEGV | result=0 | FAIL |

The remaining tested fixed-invalid fragments were classified UNRESOLVED.

## Suitability decision

Rejected as a formal DDMIN/SBFL subject.

Every tested fragment accepted by the fixed implementation triggered the
buggy crash. Therefore the mutable fragment does not provide a useful
natural PASS/FAIL boundary under the upstream triggering context.

Using this subject would likely produce failing tests for essentially all
usable inputs and would provide little useful passing-spectrum information
for SBFL.

The bug itself is reproducible, but it is unsuitable for the current
DDMIN -> fuzzing -> SBFL experiment design.
