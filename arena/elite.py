"""Elite fights (pre-registered track B): every player fights the same act 1 elites from the same state.

States: mcts-heuristic plays seeds 1, 2, 3, ... in order. On each seed, the first act 1 map elite it
enters (Gremlin Nob, Lagavulin or 3 Sentries; event fights excluded) is copied at the start of the fight.
A type stops at 30 states and the scan at seed 500. The scan is deterministic, so a rerun finds the
same states. Every player then plays every state from a copy: the fight's randomness comes from the
seed and floor, so each copy starts the same fight.

    uv run python -m arena.elite --players nimble,laya-english,laya-multilingual,laya-typed,random,mcts-heuristic \
        --perms 4 --out runs/elite

Writes <out>/states.jsonl, <out>/<player>/fights.jsonl (one line per state) and, for text players,
<out>/<player>/state-<seed>.jsonl (every model decision, as arena.run logs them). Resumable: states
already in fights.jsonl are skipped.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import itertools
import json
import threading
import time
import traceback
from pathlib import Path

import slaythespire as sts

from . import describe as D
from . import prompt as P
from .bench import DEFAULT_WORKERS
from .players import FAMILIES, make_player
from .run import MAX_BATTLE_DECISIONS, _log

ELITES = (sts.MonsterEncounter.GREMLIN_NOB, sts.MonsterEncounter.LAGAVULIN, sts.MonsterEncounter.THREE_SENTRIES)
MCTS_SIMS = 1000


def _agent() -> sts.Agent:
    agent = sts.Agent()
    agent.simulation_count_base = MCTS_SIMS
    agent.verbosity_level = 0
    return agent


def first_elite(seed: int):
    """mcts-heuristic's game on `seed`, stopped at the start of its first act 1 map elite (None if it has none)."""
    gc = sts.GameContext(sts.CharacterClass.IRONCLAD, seed, 0)
    agent = _agent()
    while gc.outcome == sts.GameOutcome.UNDECIDED and gc.act == 1:
        if gc.screen_state == sts.ScreenState.BATTLE:
            if gc.cur_room == sts.Room.ELITE and gc.encounter in ELITES:
                return gc
            agent.playout_battle(gc)
        else:
            agent.pick_gameaction(gc).execute(gc)
    return None


def scan(per_type: int, max_seed: int, workers: int) -> list[tuple[int, object]]:
    """(seed, state) in seed order, at most `per_type` of each elite."""
    taken: dict[str, int] = {e.name: 0 for e in ELITES}
    states = []
    seeds = iter(range(1, max_seed + 1))
    with cf.ThreadPoolExecutor(workers) as pool:
        while min(taken.values()) < per_type:
            batch = list(itertools.islice(seeds, workers * 4))
            if not batch:
                break
            for seed, gc in zip(batch, pool.map(first_elite, batch)):   # map keeps seed order
                if gc is not None and taken[gc.encounter.name] < per_type:
                    taken[gc.encounter.name] += 1
                    states.append((seed, gc))
    print(f"states: {taken} from seeds 1-{states[-1][0] if states else 0}", flush=True)
    return states


def describe_state(seed: int, gc) -> dict:
    potions = [D.potion_label(p) for p in gc.potions if D._name(p) not in ("EMPTY_POTION_SLOT", "INVALID")]
    return {"seed": seed, "encounter": gc.encounter.name, "floor": gc.floor_num, "hp": gc.cur_hp, "max_hp": gc.max_hp,
            "deck": D._deck_summary(gc.deck), "relics": [D.relic_label(r.id) for r in gc.relics], "potions": potions}


