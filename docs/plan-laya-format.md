# Plan: Laya in its maker's documented format (exploratory)

Written 2026-10-01, before any game of this run was played. Not part of either pre-registration: every result is reported as exploratory, next to the registered results, which stay the headline.

## Question

Does Laya reach a higher floor when it is asked the way Convai documents it, and does Nimble-9B's lead hold?

## What changes, for Laya only

| | Registered runs | This run |
|---|---|---|
| Option order | 4 orders (two seeded shuffles and their reverses), majority vote; option keys follow positions | Every rotation of one seeded shuffle (n requests for n options), probabilities averaged per option, highest mean wins (ties: seeded coin); option keys stay with their option, as Laya's `option_order` does |
| Input budget (`max_len` / `head_max_len`) | english and english fine-tuned 512 / 320, typed-decisions 1,024 / 320, multilingual 4,096 / 320 | 1,024 / 512 for english, typed-decisions and english fine-tuned; 4,096 / 512 for multilingual |
| Harness fit of question + options (ModernBERT tokens) | 320 | 512 |

Unchanged: the simulator, seeds, state text, option texts, question wording, option keys (`o1`, `o2`, ...), and the `laya` package's 48-token cut per option, which no setting changes.

Sources: Convai's README recommends averaging over rotations with `option_order` and raising `head_max_len` / `max_len` for many options. Nimble-9B's card documents the `enum` / `choice_descriptions` format the registered runs already use and says nothing about option order, so Nimble-9B is not rerun.

## Runs

Players `laya-english-rec`, `laya-typed-rec`, `laya-multilingual-rec`, `laya-english-ft-rec`, seeds 1-200, with the packages in `runtimes/laya.txt`. Output `results/laya-format/`.

## Analysis

Per model, against the same model in the registered run: mean floor with a paired bootstrap 95% interval (10,000 resamples, seed 0) and a Wilcoxon test, act 1 clears, and the share of decisions where every rotation picked the same option. Nimble-9B against each Laya model in this format, the same way (Nimble-9B from `results/final`, fine-tuned Nimble-9B from `results/round2`). Input cuts recounted as in README Table 10. No correction for multiple comparisons; nothing here is confirmatory.

How it will be read, decided now:
- If Nimble-9B's lead over Laya english (and fine-tuned over fine-tuned) keeps an interval above zero, the registered conclusion also holds in Laya's documented format.
- If an interval includes zero or flips, the README says the gap depends on the input format.
- Either way every number is published, including runs that end worse for Laya.

## Status

2026-10-01: the three zero-shot Laya runs finished (200 seeds each, no errors); `results/laya-format/`, `scripts/laya_format.py`. The fine-tuned run (`laya-english-ft-rec`) was paused at 77 of 200 seeds and will resume from there; 20 of its games had failed while the model server was down and are replayed on resume. The README reports this run once all four are done.
