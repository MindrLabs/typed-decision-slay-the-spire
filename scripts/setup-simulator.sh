#!/usr/bin/env bash
# Builds the simulator the benchmark ran on: daniel-ziegler/sts_lightspeed at 84ab3ead plus the five
# commits in patches/sts_dz, compiled into the Python module `slaythespire` for this project's venv.
# heart1 (a search-bot baseline) also needs `--heart1`, which downloads its 23 MB checkpoint.
set -euo pipefail
cd "$(dirname "$0")/.."

REPO=https://github.com/daniel-ziegler/sts_lightspeed
BASE=84ab3ead9d88c01c4be09a6773fb9a947f57d5ff
DIR=vendor/sts_lightspeed

if [ ! -d "$DIR" ]; then
  git clone --recursive "$REPO" "$DIR"
  git -C "$DIR" checkout -q -b arena/enumerate-actions "$BASE"
  git -C "$DIR" submodule update -q --init --recursive
  git -C "$DIR" -c user.name=arena -c user.email=arena@localhost am -q "$PWD"/patches/sts_dz/*.patch
fi

uv sync
cmake -S "$DIR" -B "$DIR/build" -DCMAKE_BUILD_TYPE=Release -DPYBIND11_FINDPYTHON=ON -DPython_EXECUTABLE="$PWD/.venv/bin/python"
cmake --build "$DIR/build" -j "$(nproc)" --target slaythespire

if [ "${1:-}" = "--heart1" ]; then
  mkdir -p "$DIR/runs"
  curl -sfL -o "$DIR/runs/heart1.pt" "$REPO/releases/latest/download/heart1.pt"
fi
echo "simulator: $DIR/build ($(git -C "$DIR" rev-parse --short HEAD))"
