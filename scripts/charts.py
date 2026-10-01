"""The README figures in English, Korean and Chinese, from the files under results/.

    uv run python scripts/charts.py

Writes docs/images/<lang>/{survival-round1,head-to-head,consistency,elite,survival-round2}.png.
Captions live in the READMEs; the images carry only axes and legends. Nimble is teal, the Laya
models are shades of orange, and the search bots are grey and dashed.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import stats as S  # noqa: E402  (scripts/stats.py)

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
INK, MUTED, RULE, PAPER, SAME = "#1b2530", "#5b6b7a", "#d5dbe0", "#ffffff", "#c9d1d8"
COLORS = {**S.COLORS, "nimble-ft": S.COLORS["nimble"], "laya-english-ft": S.COLORS["laya-english"]}

TEXT = {
    "en": {
        "names": {"nimble": "Nimble-9B", "laya-english": "Laya english", "laya-typed": "Laya typed-decisions",
                  "laya-multilingual": "Laya multilingual", "heart1": "heart1 (search bot)",
                  "mcts-heuristic": "mcts-heuristic (search bot)", "random": "Random",
                  "nimble-ft": "Nimble-9B, fine-tuned", "laya-english-ft": "Laya english, fine-tuned"},
        "floor": "Floor", "alive": "Runs that reached this floor (%)",
        "bosses": ("act 1 boss", "act 2 boss", "act 3 boss"),
        "seeds": "Seeds", "h2h": ("Nimble higher", "Same floor", "Laya higher"),
        "agree": "Decisions where all 4 orders picked the same action (%)",
        "won": "Fights won (%)",
    },
    "ko": {
        "names": {"nimble": "Nimble-9B", "laya-english": "Laya english", "laya-typed": "Laya typed-decisions",
                  "laya-multilingual": "Laya multilingual", "heart1": "heart1 (탐색 봇)",
                  "mcts-heuristic": "mcts-heuristic (탐색 봇)", "random": "무작위",
                  "nimble-ft": "Nimble-9B, 파인튜닝", "laya-english-ft": "Laya english, 파인튜닝"},
        "floor": "층", "alive": "이 층까지 온 판 (%)",
        "bosses": ("1막 보스", "2막 보스", "3막 보스"),
        "seeds": "seed 수", "h2h": ("Nimble이 높음", "같은 층", "Laya가 높음"),
        "agree": "4가지 순서 모두 같은 행동을 고른 결정 (%)",
        "won": "이긴 전투 (%)",
    },
    "zh-cn": {
        "names": {"nimble": "Nimble-9B", "laya-english": "Laya english", "laya-typed": "Laya typed-decisions",
                  "laya-multilingual": "Laya multilingual", "heart1": "heart1（搜索机器人）",
                  "mcts-heuristic": "mcts-heuristic（搜索机器人）", "random": "随机",
                  "nimble-ft": "Nimble-9B，微调", "laya-english-ft": "Laya english，微调"},
        "floor": "层数", "alive": "到达该层的对局 (%)",
        "bosses": ("第 1 幕 Boss", "第 2 幕 Boss", "第 3 幕 Boss"),
        "seeds": "种子数", "h2h": ("Nimble 更高", "同层", "Laya 更高"),
        "agree": "4 种顺序都选同一动作的决策 (%)",
        "won": "获胜的战斗 (%)",
    },
}


def setup() -> None:
    plt.rcParams.update({"font.family": ["Noto Sans CJK JP", "DejaVu Sans"], "font.size": 13,
                         "axes.edgecolor": RULE, "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
                         "figure.facecolor": PAPER, "axes.facecolor": PAPER})


def figure(left: float = 0.08, height: float = 5.0, bottom: float = 0.13):
    fig, ax = plt.subplots(figsize=(10, height), dpi=160)
    fig.subplots_adjust(left=left, right=0.97, top=0.9, bottom=bottom)
    ax.spines[["top", "right"]].set_visible(False)
    return fig, ax


def survival_axes(ax, t: dict, curves: list[tuple[str, list[int], bool, bool]], xmax: int = 55) -> None:
    """curves: (player, floors, dashed, thin)."""
    xs = list(range(0, xmax + 1))
    for p, fl, dashed, thin in curves:
        alive = [100 * sum(f >= x for f in fl) / len(fl) for x in xs]
        ax.step(xs, alive, where="post", color=COLORS[p], lw=1.6 if thin else 3.0,
                ls=(0, (4, 3)) if dashed else "-", label=t["names"][p], zorder=2 if thin else 3)
    for x, name in zip((16.5, 33.5, 50.5), t["bosses"]):
        ax.axvline(x, color=RULE, lw=1, zorder=1)
        ax.text(x + 0.4, 103, name, fontsize=10, color=MUTED, va="bottom")
    ax.set_xlim(0, xmax)
    ax.set_ylim(0, 102)
    ax.set_xlabel(t["floor"])
    ax.set_ylabel(t["alive"])
    ax.legend(frameon=False, fontsize=10.5, loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=4)


def survival_round1(g: dict, seeds: list[int], t: dict, out: Path) -> None:
    fig, ax = figure(height=6.0, bottom=0.24)
    curves = [(p, [g[p][s]["floor"] for s in seeds], p in S.REFS, p in S.REFS) for p in S.MODELS + S.REFS]
    survival_axes(ax, t, curves)
    fig.savefig(out / "survival-round1.png")
    plt.close(fig)


def survival_round2(g: dict, seeds: list[int], t: dict, out: Path) -> None:
    fig, ax = figure(height=6.0, bottom=0.24)
    curves = [("nimble-ft", False, False), ("nimble", True, True), ("laya-english-ft", False, False),
              ("laya-english", True, True), ("heart1", True, True)]
    survival_axes(ax, t, [(p, [g[p][s]["floor"] for s in seeds], d, th) for p, d, th in curves])
    fig.savefig(out / "survival-round2.png")
    plt.close(fig)


def head_to_head(g: dict, seeds: list[int], t: dict, out: Path) -> None:
    fig, ax = figure(left=0.24, height=4.2, bottom=0.17)
    rows = []
    for lay in S.LAYAS:
        d = [g["nimble"][s]["floor"] - g[lay][s]["floor"] for s in seeds]
        rows.append((t["names"][lay], sum(x > 0 for x in d), sum(x == 0 for x in d), sum(x < 0 for x in d)))
    for i, (_, hi, same, lo) in enumerate(reversed(rows)):
        left = 0
        for n, color, text_color in ((hi, COLORS["nimble"], "white"), (same, SAME, INK), (lo, COLORS["laya-english"], "white")):
            ax.barh(i, n, left=left, color=color, height=0.62)
            if n >= len(seeds) * 0.04:
                ax.text(left + n / 2, i, str(n), ha="center", va="center", color=text_color, fontsize=13, fontweight="bold")
            left += n
    ax.set_yticks(range(len(rows)), [r[0] for r in reversed(rows)], fontsize=12, color=INK)
    ax.set_xlim(0, len(seeds))
    ax.set_xlabel(t["seeds"])
    ax.tick_params(axis="y", length=0)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (COLORS["nimble"], SAME, COLORS["laya-english"])]
    ax.legend(handles, t["h2h"], frameon=False, ncol=3, fontsize=11, loc="lower left", bbox_to_anchor=(0, 1.0))
    fig.savefig(out / "head-to-head.png")
    plt.close(fig)


def consistency(runs: dict[str, Path], seeds: list[int], t: dict, out: Path) -> None:
    players = S.MODELS + ["nimble-ft", "laya-english-ft"]
    fig, ax = figure(left=0.3, height=4.6)
    vals = []
    for p in players:
        four = [d for d in S.decisions(runs[p], p, seeds) if d["votes"] and len(d["votes"]) == 4]
        vals.append((t["names"][p], 100 * sum(len(set(d["votes"])) == 1 for d in four) / max(1, len(four)), COLORS[p],
                     p.endswith("-ft")))
    for i, (_, v, color, ft) in enumerate(reversed(vals)):
        ax.barh(i, v, color=color, height=0.62, hatch="//" if ft else None, edgecolor="white" if ft else None)
        ax.text(v + 1, i, f"{v:.0f}%", va="center", fontsize=13, color=INK, fontweight="bold")
    ax.set_yticks(range(len(vals)), [v[0] for v in reversed(vals)], fontsize=12, color=INK)
    ax.set_xlim(0, 100)
    ax.set_xlabel(t["agree"])
    ax.tick_params(axis="y", length=0)
    fig.savefig(out / "consistency.png")
    plt.close(fig)


def elite(path: Path, t: dict, out: Path) -> None:
    states = [json.loads(line) for line in (path / "states.jsonl").read_text().splitlines()]
    players = S.MODELS + ["mcts-heuristic", "random"]
    fights = {p: {x["seed"]: x for x in map(json.loads, (path / p / "fights.jsonl").read_text().splitlines())}
              for p in players}
    done = [s["seed"] for s in states if all(s["seed"] in fights[p] for p in players)]
    fig, ax = figure(left=0.3, height=4.6)
    for i, p in enumerate(reversed(players)):
        k = sum(fights[p][s]["win"] for s in done)
        lo, hi = S.wilson(k, len(done))
        v = 100 * k / len(done)
        ax.barh(i, v, color=COLORS[p], height=0.62, alpha=0.55 if p not in S.MODELS else 1.0)
        ax.errorbar(v, i, xerr=[[v - 100 * lo], [100 * hi - v]], color=INK, capsize=4, lw=1.2)
        ax.text(100 * hi + 1.5, i, f"{k}/{len(done)}", va="center", fontsize=12, color=INK)
    ax.set_yticks(range(len(players)), [t["names"][p] for p in reversed(players)], fontsize=12, color=INK)
    ax.set_xlim(0, 112)
    ax.set_xlabel(t["won"])
    ax.tick_params(axis="y", length=0)
    fig.savefig(out / "elite.png")
    plt.close(fig)


def main() -> None:
    setup()
    final, main_run, round2 = RESULTS / "final", RESULTS / "main", RESULTS / "round2"
    g = {p: S.games(final, p) for p in S.MODELS}
    g |= {p: S.games(main_run, p) for p in S.REFS}
    g |= {p: S.games(round2, p) for p in ("nimble-ft", "laya-english-ft")}
    seeds = sorted(set.intersection(*(set(g[p]) for p in S.MODELS)))
    runs = {**{p: final for p in S.MODELS}, "nimble-ft": round2, "laya-english-ft": round2}
    for lang, t in TEXT.items():
        out = ROOT / "docs" / "images" / lang
        out.mkdir(parents=True, exist_ok=True)
        survival_round1(g, seeds, t, out)
        head_to_head(g, seeds, t, out)
        consistency(runs, seeds, t, out)
        elite(RESULTS / "elite", t, out)
        survival_round2(g, seeds, t, out)
        print(out)


if __name__ == "__main__":
    main()
