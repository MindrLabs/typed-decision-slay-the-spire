"""Short English text for event screens: one context line plus one line per legal option.

Numbers come from the engine state (screen_state_info / gc), and the wording follows what the
C++ engine actually does in GameContext::chooseEventOption, which is the source of truth where it
differs from the real game (see the "engine:" notes below).
"""
from __future__ import annotations

import struct

import slaythespire as sts

from arena.gamedata import lookup

E = sts.Event


# ---------------------------------------------------------------- name helpers

def _f32(x: float) -> float:
    return struct.unpack("f", struct.pack("f", x))[0]


def frac_max_hp(gc, percent: float, mode: str = "floor") -> int:
    """GameContext::fractionMaxHp with float32 arithmetic (floor | round | ceil)."""
    import math
    v = _f32(_f32(float(gc.max_hp)) * _f32(percent))
    if mode == "round":
        return int(math.floor(v + 0.5))
    return int(math.ceil(v)) if mode == "ceil" else int(v)


def card_name(card) -> str:
    name = sts.getCardName(card.id)
    if card.id == sts.CardId.SEARING_BLOW and card.upgrade_count > 0:
        return f"{name}+{card.upgrade_count}"
    return name + ("+" if card.upgraded else "")


def relic_name(relic_id) -> str:
    return sts.getRelicName(relic_id)


def potion_name(potion) -> str:
    item = lookup("potions", potion.name)
    return item["name"] if item else potion.name.replace("_", " ").title()


def event_name(event) -> str:
    if event == E.NEOW:
        return "Neow"
    item = lookup("events", event.name)
    return item["name"] if item else event.name.replace("_", " ").title()


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def _unfav(gc) -> bool:
    return gc.ascension >= 15


def _has_relic(gc, rid) -> bool:
    return any(r.id == rid for r in gc.relics)


_ENCOUNTER = {
    "THREE_SENTRIES": "3 Sentries",
    "GREMLIN_NOB": "Gremlin Nob",
    "LAGAVULIN_EVENT": "Lagavulin",
}
_DEAD_ADV_LOOT = {0: "30 gold", 1: "nothing", 2: "a relic"}


# ---------------------------------------------------------------- Neow

_NEOW_BONUS = {
    "THREE_CARDS": "choose 1 of 3 cards",
    "ONE_RANDOM_RARE_CARD": "obtain a random rare card",
    "REMOVE_CARD": "choose a card to remove",
    "UPGRADE_CARD": "choose a card to upgrade",
    "TRANSFORM_CARD": "choose a card to transform",
    "RANDOM_COLORLESS": "choose 1 of 3 colorless cards",
    "THREE_SMALL_POTIONS": "obtain 3 random potions",
    "RANDOM_COMMON_RELIC": "obtain a random common relic",
    "THREE_ENEMY_KILL": "obtain Neow's Lament (enemies in your first 3 combats have 1 HP)",
    "HUNDRED_GOLD": "gain 100 gold",
    "RANDOM_COLORLESS_2": "choose 1 of 3 rare colorless cards",
    "REMOVE_TWO": "choose 2 cards to remove",
    "ONE_RARE_RELIC": "obtain a random rare relic",
    "THREE_RARE_CARDS": "choose 1 of 3 rare cards",
    "TWO_FIFTY_GOLD": "gain 250 gold",
    "TRANSFORM_TWO_CARDS": "choose 2 cards to transform",
    "BOSS_RELIC": "obtain a random boss relic",
}


def _neow_bonus(gc, bonus) -> str:
    name = bonus.name
    if name in ("TEN_PERCENT_HP_BONUS", "TWENTY_PERCENT_HP_BONUS"):
        # engine: only Max HP rises; current HP is not healed.
        gain = int(_f32(gc.max_hp * _f32(0.1 if name.startswith("TEN") else 0.2)))
        return f"gain {gain} Max HP (current HP unchanged)"
    return _NEOW_BONUS[name]


