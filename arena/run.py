"""Play full Ironclad runs with one player making every decision, logging each one as text.

    uv run python -m arena.run --player random --seeds 1-3 --out runs/smoke

Writes <out>/<player>/seed-<n>.jsonl (one line per model decision) and appends the game
summary to <out>/<player>/games.jsonl.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import slaythespire as sts

from . import prompt as P
from .players import RotationPlayer, make_player

MAX_BATTLE_DECISIONS = 3000   # guards against a fight that never ends (e.g. endless 0-cost plays)
MAX_GAME_STEPS = 20000


def _log(fh, d: P.Decision, choice, gc, player: str, seed: int):
    fh.write(json.dumps({
        "player": player, "seed": seed, "act": gc.act, "floor": gc.floor_num, "screen": d.screen,
        "kind": d.kind, "state": d.state, "options": d.texts, "chosen": choice.index,
        "chosen_text": d.texts[choice.index], "scores": choice.scores, "latency_ms": choice.latency_ms,
        "shortened": choice.shortened, "dropped_duplicates": d.dropped_duplicates, "votes": choice.votes,
    }, ensure_ascii=False) + "\n")


def play_game(seed: int, player_name: str, out_dir: Path, ascension: int = 0,
              perms: int = 1, power_notes: bool = False, wording: str = "main") -> dict:
    player = make_player(player_name, seed, perms)
    gc = sts.GameContext(sts.CharacterClass.IRONCLAD, seed, ascension)
    heuristic = sts.Agent()  # only for Match and Keep, a memory minigame with no describable choice
    heuristic.verbosity_level = 0
    counts = {"model_decisions": 0, "forced": 0, "heuristic": 0, "shortened": 0, "unanimous": 0, "aborted": None}
    latencies: list[float] = []
    t0 = time.perf_counter()

    def decide(d: P.Decision, fh) -> int:
        c = player.choose(d)
        _log(fh, d, c, gc, player_name, seed)
        counts["model_decisions"] += 1
        counts["shortened"] += c.shortened
        counts["unanimous"] += bool(c.votes) and len(set(c.votes)) == 1
        if c.latency_ms is not None:
            latencies.append(c.latency_ms)
        return c.index

    with open(out_dir / f"seed-{seed}.jsonl", "w") as fh:
        steps = 0
        while gc.outcome == sts.GameOutcome.UNDECIDED:
            steps += 1
            if steps > MAX_GAME_STEPS:
                counts["aborted"] = "game step limit"
                break
            if gc.screen_state == sts.ScreenState.BATTLE:
                bc = gc.create_battle_context()
                n = 0
                while bc.outcome == sts.BattleOutcome.UNDECIDED:
                    n += 1
                    if n > MAX_BATTLE_DECISIONS:
                        counts["aborted"] = "battle decision limit"
                        break
                    d = P.battle_decision(bc, gc, power_notes, wording)
                    if len(d.actions) == 1:
                        counts["forced"] += 1
                        d.actions[0].execute(bc)
                        continue
                    d.actions[decide(d, fh)].execute(bc)
                if counts["aborted"]:
                    break
                gc.sync_from_battle_context(bc)
                continue
            if gc.screen_state == sts.ScreenState.EVENT_SCREEN and gc.cur_event == sts.Event.MATCH_AND_KEEP:
                counts["heuristic"] += 1
                heuristic.pick_gameaction(gc).execute(gc)
                continue
            d = P.overworld_decision(gc, wording)
            if len(d.actions) == 1:
                counts["forced"] += 1
                d.actions[0].execute(gc)
                continue
            d.actions[decide(d, fh)].execute(gc)
    latencies.sort()
    return {
        "player": player_name, "seed": seed, "ascension": ascension,
        "perms": "rotations" if isinstance(player, RotationPlayer) else perms, "power_notes": power_notes, "wording": wording,
        "outcome": gc.outcome.name, "floor": gc.floor_num, "act": gc.act, "hp": gc.cur_hp,
        "seconds": round(time.perf_counter() - t0, 2),
        "latency_p50_ms": round(latencies[len(latencies) // 2], 1) if latencies else None,
        **counts,
    }


def _seeds(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        a, _, b = part.partition("-")
        out += list(range(int(a), int(b or a) + 1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--player", required=True)
    ap.add_argument("--seeds", default="1")
    ap.add_argument("--ascension", type=int, default=0)
    ap.add_argument("--out", default="runs")
    ap.add_argument("--perms", type=int, default=1, help="option orders per model decision, majority vote")
    ap.add_argument("--power-notes", action="store_true", help="explain enemy powers in the battle state")
    ap.add_argument("--wording", choices=sorted(P.INSTRUCTIONS), default="main", help="wording of the two questions")
    args = ap.parse_args()
    out_dir = Path(args.out) / args.player
    out_dir.mkdir(parents=True, exist_ok=True)
    for seed in _seeds(args.seeds):
        summary = play_game(seed, args.player, out_dir, args.ascension, args.perms, args.power_notes, args.wording)
        with open(out_dir / "games.jsonl", "a") as fh:
            fh.write(json.dumps(summary) + "\n")
        print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
