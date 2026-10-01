"""The pre-registered analysis of round 2 (https://gist.github.com/kecan0406/aa20d9488e25d78ee508e2fe525d4c4d): fine-tuned against zero-shot.

    uv run python scripts/stats_round2.py --out reports/round2

Reads results/round2 (laya-english-ft, nimble-ft), results/final (the zero-shot runs), results/main (the
reference players), results/check (seeds 201-250), results/training/*.json and results/latency.
Writes <out>.md and <out>-survival.png and prints the markdown. Uses the round-1 statistics
(scripts/stats.py): paired bootstrap intervals, Wilcoxon, exact McNemar, Wilson, Holm.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np

import stats as S

ZS = {"laya-english": "results/final", "nimble": "results/final"}
FT = {"laya-english-ft": "results/round2", "nimble-ft": "results/round2"}
NAMES = {**S.NAMES, "laya-english-ft": "Laya english, fine-tuned", "nimble-ft": "Nimble-9B, fine-tuned"}
COLORS = {**S.COLORS, "laya-english-ft": "#a8440f", "nimble-ft": "#15604f"}
PRIMARY = [("laya-english-ft", "laya-english"), ("nimble-ft", "nimble"), ("nimble-ft", "laya-english-ft")]


def summary_row(p: str, run: Path, g: dict, seeds: list[int]) -> str:
    rows = [g[s] for s in seeds]
    floors = np.array([r["floor"] for r in rows], dtype=float)
    se = floors.std(ddof=1) / math.sqrt(len(floors))
    clears = sum(S.act1_clear(r) for r in rows)
    wins = sum(r["outcome"] == "PLAYER_VICTORY" for r in rows)
    ds = S.decisions(run, p, seeds)
    voted = [d for d in ds if d.get("votes")]
    four = [d for d in voted if len(d["votes"]) == 4]
    agree = lambda xs: f"{100 * sum(len(set(d['votes'])) == 1 for d in xs) / len(xs):.1f}%" if xs else "-"
    err = run / p / "errors.jsonl"
    n_err = len(err.read_text().splitlines()) if err.exists() else 0
    return (f"| {NAMES[p]} | {floors.mean():.2f} ± {se:.2f} | {S.pct(clears, len(rows))} | {wins} | {agree(voted)} | "
            f"{agree(four)} | {n_err} / {sum(bool(r.get('aborted')) for r in rows)} |")


def main() -> None:
    ap = argparse.ArgumentParser(description="Pre-registered round-2 analysis.")
    ap.add_argument("--out", type=Path, default=Path("reports/round2"))
    args = ap.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    runs = {**{p: Path(r) for p, r in ZS.items()}, **{p: Path(r) for p, r in FT.items()}}
    g = {p: S.games(runs[p], p) for p in runs}
    seeds = sorted(set.intersection(*(set(v) for v in g.values())))
    refs = {p: S.games(Path("results/main"), p) for p in S.REFS}
    md = ["# Slay the Spire: Nimble vs Laya, round 2 (fine-tuned), pre-registered analysis", "",
          f"Plan: https://gist.github.com/kecan0406/aa20d9488e25d78ee508e2fe525d4c4d. Seeds analysed: {len(seeds)}. Intervals are paired bootstrap "
          f"({S.RESAMPLES:,} resamples, seed {S.RNG_SEED}); rates carry Wilson 95% intervals.", "",
          "| Player | Mean floor ± SE | Act 1 cleared [95% CI] | Wins | Same pick in every order | "
          "Same pick, 4-order decisions | Errors / aborted |", "|---|---|---|---|---|---|---|"]
    for p in ("nimble-ft", "nimble", "laya-english-ft", "laya-english"):
        md.append(summary_row(p, runs[p], g[p], seeds))
    for p in S.REFS:
        fl = np.array([refs[p][s]["floor"] for s in seeds], dtype=float)
        md.append(f"| {NAMES[p]} | {fl.mean():.2f} ± {fl.std(ddof=1) / math.sqrt(len(fl)):.2f} | "
                  f"{S.pct(sum(S.act1_clear(refs[p][s]) for s in seeds), len(seeds))} | "
                  f"{sum(refs[p][s]['outcome'] == 'PLAYER_VICTORY' for s in seeds)} | - | - | - |")
    md += ["", "## Primary comparisons, per seed (Holm over the three)", "",
           "| Comparison | A higher / same / lower | Mean floor difference A - B [95% CI] | Wilcoxon p (zeros) | Holm p | "
           "Act 1 clears, only A / only B | McNemar p |", "|---|---|---|---|---|---|---|"]
    rows, ps = [], []
    for a, b in PRIMARY:
        d = [g[a][s]["floor"] - g[b][s]["floor"] for s in seeds]
        p, zeros = S.wilcoxon(d)
        oa, ob, pm = S.mcnemar([S.act1_clear(g[a][s]) for s in seeds], [S.act1_clear(g[b][s]) for s in seeds])
        rows.append((a, b, d, p, zeros, oa, ob, pm))
        ps.append(p)
    for (a, b, d, p, zeros, oa, ob, pm), ph in zip(rows, S.holm(ps)):
        md.append(f"| {NAMES[a]} vs {NAMES[b]} | {sum(x > 0 for x in d)} / {sum(x == 0 for x in d)} / {sum(x < 0 for x in d)} | "
                  f"{np.mean(d):+.2f} {S.fmt_ci(*S.boot_ci(d), 2)} | {S.fmt_p(p)} ({zeros}) | {S.fmt_p(ph)} | {oa} / {ob} | {S.fmt_p(pm)} |")
    md += ["", "## Where runs end (last fight, top 6)", ""]
    for p in ("nimble-ft", "laya-english-ft"):
        ends = Counter(S.last_fight(S.decisions(runs[p], p, [s])) or "outside a fight" for s in seeds)
        md.append(f"- {NAMES[p]}: " + ", ".join(f"{k} {v}" for k, v in ends.most_common(6)))
    md += ["", "## Survival: share of runs that reached each floor", "",
           "| Player | Floor 10 | Floor 16 (act 1 boss) | Floor 17 (act 2) | Floor 33 (act 2 boss) | Floor 34 (act 3) |",
           "|---|---|---|---|---|---|"]
    for p in ("nimble-ft", "nimble", "laya-english-ft", "laya-english"):
        fl = np.array([g[p][s]["floor"] for s in seeds])
        md.append(f"| {NAMES[p]} | " + " | ".join(f"{100 * (fl >= f).mean():.0f}%" for f in (10, 16, 17, 33, 34)) + " |")
    md += ["", "## Training and checks", "", "| Model | Teacher agreement on validation, before -> after | Training time | Check games 201-250, zero-shot -> fine-tuned |",
           "|---|---|---|---|"]
    for ft, zs, key in (("laya-english-ft", "laya-english", "teacher_agreement"), ("nimble-ft", "nimble", "accuracy")):
        rep = Path(f"results/training/{ft}.json")
        agree = hours = "-"
        if rep.exists():
            r = json.loads(rep.read_text())
            get = (lambda x: x[key]) if key == "teacher_agreement" else (lambda x: x["all"]["accuracy"])
            agree = f"{get(r['before']):.3f} -> {get(r['after']):.3f}"
            hours = f"{r['train_seconds'] / 3600:.2f} h"
        check = "-"
        cz, cf = S.games(Path("results/check"), zs), S.games(Path("results/check"), ft)
        common = sorted(set(cz) & set(cf))
        if common:
            check = f"{np.mean([cz[s]['floor'] for s in common]):.2f} -> {np.mean([cf[s]['floor'] for s in common]):.2f} ({len(common)} seeds)"
        md.append(f"| {NAMES[ft]} | {agree} | {hours} | {check} |")
    md += [""]
    lat = Path("results/latency")
    if any((lat / f"{p}.json").exists() for p in FT):
        md += ["## Decision time, one server at a time", "", "| Model | Per request, median / p95 | Per decision, median / p95 |", "|---|---|---|"]
        for p in ("nimble-ft", "nimble", "laya-english-ft", "laya-english"):
            f = lat / f"{p}.json"
            if f.exists():
                r = json.loads(f.read_text())
                md.append(f"| {NAMES[p]} | {r['per_request']['median_ms']:.0f} / {r['per_request']['p95_ms']:.0f} ms | "
                          f"{r['per_decision']['median_ms']:.0f} / {r['per_decision']['p95_ms']:.0f} ms |")
        md.append("")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 5.6), dpi=160)
    for p in ("nimble-ft", "nimble", "laya-english-ft", "laya-english"):
        fl = np.array([g[p][s]["floor"] for s in seeds])
        ax.step(range(56), [100 * (fl >= f).mean() for f in range(56)], where="post", color=COLORS[p],
                lw=2.6 if p in FT else 1.6, ls="-" if p in FT else "--", label=NAMES[p])
    for x in (16, 33, 50):
        ax.axvline(x + 0.5, color="#888", lw=0.6, ls=":")
    ax.set_xlim(0, 55)
    ax.set_ylim(0, 101)
    ax.set_xlabel("Floor")
    ax.set_ylabel("Runs that reached the floor (%)")
    ax.set_title(f"Fine-tuned (solid) and zero-shot (dashed) on the same {len(seeds)} seeds")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(args.out.with_name(args.out.name + "-survival.png"))
    text = "\n".join(md)
    args.out.with_suffix(".md").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
