"""Decision makers. A player sees a Decision and returns the index of the option it picks."""
from __future__ import annotations

import dataclasses
import math
import os
import random
import time

import httpx

from . import prompt as P

# Option texts are fitted once, with one tokenizer, so every model sees identical text.
HEAD_BUDGET = 320


@dataclasses.dataclass
class Choice:
    index: int
    scores: dict[str, float] | None = None
    latency_ms: float | None = None
    shortened: bool = False
    votes: list[int] | None = None   # option picked under each order, when several orders were asked


class RandomPlayer:
    name = "random"

    def __init__(self, seed: int):
        self.rng = random.Random(seed)

    def choose(self, d: P.Decision) -> Choice:
        return Choice(self.rng.randrange(len(d.actions)))


class TypedDecisionPlayer:
    """A model-compose typed-decision workflow (laya: choice schema, nimble: enum schema).

    With perms > 1 every decision is asked in several option orders (seeded shuffles paired with
    their reverses) and the option picked most often wins, so a model's preference for a
    position cannot pick the action. Votes, not probabilities: neither family's probabilities
    are calibrated, so averaging them would weigh the models differently. Ties go to the Borda
    count of each order's ranking (scale-free), then to a seeded coin. Each order is its own
    request: nimble renders every field of a schema into one prompt, so batching the orders as
    fields would show them all at once.
    """

    def __init__(self, name: str, url: str, family: str, seed: int, perms: int = 1,
                 timeout: float = 900.0, retries: int = 2):
        self.name, self.url, self.family, self.retries, self.perms = name, url.rstrip("/"), family, retries, perms
        self.rng = random.Random(seed)
        self.client = httpx.Client(timeout=timeout)

    def _orders(self, n: int) -> list[list[int]]:
        """Distinct seeded shuffles, each followed by its reverse. The engine's own order is never
        used as is: it puts End turn last and cards in hand order, so a fixed order (or its
        reverse) would hand a position-biased model the same options every time."""
        orders: list[list[int]] = []
        want = min(self.perms, math.factorial(n))
        while len(orders) < want:
            o = self.rng.sample(range(n), n)
            for cand in (o, o[::-1]):
                if cand not in orders and len(orders) < want:
                    orders.append(cand)
        return orders

    def _ask(self, d: P.Decision, texts: list[str]) -> tuple[str, dict[str, float] | None]:
        payload = P.laya_payload(d, texts) if self.family == "laya" else P.nimble_payload(d, texts)
        for attempt in range(self.retries + 1):
            try:
                r = self.client.post(f"{self.url}/workflows/runs", json={"workflow_id": self.name, "input": payload})
                r.raise_for_status()
                body = r.json()
                if body.get("status") != "completed":
                    raise RuntimeError(f"{self.name}: workflow status {body.get('status')}: {body.get('error')}")
                out = body["output"]
                return out["decision"]["pick"], (out.get("fields") or {}).get("pick", {}).get("scores")
            except (httpx.HTTPError, RuntimeError, KeyError, ValueError):
                if attempt == self.retries:
                    raise
                time.sleep(1.0 * (attempt + 1))
        raise AssertionError("unreachable")

    def choose(self, d: P.Decision) -> Choice:
        texts, shortened = P.fitted_texts(d, HEAD_BUDGET)
        t0 = time.perf_counter()
        if self.perms == 1:
            key, scores = self._ask(d, texts)
            return Choice(d.keys.index(key), scores, (time.perf_counter() - t0) * 1000, shortened)
        n = len(texts)
        votes, borda = [], [0] * n
        for order in self._orders(n):
            key, scores = self._ask(d, [texts[i] for i in order])
            if not scores:
                raise RuntimeError(f"{self.name}: no scores to break vote ties with")
            votes.append(order[d.keys.index(key)])
            ranked = sorted(range(n), key=lambda pos: scores[d.keys[pos]])   # worst first
            for points, pos in enumerate(ranked):
                borda[order[pos]] += points
        count = [votes.count(i) for i in range(n)]
        best = max(count)
        tied = [i for i in range(n) if count[i] == best]
        top = max(borda[i] for i in tied)
        index = self.rng.choice([i for i in tied if borda[i] == top])
        return Choice(index, None, (time.perf_counter() - t0) * 1000, shortened, votes)


# model-compose.yml serves every model as a workflow named after the player.
SERVER = os.environ.get("ARENA_SERVER", "http://127.0.0.1:8080/api")
FAMILIES = {
    "laya-english": "laya", "laya-multilingual": "laya", "laya-typed": "laya", "nimble": "nimble",
    # round 2: the same models fine-tuned on teacher decisions
    "laya-english-ft": "laya", "nimble-ft": "nimble",
}


def make_player(name: str, seed: int, perms: int = 1):
    if name == "random":
        return RandomPlayer(seed)
    return TypedDecisionPlayer(name, SERVER, FAMILIES[name], seed, perms)
