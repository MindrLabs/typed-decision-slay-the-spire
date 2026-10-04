"""The potion round's tables, recomputed from the files in results/potion (exploratory, not pre-registered).

    uv run python scripts/stats_potion.py [--out reports/potion]

results/potion/<player>/ holds games.jsonl and decisions.jsonl as in the other runs, with a sixth number per
decision, a sum of flags (scripts/export_public.py in the research repository writes them from the option
texts, which stay private):

    1   a potion could be used at this decision
    2   the pick uses one
    4   the reward screen was closed with a relic or gold still on it
    8   a shop decision
    16  the pick buys something
    32  the first shop decision on a floor (a visit starts)

Writes <out>/potion.md (the tables of README section 3.6) and <out>/gate-<player>.json, the pass/fail
check each fine-tuned model went through against the model it started from. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
from pathlib import Path

RESULTS = Path(__file__).resolve().parent.parent / "results" / "potion"
START = {"laya-english-ft2": "laya-english-ft", "laya-english-ft3": "laya-english-ft",
         "laya-english-ft4": "laya-english-ft", "nimble-ft4": "nimble-ft"}
ROWS = ["laya-english-ft", "laya-english-ft2", "laya-english-ft3", "laya-english-ft4", "nimble-ft", "nimble-ft4"]
NAMES = {"laya-english-ft": "Laya english, round-2 fine-tune (start)",
         "laya-english-ft2": "Laya FT2: one DAgger round, no potion step",
         "laya-english-ft3": "Laya FT3: potion step, visit targets, DAgger round 1",
         "laya-english-ft4": "**Laya FT4**: DAgger round 2",
         "nimble-ft": "Nimble-9B, round-2 fine-tune (start)", "nimble-ft4": "**Nimble-9B FT4**"}


def load(player: str) -> tuple[dict, dict]:
    run = RESULTS / player
    games = {g["seed"]: g for g in map(json.loads, (run / "games.jsonl").read_text().splitlines())}
    decisions = {r["seed"]: r["decisions"] for r in map(json.loads, (run / "decisions.jsonl").read_text().splitlines())}
    return games, decisions


def metrics(player: str) -> dict:
    games, decisions = load(player)
    used = held = lost = left = shops = bought = 0
    for seed, game in games.items():
        rows = decisions[seed]
        used += sum(bool(d[5] & 2) for d in rows if d[0] in ("battle", "potion"))
        left += sum(bool(d[5] & 4) for d in rows)
        purchased = False
        for d in rows:
            if d[5] & 32:
                shops, purchased = shops + 1, False
            if d[5] & 16 and not purchased:
                bought, purchased = bought + 1, True
        if game["outcome"] != "PLAYER_VICTORY":
            lost += 1
            fights = [d for d in rows if d[0] == "battle"]
            held += bool(fights) and bool(fights[-1][5] & 1)
    n = len(games)
    return {"games": n, "mean_floor": round(statistics.mean(g["floor"] for g in games.values()), 2),
            "potions_per_game": round(used / n, 2), "lost_holding_potions": round(held / max(lost, 1), 3),
            "relic_or_gold_left_behind": left, "shop_visits_with_purchase": round(bought / max(shops, 1), 3),
            "act1_cleared": sum(g["floor"] > 16 for g in games.values()), "act3_reached": sum(g["act"] >= 3 for g in games.values()),
            "victories": sum(g["outcome"] == "PLAYER_VICTORY" for g in games.values())}


def paired(player: str, start: str) -> tuple[float, float, float]:
    """Mean floor difference on the same seeds and its 95% bootstrap interval (5,000 resamples, seed 0)."""
    a, b = load(start)[0], load(player)[0]
    diff = [b[s]["floor"] - a[s]["floor"] for s in a]
    rng = random.Random(0)
    boots = sorted(statistics.mean(rng.choices(diff, k=len(diff))) for _ in range(5000))
    return statistics.mean(diff), boots[124], boots[4874]


def gate(player: str, start: str) -> dict:
    a, b = metrics(start), metrics(player)
    checks = {
        "potions_per_game >= 3": b["potions_per_game"] >= 3,
        "lost_holding_potions <= 0.5": b["lost_holding_potions"] <= 0.5,
        "mean_floor not lower": b["mean_floor"] >= a["mean_floor"],
        "relic_or_gold_left_behind == 0": b["relic_or_gold_left_behind"] == 0,
        "shop purchase rate within 10 points": b["shop_visits_with_purchase"] >= a["shop_visits_with_purchase"] - 0.10,
    }
    return {start: a, player: b, "checks": checks, "pass": all(checks.values())}


def arena_table() -> list[str]:
    matches = [json.loads(line) for line in (RESULTS / "arena" / "matches.jsonl").read_text().splitlines()]
    out = ["| | Mean floor | Wins | Matches won |", "|---|---|---|---|"]
    for slot, name in (("p1", "Nimble-9B FT4"), ("p2", "Laya english FT4")):
        floors = [m[slot]["floor"] for m in matches]
        out.append(f"| {name} | {statistics.mean(floors):.1f} | {sum(bool(m[slot].get('victory')) for m in matches)}"
                   f" | {sum(m['winner'] == slot for m in matches)} |")
    draws = sum(m["winner"] == "draw" for m in matches)
    return out + ["", f"{len(matches)} matches, seeds {', '.join(str(m['seed']) for m in matches)}; {draws} draw."]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("reports/potion"))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    md = ["# The potion round (exploratory)", "",
          "Check seeds 201-250, 4 option orders, potion step on for the FT3 and FT4 models. Mean-floor differences are against "
          "the model each one started from, on the same seeds, with the 95% bootstrap interval.", "",
          "| Player | Mean floor | Same-seed difference | Potions per game | Lost games with a usable potion left | "
          "Cleared act 1 | Reached act 3 | Wins | Relic or gold left behind | Shop visits with a purchase | Gate |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for p in ROWS:
        m = metrics(p)
        if p in START:
            g = gate(p, START[p])
            (args.out / f"gate-{p}.json").write_text(json.dumps(g, indent=2) + "\n")
            mean, lo, hi = paired(p, START[p])
            diff, verdict = f"{mean:+.1f} [{lo:+.1f}, {hi:+.1f}]", "pass" if g["pass"] else "not passed"
        else:
            diff, verdict = "-", "start"
        md.append(f"| {NAMES[p]} | {m['mean_floor']:.1f} | {diff} | {m['potions_per_game']:.2f} | "
                  f"{100 * m['lost_holding_potions']:.0f}% | {m['act1_cleared']} | {m['act3_reached']} | {m['victories']} | "
                  f"{m['relic_or_gold_left_behind']} | {100 * m['shop_visits_with_purchase']:.0f}% | {verdict} |")
    md += ["", "Gate: potions per game >= 3, lost games with a usable potion left <= 50%, mean floor not lower, no relic or "
           "gold left behind, shop purchase rate no more than 10 points lower.", "",
           "## Real game, 8 matches (`nimble-ft4` against `laya-english-ft4`, potion step on)", ""] + arena_table()
    (args.out / "potion.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
