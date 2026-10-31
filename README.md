# XML DDMIN-SBFL

An experimental implementation of failure-inducing input minimization and
spectrum-based fault localization for XML-processing programs.

## Current pipeline

```text
XML input
    -> PASS / FAIL / UNRESOLVED oracle
    -> DDMIN test generation
    -> statement coverage
    -> SBFL suspiciousness ranking
## Node-context experiment

- [libxml2 #672: namespace context experiments](reports/libxml2_node_context/README.md): original screening, namespace-free control, mutable-namespace character DDMIN and reproduction commands.
