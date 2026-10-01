"""Build one decision (state text + deduplicated options) and render it for each model family."""
from __future__ import annotations

import dataclasses
import functools
import threading

import slaythespire as sts

from . import describe as D

OVERWORLD_INSTRUCTIONS = "Which option gives the best chance of winning this Slay the Spire run?"
BATTLE_INSTRUCTIONS = "Which action should the player take now to win this fight while losing as little HP as possible?"
# The same two questions in other words, to check that the models' ranking does not hinge on the
# wording (bench --wording alt). Only the question changes: state and options stay as they are, and
# each version has as many ModernBERT tokens as the original (16 and 19), so options are shortened
# for the same decisions.
INSTRUCTIONS = {
    "main": {"overworld": OVERWORLD_INSTRUCTIONS, "battle": BATTLE_INSTRUCTIONS},
    "alt": {"overworld": "Pick the option that makes winning this Slay the Spire run most likely.",
            "battle": "Choose the move that wins this combat and keeps as much of the player's HP as possible."},
}


@dataclasses.dataclass
class Decision:
    kind: str                 # "overworld" | "battle"
    screen: str               # e.g. REWARDS, MAP_SCREEN, BATTLE
    state: str
    instructions: str
    actions: list             # one engine action per option (duplicates already dropped)
    texts: list[str]          # full option text
    labels: list[str]         # short option text, used when the full texts do not fit the budget
    dropped_duplicates: int = 0

    @property
    def keys(self) -> list[str]:
        return [f"o{i + 1}" for i in range(len(self.actions))]


def _short(text: str) -> str:
    """'Take card Pommel Strike+ [1 Attack]: Deal 10 damage.' -> 'Take card Pommel Strike+ [1 Attack]'."""
    head, sep, _ = text.partition(": ")
    return head if sep else text


def _decision(kind, screen, state, instructions, actions, texts) -> Decision:
    seen: dict[str, int] = {}
    keep_actions, keep_texts = [], []
    for a, t in zip(actions, texts):
        if t in seen:
            continue
        seen[t] = len(keep_texts)
        keep_actions.append(a)
        keep_texts.append(t)
    return Decision(kind, screen, state, instructions, keep_actions, keep_texts,
                    [_short(t) for t in keep_texts], len(texts) - len(keep_texts))


def overworld_decision(gc, wording: str = "main") -> Decision:
    actions = sts.GameAction.getAllActionsInState(gc)
    texts = [D.describe_option(gc, a) for a in actions]
    state = D.screen_context(gc) + "\n" + D.run_header(gc)
    return _decision("overworld", D._name(gc.screen_state), state, INSTRUCTIONS[wording]["overworld"], actions, texts)


def battle_decision(bc, gc, power_notes: bool = False, wording: str = "main") -> Decision:
    actions = sts.Action.enumerate_actions(bc)
    texts = [D.describe_battle_action(bc, a) for a in actions]
    lines = [D.battle_state(bc, power_notes)]
    if D._name(bc.input_state) == "CARD_SELECT":
        lines.insert(0, D.battle_select_context(bc))
    lines.append(f"Relics: {', '.join(D.relic_label(r.id) for r in gc.relics) or 'none'}.")
    return _decision("battle", "BATTLE", "\n".join(lines), INSTRUCTIONS[wording]["battle"], actions, texts)


# --- rendering ----------------------------------------------------------------

_tokenizer_lock = threading.Lock()


@functools.cache
def _load_tokenizer(name: str):
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(name)


def _tokenizer(name: str):
    # bench threads hit this together on their first decision; transformers' lazy import is
    # not thread-safe ("cannot import name 'AutoTokenizer'"), so load under a lock.
    with _tokenizer_lock:
        return _load_tokenizer(name)


def option_tokens(d: Decision, texts: list[str], tokenizer: str = "answerdotai/ModernBERT-large") -> int:
    tok = _tokenizer(tokenizer)
    body = d.instructions + " " + " ".join(f"{k}: {t}" for k, t in zip(d.keys, texts))
    return len(tok(body, add_special_tokens=False)["input_ids"])


def fitted_texts(d: Decision, budget: int | None) -> tuple[list[str], bool]:
    """Full option texts when they fit `budget` tokens (question head), else the short labels."""
    if budget is None or option_tokens(d, d.texts) <= budget:
        return d.texts, False
    return d.labels, True


def laya_payload(d: Decision, texts: list[str]) -> dict:
    return {"text": d.state, "schema": {"pick": {
        "type": "choice", "instructions": d.instructions,
        "criteria": dict(zip(d.keys, texts))}}}


def nimble_payload(d: Decision, texts: list[str]) -> dict:
    return {"text": d.state, "schema": {"pick": {
        "type": "enum", "choices": d.keys, "description": d.instructions,
        "choice_descriptions": dict(zip(d.keys, texts))}}}
