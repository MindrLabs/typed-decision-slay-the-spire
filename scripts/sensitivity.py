"""How much the software environment moves the results: seeds 1-50 played again with the packages
model-compose installs by itself (results/sensitivity, environment.txt) against the published run.

    uv run python scripts/sensitivity.py

Floors are compared per seed as in the pre-registered analysis. A game counts as identical when every
model decision has the same kind, option count, pick and votes: the simulator is deterministic, so the
same picks replay the same game. Not pre-registered (exploratory).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import stats as S

ROOT = Path(__file__).resolve().parents[1] / "results"
SEEDS = list(range(1, 51))


def rows(run: str, player: str) -> dict[int, list]:
    f = ROOT / run / player / "decisions.jsonl"
    return {r["seed"]: r["decisions"] for r in map(json.loads, f.read_text().splitlines())}


def first_difference(a: list, b: list) -> int | None:
    """1-based index of the first decision that differs, None when the games are identical."""
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i + 1
    return None if len(a) == len(b) else min(len(a), len(b)) + 1


def main() -> None:
    print("| Model | Published | Default packages | Difference [95% CI] | Wilcoxon p | Same floor | Identical games | First different decision, median |")
    print("|---|---|---|---|---|---|---|---|")
    pub, new = {}, {}
    for p in S.MODELS:
        pub[p], new[p] = S.games(ROOT / "final", p), S.games(ROOT / "sensitivity", p)
        d = [new[p][s]["floor"] - pub[p][s]["floor"] for s in SEEDS]
        lo, hi = S.boot_ci(d)
        pv, _ = S.wilcoxon(d)
        a, b = rows("final", p), rows("sensitivity", p)
        firsts = sorted(f for s in SEEDS if (f := first_difference(a[s], b[s])) is not None)
        median = firsts[len(firsts) // 2] if firsts else "-"
        print(f"| {S.NAMES[p]} | {np.mean([pub[p][s]['floor'] for s in SEEDS]):.2f} | "
              f"{np.mean([new[p][s]['floor'] for s in SEEDS]):.2f} | {np.mean(d):+.2f} {S.fmt_ci(lo, hi, 2)} | "
              f"{S.fmt_p(pv)} | {sum(x == 0 for x in d)} / 50 | {50 - len(firsts)} / 50 | {median} |")
    print()
    for name, g in (("Published", pub), ("Default packages", new)):
        means = {p: np.mean([g[p][s]["floor"] for s in SEEDS]) for p in S.MODELS}
        gaps = ", ".join(
            f"{S.NAMES[lay]} {np.mean(d := [g['nimble'][s]['floor'] - g[lay][s]['floor'] for s in SEEDS]):+.2f} "
            f"{S.fmt_ci(*S.boot_ci(d), 2)}" for lay in S.LAYAS)
        print(f"- {name}: order {' > '.join(S.NAMES[p] for p in sorted(S.MODELS, key=lambda p: -means[p]))}; "
              f"Nimble-9B minus {gaps}")


if __name__ == "__main__":
    main()
