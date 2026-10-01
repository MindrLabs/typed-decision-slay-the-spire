"""Count the Laya decisions whose input the `laya` package cut (README Table 10), from full decision logs.

    .runtime/laya-english/bin/python scripts/laya_input_cuts.py runs/final/laya-english [--max-len 512] [--head 320]
        [--checkpoint typed-decisions | multilingual | MindrLabs/sts-arena-laya-english-ft]

Replays the package's own input builder (`laya.common.build_sequence`) on every logged decision: the
state cut to what fits `max_len`, options cut at 48 tokens, and all options shrunk when they do not
fit `head` together. Needs the seed-N.jsonl logs a run writes, which this repository does not ship
because they quote the game text. Run it with a Laya runtime's Python.
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

from huggingface_hub import snapshot_download
from laya.agent import Agent, _load_tokenizer
from laya.common import render_options, serialize_state

LAYA = ("convaiinnovations/laya", "55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851")
OVERWORLD = "Which option gives the best chance of winning this Slay the Spire run?"
BATTLE = "Which action should the player take now to win this fight while losing as little HP as possible?"


def checkpoint_dir(name: str | None) -> Path:
    if name and "/" in name:
        return Path(snapshot_download(name))
    root = Path(snapshot_download(LAYA[0], revision=LAYA[1]))
    return root / name if name else root


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", type=Path, help="a player's folder of seed-N.jsonl logs")
    ap.add_argument("--checkpoint", help="typed-decisions, multilingual, or a Hugging Face repository (default: english)")
    ap.add_argument("--max-len", type=int, help="model input budget (default: the checkpoint's max_len)")
    ap.add_argument("--head", type=int, default=320, help="question + options budget (head_max_len)")
    args = ap.parse_args()
    d = checkpoint_dir(args.checkpoint)
    cfg = json.loads((d / "rl_agent_config.json").read_text())
    tok = _load_tokenizer(str(d / "tokenizer" if (d / "tokenizer").exists() else d), cfg)
    max_len = args.max_len or cfg.get("max_len", 512)
    n = state_cut = over48 = shrunk = question_cut = 0
    lost: list[float] = []
    for f in sorted(glob.glob(str(args.logs / "seed-*.jsonl"))):
        for line in open(f):
            x = json.loads(line)
            keys = [f"o{i + 1}" for i in range(len(x["options"]))]
            q = Agent._to_internal({"type": "choice", "instructions": BATTLE if x["kind"] == "battle" else OVERWORLD,
                                    "criteria": dict(zip(keys, x["options"]))})
            head_ids = tok("%s question: %s" % (q["t"], q["ins"]), add_special_tokens=False)["input_ids"]
            full = [len(tok(" " + o, add_special_tokens=False)["input_ids"]) for o in render_options(q)]
            opts = [1 + min(48, k) for k in full]
            budget, was_shrunk = args.head - sum(opts), False
            if budget < 16:
                per = max(4, (args.head - 16) // len(opts))
                opts, was_shrunk = [min(per, k) for k in opts], True
                budget = args.head - sum(opts)
            room = max(0, max_len - (3 + min(len(head_ids), max(8, budget)) + sum(opts)) - 1)
            state = len(tok(serialize_state(x["state"]), add_special_tokens=False)["input_ids"])
            n += 1
            over48 += any(k > 48 for k in full)
            shrunk += was_shrunk
            question_cut += len(head_ids) > max(8, budget)
            if state > room:
                state_cut += 1
                lost.append((state - room) / state)
    lost.sort()
    print(json.dumps({"logs": str(args.logs), "max_len": max_len, "head": args.head, "decisions": n,
                      "state_cut": state_cut, "state_lost_median_pct": round(100 * lost[len(lost) // 2], 1) if lost else 0,
                      "state_lost_max_pct": round(100 * lost[-1], 1) if lost else 0,
                      "option_over_48": over48, "options_shrunk": shrunk, "question_cut": question_cut}))


if __name__ == "__main__":
    main()