def _neow_drawback(gc, drawback) -> str:
    name = drawback.name
    if name == "NONE":
        return ""
    if name == "TEN_PERCENT_HP_LOSS":
        loss = gc.max_hp - int(_f32(_f32(0.9) * gc.max_hp))
        return f"lose {loss} Max HP"
    if name == "NO_GOLD":
        return f"lose all {gc.gold} gold"
    if name == "CURSE":
        return "obtain a random curse"
    if name == "PERCENT_DAMAGE":
        return f"lose {gc.cur_hp - gc.cur_hp // 10 * 7} HP"
    if name == "LOSE_STARTER_RELIC":
        starter = next((relic_name(r.id) for r in gc.relics if r.id == sts.RelicId.BURNING_BLOOD), "your starter relic")
        return f"lose {starter}"
    raise ValueError(f"unknown Neow drawback {name}")


def _neow(gc, i: int) -> str:
    opt = gc.screen_state_info.neowRewards[i]
    bonus = _neow_bonus(gc, opt.r)
    cost = _neow_drawback(gc, opt.d)
    text = f"{bonus[0].upper()}{bonus[1:]}"
    return f"{text}; {cost}." if cost else f"{text}."


# ---------------------------------------------------------------- per-event option text
# Each entry maps an engine option index to a function (gc, info) -> str.

def _leave(_gc, _si) -> str:
    return "Leave: nothing happens."


def _falling(kind: str, label: str, attr: str):
    def f(gc, si) -> str:
        idx = getattr(si, attr)
        return f"{label}: lose {card_name(gc.deck[idx])} ({kind}) from your deck."
    return f


def _cursed_tome(gc, si, i: int) -> str:
    if i == 0:
        return "Read: start reading (next pages cost 1, 2, 3 HP; then take a book for 10 HP or stop for 3 HP)."
    if i in (2, 3, 4):
        return f"Continue reading: lose {si.event_data} HP."
    if i == 5:
        return (f"Take the book: lose {15 if _unfav(gc) else 10} HP, obtain a random book relic "
                "(Necronomicon, Enchiridion or Nilry's Codex).")
    if i == 6:
        return "Stop reading: lose 3 HP, leave with nothing."
    return "Leave: nothing happens."


def _dead_adventurer(gc, si, i: int) -> str:
    if i == 1:
        return "Leave: stop searching, keep what you found."
    chance = si.phase * 25 + (35 if _unfav(gc) else 25)
    enemy = _ENCOUNTER.get(si.encounter.name, si.encounter.name)
    left = sorted({_DEAD_ADV_LOOT[r] for r in list(si.event_rewards)[si.phase:]})
    return (f"Search: {chance}% chance {enemy} attacks (win: all remaining loot + card); "
            f"else find one of: {', '.join(left)}.")


def _designer(gc, si, i: int) -> str:
    u = _unfav(gc)
    c0, c1, c2, hp = (50, 75, 110, 5) if u else (40, 60, 90, 3)
    if i == 0:
        return f"Adjustments: pay {c0} gold, choose a card to upgrade."
    if i == 1:
        # engine: this branch charges no gold.
        return "Adjustments: upgrade 2 random cards (engine charges no gold)."
    if i == 2:
        return f"Clean Up: pay {c1} gold, choose a card to remove."
    if i == 3:
        # engine: case 3 falls through into cases 4 and 5 (missing breaks); transformRandomCards is a no-op.
        return (f"Clean Up: pay {c1 + c2} gold total, upgrade 1 random card, lose {hp} HP "
                "(engine quirk: no transform).")
    if i == 4:
        # engine: case 4 falls through into case 5; the removal screen is skipped.
        return f"Full Service: pay {c2} gold, upgrade 1 random card, lose {hp} HP (engine quirk: no removal)."
    return f"Punch: lose {hp} HP."


def _knowing_skull(gc, si, i: int) -> str:
    if i == 0:
        return f"Riches?: lose {si.hpAmount0} HP, gain 90 gold; ask again after."
    if i == 1:
        return f"Success?: lose {si.hpAmount1} HP, obtain a random uncommon colorless card; ask again after."
    if i == 2:
        full = all(p != sts.Potion.EMPTY_POTION_SLOT for p in gc.potions[:gc.potion_capacity])
        tail = " (your potion slots are full: it is lost)" if full else ""
        return f"A Pick Me Up?: lose {si.hpAmount2} HP, obtain a random potion{tail}; ask again after."
    return "How do I leave?: lose 6 HP and leave."


