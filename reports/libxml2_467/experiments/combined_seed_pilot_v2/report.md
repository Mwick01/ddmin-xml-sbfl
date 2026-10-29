# libxml2 #467: combined-seed AFLSmart mixed pilot

Pilot run: `/home/user/ddmin-xml-sbfl/results/libxml2_467/combined_seed_pilot_v2_300s_20261029_124039/runs/rep01/aflsmart-mixed`

One new 300-second AFLSmart mixed run with 25 character-DDMIN seeds and 3 structural-DDMIN seeds; one input was shared, so AFLSmart received 27 unique seed files. The PIT-v2 model and AFL target SHA-256 hashes match the existing character and structural campaigns. The pilot produced Peach chunk files, confirming structure-aware activity.

## Outcome

| Test suite | PASS | FAIL | Unique usable tests | Jaccard fault rank | Ochiai fault rank |
|---|---:|---:|---:|---:|---:|
| Character DDMIN baseline | 232 | 25 | 257 | 7.5 | 7.5 |
| Pooled DDMIN baseline | 246 | 27 | 273 | 9.5 | 9.5 |
| Character-only AFLSmart mixed rep01 + character baseline | 264 | 33 | 297 | 7.5 | 7.5 |
| Structural-only AFLSmart mixed rep01 + structural baseline | 64 | 16 | 80 | 10.5 | 9.5 |
| Character-only AFLSmart mixed rep01 + pooled baseline | 278 | 35 | 313 | 9.5 | 9.5 |
| Combined-seed AFLSmart mixed pilot + character baseline | 302 | 30 | 332 | 9.5 | 9.5 |
| Combined-seed AFLSmart mixed pilot + pooled baseline | 316 | 32 | 348 | 9.5 | 9.5 |

Ranks are tie-aware average ranks for faulty line `parser.c:9596`; lower is better. Test inputs were deduplicated by SHA-256 of their bytes, and duplicate inputs had consistent classification and coverage.

## Generated-input and fuzzer diagnostics

| Run | Generated PASS | Generated FAIL | UNRESOLVED | Usable rate | Executions | Queue paths | Peach chunks |
|---|---:|---:|---:|---:|---:|---:|---:|
| Character-only rep01 | 32 | 8 | 1246 | 3.11% | 372251 | 1311 | 2 |
| Structural-only rep01 | 49 | 13 | 1169 | 5.04% | 322257 | 1235 | 2 |
| Combined-seed pilot | 70 | 5 | 1332 | 5.33% | 452704 | 1434 | 4 |

## Interpretation

The combined-seed pilot generated more usable tests than either historical repetition (75 versus 40 character-only and 62 structural-only), but it did not improve the fault rank. With the character DDMIN baseline, its Jaccard/Ochiai rank was 9.5/9.5 versus 7.5/7.5 for character-only rep01. With the pooled baseline, both the combined-seed pilot and character-only rep01 ranked the fault at 9.5/9.5.

This is one exploratory run. AFLSmart does not expose a matched mutation random seed in these campaigns, so differences from a historical repetition are suggestive rather than a controlled causal estimate. A formal comparison would repeat this combined-seed treatment five times under the same 300-second budget, then compare the distributions with the existing arms. The character and pooled baselines are both shown because the choice of SBFL baseline changes the absolute fault rank.

Seed manifest: `/home/user/ddmin-xml-sbfl/results/libxml2_467/combined_seed_pilot_v2_300s_20261029_124039/seed_manifest.json`. Pilot metadata and raw queue are under `/home/user/ddmin-xml-sbfl/results/libxml2_467/combined_seed_pilot_v2_300s_20261029_124039/runs/rep01/aflsmart-mixed`.
