"""Text for engine entities, from the spire-archive STS1 dump that scripts/fetch-game-text.sh puts in data/sts1."""
from __future__ import annotations

import functools
import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "sts1"


def norm(name: str) -> str:
    """Engine enum names and dataset ids/names collapse to the same key (e.g. PERFECTED_STRIKE / "Perfected Strike")."""
    return re.sub(r"[^A-Z0-9]", "", name.upper())


@functools.cache
def _table(kind: str) -> dict[str, dict]:
    path = DATA_DIR / f"{kind}.json"
    if not path.exists():
        raise SystemExit(f"{path} is missing: run scripts/fetch-game-text.sh")
    table: dict[str, dict] = {}
    for item in json.loads(path.read_text()):
        for key in (item.get("id"), item.get("name")):
            if key:
                table.setdefault(norm(key), item)
    return table


# Engine enum names whose dataset id differs beyond punctuation.
_ALIASES = {
    "STRIKERED": "STRIKER", "DEFENDRED": "DEFENDR",
    "STRIKEGREEN": "STRIKEG", "DEFENDGREEN": "DEFENDG",
    "STRIKEBLUE": "STRIKEB", "DEFENDBLUE": "DEFENDB",
    "STRIKEPURPLE": "STRIKEP", "DEFENDPURPLE": "DEFENDP",
    "HYPNOTIZINGCOLOREDMUSHROOMS": "MUSHROOMS",
}


def lookup(kind: str, engine_name: str) -> dict | None:
    key = norm(engine_name)
    return _table(kind).get(_ALIASES.get(key, key))
