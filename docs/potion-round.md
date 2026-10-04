# The potion round (exploratory)

Written 2026-10-04, after the runs. Unlike the two pre-registrations and `plan-laya-format.md`, this round was not planned in public before it ran. Its pass/fail check was fixed before any check game was played (it first ran as `scripts/ft2_gate.py` in the research repository; `scripts/stats_potion.py` recomputes it with the same rules and gets the same numbers), but the methods were chosen after looking at the round-2 logs. Read every number here as exploratory. The registered results stay the headline, and none of this changes them.

## Why

After round 2 both fine-tuned models took the gold and relic of every reward screen and bought in shops, but they died with potions on the belt. On the 50 check seeds (201-250), 98% of the games each lost ended with a potion the model could still have used, and each model used 0.3 to 0.6 potions a game. heart1, the search bot whose moves they were trained on, uses about 10.

## What we measured on the round-2 models

- **The training data had few examples of drinking.** heart1 drank or threw a potion in 383 of the 13,449 battle decisions that offered one (2.8%). Those states came from heart1's own games and from the zero-shot models', which rarely held a potion. In the states the fine-tuned Laya english reached itself, with its belt full, heart1 used a potion in about one decision in five.
- **The models could not tell when.** On states where heart1 chose a potion, the probability the first potion-round Laya model (FT2) gave to any potion separated those states from the rest with an AUC of 0.61; for the round-2 Nimble-9B it was 0.70, and its probability for a potion was close to zero. heart1 is confident when it drinks: the potion it chose got a median 84% of its search visits (FT2's states).
- **Majority voting hid what was left.** In the round-2 models' check games, when at least one of the 4 option orders picked a potion, the vote picked it 45% of the time (Laya) and 63% (Nimble-9B).
- **The state did not say what kind of fight it was.** heart1's search counts every potion left after a won fight as worth points, so we read its potion moves as "this fight is dangerous enough". The fight's kind (normal, elite, boss) and the floor were not in the text.

## What changed

Four things, all for this round; none touches the registered runs (`--potion-step` is off unless asked for).

1. **A potion step.** At the start of each turn in which the player holds a usable potion, it is first asked on its own: use one of these potions, or keep them. The question is answered by the same models in the same way (4 option orders, majority vote). The turn's card decisions still list the potions, for ones that fit mid-turn. (`arena/prompt.py`, `PotionStep`)
2. **A fight line.** In the potion step and the battle decisions of that run, the state starts with `Fight: normal|elite|boss. Act N, floor M.`
3. **Visit targets.** The training target for each decision is half heart1's chosen option and half heart1's search distribution over the options: its root visit counts, squared and normalised. The potion step's answer is the potion heart1 plays in that turn, or "keep".
4. **Two DAgger rounds.** A fine-tuned model plays 60 seeds with the potion step on, heart1 labels every state it reaches, and Laya is trained further on those states plus 4,000 round-2 examples. In round A `laya-english-ft2` plays (the first potion-round model: `laya-english-ft` trained on one DAgger round of its own play, with no potion step); `laya-english-ft2` trained on round A's states is `laya-english-ft3`. In round B `laya-english-ft3` plays; `laya-english-ft2` trained on both rounds' states is `laya-english-ft4`. Nimble-9B is trained once, from `nimble-ft`, on the same two rounds' states, all of which Laya models played.

Training: Laya english, from `laya-english-ft2`, learning rate 1e-5, 2 epochs, token-budgeted batches of 4,096 as in round 2 (FT3 0.74 h, FT4 0.57 h). Nimble-9B, from the round-2 adapter, learning rate 2.5e-5, 1 epoch, 3,000 steps at batch 2 x 4 (4.4 h, peak 38.8 GiB). The set has 24,000 examples: 20,000 new decisions (every potion step and every battle decision where heart1 plays a potion, 8,094 in all, and a sample of the rest), and 4,000 from round 2. heart1 labels with 2,000 simulations per battle decision, as in round 2. The training and data-generation code is not in this repository, as for round 2, and neither are the training data, which quote the game text.

`results/training/` has each model's report (validation agreement with heart1 and time).

## Results

Check seeds 201-250, 4 option orders, potion step on for FT3 and FT4. Differences in mean floor are from the model each one started from, on the same seeds, with a bootstrap 95% interval. `scripts/stats_potion.py` recomputes this table from `results/potion`.

Table P1: Check games, 50 seeds

| Player | Mean floor | Same-seed difference | Potions per game | Lost games with a usable potion left | Cleared act 1 | Reached act 3 | Wins | Relic or gold left behind | Shop visits with a purchase | Check |
|---|---|---|---|---|---|---|---|---|---|---|
| Laya english, round-2 fine-tune (start) | 16.7 | | 0.30 | 98% | 19 | 0 | 0 | 0 | 89% | start |
| Laya FT2: one DAgger round, no potion step | 20.9 | +4.3 [+1.9, +6.7] | 2.32 | 88% | 26 | 2 | 0 | 0 | 90% | not passed |
| Laya FT3: potion step, visit targets, DAgger round A | 23.5 | +6.8 [+4.1, +9.6] | 3.72 | 74% | 30 | 4 | 0 | 1 | 92% | not passed |
| **Laya FT4**: DAgger round B | **28.7** | **+12.0 [+8.5, +15.7]** | **6.04** | **30%** | **37** | **14** | **3** | **0** | 87% | **passed** |
| Nimble-9B, round-2 fine-tune (start) | 20.5 | | 0.58 | 98% | 28 | 2 | 0 | 0 | 98% | start |
| **Nimble-9B FT4** | **26.6** | **+6.1 [+2.6, +9.6]** | **6.16** | **16%** | **33** | **9** | 0 | 1 | 97% | not passed |

The check: potions per game at least 3, lost games with a usable potion left at most 50%, mean floor not lower, no relic or gold left behind, shop purchase rate no more than 10 points lower. Nimble-9B FT4 meets every part but one: on seed 212 it left the relic Smiling Mask behind at floor 26. We report the model as not passed, and did not change the check after seeing it.

FT2 and FT3 are intermediate Laya models; their weights are not published.

### The real game

Eight matches in the real game (the live demo's setup, seeds 1-8, `nimble-ft4` on the left against `laya-english-ft4`, potion step on). The behaviour counts (potions, rewards, shops) come from a script of the research repository (`scripts/arena/behaviour.py`) run on decision logs that quote the game text, so they cannot be recomputed from the published files; `results/potion/arena/` keeps the match results and that script's output.

Table P2: Real game, seeds 1-8

| | Mean floor | Wins | Matches won | Potions per game | Lost games with a usable potion left | Reward screens left with a relic or gold | Shop visits with a purchase |
|---|---|---|---|---|---|---|---|
| Nimble-9B FT4 | 29.9 | 1 (seed 5, floor 51, act 3 boss beaten) | 6 | 6.1 | 1 of 7 | 0 | 9 of 11 |
| Laya english FT4 | 23.6 | 0 | 1 (1 draw) | 4.9 | 3 of 8 | 0 | 10 of 10 |

## What this does and does not show

- Fine-tuning on the states the models reach themselves, with the search bot's visit distribution as the target, cut the share of lost games that ended with a usable potion from 98% to 30% (Laya) and 16% (Nimble-9B), and raised the mean floor by 12.0 and 6.1 on the same seeds. In the real game both models kept taking every reward and shop item, and Nimble-9B FT4 beat the act 3 boss once in 8 matches.
- **We cannot say which change did it.** The potion step, the fight line, the visit targets and the extra rounds of play were never taken apart. The potion step itself was chosen in 1% to 2% of its questions (Laya 1.1%, Nimble-9B 1.6% in the check games; 5 of 313 and 8 of 323 in the real game), and about 90% of the potions drunk were drunk in the ordinary battle decisions. The step may not be what mattered.
- The check seeds (201-250) were also the gate in round 2. No game of the training sets used them (training seeds 3001-3060 and 3201-3260).
- The real game is 8 matches. Which model gets further there (Nimble-9B, 29.9 against 23.6) is the reverse of the check games (Laya, 28.7 against 26.6, on other seeds), and neither order is settled.
- All of Nimble-9B FT4's new training states were played by Laya models.
- This is one training run per model, as in round 2. How far the numbers move with another run is not in the intervals.
- Nimble-9B FT4 asks decisions with up to 29 options on seeds 208, 216 and 219. model-compose 0.4.113 refuses more than 26; those games ran on the local patch described in the README. The other 47 seeds replay on 0.4.113.
- The results come from the DGX Spark; on other hardware a decision-for-decision replay is not expected (README, section 5).

## Reproduce

```bash
uv run python scripts/stats_potion.py                  # Table P1 and the checks, from results/potion
uv run python -m arena.run --player laya-english-ft4 --seeds 202 --perms 4 --potion-step
uv run python -m arena.run --player nimble-ft4 --seeds 202 --perms 4 --potion-step
```

The two FT4 workflows load `MindrLabs/sts-arena-laya-english-ft4` and `MindrLabs/sts-arena-nimble-ft4` (private, like the round-2 repositories, because the training data quote the game text). After `scripts/setup-runtimes.sh` and `model-compose up`, seed 202 replays all 236 published decisions of Laya english FT4 and all 134 of Nimble-9B FT4 (checked in a fresh clone on the DGX Spark).
