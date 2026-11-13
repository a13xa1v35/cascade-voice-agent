#!/usr/bin/env bash
# Maintainer helper: regenerate patches/fdb.patch from the working tree of the
# patched upstream clone (evals/turn_taking/scoring/third_party/Full-Duplex-Bench).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE/third_party/Full-Duplex-Bench"
git add -N v1_v1.5
git diff -- v1_v1.5 > "$HERE/patches/fdb.patch"
git reset -q
echo "wrote $HERE/patches/fdb.patch ($(grep -c '^diff' "$HERE/patches/fdb.patch") files)"
