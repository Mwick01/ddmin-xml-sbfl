#!/usr/bin/env bash
# Build the exploratory TinyXML-2 #997 coverage executable.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
build_dir=build/tinyxml2_character_ref_cov
source_dir=subjects/tinyxml2-character-ref/buggy
mkdir -p "$build_dir"
g++ -O0 -g --coverage -DTINYXML2_DEBUG -I "$source_dir" \
    -c "$source_dir/tinyxml2.cpp" -o "$build_dir/tinyxml2.o"
g++ -O0 -g --coverage -DTINYXML2_DEBUG -I "$source_dir" \
    -c subjects/tinyxml2-character-ref/coverage_driver.cpp -o "$build_dir/driver.o"
g++ --coverage "$build_dir/tinyxml2.o" "$build_dir/driver.o" \
    -o "$build_dir/tinyxml_cov"
printf 'binary=%s\nobject=%s\n' "$build_dir/tinyxml_cov" "$build_dir/tinyxml2.o"