def _scrap_ooze(gc, si, i: int) -> str:
    if i == 1:
        return "Leave: nothing happens."
    dmg = 5 if _unfav(gc) else 3
    chance = si.event_data * 10 + 25 + 1  # engine: roll(0..99) >= 99 - (10*tries + 25)
    return f"Reach Inside: take {dmg} damage; {chance}% chance to find a random relic and leave, else try again."


def _golden_idol(gc, si, i: int) -> str:
    if i == 0:
        return (f"Take: obtain Golden Idol (+25% gold) and spring a boulder trap "
                f"(then: curse Injury, {si.hpAmount0} damage, or -{si.hpAmount1} Max HP).")
    if i == 1:
        return "Leave: nothing happens."
    if i == 2:
        return "Outrun: become cursed with Injury."
    if i == 3:
        return f"Smash: take {si.hpAmount0} damage."
    return f"Hide: lose {si.hpAmount1} Max HP."


def _colosseum(gc, si, i: int) -> str:
    if si.event_data == 0:
        return ("Fight: battle Blue Slaver + Red Slaver; win 25-35 gold, a card reward, maybe a potion; "
                "then choose to leave or fight again.")
    if i == 0:
        return "Cowardice: leave with your spoils."
    return "Victory: battle Taskmaster + Gremlin Nob; win a rare relic, 25-35 gold, a card reward, maybe a potion."


def _nloth(slot: str):
    def f(gc, si) -> str:
        rid = gc.relics[getattr(si, slot)].id
        return f"Offer {relic_name(rid)}: lose it, obtain N'loth's Gift (rare cards appear more often)."
    return f


def _divine_fountain(gc, si) -> str:
    curses = [card_name(c) for c in gc.deck if c.type == sts.CardType.CURSE and c.transformable]
    listed = ", ".join(curses) if curses else "none removable"
    n_parasite = sum(1 for c in curses if c.startswith("Parasite"))
    tail = f"; each Parasite removed costs 3 Max HP (-{3 * n_parasite})" if n_parasite else ""
    return f"Drink: remove all curses from your deck ({listed}){tail}."


def _vampires(gc, si, i: int) -> str:
    n = sum(1 for c in gc.deck if c.id == sts.CardId.STRIKE_RED)
    swap = f"replace all {_plural(n, 'Strike')} with 5 Bite"
    if i == 0:
        return f"Offer Blood Vial: lose it, {swap}."
    if i == 1:
        return f"Accept: lose {si.hpAmount0} Max HP, {swap}."
    return "Refuse: nothing happens."


def _we_meet_again(gc, si, i: int) -> str:
    if i == 0:
        return f"Give Potion: lose {potion_name(gc.potions[si.potionIdx])}, obtain a random relic."
    if i == 1:
        return f"Give Gold: lose {si.gold} gold, obtain a random relic."
    if i == 2:
        return f"Give Card: lose {card_name(gc.deck[si.cardIdx])} from your deck, obtain a random relic."
    return "Attack: the thief flees; nothing happens."


def _woman_in_blue(gc, si, i: int) -> str:
    if i < 3:
        # engine: no gold is charged for the potions.
        return f"Buy {_plural(i + 1, 'potion')}: obtain {_plural(i + 1, 'random potion')} (engine charges no gold; real game 20/30/40)."
    if _unfav(gc):
        return f"Leave: lose {si.hpAmount0} HP."
    return "Leave: nothing happens."


def _tomb(gc, si, i: int) -> str:
    if i == 0:
        return "Don the Red Mask: gain 222 gold."
    if i == 1:
        return f"Offer all {gc.gold} gold: obtain Red Mask relic (enemies start Weak)."
    return "Leave: nothing happens."


