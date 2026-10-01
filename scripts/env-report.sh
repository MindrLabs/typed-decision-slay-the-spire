#!/usr/bin/env bash
# Prints what a rerun has to report next to its results: the GPU, driver and CUDA, and the packages
# that change the models' numbers in each runtime under .runtime/. Run it after setup-runtimes.sh.
set -euo pipefail
cd "$(dirname "$0")/.."

nvidia-smi --query-gpu=name,driver_version --format=csv,noheader 2>/dev/null | sed 's/^/gpu, driver: /' || echo "gpu: nvidia-smi not found"
for runtime in .runtime/*/; do
  [ -x "$runtime/bin/python" ] || continue
  "$runtime/bin/python" - "$runtime" <<'PY'
import importlib.metadata as md
import sys

def version(name):
    try:
        return md.version(name)
    except md.PackageNotFoundError:
        return "-"

line = f"{sys.argv[1].rstrip('/')}: " + ", ".join(
    f"{p} {version(p)}" for p in ("torch", "triton", "flash-linear-attention", "laya", "transformers"))
try:
    import torch
    if torch.cuda.is_available():
        props = torch.cuda.get_device_properties(0)
        line += f", cuda {torch.version.cuda}, {props.name}, {props.multi_processor_count} SMs"
except ImportError:
    pass
print(line)
PY
done
