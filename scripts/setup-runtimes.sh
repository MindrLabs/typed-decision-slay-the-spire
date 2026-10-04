#!/usr/bin/env bash
# Creates the model-compose runtimes under .runtime/ with the packages the published runs used
# (runtimes/nimble.txt, runtimes/laya.txt), before `model-compose up` would install the newest ones.
# Linux with an NVIDIA GPU only; elsewhere skip it and let model-compose install its own.
#
# Without it Nimble gets a newer torch and triton and no flash-linear-attention: it still plays, but its
# scores move in the third decimal place, near-tie votes flip, and a seed stops replaying the published
# game. Laya gets a newer `laya` package. With it, seed 1 replayed every published decision of both.
set -euo pipefail
cd "$(dirname "$0")/.."

for runtime in nimble nimble-ft nimble-ft4 laya-english laya-typed laya-multilingual laya-english-ft laya-english-ft4 \
               laya-english-rec laya-typed-rec laya-multilingual-rec laya-english-ft-rec; do
  lock=runtimes/${runtime%%-*}.txt
  [ -d ".runtime/$runtime" ] || uv venv -q -p 3.12 ".runtime/$runtime"
  uv pip install -q --python ".runtime/$runtime/bin/python" --index-url https://pypi.org/simple -r "$lock"
  echo ".runtime/$runtime: $lock"
done
