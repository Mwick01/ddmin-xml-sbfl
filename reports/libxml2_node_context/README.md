# libxml2 #672: namespace context experiments

Character DDMIN produces both PASS and FAIL cases when the namespace declaration is part of the mutable input. The original fragment-only screen and the namespace-free control are preserved as separate configurations.

| Input model | PASS | FAIL | UNRESOLVED | Status |
|---|---:|---:|---:|---|
| Original fragment-only screen | 0 | 18 | 6 | Historical 24-fragment screen; rejected for this input model |
| Character DDMIN, namespace fixed in driver | 0 | 5 | 1 | Reduced 18 characters to 1 |
| Character DDMIN, namespace removed from driver | 1 | 0 | 0 | Initial seed is PASS; reduction stops |
| Character DDMIN, namespace and fragment mutable | 4 | 7 | 149 | Reduced 51 characters to 26 |

The first row is the original September screening corpus. The other rows were recorded on 2026-10-31 (Asia/Colombo). They have different input domains and candidate sets. The namespace-free replay, fresh boundary screen and supplementary character-deletion screen are described separately in the control report.

The mutable seed is:

```xml
<case xmlns:p="urn:probe"><span>probe</span></case>
```

These actual DDMIN candidates form a matching-fragment pair:

```xml
<!-- FAIL: namespace declaration attached to the HTML context -->
<case xmlns:p="u">></case>

<!-- PASS: colon deletion makes this an ordinary attribute -->
<case xmlnsp="u">></case>
```

The shared Python XML decoder takes root namespace declarations as context configuration and serializes child nodes as the fragment. Root names and ordinary root attributes are inert envelope metadata. The driver constructs the same fixed HTML document, applies input-derived declarations with `xmlNewNs`, and calls `xmlParseInNodeContext`. Both library versions receive the same decoded setup.

FAIL requires v2.12.5 acceptance and v2.12.4 SIGSEGV. PASS requires both probes to accept and print the same result/list summary. Other outcomes, including malformed envelopes, are UNRESOLVED. Of the mutable run's 149 unresolved candidates, 148 failed envelope decoding and one reached the probes. The oracle does not compare fully serialized output trees. Coverage, SBFL ranks and fuzzing have not been evaluated for this expanded input model.

## Recorded evidence

- [Original suitability screen](../libxml2_node_context_suitability/README.md).
- [Namespace-removal control report](../libxml2_node_context_namespace_removed/README.md).
- [Mutable-namespace character-DDMIN report](../libxml2_node_context_mutable_namespace/README.md).
- [All 160 unique mutable candidates](../libxml2_node_context_mutable_namespace/runs/20261031_100744/candidates.csv).
- [Decoded inputs and process results](../libxml2_node_context_mutable_namespace/runs/20261031_100744/oracle_results.jsonl).
- [Recorded validation](../libxml2_node_context_mutable_namespace/validation.json).
- [Repository launcher reproduction checks](reproduction_validation.json).

The two new report directories are exact snapshots of the original workspace artifacts, excluding Python caches. Their recorded absolute paths, build manifests and original scripts document that workspace. Use the repository launcher below for new runs; it writes into ignored `build/` and `results/` directories and leaves these snapshots intact. `SHA256SUMS.txt` in each snapshot verifies the saved files relative to that directory. No source trees, binaries or coverage artifacts are included.

## Reproduce from the repository root

Requirements: Linux or WSL, Python 3.12+, GCC, CMake, Make, Asia/Colombo timezone data, and a local libxml2 Git checkout containing v2.12.4 and v2.12.5. The exact expected commits are checked when building libraries. The launcher uses the byte-for-byte archived character reducer and verifies it matches this branch's `scripts/ddmin.py`.

```bash
# If no local source checkout is available:
git clone --filter=blob:none --no-checkout https://github.com/GNOME/libxml2.git temporary/libxml2-node-context-source

python3 scripts/run_libxml2_node_context.py --mode mutable \
  --source-repo temporary/libxml2-node-context-source
```

On the original WSL machine, the existing source repository is `temporary/libxml2-467-source`, which is also the launcher's default. No checkout changes are made inside that source repository. The launcher builds v2.12.4 and v2.12.5 with the same CMake options and records library/probe hashes for every new run.

```bash
python3 scripts/run_libxml2_node_context.py --mode mutable
python3 scripts/run_libxml2_node_context.py --mode original
python3 scripts/run_libxml2_node_context.py --mode namespace-removed
```

The namespace-removed mode treats the archived reducer's initial-PASS refusal as the expected result and reports `stopped_initial_input_PASS`. It does not claim a completed minimization. Each mode creates a fresh directory under `results/libxml2_node_context/`.

Existing libraries can be reused with `--library-root PATH`, where PATH contains `src-2.12.4/include`, `src-2.12.5/include` and the corresponding `build-VERSION/libxml2.a` and generated headers. The version headers and library hashes are checked/recorded; original artifact hashes remain in the archived manifests. Builds and modes should run sequentially because the probe binary paths are shared.
