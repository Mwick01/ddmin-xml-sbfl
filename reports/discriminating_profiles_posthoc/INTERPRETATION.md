# Post-hoc discriminating-spectrum analysis

This analysis was defined after inspecting the formal experiment
results and is therefore explanatory rather than confirmatory.

## Main observation

Raw numbers of generated tests or coverage profiles do not by
themselves explain SBFL improvement.

Instead, localization changes are associated with whether generated
spectra discriminate the known fault from statements tied with it in
the DDMIN-only baseline.

## libyaml

Helpful discrimination is PASS-driven.

Generated passing tests can cover baseline-tied competing statements
without covering the representative fault at parser.c:1062.

Across the formal repetitions:

- helpful discrimination has positive net direction;
- harmful discrimination is absent;
- runs with no discriminating spectra retain the original 17-way tie;
- runs with helpful discrimination move baseline competitors below
  the fault.

Thus the principal tie-breaking mechanism on libyaml is passing-spectrum
discrimination.

## Expat

Helpful discrimination is FAIL-driven.

Generated failing tests can cover the representative fault while
excluding some statements tied with it in the DDMIN baseline.

AFLSmart nonstack produces substantially more helpful failing-spectrum
discrimination than AFL or AFLSmart mixed and has the least-negative
net discriminating density.

However, harmful discrimination remains present and exceeds helpful
discrimination overall. Consequently, nonstack is descriptively better
than the other fuzzing configurations but does not consistently improve
the Jaccard rank relative to the DDMIN-only baseline. Ochiai shows a
modest mean improvement.

Thus the useful mechanism on Expat is failing-spectrum discrimination,
but its benefit can be diluted by spectra that discriminate in the
opposite direction.

## Cross-subject implication

The two subjects demonstrate different useful spectrum directions:

- libyaml: helpful PASS spectra;
- Expat: helpful FAIL spectra.

Therefore the localization value of fuzz-generated tests depends on the
direction of coverage discrimination relative to the fault and its
baseline competitors, rather than merely the number of generated tests,
valid tests, paths, or distinct coverage profiles.

These conclusions are based on a post-hoc explanatory analysis and
should not be presented as preregistered confirmatory evidence.
