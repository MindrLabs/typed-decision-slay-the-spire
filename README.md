[English](README.md) · [한국어](README.ko.md) · [中文](README.zh-cn.md)

# typed-decision-slay-the-spire

This repository has a typed-decision model make every choice of a Slay the Spire run on a headless simulator, from the opening blessing and card rewards to each card played in combat.

We served Bespoke Nimble-9B and three Convai Laya checkpoints with model-compose on an NVIDIA DGX Spark and had each play the same 200 seeds as the Ironclad at ascension 0, reading identical text. We compared them twice: zero-shot, and after fine-tuning Nimble-9B and Laya english once on the same decisions of a search bot. Both rounds and their analyses were pre-registered before they ran. Every number comes from the runs; nothing was judged by hand. We measured on the DGX Spark only.

A follow-up on the potions the fine-tuned models left unused was not pre-registered and is reported as exploratory in section 3.6.

## Contents

- [Quick Start](#quick-start)
- [Summary](#summary)
- [1 Setup](#1-setup)
- [2 What it takes to run](#2-what-it-takes-to-run)
- [3 Results](#3-results)
  - [3.1 How far each model gets](#31-how-far-each-model-gets)
  - [3.2 Does the model read the options?](#32-does-the-model-read-the-options)
  - [3.3 The same elite fight](#33-the-same-elite-fight)
  - [3.4 Rewording the question](#34-rewording-the-question)
  - [3.5 After fine-tuning](#35-after-fine-tuning)
  - [3.6 Potions, outside the pre-registration](#36-potions-outside-the-pre-registration)
- [4 Recommendations](#4-recommendations)
- [5 Limitations and what we did not measure](#5-limitations-and-what-we-did-not-measure)
  - [What the intervals cover](#what-the-intervals-cover)
  - [Changes from the pre-registration](#changes-from-the-pre-registration)
  - [How much the software environment matters](#how-much-the-software-environment-matters)
  - [What the models could not read](#what-the-models-could-not-read)
  - [Other limitations](#other-limitations)
- [License](#license)

## Models

A typed-decision model takes a text and a list of allowed answers and returns one of them, with a probability for each. It never writes free text, so it cannot answer outside the list.

| Player | Model | Size | How it picks |
|---|---|---|---|
| `nimble` | [`bespokelabs/Bespoke-Nimble-9B`](https://huggingface.co/bespokelabs/Bespoke-Nimble-9B), a LoRA adapter on [`Qwen/Qwen3.5-9B`](https://huggingface.co/Qwen/Qwen3.5-9B) | 9B | Reads the answer letters' logits from a language model |
| `laya-english` | [`convaiinnovations/laya`](https://huggingface.co/convaiinnovations/laya), english checkpoint | 421M | Encoder (ModernBERT-large) with a choice head |
| `laya-typed` | the same repository, typed-decisions checkpoint (english, fine-tuned by Convai on four business workflows) | 421M | Same |
| `laya-multilingual` | the same repository, multilingual checkpoint | 322M | Same |
| `nimble-ft` | [`MindrLabs/sts-arena-nimble-ft`](https://huggingface.co/MindrLabs/sts-arena-nimble-ft): Nimble-9B's adapter trained one more epoch on this game | 9B | Same as Nimble-9B |
| `laya-english-ft` | [`MindrLabs/sts-arena-laya-english-ft`](https://huggingface.co/MindrLabs/sts-arena-laya-english-ft): Laya english fully fine-tuned for one epoch on this game | 421M | Same as Laya english |
| `laya-english-ft4` | [`MindrLabs/sts-arena-laya-english-ft4`](https://huggingface.co/MindrLabs/sts-arena-laya-english-ft4): Laya english trained further on its own play, with potions asked as a separate question (section 3.6) | 421M | Same as Laya english; play it with `--potion-step` |
| `nimble-ft4` | [`MindrLabs/sts-arena-nimble-ft4`](https://huggingface.co/MindrLabs/sts-arena-nimble-ft4): Nimble-9B's round-2 adapter trained further on those states (section 3.6) | 9B | Same as Nimble-9B; play it with `--potion-step` |

## Demo

![Nimble-9B and Laya english playing the same seed side by side in the real game, with each model's current options and votes below](docs/images/shared/arena-demo.gif)

A live demo in the real game, separate from the benchmark: Nimble-9B (left) and Laya english (right) on the same seed, both at the act 1 boss. Below each game are the options of the current decision and how many of the 4 option orders picked each.

## Quick Start

It needs [model-compose](https://github.com/hanyeol/model-compose) 0.4.113 or later, [uv](https://docs.astral.sh/uv/), CMake 3.19+ and a C++20 compiler. We ran it on Linux with an NVIDIA GPU (DGX Spark).

Install model-compose with uv:

```bash
uv pip install model-compose
```

Or with pip:

```bash
pip install model-compose
```

Clone this repository and prepare it:

```bash
git clone https://github.com/MindrLabs/typed-decision-slay-the-spire
cd typed-decision-slay-the-spire
scripts/fetch-game-text.sh      # the game text the models read, into data/sts1
scripts/setup-simulator.sh      # builds the simulator and the runner's .venv
scripts/setup-runtimes.sh       # the model runtimes, with the packages the published runs used
```

Start the models:

```bash
model-compose up
```

In a second terminal, have a model play seed 1:

```bash
uv run python -m arena.run --player nimble --seeds 1 --perms 4
```

The run writes `runs/nimble/games.jsonl` (one line per game: floor, outcome, decision count) and `runs/nimble/seed-1.jsonl` (every decision: the state and options the model read, its pick in each option order, and the majority pick). `--player` takes any name in the [Models](#models) table, or `random`. `--perms 4` is the pre-registered setting: each decision is asked in 4 option orders and the majority wins. Leave it out to ask once in the simulator's order.

The gradio interface opens on `http://localhost:8081` and the HTTP API on `http://localhost:8080/api`.
`SERVER_PORT` and `PORT` change each port; the runner reads the API address from `ARENA_SERVER`.

| On the first run | What happens |
| :---: | --- |
| Game text | `fetch-game-text.sh` downloads five files (cards, relics, potions, events, monsters) from [spire-archive](https://github.com/nkhoit/spire-archive) at `687e6dce` and checks their sha256. The text belongs to the game, so this repository does not include it |
| Simulator | `setup-simulator.sh` clones [sts_lightspeed](https://github.com/daniel-ziegler/sts_lightspeed) at `84ab3ead`, applies the five commits in `patches/sts_dz`, creates the runner's `.venv` with uv, and builds the `slaythespire` Python module into it |
| Virtual environments | `setup-runtimes.sh` builds one environment per model under `.runtime/` from `runtimes/nimble.txt` and `runtimes/laya.txt`, pinned by version and wheel hash (torch 2.14.0 for both). `scripts/env-report.sh` prints the GPU, driver and packages to report with a rerun |
| Checkpoints | Each model loads on its first request. Nimble-9B downloads its adapter (0.19 GB) and `Qwen/Qwen3.5-9B` (19.3 GB) and merges them once into `~/.cache/models/nimble-merged` (18.8 GB). The three Laya models share `convaiinnovations/laya` (2.4 GB). The fine-tuned models download `MindrLabs/sts-arena-nimble-ft` (1.3 GB, two training checkpoints included), merged onto the same base into another 18.8 GB, and `MindrLabs/sts-arena-laya-english-ft` (1.7 GB). No token is needed; `HF_TOKEN` only raises the download rate limit |

The two search bots in the results play without a model server:

```bash
scripts/setup-simulator.sh --heart1      # downloads heart1's checkpoint (23 MB)
uv run --extra baselines python -m arena.bench --players mcts-heuristic,heart1 --seeds 1-200 --out runs/main
```

To rerun a whole round, or to recompute every table and figure below from the files in `results/`:

```bash
uv run python -m arena.bench --players nimble,laya-english,laya-typed,laya-multilingual \
  --seeds 1-200 --perms 4 --workers nimble=4 --out runs/final
uv run python scripts/stats.py results/final --refs results/main --single results/main \
  --wording results/wording --elite results/elite --latency results/latency --out reports/round1
uv run python scripts/stats_round2.py --out reports/round2
uv run python scripts/sensitivity.py
uv run python scripts/charts.py
uv run python scripts/stats_potion.py          # section 3.6
```

Example request:

```bash
curl localhost:8080/api/workflows/runs -H 'Content-Type: application/json' -d '{
  "workflow_id": "nimble",
  "input": {
    "text": "Floor 5, campfire. HP 31/80. Next floor: an elite fight.",
    "schema": {"pick": {"type": "enum", "choices": ["A", "B"],
      "description": "Which option gives the best chance of winning this Slay the Spire run?",
      "choice_descriptions": {"A": "Rest: heal 24 HP.", "B": "Smith: upgrade Bash."}}}
  }
}'
```

It returns `{"decision": {"pick": "A"}, "fields": {"pick": {"scores": {"A": 0.62, "B": 0.38}}}}`. The Laya workflows take the same question as `{"type": "choice", "instructions": ..., "criteria": {"A": ..., "B": ...}}`.

## Summary

1. Without training, Nimble-9B climbed higher than every Laya model: a mean of floor 14.1, against 10.4 for Laya english, 10.6 for typed-decisions and 2.4 for multilingual. On the same seed it beat Laya english 128 times, tied 36 and lost 36. No text model won a run. The search bot heart1 averaged floor 53 and won 165 of 200.
2. Nimble-9B reads the options more. Asked the same decision with the options in 4 different orders, it picked the same action every time in 57% of decisions; Laya english did in 20%, typed-decisions in 26% and multilingual in 3%. Taking the majority over the 4 orders raised Nimble-9B by 1.2 floors, left Laya english and typed-decisions where they were, and dropped multilingual from 5.8 to 2.4: its earlier score came from favouring the first options.
3. Put in the same act 1 elite fight with the same deck, Nimble-9B and Laya english won about equally often (84 and 80 of 90). The gap between them builds up over a run's other choices, not inside one fight.
4. Fine-tuned once on the same 39,884 decisions of the search bot, Laya english rose 6.7 floors (10.4 to 17.1) and Nimble-9B 5.4 (14.1 to 19.5). Fine-tuned Nimble-9B still led by 2.4 floors, but it also trained 17 times longer (7.9 h against 0.5 h), so that lead mixes the model with its training budget. Both then picked the same action in every order in about 80% of decisions. Neither won a run.
5. Laya answers in a sixth of the time and memory: 24 ms per request and about 3 GB on the DGX Spark, against 146 ms and 19 GB for Nimble-9B.
6. *(exploratory)* The fine-tuned models still died with potions unused. Training Laya english further on its own play, with potions asked as a separate question, raised its mean floor on 50 check seeds from 16.7 to 28.7 and cut the lost games that ended with a usable potion from 98% to 30%; Nimble-9B went from 20.5 to 26.6, with 16% of its lost games ending that way. In the real game Nimble-9B beat the act 3 boss once in 8 matches. Section 3.6 says what this does not show.

Table 1: Summary by model (200 seeds each, 4 option orders per decision)

| Model | Mean floor, zero-shot | Mean floor, fine-tuned | Same pick in all 4 orders, zero-shot → fine-tuned | Per request | GPU memory |
|---|---|---|---|---|---|
| Nimble-9B | 14.1 | 19.5 | 57% → 78% | 146 ms | 19 GB |
| Laya english | 10.4 | 17.1 | 20% → 80% | 24 ms | about 3 GB |
| Laya typed-decisions | 10.6 | Not trained | 26% | 24 ms | about 3 GB |
| Laya multilingual | 2.4 | Not trained | 3% | 14 ms | about 3 GB |
| For reference: heart1 (search bot) | 53.2, 165 wins | | | | |

## 1 Setup

Table 2: Device and software

| Item | Value |
|---|---|
| Device | NVIDIA DGX Spark: GB10, driver 580.126.09, CUDA 13.0, 128 GB unified memory. Shared with other jobs |
| Model server | model-compose `e8ce0d4b` (round 1) and the same plus local commit `3f31d447` (round 2). This repository runs the same models with model-compose 0.4.113 from PyPI |
| Model runtimes | torch 2.14.0 for both families; Nimble-9B with flash-linear-attention 0.5.2, Laya with `laya` 0.3.20 (`runtimes/*.txt`) |
| Weights | Nimble-9B adapter `bd792f44` on `Qwen/Qwen3.5-9B` `c2022362`; Laya `55cf4c4e` (model-compose does not take a Laya revision, so it is recorded, not pinned) |
| Simulator | sts_lightspeed, Daniel Ziegler's fork of gamerpuppy's C++ reimplementation of Slay the Spire, at `84ab3ead` plus five commits that expose more game state to Python |
| Runs | Ironclad, ascension 0, seeds 1-200 for every player |

- **What the model reads.** Each decision is a text state (floor, HP, gold, deck, relics, potions; in combat also the hand, energy, and each enemy's HP, intent and powers) and a list of options written as sentences, with card, relic and event descriptions taken from the game text. Every model gets the same text. Option texts are fitted once with the ModernBERT tokenizer to 320 tokens; 1.6% of decisions had an option shortened.
- **What the model decides.** Everything, in and out of combat: the opening blessing, map path, card rewards, shop, campfire, events and each card or potion in a fight. The one exception is Match and Keep, a memory minigame with no option to describe, which the simulator's heuristic plays. Decisions with a single option are taken automatically.
- **4 option orders.** Each decision with 3 or more options is asked in 4 orders (two seeded shuffles and their reverses; 2 orders when there are only 2 options) and the action picked most often is played. Ties go to the sum of each order's ranking, then to a seeded coin. A model that picks by position rather than content then cannot steer the game. The 4 orders cancel a steady preference for early or late positions, but they do not put every option in every position, as averaging over all rotations would.
- **Reference players.** heart1 (silverbot's policy network out of combat, the simulator's battle search in combat) and mcts-heuristic (the simulator's heuristic and battle search) play the same seeds without reading any text. Their search samples the cards still to be drawn and other random outcomes instead of reading them. They are a ceiling for scale, not competitors. random picks uniformly.
- **Exploratory analyses.** Analyses that are not in the pre-registration are marked *(exploratory)*.
- **Pre-registration.** The models, seeds, settings, primary comparisons and statistics were published before each round ran: [round 1](https://gist.github.com/kecan0406/5816965b9711d07509ab91c291dda7d7), [round 2](https://gist.github.com/kecan0406/aa20d9488e25d78ee508e2fe525d4c4d). Floors are compared seed by seed with a paired bootstrap (10,000 resamples) and a Wilcoxon test, Holm-corrected over each round's three primary comparisons.

The published decisions replay exactly with this repository. On seed 1, every decision of the four zero-shot models came out the same (Nimble-9B 207, Laya english 134, typed-decisions 124, multilingual 13), and so did every decision of the two fine-tuned models (Nimble-9B 274, Laya english 368, downloaded from Hugging Face); both search bots ended on the same floor. That needs `setup-runtimes.sh`: without it, model-compose installs newer packages, and while Laya english still matched, Nimble-9B's scores moved in the third decimal place, a near-tie vote flipped at decision 13, and the game went another way. Over 50 seeds the averages and the ranking stayed the same (Table 9).

## 2 What it takes to run

Table 3: Time per decision on the DGX Spark (one model loaded at a time, 500 decisions replayed from the published games)

| Model | Per request, median / p95 | Per decision (4 orders), median / p95 | GPU memory |
|---|---|---|---|
| Nimble-9B | 146 / 187 ms | 581 / 739 ms | 19 GB |
| Nimble-9B, fine-tuned | 172 / 235 ms | 681 / 934 ms | 19 GB |
| Laya english | 24 / 29 ms | 96 / 117 ms | about 3 GB |
| Laya english, fine-tuned | 27 / 49 ms | 111 / 168 ms | about 3 GB |
| Laya typed-decisions | 24 / 30 ms | 97 / 123 ms | about 3 GB |
| Laya multilingual | 14 / 39 ms | 56 / 108 ms | about 3 GB |

- For reference, Convai's model card gives 39.5 ms for Laya english and 32.8 ms for multilingual per question on a T4 GPU. Bespoke's card gives no latency.
- One game of seed 1 took 20 s with Laya english (134 decisions) and about 2 minutes with Nimble-9B (207 decisions), not counting loading the model.
- A decision is up to 4 requests, one per option order, so it takes about 4 times a request.
- The fine-tuned models are slower per request because they reach deeper floors, where the state text is longer.
- Models loaded side by side share the GPU badly when busy. Nimble-9B went from 0.15 s to about 0.4 s per request while three Laya models were also busy, and Laya from 24 ms to about 250 ms next to a busy Nimble-9B. Run one model family at a time for long runs; the results do not depend on it.
- The first request to Nimble-9B after `model-compose up` waits for the model to load (about 1-2 minutes with the merged weights cached; the first merge also downloads 19.5 GB).

## 3 Results

Table 4: Results by question

| Question | Result |
|---|---|
| Which model gets further without training? | Nimble-9B, by 3.5 to 11.7 floors on average. Every Laya model trails it on the same seeds |
| Does the model read what the options say? | Nimble-9B mostly does: 57% of decisions get the same pick in all 4 orders. Laya english and typed-decisions do far less (20%, 26%), and multilingual picks by position (3%) |
| Where does the gap come from? | From the run as a whole. In the same elite fight with the same deck the two are about even |
| Does the ranking hold if the question is reworded? | Nimble-9B stays first. Laya typed-decisions loses its lead over english, and the two tie |
| How much does one round of fine-tuning help? | 5 to 7 floors for both. The smaller Laya gains more, Nimble-9B stays ahead |
| *(exploratory)* Can the fine-tuned models learn to use potions? | Mostly. Lost games that ended with a usable potion fell from 98% to 30% (Laya english) and 16% (Nimble-9B). Which change did it is not known |

### 3.1 How far each model gets

Table 5: Floor reached on seeds 1-200 (4 option orders, majority vote)

| Player | Mean floor ± SE | Cleared act 1 [95% CI] | Wins | Nimble-9B higher / same / lower | Mean difference, Nimble-9B − this [95% CI] |
|---|---|---|---|---|---|
| Nimble-9B | 14.12 ± 0.35 | 31 (15.5% [11.1, 21.2]) | 0 | | |
| Laya english | 10.45 ± 0.30 | 8 (4.0% [2.0, 7.7]) | 0 | 128 / 36 / 36 | +3.67 [+2.90, +4.46] |
| Laya typed-decisions | 10.64 ± 0.34 | 14 (7.0% [4.2, 11.4]) | 0 | 136 / 25 / 39 | +3.48 [+2.62, +4.31] |
| Laya multilingual | 2.39 ± 0.14 | 0 (0.0% [0.0, 1.9]) | 0 | 198 / 0 / 2 | +11.73 [+10.99, +12.47] |
| heart1 (search bot) | 53.24 ± 0.48 | 197 (98.5%) | 165 | | |
| mcts-heuristic (search bot) | 32.39 ± 0.81 | 174 (87.0%) | 20 | | |
| random | 3.56 ± 0.17 | 0 | 0 | | |

All three primary comparisons have Holm-corrected p < 0.0001. Nimble-9B's runs end most often at the act 1 boss (The Guardian 31, Hexaghost 31); Laya english's and typed-decisions' most often at an act 1 elite (Lagavulin 26 and 19, Gremlin Nob 22 and 16, 3 Sentries 20 and 17).

![Share of runs that reached each floor for the four models and three reference players](docs/images/en/survival-round1.png)

Figure 1 (DGX Spark): Share of the 200 runs that reached each floor. Act 1 ends at floor 16.

![Nimble-9B against each Laya model, seed by seed: higher, same floor, lower](docs/images/en/head-to-head.png)

Figure 2 (DGX Spark): Nimble-9B against each Laya model on the same seed.

### 3.2 Does the model read the options?

![Share of decisions where all 4 option orders picked the same action, per model](docs/images/en/consistency.png)

Figure 3 (DGX Spark): Decisions asked in 4 option orders where all 4 picked the same action. Hatched bars are the fine-tuned models (Section 3.5).

A model that reads the options picks the same action whatever their order. Laya english and typed-decisions agree with themselves in a fifth to a quarter of decisions, and multilingual almost never: it picks by where an option sits.

Table 6: Asking once in the simulator's order against the majority of 4 orders (same 200 seeds)

| Model | One order | Majority of 4 | Difference [95% CI] |
|---|---|---|---|
| Nimble-9B | 12.89 | 14.12 | +1.23 [+0.45, +2.04] |
| Laya english | 10.44 | 10.45 | +0.01 [-0.68, +0.69] |
| Laya typed-decisions | 10.35 | 10.64 | +0.30 [-0.32, +0.92] |
| Laya multilingual | 5.79 | 2.39 | -3.40 [-3.95, -2.88] |

In the simulator's own order the first options in a fight are often attack cards such as Bash, so a model that leans towards early options does better there than its reading deserves. The vote removes that, which is why multilingual falls.

### 3.3 The same elite fight

We copied 90 act 1 elite fights (30 each of Gremlin Nob, Lagavulin and 3 Sentries) from mcts-heuristic's runs, with its deck, relics and potions, and had every player fight each one from the same state.

![Share of the 90 elite fights won by each player, with 95% intervals](docs/images/en/elite.png)

Figure 4 (DGX Spark): Elite fights won out of 90, with Wilson 95% intervals.

| Against Nimble-9B | Fights won only by Nimble-9B / only by this | McNemar p | HP left, difference [95% CI] |
|---|---|---|---|
| Laya english | 7 / 3 | 0.344 | +2.5 [-1.1, +5.9] |
| Laya typed-decisions | 13 / 2 | 0.0074 | +6.5 [+2.7, +10.3] |
| Laya multilingual | 76 / 0 | <0.0001 | +36.7 [+32.1, +41.3] |

With a good deck, Nimble-9B (84 of 90) and Laya english (80) win about equally. Yet Laya english's runs end at elites more often (Section 3.1). The gap builds up in the choices before the fight: the cards taken, the path and the HP kept. This reading is exploratory, not pre-registered.

### 3.4 Rewording the question

On seeds 1-50, the two questions the models are asked ("Which option gives the best chance of winning this Slay the Spire run?" and the battle one) were replaced by sentences with the same meaning and the same token count.

| Model | Original | Reworded | Difference [95% CI] |
|---|---|---|---|
| Nimble-9B | 13.74 | 13.32 | -0.42 [-1.72, +0.88] |
| Laya english | 10.48 | 10.26 | -0.22 [-1.44, +1.04] |
| Laya typed-decisions | 11.34 | 10.26 | -1.08 [-2.08, -0.10] |
| Laya multilingual | 2.86 | 2.72 | -0.14 [-0.62, +0.32] |

Nimble-9B stays first and ahead of each Laya model. The pre-registered check (the same order of all four models) fails, because Laya typed-decisions and english tie after the rewording.

### 3.5 After fine-tuning

The data are the decisions of heart1, the strongest reference player, on the states each model actually reaches: games played by heart1 (seeds 1001-1025), by zero-shot Laya english (1101-1265) and by zero-shot Nimble-9B (1301-1365), each decision labelled with heart1's move. That gave 39,884 training decisions; both models trained on exactly the same examples with the same option orders. Each model was trained once for one epoch with its maker's published settings and no search: Laya english as a full fine-tune (learning rate 2e-5), Nimble-9B by training its released LoRA adapter further with Bespoke's own trainer (learning rate 5e-5). None of these seeds is an evaluation seed.

Table 7: Fine-tuned against zero-shot, seeds 1-200

| Comparison | Higher / same / lower | Mean difference [95% CI] | Holm p |
|---|---|---|---|
| Laya english, fine-tuned vs zero-shot | 146 / 27 / 27 | +6.66 [+5.65, +7.70] | <0.0001 |
| Nimble-9B, fine-tuned vs zero-shot | 126 / 30 / 44 | +5.37 [+4.14, +6.57] | <0.0001 |
| Nimble-9B, fine-tuned vs Laya english, fine-tuned | 89 / 46 / 65 | +2.39 [+1.23, +3.54] | 0.0002 |

![Share of runs that reached each floor, fine-tuned against zero-shot](docs/images/en/survival-round2.png)

Figure 5 (DGX Spark): Share of runs that reached each floor. Solid lines are fine-tuned, dashed lines zero-shot.

| Model | Agreement with heart1 on held-out decisions, before → after | Training time | Cleared act 1 |
|---|---|---|---|
| Laya english | 0.255 → 0.573 | 0.46 h | 8 → 71 of 200 |
| Nimble-9B | 0.337 → 0.599 | 7.94 h | 31 → 100 of 200 |

Nimble-9B's training took 17 times as long as Laya english's on the same DGX Spark, so the 2.4-floor lead between the fine-tuned models reflects both the model and that budget. Each model was trained once; how far the result moves with another training run is not in the intervals.

- Half of fine-tuned Nimble-9B's runs pass act 1, and its best run reached floor 50. heart1 averages 53.
- *(exploratory)* Both fine-tuned models take the gold and relic of every reward screen. Zero-shot, Nimble-9B took the gold 77% of the time and Laya english 29%.

### 3.6 Potions, outside the pre-registration

*(exploratory; the full account is in [docs/potion-round.md](docs/potion-round.md))*

After round 2 both fine-tuned models took every reward and bought in shops, but 98% of the games each lost ended with a potion they could still have used. They used 0.3 to 0.6 potions a game; heart1, whose moves they learned, uses about 10. The training data had few examples of drinking (heart1 drank in 2.8% of the battle decisions that offered a potion), the models could not tell when to, and the majority over 4 orders dropped the votes for a potion that remained.

We changed four things: potions are asked about on their own at the start of each turn (`--potion-step`), the fight's kind and floor are in the state, the training target is half heart1's move and half its search distribution, and the models were trained further on the states they reach themselves (two rounds of DAgger: the model plays, heart1 labels every state). Laya english was trained twice that way (FT3, FT4) and Nimble-9B once, on the same states (FT4). The registered runs are untouched.

Table 7a: Check games, seeds 201-250 (4 option orders, potion step on for FT3 and FT4)

| Player | Mean floor | Same-seed difference [95% CI] | Potions per game | Lost games with a usable potion left | Wins | Check |
|---|---|---|---|---|---|---|
| Laya english, round 2 (start) | 16.7 | | 0.30 | 98% | 0 | |
| Laya english FT3 (round A) | 23.5 | +6.8 [+4.1, +9.6] | 3.72 | 74% | 0 | not passed |
| **Laya english FT4** (round B) | **28.7** | **+12.0 [+8.5, +15.7]** | **6.04** | **30%** | **3** | **passed** |
| Nimble-9B, round 2 (start) | 20.5 | | 0.58 | 98% | 0 | |
| **Nimble-9B FT4** | **26.6** | **+6.1 [+2.6, +9.6]** | **6.16** | **16%** | 0 | not passed |

The check was fixed before any of these games: potions per game at least 3, lost games with a usable potion left at most 50%, mean floor not lower, no relic or gold left behind, shop purchase rate no more than 10 points lower. FT3 missed the potion share and left one relic behind. Nimble-9B FT4 met every part but one: on seed 212 it left the relic Smiling Mask behind. We report it as not passed. `scripts/stats_potion.py` recomputes this table, and the columns not shown here, from `results/potion`.

Table 7b: Real game, seeds 1-8, `nimble-ft4` against `laya-english-ft4` (potion step on; 1 draw)

| | Mean floor | Wins | Matches won | Potions per game | Lost games with a usable potion left | Reward screens left with a relic or gold |
|---|---|---|---|---|---|---|
| Nimble-9B FT4 | 29.9 | 1 (seed 5, floor 51, act 3 boss) | 6 | 6.1 | 1 of 7 | 0 |
| Laya english FT4 | 23.6 | 0 | 1 | 4.9 | 3 of 8 | 0 |

- **What it shows**: Training on the models' own states, with the search bot's distribution as the target, took away most of the unused potions and raised the mean floor by 12.0 (Laya english) and 6.1 (Nimble-9B) on the same seeds. In the real game both kept taking every reward and shop item, and Nimble-9B FT4 beat the act 3 boss once, the only win in any of our live matches.
- **What it does not show**: which change did it. The potion step, the fight line, the visit targets and the extra rounds were never taken apart, and the potion step was chosen in only 1% to 2% of its questions: about 90% of the potions drunk were drunk in ordinary battle decisions. The check seeds were also the gate in round 2 (no training game used them). Eight real-game matches cannot rank the two models, and the order there (Nimble-9B ahead) is the reverse of the check games. The real-game counts come from decision logs that quote the game text, so `results/` cannot recompute them.
- **Weights**: like round 2's, in private repositories, because the training data quote the game text. FT2 and FT3 are intermediate Laya models and are not published.

## 4 Recommendations

- **No training data**: Use Nimble-9B. It reads the options well enough to play a long game it was not trained on; Laya, as Convai itself says, is close to random zero-shot on an unfamiliar task.
- **Tight latency or memory, and data to train on**: Fine-tune Laya english. One epoch on 40k examples (27 minutes on the DGX Spark) took it from 10.4 to 17.1 floors, close to fine-tuned Nimble-9B (19.5), at a sixth of the time per request and memory.
- **Before trusting a typed-decision model**: Ask a sample of decisions with the options in several orders. Low agreement means the model is picking by position, as Laya multilingual does here; its plain score can look better than its reading.
- **Multilingual Laya**: Do not use it on English tasks like this one without fine-tuning.
- **After fine-tuning**: Count what the model leaves undone, not only its score. Ours took every reward and still died with potions unused; training further on its own play, with potions asked as a separate question and the search bot's distribution as the target, removed most of it (section 3.6, exploratory; which part mattered is not known).
- **Reproducing a run**: Run `scripts/setup-runtimes.sh` before `model-compose up`. Fresh model-compose environments get newer packages, and a newer triton alone is enough to flip some of Nimble-9B's near-tie votes.

## 5 Limitations and what we did not measure

### What the intervals cover

The 95% intervals and p-values count only how results vary from one game seed to another. Behind them are one fine-tuning run per model, one software environment, one shared input format and one fixed set of 4 option orders. How far the numbers move with another training run, another environment (Table 9) or another wording (Section 3.4) is not in them.

### Changes from the pre-registration

The pre-registrations promised to list every deviation with its reason. Gist revisions are linked in each round's revision history.

Table 8: Changes from the pre-registrations

| Round | What changed | When | Why | Effect on results |
|---|---|---|---|---|
| 1 | Track B's code (`arena/elite.py`) and command were fixed in revision r2 | 2026-09-26 15:42 UTC, one minute after the track B run started. The random and mcts-heuristic fights and 2 of 90 fights per Laya model were done | The plan described the procedure but did not name the file | None; the design did not change |
| 1 | The search bots' description was corrected (r3) | 2026-09-26 23:22 UTC, after all runs | r1 said they could see the simulator's random state. Their search works on the player's information set | None |
| 1 | model-compose PR #27 was called a draft (r4) | 2026-09-28, after all runs | It had been merged on 2026-09-25, before registration | None; same commits |
| 1 | The run added `--workers nimble=4` to the registered command | During the run | Throughput | None: decisions depend only on the seed, and seed 1 replays exactly |
| 1 | Track C's decision times were first reported without the makers' numbers | Added in this README, 2026-10-01 | Missed in the first analysis | None |
| 2 | The training set was to be subsampled to 40,000 decisions | Data generation, 2026-09-27 | Only 39,884 decisions existed | All were used |
| 2 | model-compose PR #27 was called a draft (r2) | 2026-09-28, after all runs | As in round 1 | None |
| This repository | The models are served by model-compose 0.4.113 instead of `e8ce0d4b` (+ `3f31d447` in round 2), and the runner talks to one server | 2026-10-01 | Public release | Seed 1 replays every published decision of all six models. `nimble-ft` needs PR #29 for decisions over 26 options (Other limitations) |
| Potion round | Added after both rounds, not pre-registered: the methods were chosen after reading the round-2 logs, the pass/fail check before its check games | 2026-10-03 | The fine-tuned models died with potions unused | None on the registered results; exploratory, section 3.6 |

### How much the software environment matters

*(exploratory)* We played seeds 1-50 again without `setup-runtimes.sh`, with the packages model-compose installs by itself on 2026-10-01 (torch 2.14.1, a different triton 3.8.0 build, no flash-linear-attention, `laya` 0.3.22; `results/sensitivity/environment.txt`), and compared them seed by seed with the published run. `scripts/sensitivity.py` recomputes the table.

Table 9: Published run against the same seeds with default packages (seeds 1-50, 4 option orders)

| Model | Published | Default packages | Difference [95% CI] | Same floor | Identical games | First different decision, median |
|---|---|---|---|---|---|---|
| Nimble-9B | 13.74 | 14.30 | +0.56 [−0.28, +1.52] | 35 of 50 | 2 of 50 | 15 |
| Laya english | 10.48 | 10.56 | +0.08 [0.00, +0.24] | 49 of 50 | 43 of 50 | 33 |
| Laya typed-decisions | 11.34 | 11.34 | 0.00 [−0.20, +0.16] | 47 of 50 | 31 of 50 | 51 |
| Laya multilingual | 2.86 | 2.80 | −0.06 [−0.20, +0.08] | 46 of 50 | 41 of 50 | 10 |

- Nimble-9B is the most sensitive: 48 of 50 games went another way, usually from about the 15th decision, where a near-tie vote flipped. Its mean still moved by only +0.56 floors, with an interval that includes zero, and 35 games ended on the same floor. The Laya models mostly replayed.
- The conclusions hold. In both environments the order is Nimble-9B, typed-decisions, english, multilingual, and Nimble-9B's lead over each Laya model stays above zero: over Laya english +3.26 [+1.80, +4.72] published and +3.74 [+1.98, +5.56] with default packages.
- A single game is not reproducible across environments; an average over many seeds is. Compare reruns by their means, not game by game.


### What the models could not read

*(exploratory)* The runner fits the question and options to 320 tokens with the ModernBERT tokenizer for every model; 1.6% of decisions had an option shortened that way. On top of that, the `laya` package cuts each option at 48 tokens, shrinks every option when they do not fit its 320-token budget together, and keeps only as much of the state as fits in the model's input (512 tokens for english, 1,024 for typed-decisions; multilingual was set to 4,096). Nimble-9B reads up to 4,096 tokens and cuts nothing. Counted by replaying the `laya` package's input builder on every published decision:

Table 10: Laya decisions whose input was cut

| Model | Decisions | State cut | An option cut at 48 tokens | All options shrunk |
|---|---|---|---|---|
| Laya english | 19,768 | 17 (0.09%; at most 8.6% of the state lost) | 1,031 (5.2%) | 332 (1.7%) |
| Laya typed-decisions | 22,296 | 0 | 1,326 (5.9%) | 455 (2.0%) |
| Laya multilingual | 6,025 | 0 | 66 (1.1%) | 6 (0.1%) |
| Laya english, fine-tuned | 45,148 | 541 (1.2%; median 6.4%, at most 30% lost) | 11,870 (26%) | 2,503 (5.5%) |

Losing state text is rare. Cutting long option texts is not, and it grows for fine-tuned Laya english, whose deeper runs offer longer card and relic descriptions. It was trained through the same input builder, so it learned with the same cuts.

### Other limitations

- One game, one character, one difficulty (Ironclad, ascension 0). The simulator reimplements the game and differs from it in places (for example Designer In-Spire, Scrap Ooze and Woman in Blue).
- Zero-shot Laya is used outside what Convai claims for it, and typed-decisions was fine-tuned for business workflows, not games. The models also differ about 20-fold in size (9B against 421M and 322M).
- Fine-tuning used one method per model, the makers' published settings and one epoch, with 17 times more training time for Nimble-9B. We do not know how far either model goes with other methods, more epochs or more data. LoRA, which Nimble-9B uses, generally needs more epochs than full fine-tuning to peak.
- `nimble-ft` asked 12 decisions with more than 26 options over the 200 seeds. model-compose 0.4.113 refuses those; the published run used a local patch that builds such prompts with the checkpoint's own `serving_schema`, which [hanyeol/model-compose#29](https://github.com/hanyeol/model-compose/pull/29) (open as of 2026-10-01) brings to model-compose. Until it is released, `nimble-ft` needs model-compose from that pull request. With it, 23 of 23 decisions we checked picked as the published server did; we did not replay whole games with it.
- `nimble-ft4` asked decisions with up to 29 options on seeds 208, 216 and 219. model-compose 0.4.113 refuses more than 26, so those three seeds need the same patch as `nimble-ft`; the other 47 replay on 0.4.113.
- We measured only on the DGX Spark, a machine shared with other jobs. Times are with one model loaded at a time. RTX-class GPUs, Macs and Laya's TileLang fast path (x86-64 only) were not tried. On other hardware a decision-for-decision replay is not expected; `scripts/env-report.sh` prints what a rerun should report.
- The search bots are not competitors: they search the simulator, which no text model can.
- The input format is ours and shared by all models. Section 3.4 shows the Laya models' order depends on the wording; neither maker's own recommended format was tried.
- The decision logs quote the game text, so `results/` keeps only per-game summaries and, per decision, its kind, option count, pick and votes. The tables above are recomputed from those files.
- The live demo (Demo) runs the real game and is not part of the benchmark.

## License

| Covers | License | Commercial use |
| :---: | --- | :---: |
| This repository | [`LICENSE`](LICENSE) (MIT) | ✓ |
| `bespokelabs/Bespoke-Nimble-9B`, `Qwen/Qwen3.5-9B` weights | Apache-2.0 | ✓ |
| `convaiinnovations/laya` weights | Apache-2.0 | ✓ |
| `MindrLabs/sts-arena-*-ft` weights | Apache-2.0 | ✓ |
| sts_lightspeed (the simulator, built by `setup-simulator.sh`) | MIT | ✓ |
| Game text (spire-archive, downloaded by `fetch-game-text.sh`) | none; it belongs to Mega Crit and is not included | ✗ |
| Game footage in the demo | Slay the Spire © Mega Crit | ✗ |
