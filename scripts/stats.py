"""The pre-registered analysis (https://gist.github.com/kecan0406/5816965b9711d07509ab91c291dda7d7) of a headline run, plus its secondary tracks.

    uv run python scripts/stats.py results/final --refs results/main --single results/main \
        --wording results/wording --elite results/elite --latency results/latency --out reports/round1

Writes <out>.md and <out>-survival.png and prints the markdown. Every track is optional except the
headline run; a track whose folder is missing or unfinished is analysed on the seeds it has.
"""
from __future__ import annotations

import argparse
import functools
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
from scipy import stats

MODELS = ["nimble", "laya-english", "laya-typed", "laya-multilingual"]
LAYAS = MODELS[1:]
REFS = ["heart1", "mcts-heuristic", "random"]
NAMES = {"nimble": "Nimble-9B", "laya-english": "Laya english", "laya-typed": "Laya typed-decisions",
         "laya-multilingual": "Laya multilingual", "heart1": "heart1 (search bot)",
         "mcts-heuristic": "mcts-heuristic (search bot)", "random": "random"}
COLORS = {"nimble": "#2a9d82", "laya-english": "#e07a36", "laya-typed": "#b5562a", "laya-multilingual": "#f0b27a",
          "heart1": "#6c7a89", "mcts-heuristic": "#95a3b0", "random": "#c5ced6"}
RNG_SEED, RESAMPLES = 0, 10_000


# --- data -----------------------------------------------------------------------------------

def games(run: Path, player: str) -> dict[int, dict]:
    f = run / player / "games.jsonl"
    return {g["seed"]: g for g in map(json.loads, f.read_text().splitlines())} if f.exists() else {}


@functools.cache
def _decision_rows(run: Path, player: str) -> dict[int, dict]:
    f = run / player / "decisions.jsonl"
    return {r["seed"]: r for r in map(json.loads, f.read_text().splitlines())} if f.exists() else {}


def decisions(run: Path, player: str, seeds) -> list[dict]:
    """Model decisions of the given seeds as {kind, options, chosen, votes, shortened, last_fight}."""
    out = []
    for s in seeds:
        row = _decision_rows(run, player).get(s)
        if row:
            out += [{"kind": k, "options": n, "chosen": c, "votes": v, "shortened": bool(sh), "last_fight": row["last_fight"]}
                    for k, n, c, v, sh in row["decisions"]]
    return out


def act1_clear(g: dict) -> bool:
    return g["act"] >= 2 or g["outcome"] == "PLAYER_VICTORY"


# --- statistics -----------------------------------------------------------------------------

def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


def boot_ci(diffs, resamples: int = RESAMPLES) -> tuple[float, float]:
    d = np.asarray(diffs, dtype=float)
    idx = np.random.default_rng(RNG_SEED).integers(0, len(d), size=(resamples, len(d)))
    means = d[idx].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def wilcoxon(diffs) -> tuple[float, int]:
    """Two-sided signed-rank p with zero differences dropped, and the number dropped."""
    d = np.asarray(diffs, dtype=float)
    zeros = int((d == 0).sum())
    if zeros == len(d):
        return 1.0, zeros
    return float(stats.wilcoxon(d, zero_method="wilcox", alternative="two-sided").pvalue), zeros


def mcnemar(a: list[bool], b: list[bool]) -> tuple[int, int, float]:
    """Exact McNemar: (only a, only b, two-sided p)."""
    only_a = sum(x and not y for x, y in zip(a, b))
    only_b = sum(y and not x for x, y in zip(a, b))
    n = only_a + only_b
    p = 1.0 if n == 0 else float(stats.binomtest(min(only_a, only_b), n, 0.5).pvalue)
    return only_a, only_b, p


def holm(ps: list[float]) -> list[float]:
    order = sorted(range(len(ps)), key=ps.__getitem__)
    adjusted, running = [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(ps) - rank) * ps[i]))
        adjusted[i] = running
    return adjusted


def fmt_p(p: float) -> str:
    return "<0.0001" if p < 1e-4 else f"{p:.4f}" if p < 0.01 else f"{p:.3f}"


def fmt_ci(lo: float, hi: float, digits: int = 1) -> str:
    return f"[{lo:+.{digits}f}, {hi:+.{digits}f}]"


