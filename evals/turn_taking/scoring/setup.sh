#!/usr/bin/env bash
# Idempotent setup of the Full-Duplex-Bench evaluation environment.
#   1. clone upstream (CC BY-NC 4.0, NOT vendored in git) at the pinned SHA
#   2. apply evals/turn_taking/scoring/patches/fdb.patch
#   3. create the eval uv env (evals/turn_taking/scoring/.venv)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TP="$HERE/third_party"
DEST="$TP/Full-Duplex-Bench"
SHA="$(tr -d '[:space:]' < "$HERE/UPSTREAM_COMMIT")"
PATCH="$HERE/patches/fdb.patch"
REPO_URL="${FDB_UPSTREAM_URL:-https://github.com/DanielLin94144/Full-Duplex-Bench.git}"

mkdir -p "$TP"
if [ ! -d "$DEST/.git" ]; then
  echo "[setup] cloning $REPO_URL"
  git clone --quiet "$REPO_URL" "$DEST"
fi

cd "$DEST"
if ! git cat-file -e "$SHA^{commit}" 2>/dev/null; then
  git fetch --quiet origin
fi

if git apply --check --reverse "$PATCH" 2>/dev/null; then
  echo "[setup] patch already applied at $(git rev-parse --short HEAD)"
else
  # Not applied (or tree dirty): reset tracked files to the pinned SHA, then apply.
  git checkout --quiet --force "$SHA"
  git clean -fdq -- v1_v1.5   # drop files added by a previous patch version
  git apply --whitespace=nowarn "$PATCH"
  echo "[setup] checked out ${SHA:0:7} and applied $(basename "$PATCH")"
fi
HEAD_SHA="$(git rev-parse HEAD)"
[ "$HEAD_SHA" = "$SHA" ] || { echo "[setup] ERROR: HEAD $HEAD_SHA != pinned $SHA" >&2; exit 1; }

echo "[setup] syncing eval environment (uv, evals/turn_taking/scoring)"
cd "$HERE"
uv sync --project "$HERE"

echo "[setup] prefetching model weights (Parakeet ~2.4 GB, UTMOSv2 ~0.8 GB)"
uv run --project "$HERE" python "$HERE/prefetch_models.py"

echo "[setup] smoke test: NeMo import"
uv run --project "$HERE" python -c "import nemo.collections.asr, utmosv2, silero_vad; print('imports ok')" 2>&1 | tail -1
echo "[setup] done. Upstream tree: $DEST"
