#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

exec "$ROOT/build/libxml2_467_cov/xmllint" \
  --nonet \
  --dtdattr \
  --format \
  "$1"
