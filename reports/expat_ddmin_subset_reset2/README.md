# Expat DDMIN subset-reset2 ablation

Variant:
- In the accepted failing-subset branch, changed:
  `granularity = max(granularity - 1, 2)`
  to:
  `granularity = 2`

Subject:
- Expat 2.2.5 / 2.2.6 resume regression
- Input: `subjects/expat_resume/inputs/failing_rich.xml`

Result:
- Original size: 52 characters
- Minimal size: 23 characters
- Reduction: 55.77%
- Iterations: 21
- Oracle attempts: 552
- Unique candidates: 216
- PASS: 6
- FAIL: 16
- UNRESOLVED: 194
- Minimal failure: `<?l?><!----><doc a=""/>`

Observation:
The reduction trace accepted only failing complements and did not accept
a failing subset. Therefore, the modified failing-subset granularity
assignment was not exercised on this input.

Conclusion:
This run does not provide evidence for or against resetting granularity
to 2 after accepting a failing subset. The result is identical to the
original rich Expat DDMIN baseline.
