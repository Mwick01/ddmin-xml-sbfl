#!/usr/bin/env bash
set -euo pipefail

ROOT="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/.." &&
  pwd
)"

REPO="https://github.com/yaml/libyaml.git"

BUGGY_COMMIT="588eabff23ba2292f537872bbea5b64bce1e1a21"
FIXED_COMMIT="840b65c40675e2d06bf40405ad3f12dec7f35923"

BUGGY_DEST="$ROOT/third_party/libyaml-588eabf"
FIXED_DEST="$ROOT/third_party/libyaml-840b65c"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

git clone \
  "$REPO" \
  "$TMP/libyaml"

rm -rf \
  "$BUGGY_DEST" \
  "$FIXED_DEST"

mkdir -p \
  "$BUGGY_DEST" \
  "$FIXED_DEST"

git -C "$TMP/libyaml" \
  archive "$BUGGY_COMMIT" \
  | tar -x -C "$BUGGY_DEST"

git -C "$TMP/libyaml" \
  archive "$FIXED_COMMIT" \
  | tar -x -C "$FIXED_DEST"

echo "Reconstructed:"
echo "  buggy: $BUGGY_DEST"
echo "  fixed: $FIXED_DEST"

echo
echo "Buggy HEAD source:"
git -C "$TMP/libyaml" show -s \
  --format='%H %s' \
  "$BUGGY_COMMIT"

echo
echo "Fixed HEAD source:"
git -C "$TMP/libyaml" show -s \
  --format='%H %s' \
  "$FIXED_COMMIT"
