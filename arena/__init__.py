"""Slay the Spire runs where a typed-decision model makes every choice."""
import sys
from pathlib import Path

# scripts/setup-simulator.sh builds the `slaythespire` module here; silverbot (heart1) sits in the checkout.
SIMULATOR = Path(__file__).resolve().parent.parent / "vendor" / "sts_lightspeed"
sys.path[:0] = [str(SIMULATOR / "build"), str(SIMULATOR)]