_OPTIONS: dict = {
    E.OMINOUS_FORGE: {
        0: lambda gc, si: "Forge: choose a card to upgrade.",
        1: lambda gc, si: "Rummage: obtain Warped Tongs relic (upgrade a random card each combat), become cursed with Pain.",
        2: _leave,
    },
    E.PLEADING_VAGRANT: {
        0: lambda gc, si: "Offer Gold: pay 85 gold, obtain a random relic.",
        1: lambda gc, si: "Rob: obtain a random relic, become cursed with Shame.",
        2: _leave,
    },
    E.ANCIENT_WRITING: {
        0: lambda gc, si: "Elegance: choose a card to remove.",
        1: lambda gc, si: "Simplicity: upgrade all {} Strikes and Defends.".format(
            sum(1 for c in gc.deck if c.is_starter_strike_or_defend and not c.upgraded)),
    },
    E.OLD_BEGGAR: {
        0: lambda gc, si: "Offer Gold: pay 75 gold, choose a card to remove.",
        1: _leave,
    },
    E.BIG_FISH: {
        0: lambda gc, si: f"Banana: heal {frac_max_hp(gc, 1 / 3)} HP.",
        1: lambda gc, si: "Donut: gain 5 Max HP (and heal 5).",
        2: lambda gc, si: "Box: obtain a random relic, become cursed with Regret.",
    },
    E.BONFIRE_SPIRITS: {
        0: lambda gc, si: "Offer: choose a card to offer; reward depends on its rarity.",
    },
    E.AUGMENTER: {
        0: lambda gc, si: "Test J.A.X.: obtain the card J.A.X. (lose 3 HP, gain 2 Strength).",
        1: lambda gc, si: "Become Test Subject: choose 2 cards to transform.",
        2: lambda gc, si: "Ingest Mutagens: obtain Mutagenic Strength relic (+3 Strength at combat start, lost at turn end).",
    },
    E.DUPLICATOR: {
        0: lambda gc, si: "Pray: choose a card to duplicate.",
        1: _leave,
    },
    E.FACE_TRADER: {
        0: lambda gc, si: f"Touch: take {si.hpAmount0} damage, gain {50 if _unfav(gc) else 75} gold.",
        1: lambda gc, si: "Trade: obtain a random face relic you lack (Cultist Headpiece, Face of Cleric, "
                          "Gremlin Visage, N'loth's Hungry Face or Ssserpent Head).",
        2: _leave,
    },
    E.FALLING: {
        0: _falling("skill", "Land", "skillCardDeckIdx"),
        1: _falling("power", "Channel", "powerCardDeckIdx"),
        2: _falling("attack", "Strike", "attackCardDeckIdx"),
        3: lambda gc, si: "Splat: land safely, lose nothing.",
    },
    E.FORGOTTEN_ALTAR: {
        0: lambda gc, si: "Offer Golden Idol: swap it for Bloody Idol (heal 5 HP whenever you gain gold).",
        1: lambda gc, si: f"Sacrifice: gain 5 Max HP (heal 5), lose {si.hpAmount0} HP (net -{si.hpAmount0 - 5} HP).",
        2: lambda gc, si: "Desecrate: become cursed with Decay.",
    },
    E.THE_DIVINE_FOUNTAIN: {0: _divine_fountain, 1: _leave},
    E.GHOSTS: {
        0: lambda gc, si: f"Accept: lose {si.hpAmount0} Max HP, obtain {3 if _unfav(gc) else 5} Apparition (Intangible 1, Ethereal).",
        1: lambda gc, si: "Refuse: nothing happens.",
    },
    E.GOLDEN_SHRINE: {
        0: lambda gc, si: f"Pray: gain {50 if _unfav(gc) else 100} gold.",
        1: lambda gc, si: "Desecrate: gain 275 gold, become cursed with Regret.",
        2: _leave,
    },
    E.WING_STATUE: {
        0: lambda gc, si: "Pray: take 7 damage, choose a card to remove.",
        1: lambda gc, si: "Destroy: gain 50-80 gold (random).",
        2: _leave,
    },
    E.LAB: {0: lambda gc, si: f"Search: obtain {2 if _unfav(gc) else 3} random potions."},
    E.THE_SSSSSERPENT: {
        0: lambda gc, si: f"Agree: gain {150 if _unfav(gc) else 175} gold, become cursed with Doubt.",
        1: lambda gc, si: "Disagree: nothing happens.",
    },
    E.LIVING_WALL: {
        0: lambda gc, si: "Forget: choose a card to remove.",
        1: lambda gc, si: "Change: choose a card to transform.",
        2: lambda gc, si: "Grow: choose a card to upgrade.",
    },
    E.MASKED_BANDITS: {
        0: lambda gc, si: f"Pay: lose all {gc.gold} gold.",
        1: lambda gc, si: "Fight: battle Pointy, Romeo and Bear; win Red Mask relic, 25-35 gold, a card reward.",
    },
    E.MINDBLOOM: {
        0: lambda gc, si: f"I am War: fight a random Act 1 boss; win a rare relic, {25 if _unfav(gc) else 50} gold, a card reward.",
        1: lambda gc, si: "I am Awake: upgrade all cards, obtain Mark of the Bloom (you can no longer heal).",
        2: lambda gc, si: "I am Rich: gain 999 gold, become cursed with 2 Normality.",
        3: lambda gc, si: f"I am Healthy: heal to full (+{gc.max_hp - gc.cur_hp} HP), become cursed with Doubt.",
    },
    E.HYPNOTIZING_COLORED_MUSHROOMS: {
        0: lambda gc, si: "Stomp: fight 3 Fungi Beasts; win Odd Mushroom relic, 20-30 gold, a card reward.",
        1: lambda gc, si: f"Eat: heal {frac_max_hp(gc, 0.25)} HP, become cursed with Parasite.",
    },
    E.MYSTERIOUS_SPHERE: {
        0: lambda gc, si: "Open Sphere: fight 2 Orb Walkers; win a rare relic, 45-55 gold, a card reward.",
        # engine: the "leave" branch grants gold (copied from The Nest).
        1: lambda gc, si: f"Leave: gain {50 if _unfav(gc) else 99} gold (engine quirk).",
    },
    E.THE_NEST: {
        0: lambda gc, si: f"Smash and Grab: gain {50 if _unfav(gc) else 99} gold.",
        1: lambda gc, si: "Stay in Line: take 6 damage, obtain the card Ritual Dagger.",
    },
    E.NLOTH: {0: _nloth("relicIdx0"), 1: _nloth("relicIdx1"), 2: _leave},
    E.NOTE_FOR_YOURSELF: {
        0: lambda gc, si: f"Take and Give: obtain {card_name(gc.note_for_yourself_card)}, then choose a card to remove (stored).",
        1: lambda gc, si: "Ignore: nothing happens.",
    },
    E.PURIFIER: {0: lambda gc, si: "Pray: choose a card to remove.", 1: _leave},
    E.SECRET_PORTAL: {
        0: lambda gc, si: "Enter the Portal: skip the rest of the act and fight its boss now.",
        1: _leave,
    },
    E.SENSORY_STONE: {
        0: lambda gc, si: "Recall: choose 1 colorless card (1 card reward).",
        1: lambda gc, si: "Recall: lose 5 HP, 2 colorless card rewards.",
        2: lambda gc, si: "Recall: lose 10 HP, 3 colorless card rewards.",
    },
    E.SHINING_LIGHT: {
        0: lambda gc, si: f"Enter: take {si.hpAmount0} damage, upgrade 2 random cards.",
        1: _leave,
    },
    E.THE_CLERIC: {
        0: lambda gc, si: f"Heal: pay 35 gold, heal {si.hpAmount0} HP.",
        1: lambda gc, si: f"Purify: pay {75 if _unfav(gc) else 50} gold, choose a card to remove.",
        2: _leave,
    },
    E.THE_JOUST: {
        0: lambda gc, si: "Bet on the Murderer: pay 50 gold; 70% chance to get 100 gold back (net +50).",
        1: lambda gc, si: "Bet on the Owner: pay 50 gold; 30% chance to get 250 gold back (net +200).",
    },
    E.THE_LIBRARY: {
        0: lambda gc, si: "Read: choose 1 of 20 random cards to add to your deck.",
        1: lambda gc, si: f"Sleep: heal {si.hpAmount0} HP.",
    },
    E.THE_MAUSOLEUM: {
        0: lambda gc, si: "Open Coffin: obtain a random relic; {} become cursed with Writhe.".format(
            "also" if _unfav(gc) else "50% chance to"),
        1: _leave,
    },
    E.THE_MOAI_HEAD: {
        0: lambda gc, si: f"Jump Inside: lose {si.hpAmount0} Max HP, then heal to full.",
        1: lambda gc, si: "Offer Golden Idol: lose it, gain 333 gold.",
        2: _leave,
    },
    E.TRANSMORGRIFIER: {0: lambda gc, si: "Pray: choose a card to transform.", 1: _leave},
    E.UPGRADE_SHRINE: {0: lambda gc, si: "Pray: choose a card to upgrade.", 1: _leave},
    E.WHEEL_OF_CHANGE: {
        0: lambda gc, si: (f"Spin: random prize - {gc.act * 100} gold, a relic, full heal, curse Decay, "
                           f"remove a card, or lose {frac_max_hp(gc, 0.15 if _unfav(gc) else 0.10)} HP."),
    },
    E.WINDING_HALLS: {
        0: lambda gc, si: f"Embrace Madness: lose {si.hpAmount0} HP, obtain 2 Madness.",
        1: lambda gc, si: f"Press On: heal {si.hpAmount1} HP, become cursed with Writhe.",
        2: lambda gc, si: f"Retrace Your Steps: lose {si.hpAmount2} Max HP.",
    },
    E.WORLD_OF_GOOP: {
        0: lambda gc, si: "Gather Gold: take 11 damage, gain 75 gold.",
        1: lambda gc, si: f"Leave It: lose {si.goldLoss} gold.",
    },
}

