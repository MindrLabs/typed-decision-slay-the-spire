"""Run a (players x seeds) matrix, resumably: seeds already in <out>/<player>/games.jsonl are skipped.

    uv run python -m arena.bench --players random,laya-english,nimble,mcts-heuristic --seeds 1-10 --out runs/trial

Each player gets its own thread pool. The engine releases the GIL during MCTS and model calls
are HTTP, so threads are enough; the model servers themselves serialize GPU work.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import threading
import traceback
from pathlib import Path

from . import prompt as P
from .baselines import play_baseline_game
from .run import _seeds, play_game

BASELINES = {"mcts-heuristic", "heart1"}
DEFAULT_WORKERS = {"random": 4, "laya-english": 3, "laya-multilingual": 3, "laya-typed": 3,
                   "nimble": 2, "laya-english-ft": 3, "nimble-ft": 2, "mcts-heuristic": 4, "heart1": 4}


def _done(out_dir: Path) -> set[int]:
    games = out_dir / "games.jsonl"
    if not games.exists():
        return set()
    return {json.loads(line)["seed"] for line in games.read_text().splitlines() if line.strip()}


def run_player(player: str, seeds: list[int], out: Path, workers: int, ascension: int, mcts_sims: int,
               perms: int, power_notes: bool, wording: str) -> None:
    out_dir = out / player
    out_dir.mkdir(parents=True, exist_ok=True)
    todo = [s for s in seeds if s not in _done(out_dir)]
    print(f"[{player}] {len(seeds) - len(todo)} done, {len(todo)} to play, {workers} workers", flush=True)
    lock = threading.Lock()

    def one(seed: int) -> None:
        try:
            if player in BASELINES:
                summary = play_baseline_game(seed, player, ascension, mcts_sims)
            else:
                summary = play_game(seed, player, out_dir, ascension, perms, power_notes, wording)
        except Exception as e:
            with lock, open(out_dir / "errors.jsonl", "a") as fh:
                fh.write(json.dumps({"seed": seed, "error": repr(e), "trace": traceback.format_exc()}) + "\n")
            print(f"[{player}] seed {seed} ERROR {e!r}", flush=True)
            return
        with lock, open(out_dir / "games.jsonl", "a") as fh:
            fh.write(json.dumps(summary) + "\n")
        print(f"[{player}] {json.dumps(summary)}", flush=True)

    with cf.ThreadPoolExecutor(workers, thread_name_prefix=player) as pool:
        list(pool.map(one, todo))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--players", required=True, help="comma list")
    ap.add_argument("--seeds", required=True, help="e.g. 1-200")
    ap.add_argument("--out", required=True)
    ap.add_argument("--ascension", type=int, default=0)
    ap.add_argument("--mcts-sims", type=int, default=1000, help="baselines only")
    ap.add_argument("--perms", type=int, default=1, help="text players: option orders per decision, majority vote")
    ap.add_argument("--power-notes", action="store_true", help="text players: explain enemy powers in battle")
    ap.add_argument("--wording", choices=sorted(P.INSTRUCTIONS), default="main",
                    help="text players: wording of the two questions")
    ap.add_argument("--workers", default="", help="overrides, e.g. nimble=1,heart1=8")
    args = ap.parse_args()
    workers = dict(DEFAULT_WORKERS)
    for kv in filter(None, args.workers.split(",")):
        k, v = kv.split("=")
        workers[k] = int(v)
    seeds, out = _seeds(args.seeds), Path(args.out)
    players = args.players.split(",")
    # Players run side by side so the CPU-bound baselines overlap with the GPU-bound models.
    with cf.ThreadPoolExecutor(len(players)) as pool:
        futures = [pool.submit(run_player, p, seeds, out, workers.get(p, 2), args.ascension, args.mcts_sims,
                               args.perms, args.power_notes, args.wording)
                   for p in players]
        for f in futures:
            f.result()


if __name__ == "__main__":
    main()
