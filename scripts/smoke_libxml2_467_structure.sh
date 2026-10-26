#!/usr/bin/env bash
set -euo pipefail

# Install this script in the repository's scripts/ directory.
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$PROJECT_ROOT"

VALIDATE_ONLY=0
if [[ $# -eq 1 && "$1" == "--validate-only" ]]; then
  VALIDATE_ONLY=1
elif [[ $# -ne 0 ]]; then
  printf 'Usage: bash %s [--validate-only]\n' "$0" >&2
  exit 2
fi

PIT=aflsmart/libxml2_467.xml
SEEDS=aflsmart/libxml2_467_structure_seeds
TARGET=build/aflsmart/libxml2_467/libxml2_467_buggy
OUT="results/libxml2_467/smoke_peach_mixed_60s_$(date +%Y%m%d_%H%M%S)"

test -s "$PIT" || { printf 'Missing PIT: %s\n' "$PIT" >&2; exit 1; }
test -d "$SEEDS" || { printf 'Missing seed directory: %s\n' "$SEEDS" >&2; exit 1; }
if [[ "$VALIDATE_ONLY" == 0 ]]; then
  test -x "$TARGET" || { printf 'Missing executable: %s\n' "$TARGET" >&2; exit 1; }
  test ! -e "$OUT" || { printf 'Results already exist: %s\n' "$OUT" >&2; exit 1; }
  mkdir -p "$(dirname "$OUT")"
fi

docker run --rm -i --network none \
  --user "$(id -u):$(id -g)" \
  -e HOME=/tmp \
  -e TMPDIR=/tmp \
  -e AFL_PATH=/aflsmart \
  -e AFL_SKIP_CPUFREQ=1 \
  -e AFL_NO_AFFINITY=1 \
  -e AFL_NO_UI=1 \
  -e "VALIDATE_ONLY=$VALIDATE_ONLY" \
  -e "AFL_OUT=/work/$OUT" \
  -v "$PWD:/work" \
  -w /work \
  ddmin-aflsmart bash -s <<'CONTAINER'
set -euo pipefail
export PATH="/aflsmart/peach-3.0.202-source/output/linux_x86_64_release/bin:/aflsmart:$PATH"
PIT=/work/aflsmart/libxml2_467.xml
SEEDS=/work/aflsmart/libxml2_467_structure_seeds
TARGET=/work/build/aflsmart/libxml2_467/libxml2_467_buggy

# Check actual input cracking, not just whether the PIT is valid XML.
# Peach -t reports unsupported XSD validation on this Mono runtime.
check_dir="$(mktemp -d /tmp/libxml2_467_pit.XXXXXXXX)"
trap 'rm -rf -- "$check_dir"' EXIT
checked=0
while IFS= read -r -d '' seed; do
  repaired="$check_dir/repaired"
  rm -f -- "$repaired" "$repaired.chunks"
  if ! (
    cd "$check_dir"
    timeout -s TERM -k 5s 20s peach -1 \
      "-inputFilePath=$seed" \
      "-outputFilePath=$repaired" \
      "$PIT" > "$check_dir/peach.log" 2>&1
  ); then
    printf 'Peach failed for: %s\n' "$seed" >&2
    cat "$check_dir/peach.log" >&2
    exit 1
  fi
  cmp -s "$seed" "$repaired" || {
    printf 'PIT did not reproduce this seed exactly: %s\n' "$seed" >&2
    cat "$check_dir/peach.log" >&2
    exit 1
  }
  test -s "$repaired.chunks" || {
    printf 'No chunk boundaries for: %s\n' "$seed" >&2
    exit 1
  }
  awk -F, -v bytes="$(wc -c < "$seed")" '
    NF != 4 || $1 !~ /^[0-9]+$/ || $2 !~ /^[0-9]+$/ { bad=1 }
    $1 < 0 || $2 < $1 || $2 >= bytes { bad=1 }
    END { exit (bad || NR < 2) }
  ' "$repaired.chunks" || {
    printf 'Invalid chunk boundaries for: %s\n' "$seed" >&2
    exit 1
  }
  grep -q '~NamespaceDefault~NamespaceUri,' "$repaired.chunks" || {
    printf 'Missing DTD namespace chunks for: %s\n' "$seed" >&2
    exit 1
  }
  checked=$((checked + 1))
  printf 'PIT round-trip OK: %s\n' "$seed"
done < <(find "$SEEDS" -mindepth 1 -maxdepth 1 -type f -print0)

test "$checked" -gt 0 || { printf 'Seed directory is empty\n' >&2; exit 1; }
printf 'Validated %s seeds with Peach.\n' "$checked"
if [[ "$VALIDATE_ONLY" == 1 ]]; then
  exit 0
fi

status=0
timeout -s INT 60s /aflsmart/afl-fuzz \
  -m 200 -d \
  -i "$SEEDS" \
  -o "$AFL_OUT" \
  -w peach \
  -g "$PIT" \
  -h \
  -- "$TARGET" @@ || status=$?
if [[ "$status" != 0 && "$status" != 124 ]]; then
  printf 'Fuzzer exited unexpectedly: %s\n' "$status" >&2
  exit "$status"
fi
CONTAINER

if [[ "$VALIDATE_ONLY" == 1 ]]; then
  printf 'PIT validation complete.\n'
  exit 0
fi
test -s "$OUT/fuzzer_stats"
test -d "$OUT/queue"
test -d "$OUT/chunks"
chunk_file="$(find "$OUT/chunks" -maxdepth 1 -type f -name '*.chunks' -size +0c -print -quit)"
test -n "$chunk_file" || {
  printf 'No nonempty Peach chunk files; structural smoke failed: %s\n' "$OUT" >&2
  exit 1
}
printf 'Saved Peach mixed structural smoke run: %s\n' "$OUT"