# Events whose text depends on the phase / running state: (gc, si, idx) -> str.
_PHASED = {
    E.CURSED_TOME: _cursed_tome,
    E.DEAD_ADVENTURER: _dead_adventurer,
    E.DESIGNER_IN_SPIRE: _designer,
    E.KNOWING_SKULL: _knowing_skull,
    E.SCRAP_OOZE: _scrap_ooze,
    E.GOLDEN_IDOL: _golden_idol,
    E.COLOSSEUM: _colosseum,
    E.VAMPIRES: _vampires,
    E.WE_MEET_AGAIN: _we_meet_again,
    E.THE_WOMAN_IN_BLUE: _woman_in_blue,
    E.TOMB_OF_LORD_RED_MASK: _tomb,
}


# ---------------------------------------------------------------- context lines

_SITUATION = {
    E.OMINOUS_FORGE: "an abandoned forge",
    E.PLEADING_VAGRANT: "a vagrant begs for 85 gold",
    E.ANCIENT_WRITING: "ancient writing offers elegance or simplicity",
    E.OLD_BEGGAR: "a beggar asks for 75 gold",
    E.BIG_FISH: "a banana, a donut and a box dangle on strings",
    E.BONFIRE_SPIRITS: "spirits accept an offering",
    E.AUGMENTER: "a scientist offers experiments",
    E.DUPLICATOR: "a shrine can duplicate a card",
    E.FACE_TRADER: "a figure offers to trade faces",
    E.FALLING: "you are falling and must let go of one card",
    E.FORGOTTEN_ALTAR: "an altar demands a sacrifice",
    E.THE_DIVINE_FOUNTAIN: "a fountain can wash away curses",
    E.GHOSTS: "ghosts offer Apparitions for Max HP",
    E.GOLDEN_SHRINE: "a golden shrine",
    E.WING_STATUE: "a winged statue",
    E.LAB: "a lab full of potions",
    E.THE_SSSSSERPENT: "a serpent offers gold for a curse",
    E.LIVING_WALL: "a living wall blocks the way",
    E.MASKED_BANDITS: "bandits demand all your gold",
    E.MINDBLOOM: "a mind bloom offers visions",
    E.HYPNOTIZING_COLORED_MUSHROOMS: "glowing mushrooms block the path",
    E.MYSTERIOUS_SPHERE: "a sphere guarded by Orb Walkers",
    E.THE_NEST: "a cultist nest",
    E.NLOTH: "N'loth wants one of your relics",
    E.NOTE_FOR_YOURSELF: "a note from a past run holds a card",
    E.PURIFIER: "a purifying shrine",
    E.SECRET_PORTAL: "a portal straight to the boss",
    E.SENSORY_STONE: "a stone holds colorless memories",
    E.SHINING_LIGHT: "a shining light upgrades at a cost",
    E.THE_CLERIC: "a cleric sells healing and card removal",
    E.THE_JOUST: "bet 50 gold on a joust",
    E.THE_LIBRARY: "a quiet library",
    E.THE_MAUSOLEUM: "a coffin may hold a relic or a curse",
    E.THE_MOAI_HEAD: "a giant stone head",
    E.THE_WOMAN_IN_BLUE: "a woman sells potions",
    E.TOMB_OF_LORD_RED_MASK: "the tomb of Lord Red Mask",
    E.TRANSMORGRIFIER: "a transforming shrine",
    E.UPGRADE_SHRINE: "an upgrade shrine",
    E.VAMPIRES: "vampires offer to turn you",
    E.WE_MEET_AGAIN: "the thief Ranwid wants a gift for a relic",
    E.WHEEL_OF_CHANGE: "a wheel of random prizes",
    E.WINDING_HALLS: "endless winding halls",
    E.WORLD_OF_GOOP: "gold lies in a pool of goop",
    E.GOLDEN_IDOL: "a golden idol on a pedestal",
    E.DESIGNER_IN_SPIRE: "a designer offers services for gold",
}


