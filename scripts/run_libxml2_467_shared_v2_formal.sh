#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$PROJECT_ROOT"

case "${1:-character}" in
  character)
    CORPUS=character
    BASE=results/libxml2_467_ddmin/20260926_224640_738508
    SEEDS=aflsmart/libxml2_467_character_seeds
    ;;
  structure)
    CORPUS=structure
    BASE=results/libxml2_467_structural_ddmin/20261026_123127_300282
    SEEDS=aflsmart/libxml2_467_structure_seeds
    ;;
  *)
    printf 'Usage: bash %s [character|structure]\n' "$0" >&2
    exit 2
    ;;
esac

OUT="results/libxml2_467/formal_${CORPUS}_shared_v2_300s_$(date +%Y%m%d_%H%M%S)"
test -s "$BASE/coverage/coverage.jsonl" || {
  printf 'Missing baseline coverage: %s\n' "$BASE" >&2
  exit 1
}
test -d "$SEEDS" || { printf 'Missing seeds: %s\n' "$SEEDS" >&2; exit 1; }
test -s aflsmart/libxml2_467_shared_v2.xml || { printf 'Missing shared v2 PIT\n' >&2; exit 1; }
test ! -e "$OUT" || { printf 'Output already exists: %s\n' "$OUT" >&2; exit 1; }

# A Bash array avoids dependence on pasted line-continuation backslashes.
args=(
  --subject libxml2_467
  --baseline-run "$BASE"
  --seed-directory "$SEEDS"
  --duration 300
  --repetitions 5
  --modes afl aflsmart-mixed aflsmart-nonstack
  --results-root "$OUT"
  --order-seed 20260920
)
printf 'Formal results: %s\n' "$OUT"
# Select the versioned PIT in this process. The runner file is not edited;
# its metadata records the selected PIT path and SHA256 normally.
python3 - "${args[@]}" <<'PY'
from dataclasses import replace
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path.cwd() / 'scripts'))
import run_fuzz_experiment_expat as runner

runner.SUBJECTS['libxml2_467'] = replace(
    runner.SUBJECTS['libxml2_467'],
    pit_file=(Path.cwd() / 'aflsmart/libxml2_467_shared_v2.xml').resolve(),
)
sys.argv[0] = str(runner.__file__)
runner.main()
PY
printf 'Completed formal batch: %s\n' "$OUT"