def fight(player_name: str, seed: int, snapshot, out_dir: Path, perms: int) -> dict:
    gc = snapshot.copy()
    hp_start = gc.cur_hp
    counts = {"model_decisions": 0, "forced": 0, "shortened": 0, "unanimous": 0, "aborted": None}
    latencies: list[float] = []
    t0 = time.perf_counter()
    turns = None
    if player_name == "mcts-heuristic":
        _agent().playout_battle(gc)
        win = gc.outcome == sts.GameOutcome.UNDECIDED
    else:
        player = make_player(player_name, seed, perms)
        bc = gc.create_battle_context()
        with open(out_dir / f"state-{seed}.jsonl", "w") as fh:
            while bc.outcome == sts.BattleOutcome.UNDECIDED:
                if counts["model_decisions"] + counts["forced"] >= MAX_BATTLE_DECISIONS:
                    counts["aborted"] = "battle decision limit"
                    break
                d = P.battle_decision(bc, gc)
                if len(d.actions) == 1:
                    counts["forced"] += 1
                    d.actions[0].execute(bc)
                    continue
                c = player.choose(d)
                _log(fh, d, c, gc, player_name, seed)
                counts["model_decisions"] += 1
                counts["shortened"] += c.shortened
                counts["unanimous"] += bool(c.votes) and len(set(c.votes)) == 1
                if c.latency_ms is not None:
                    latencies.append(c.latency_ms)
                d.actions[c.index].execute(bc)
        win = bc.outcome == sts.BattleOutcome.PLAYER_VICTORY
        turns = bc.turn + 1        # bc.turn counts from 0
        gc.sync_from_battle_context(bc)
    latencies.sort()
    return {
        "player": player_name, "seed": seed, "encounter": snapshot.encounter.name, "floor": snapshot.floor_num,
        "perms": perms if player_name in FAMILIES else None, "win": win, "hp_start": hp_start,
        "hp_left": gc.cur_hp if win else 0, "max_hp": gc.max_hp, "turns": turns,
        "seconds": round(time.perf_counter() - t0, 2),
        "latency_p50_ms": round(latencies[len(latencies) // 2], 1) if latencies else None, **counts,
    }


def run_player(player: str, states, out: Path, workers: int, perms: int) -> None:
    out_dir = out / player
    out_dir.mkdir(parents=True, exist_ok=True)
    done_file = out_dir / "fights.jsonl"
    done = {json.loads(line)["seed"] for line in done_file.read_text().splitlines()} if done_file.exists() else set()
    todo = [(seed, gc) for seed, gc in states if seed not in done]
    print(f"[{player}] {len(states) - len(todo)} done, {len(todo)} to fight, {workers} workers", flush=True)
    lock = threading.Lock()

    def one(item) -> None:
        seed, gc = item
        try:
            summary = fight(player, seed, gc, out_dir, perms)
        except Exception as e:
            with lock, open(out_dir / "errors.jsonl", "a") as fh:
                fh.write(json.dumps({"seed": seed, "error": repr(e), "trace": traceback.format_exc()}) + "\n")
            print(f"[{player}] state {seed} ERROR {e!r}", flush=True)
            return
        with lock, open(done_file, "a") as fh:
            fh.write(json.dumps(summary) + "\n")
        print(f"[{player}] {json.dumps(summary)}", flush=True)

    with cf.ThreadPoolExecutor(workers, thread_name_prefix=player) as pool:
        list(pool.map(one, todo))


def main() -> None:
    ap = argparse.ArgumentParser(description="Act 1 elite fights from identical states (pre-registered track B).")
    ap.add_argument("--players", required=True, help="comma list; text players, random, mcts-heuristic")
    ap.add_argument("--out", required=True)
    ap.add_argument("--perms", type=int, default=4, help="text players: option orders per decision, majority vote")
    ap.add_argument("--per-type", type=int, default=30)
    ap.add_argument("--max-seed", type=int, default=500)
    ap.add_argument("--scan-workers", type=int, default=8)
    ap.add_argument("--workers", default="", help="overrides, e.g. nimble=1")
    args = ap.parse_args()
    workers = dict(DEFAULT_WORKERS)
    for kv in filter(None, args.workers.split(",")):
        k, v = kv.split("=")
        workers[k] = int(v)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    states = scan(args.per_type, args.max_seed, args.scan_workers)
    with open(out / "states.jsonl", "w") as fh:
        for seed, gc in states:
            fh.write(json.dumps(describe_state(seed, gc), ensure_ascii=False) + "\n")
    players = args.players.split(",")
    with cf.ThreadPoolExecutor(len(players)) as pool:
        for f in [pool.submit(run_player, p, states, out, workers.get(p, 2), args.perms) for p in players]:
            f.result()


if __name__ == "__main__":
    main()