def _situation(gc) -> str:
    ev, si = gc.cur_event, gc.screen_state_info
    if ev == E.NEOW:
        return "start-of-run blessing; pick one"
    if ev == E.COLOSSEUM:
        return ("forced into the arena against Slavers" if si.event_data == 0
                else "you beat the Slavers; fight the champions or leave")
    if ev == E.CURSED_TOME:
        if si.event_data == 0:
            return "a cursed tome on a pedestal"
        if si.event_data < 4:
            return f"reading the cursed tome, page {si.event_data} of 3"
        return "last page of the cursed tome: take the book or stop"
    if ev == E.DEAD_ADVENTURER:
        enemy = _ENCOUNTER.get(si.encounter.name, si.encounter.name)
        return f"a corpse to loot, searched {si.phase} of 3 times; {enemy} may return"
    if ev == E.GOLDEN_IDOL and _has_relic(gc, sts.RelicId.GOLDEN_IDOL):
        return "you took the idol; a boulder trap is triggered, pick how to escape"
    if ev == E.KNOWING_SKULL:
        return "a skull grants wishes for HP; costs rise by 1 per request"
    if ev == E.SCRAP_OOZE:
        return f"a slime full of scrap, {si.event_data} failed reaches so far"
    return _SITUATION[ev]


def describe_event_context(gc) -> str:
    """One line: event name + the situation relevant to the choice."""
    if gc.cur_event == E.MATCH_AND_KEEP:
        raise NotImplementedError("MATCH_AND_KEEP is handled by a heuristic, not described")
    return f"Event: {event_name(gc.cur_event)} ({_situation(gc)})."


def describe_event_option(gc, action) -> str:
    """Concise effect of choosing this event option in the current phase."""
    ev, si, idx = gc.cur_event, gc.screen_state_info, action.idx1
    if ev == E.MATCH_AND_KEEP:
        raise NotImplementedError("MATCH_AND_KEEP is handled by a heuristic, not described")
    if ev == E.NEOW:
        return _neow(gc, idx)
    if ev in _PHASED:
        return _PHASED[ev](gc, si, idx)
    table = _OPTIONS.get(ev)
    if table is None or idx not in table:
        raise KeyError(f"no description for {ev.name} option {idx}")
    return table[idx](gc, si)