def pct(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    return f"{k}/{n} ({100 * k / n:.1f}% [{100 * lo:.1f}, {100 * hi:.1f}])" if n else "-"


# --- sections -------------------------------------------------------------------------------

def last_fight(log: list[dict]) -> str | None:
    """Enemies of the seed's last battle decision, e.g. 'Gremlin Nob' or '3x Sentry'."""
    return log[-1]["last_fight"] if log else None


def headline(run: Path, refs: Path | None, single: Path | None, out: Path) -> list[str]:
    md: list[str] = []
    g = {p: games(run, p) for p in MODELS}
    common = sorted(set.intersection(*(set(v) for v in g.values()))) if all(g.values()) else []
    if refs:
        keep = set(common)
        for p in REFS:
            g[p] = {s: x for s, x in games(refs, p).items() if s in keep}
    n = len(common)
    md += [f"## Headline run `{run}`", "",
           f"Seeds analysed: {n} (seeds every model finished: {common[0]}-{common[-1]})." if n else "No seeds yet.", ""]
    if not n:
        return md

    md += ["| Player | Mean floor ± SE | Act 1 cleared [95% CI] | Wins | Same pick in every order | "
           "Same pick, 4-order decisions | Options shortened | Errors / aborted |", "|---|---|---|---|---|---|---|---|"]
    logs = {}
    for p in MODELS + (REFS if refs else []):
        rows = [g[p][s] for s in common if s in g[p]]
        if not rows:
            continue
        floors = np.array([r["floor"] for r in rows], dtype=float)
        se = floors.std(ddof=1) / math.sqrt(len(floors)) if len(floors) > 1 else 0.0
        clears = sum(act1_clear(r) for r in rows)
        wins = sum(r["outcome"] == "PLAYER_VICTORY" for r in rows)
        agree = agree4 = short = "-"
        errs = "-"
        if p in MODELS:
            logs[p] = {s: decisions(run, p, [s]) for s in common}
            ds = [d for s in common for d in logs[p][s]]
            voted = [d for d in ds if d.get("votes")]
            four = [d for d in voted if len(d["votes"]) == 4]
            unanimous = lambda xs: sum(len(set(d["votes"])) == 1 for d in xs)
            agree = f"{100 * unanimous(voted) / len(voted):.1f}%" if voted else "-"
            agree4 = f"{100 * unanimous(four) / len(four):.1f}%" if four else "-"
            short = f"{100 * sum(d['shortened'] for d in ds) / len(ds):.1f}%" if ds else "-"
            err_file = run / p / "errors.jsonl"
            n_err = len(err_file.read_text().splitlines()) if err_file.exists() else 0
            errs = f"{n_err} / {sum(bool(r.get('aborted')) for r in rows)}"
        md.append(f"| {NAMES[p]} | {floors.mean():.2f} ± {se:.2f} | {pct(clears, len(rows))} | {wins} | {agree} | "
                  f"{agree4} | {short} | {errs} |")
    md.append("")

    # Primary family: Nimble against each Laya model on floor reached.
    md += ["### Primary: Nimble against each Laya model, per seed", "",
           "| Against | Nimble higher / same / lower | Mean floor difference [95% CI] | Wilcoxon p (zeros dropped) | "
           "Holm p | Act 1 clears, only Nimble / only Laya | McNemar p (secondary) |", "|---|---|---|---|---|---|---|"]
    rows, ps = [], []
    for lay in LAYAS:
        d = [g["nimble"][s]["floor"] - g[lay][s]["floor"] for s in common]
        p, zeros = wilcoxon(d)
        a, b, pm = mcnemar([act1_clear(g["nimble"][s]) for s in common], [act1_clear(g[lay][s]) for s in common])
        rows.append((lay, d, p, zeros, a, b, pm))
        ps.append(p)
    for (lay, d, p, zeros, a, b, pm), ph in zip(rows, holm(ps)):
        hi, same, lo = sum(x > 0 for x in d), sum(x == 0 for x in d), sum(x < 0 for x in d)
        md.append(f"| {NAMES[lay]} | {hi} / {same} / {lo} | {np.mean(d):+.2f} {fmt_ci(*boot_ci(d), 2)} | "
                  f"{fmt_p(p)} ({zeros} zeros) | {fmt_p(ph)} | {a} / {b} | {fmt_p(pm)} |")
    md.append("")

    if single:
        md += ["### Against the single-order run (context)", "",
               f"Same seeds, `{single}`: one option order, no vote.", "",
               "| Model | Single order | Vote | Difference [95% CI] |", "|---|---|---|---|"]
        for p in MODELS:
            base = games(single, p)
            seeds = [s for s in common if s in base]
            if seeds:
                d = [g[p][s]["floor"] - base[s]["floor"] for s in seeds]
                md.append(f"| {NAMES[p]} | {np.mean([base[s]['floor'] for s in seeds]):.2f} | "
                          f"{np.mean([g[p][s]['floor'] for s in seeds]):.2f} | {np.mean(d):+.2f} {fmt_ci(*boot_ci(d), 2)} |")
        md.append("")

    md += ["### Where runs end (last fight, top 6)", ""]
    for p in MODELS:
        ends = Counter(last_fight(logs[p][s]) or "outside a fight" for s in common)
        md.append(f"- {NAMES[p]}: " + ", ".join(f"{k} {v}" for k, v in ends.most_common(6)))
    md.append("")

    md += survival(g, common, out)
    return md


def survival(g: dict, seeds: list[int], out: Path) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    floors = range(0, 56)
    fig, ax = plt.subplots(figsize=(10, 5.6), dpi=160)
    table = ["### Survival: share of runs that reached each floor", "",
             "| Player | Floor 6 | Floor 10 | Floor 16 (act 1 boss) | Floor 17 (act 2) | Floor 33 (act 2 boss) |",
             "|---|---|---|---|---|---|"]
    for p in [x for x in MODELS + REFS if x in g and g[x]]:
        fl = np.array([g[p][s]["floor"] for s in seeds if s in g[p]])
        alive = [100 * (fl >= f).mean() for f in floors]
        ref = p in REFS
        ax.step(list(floors), alive, where="post", label=NAMES[p], color=COLORS[p],
                lw=1.4 if ref else 2.4, ls="--" if ref else "-")
        table.append(f"| {NAMES[p]} | " + " | ".join(f"{100 * (fl >= f).mean():.0f}%" for f in (6, 10, 16, 17, 33)) + " |")
    for x in (16, 33, 50):
        ax.axvline(x + 0.5, color="#888", lw=0.6, ls=":")
    ax.set_xlabel("Floor")
    ax.set_ylabel("Runs that reached the floor (%)")
    ax.set_xlim(0, 55)
    ax.set_ylim(0, 101)
    ax.set_title(f"Slay the Spire, Ironclad A0: floors reached on the same {len(seeds)} seeds")
    ax.legend(frameon=False, fontsize=8.5)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    png = out.with_name(out.name + "-survival.png")
    fig.savefig(png)
    return table + ["", f"Chart: `{png}`", ""]


def wording(run: Path, alt: Path) -> list[str]:
    md = [f"## Track A: question wording `{alt}`", ""]
    g = {p: games(run, p) for p in MODELS}
    a = {p: games(alt, p) for p in MODELS}
    seeds = sorted(set.intersection(*(set(g[p]) & set(a[p]) for p in MODELS)))
    if not seeds:
        return md + ["No common seeds yet.", ""]
    md += [f"Seeds analysed: {len(seeds)}.", "", "| Model | Original | Rewording | Difference [95% CI] | Wilcoxon p |",
           "|---|---|---|---|---|"]
    mean_o, mean_a = {}, {}
    for p in MODELS:
        fo = [g[p][s]["floor"] for s in seeds]
        fa = [a[p][s]["floor"] for s in seeds]
        mean_o[p], mean_a[p] = np.mean(fo), np.mean(fa)
        d = [y - x for x, y in zip(fo, fa)]
        md.append(f"| {NAMES[p]} | {mean_o[p]:.2f} | {mean_a[p]:.2f} | {np.mean(d):+.2f} {fmt_ci(*boot_ci(d), 2)} | "
                  f"{fmt_p(wilcoxon(d)[0])} |")
    ranks_o, ranks_a = ranking(mean_o), ranking(mean_a)
    signs = {lay: (np.sign(mean_o["nimble"] - mean_o[lay]), np.sign(mean_a["nimble"] - mean_a[lay])) for lay in LAYAS}
    same_order = ranks_o == ranks_a
    same_signs = all(x == y for x, y in signs.values())
    md += ["", f"- Order by mean floor, original: {show(ranks_o)}",
           f"- Order by mean floor, rewording: {show(ranks_a)}",
           f"- Registered check (same order and same sign of Nimble minus each Laya): "
           f"**{'passes' if same_order and same_signs else 'fails'}** (order {'same' if same_order else 'changed'}, "
           f"signs {'same' if same_signs else 'changed'}).", ""]
    return md


def ranking(means: dict[str, float]) -> list[list[str]]:
    """Models from the highest mean down, equal means grouped together (a tie is not an order)."""
    groups: list[list[str]] = []
    for p in sorted(means, key=lambda x: -means[x]):
        if groups and math.isclose(means[groups[-1][0]], means[p], abs_tol=1e-9):
            groups[-1].append(p)
        else:
            groups.append([p])
    return groups


def show(groups: list[list[str]]) -> str:
    return " > ".join(" = ".join(NAMES[p] for p in g) for g in groups)


def elite(path: Path) -> list[str]:
    md = [f"## Track B: act 1 elite fights `{path}`", ""]
    states = [json.loads(line) for line in (path / "states.jsonl").read_text().splitlines()]
    fights = {}
    for p in MODELS + ["mcts-heuristic", "random"]:
        f = path / p / "fights.jsonl"
        fights[p] = {x["seed"]: x for x in map(json.loads, f.read_text().splitlines())} if f.exists() else {}
    done = [s["seed"] for s in states if all(s["seed"] in fights[p] for p in MODELS)]
    kinds = sorted({s["encounter"] for s in states})
    enc = {s["seed"]: s["encounter"] for s in states}
    per_kind = Counter(s["encounter"] for s in states)
    md += [f"States: {len(states)} ({', '.join(f'{k} {per_kind[k]}' for k in kinds)}); every model finished {len(done)}.", "",
           "| Player | " + " | ".join(f"{k.replace('_', ' ').title()} wins" for k in kinds) +
           " | All wins [95% CI] | HP left (loss = 0) |", "|---|" + "---|" * (len(kinds) + 2)]
    for p in MODELS + ["mcts-heuristic", "random"]:
        rows = [fights[p][s] for s in done if s in fights[p]]
        if not rows:
            continue
        cells = []
        for k in kinds:
            ks = [r for r in rows if enc[r["seed"]] == k]
            cells.append(f"{sum(r['win'] for r in ks)}/{len(ks)}")
        md.append(f"| {NAMES[p]} | " + " | ".join(cells) + f" | {pct(sum(r['win'] for r in rows), len(rows))} | "
                  f"{np.mean([r['hp_left'] for r in rows]):.1f} |")
    md += ["", "Nimble against each Laya model on the same states (secondary, uncorrected):", "",
           "| Against | Wins, only Nimble / only Laya | McNemar p | HP left difference [95% CI] | Wilcoxon p |",
           "|---|---|---|---|---|"]
    for lay in LAYAS:
        a, b, pm = mcnemar([fights["nimble"][s]["win"] for s in done], [fights[lay][s]["win"] for s in done])
        d = [fights["nimble"][s]["hp_left"] - fights[lay][s]["hp_left"] for s in done]
        md.append(f"| {NAMES[lay]} | {a} / {b} | {fmt_p(pm)} | {np.mean(d):+.1f} {fmt_ci(*boot_ci(d))} | "
                  f"{fmt_p(wilcoxon(d)[0])} |")
    md.append("")
    return md


def latency(path: Path) -> list[str]:
    md = [f"## Track C: decision time, one model server at a time `{path}`", "",
          "| Model | Per request, median / p95 | Per decision, median / p95 | Requests per decision | Measured |",
          "|---|---|---|---|---|"]
    for p in MODELS:
        f = path / f"{p}.json"
        if not f.exists():
            continue
        r = json.loads(f.read_text())
        q, d = r["per_request"], r["per_decision"]
        md.append(f"| {NAMES[p]} | {q['median_ms']:.0f} / {q['p95_ms']:.0f} ms | {d['median_ms']:.0f} / {d['p95_ms']:.0f} ms | "
                  f"{r['requests_per_decision']} | {r['when']} |")
    gpu = next((json.loads((path / f"{p}.json").read_text())["gpu"] for p in MODELS if (path / f"{p}.json").exists()), "?")
    md += ["", f"GPU: {gpu} (DGX Spark, aarch64; not an officially supported platform for either model). "
           "500 decisions per model, replayed from the headline logs after 20 warm-up requests.", ""]
    return md


def main() -> None:
    ap = argparse.ArgumentParser(description="The pre-registered analysis of a headline run and its secondary tracks.")
    ap.add_argument("run", type=Path, help="headline run, e.g. results/final")
    ap.add_argument("--refs", type=Path, help="run holding the reference players (random, mcts-heuristic, heart1)")
    ap.add_argument("--single", type=Path, help="single-order run to compare with")
    ap.add_argument("--wording", type=Path, help="track A run")
    ap.add_argument("--elite", type=Path, help="track B folder")
    ap.add_argument("--latency", type=Path, help="track C folder")
    ap.add_argument("--out", type=Path, default=Path("reports/round1"))
    args = ap.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    md = ["# Slay the Spire: Nimble vs Laya, pre-registered analysis", "",
          "Plan: https://gist.github.com/kecan0406/5816965b9711d07509ab91c291dda7d7. Floors are compared per seed; intervals are paired bootstrap "
          f"({RESAMPLES:,} resamples, seed {RNG_SEED}); rates carry Wilson 95% intervals.", ""]
    md += headline(args.run, args.refs, args.single, args.out)
    if args.wording:
        md += wording(args.run, args.wording)
    if args.elite and (args.elite / "states.jsonl").exists():
        md += elite(args.elite)
    if args.latency and args.latency.exists():
        md += latency(args.latency)
    text = "\n".join(md)
    args.out.with_suffix(".md").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
