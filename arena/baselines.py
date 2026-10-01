"""Reference bots that play whole games with the engine's MCTS in battle.

- mcts-heuristic: C++ out-of-combat heuristic (Agent.pick_gameaction) + MCTS battles.
- heart1: silverbot's heart1.pt policy network out of combat + MCTS battles (the fork's
  strongest bot, ~83% A0 heart kills per its README at 1000 sims).

They do not use the text interface: they are the ceiling the text models are measured against.
"""
from __future__ import annotations

import functools
import random
import threading
import time
from pathlib import Path

import slaythespire as sts

HEART1 = Path(__file__).resolve().parent.parent / "vendor" / "sts_lightspeed" / "runs" / "heart1.pt"
_service_lock = threading.Lock()


@functools.cache
def _heart1_service():
    from silverbot.playouts import NNService, load_net
    net = load_net(str(HEART1), torch_compile_mode="no", use_value_head=True)
    return NNService(net, batch_size=1, batch_size_factor=1, torch_compile_mode="no")


def _heart1_step(gc, agent, rng) -> None:
    """One out-of-combat step exactly as silverbot's watch_game/run_episode decide it (temperature 0)."""
    from silverbot.playouts import choose_overworld_action, construct_choice, take_free_rewards
    take_free_rewards(gc)
    if gc.outcome != sts.GameOutcome.UNDECIDED or gc.screen_state == sts.ScreenState.BATTLE:
        return
    obs = sts.getNNRepresentation(gc)
    actions = sts.GameAction.getAllActionsInState(gc)
    choice = construct_choice(gc, obs, actions)
    total = 0 if choice is None else (len(choice.cards_offered) + len(choice.relics_offered) +
                                      len(choice.potions_offered) + len(choice.fixed_actions) +
                                      len(choice.paths_offered))
    if choice is not None and total > 1:
        with _service_lock:
            service = _heart1_service()
        action, *_ = choose_overworld_action(service, choice, gc, rng, temperature=0)
    else:
        action = agent.pick_gameaction(gc)
    action.execute(gc)


def play_baseline_game(seed: int, kind: str, ascension: int = 0, mcts_sims: int = 1000) -> dict:
    gc = sts.GameContext(sts.CharacterClass.IRONCLAD, seed, ascension)
    agent = sts.Agent()
    agent.simulation_count_base = mcts_sims
    agent.verbosity_level = 0
    rng = random.Random(seed)
    t0 = time.perf_counter()
    while gc.outcome == sts.GameOutcome.UNDECIDED:
        if gc.screen_state == sts.ScreenState.BATTLE:
            agent.playout_battle(gc)
        elif kind == "heart1":
            _heart1_step(gc, agent, rng)
        else:
            agent.pick_gameaction(gc).execute(gc)
    return {
        "player": kind, "seed": seed, "ascension": ascension, "mcts_sims": mcts_sims,
        "outcome": gc.outcome.name, "floor": gc.floor_num, "act": gc.act, "hp": gc.cur_hp,
        "seconds": round(time.perf_counter() - t0, 2),
    }
