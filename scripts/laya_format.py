"""Laya in its maker's documented format against the registered runs (exploratory,
docs/plan-laya-format.md).

    uv run python scripts/laya_format.py

Reads results/laya-format (the -rec players) next to results/final and results/round2. Floors are
compared per seed as in the registered analysis; nothing here is corrected for multiple comparisons.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

import stats as S

ROOT = Path(__file__).resolve().parents[1] / "results"
FORMAT = ROOT / "laya-format"
PAIRS = [  # (documented-format player, registered player, registered run)
    ("laya-english-rec", "laya-english", "final"),
    ("laya-typed-rec", "laya-typed", "final"),
    ("laya-multilingual-rec", "laya-multilingual", "final"),
    ("laya-english-ft-rec", "laya-english-ft", "round2"),
]
NAMES = {**S.NAMES, "laya-english-ft": "Laya english, fine-tuned", "nimble-ft": "Nimble-9B, fine-tuned"}


def agreement(run: Path, player: str, seeds: list[int]) -> str:
    """Share of decisions where every order (registered) or every rotation (documented) picked the same option."""
    voted = [d for d in S.decisions(run, player, seeds) if d["votes"] and len(d["votes"]) > 1]
    return f"{100 * sum(len(set(d['votes'])) == 1 for d in voted) / len(voted):.1f}%" if voted else "-"


def paired(a: dict, b: dict, seeds: list[int]) -> str:
    d = [a[s]["floor"] - b[s]["floor"] for s in seeds]
    p, _ = S.wilcoxon(d)
    hi, same, lo = sum(x > 0 for x in d), sum(x == 0 for x in d), sum(x < 0 for x in d)
    return f"{np.mean(d):+.2f} {S.fmt_ci(*S.boot_ci(d), 2)} | {hi} / {same} / {lo} | {S.fmt_p(p)}"


def main() -> None:
    print("| Model | Registered format | Documented format | Difference [95% CI] | Higher / same / lower | Wilcoxon p | "
          "Act 1 cleared, registered → documented | Same pick in every order → every rotation |")
    print("|---|---|---|---|---|---|---|---|")
    games = {}
    for rec, reg, run in PAIRS:
        a, b = S.games(FORMAT, rec), S.games(ROOT / run, reg)
        if not a:
            continue
        seeds = sorted(set(a) & set(b))
        games[rec] = (a, seeds)
        clears = f"{sum(S.act1_clear(b[s]) for s in seeds)} → {sum(S.act1_clear(a[s]) for s in seeds)} of {len(seeds)}"
        print(f"| {NAMES[reg]} | {np.mean([b[s]['floor'] for s in seeds]):.2f} | {np.mean([a[s]['floor'] for s in seeds]):.2f} | "
              f"{paired(a, b, seeds)} | {clears} | {agreement(ROOT / run, reg, seeds)} → {agreement(FORMAT, rec, seeds)} |")
    print()
    print("| Comparison | Mean difference [95% CI] | Nimble-9B higher / same / lower | Wilcoxon p |")
    print("|---|---|---|---|")
    for nimble, run, rec in [("nimble", "final", "laya-english-rec"), ("nimble", "final", "laya-typed-rec"),
                             ("nimble", "final", "laya-multilingual-rec"), ("nimble-ft", "round2", "laya-english-ft-rec")]:
        if rec not in games:
            continue
        a, seeds = games[rec]
        n = S.games(ROOT / run, nimble)
        seeds = [s for s in seeds if s in n]
        reg = next(r for x, r, _ in PAIRS if x == rec)
        print(f"| {NAMES[nimble]} vs {NAMES[reg]}, documented format | {paired(n, a, seeds)} |")


if __name__ == "__main__":
    main()
