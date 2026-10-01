"""Turn simulator state and legal actions into short English text for decision models.

Everything here shows only what a human player could see on screen: no draw-pile order,
no RNG state. Text is kept terse because Laya english has a 512-token context.
"""
from __future__ import annotations

import collections
import functools
import json
import re

import slaythespire as sts

from .gamedata import DATA_DIR, lookup, norm

RAT = sts.RewardsActionType


def _name(enum_value) -> str:
    return str(enum_value).split(".")[-1]


def _clean(text: str) -> str:
    return " ".join(text.replace("\n", " ").split())


# --- cards, relics, potions ---------------------------------------------------

def card_label(card_id, upgraded: bool) -> str:
    data = lookup("cards", _name(card_id))
    name = data["name"] if data else _name(card_id).replace("_", " ").title()
    return name + ("+" if upgraded else "")


def card_text(card_id, upgraded: bool, cost: int | None = None) -> str:
    """'Pommel Strike+ [1 Attack]: Deal 10 damage. Draw 2 cards.'"""
    data = lookup("cards", _name(card_id))
    label = card_label(card_id, upgraded)
    if data is None:
        return label
    upgrade = data.get("upgrade") or {}
    desc = (upgraded and upgrade.get("description")) or data["description"]
    if cost is None:
        cost = upgrade.get("cost") if upgraded and upgrade.get("cost") is not None else data["cost"]
    cost_text = {-1: "X", -2: "unplayable"}.get(cost, str(cost)) if cost is not None else "?"
    return f"{label} [{cost_text} {data['type']}]: {_clean(desc)}"


def deck_card_text(card) -> str:
    return card_text(card.id, card.upgraded)


def relic_text(relic_id) -> str:
    data = lookup("relics", _name(relic_id))
    return f"{data['name']}: {_clean(data['description'])}" if data else _name(relic_id)


def relic_label(relic_id) -> str:
    data = lookup("relics", _name(relic_id))
    return data["name"] if data else _name(relic_id)


def potion_text(potion) -> str:
    data = lookup("potions", _name(potion))
    return f"{data['name']}: {_clean(data['description'])}" if data else _name(potion)


def potion_label(potion) -> str:
    data = lookup("potions", _name(potion))
    return data["name"] if data else _name(potion)


# --- run header ---------------------------------------------------------------

def _deck_summary(deck) -> str:
    counts = collections.Counter(card_label(c.id, c.upgraded) for c in deck)
    return ", ".join(f"{name} x{n}" if n > 1 else name for name, n in counts.items())


def run_header(gc) -> str:
    potions = [potion_label(p) for p in gc.potions if _name(p) != "EMPTY_POTION_SLOT"]
    lines = [
        f"Slay the Spire, Ironclad, ascension {gc.ascension}. Act {gc.act}, floor {gc.floor_num}. "
        f"HP {gc.cur_hp}/{gc.max_hp}. Gold {gc.gold}. Act boss: {_name(gc.boss).replace('_', ' ').title()}.",
        f"Relics: {', '.join(relic_label(r.id) for r in gc.relics) or 'none'}.",
        f"Potions ({len(potions)}/{gc.potion_capacity}): {', '.join(potions) or 'none'}.",
        f"Deck ({len(gc.deck)}): {_deck_summary(gc.deck)}.",
    ]
    return "\n".join(lines)


# --- map ----------------------------------------------------------------------

_ROOM_WORDS = {"MONSTER": "fight", "ELITE": "elite fight", "REST": "rest site", "SHOP": "shop",
               "EVENT": "unknown room (?)", "TREASURE": "treasure", "BOSS": "boss", "BOSS_TREASURE": "boss chest"}


def _room(gc, x: int, y: int) -> str:
    return _ROOM_WORDS.get(_name(gc.map.get_room_type(x, y)), _name(gc.map.get_room_type(x, y)).lower())


def _next_row(gc) -> int:
    return gc.cur_map_node_y + 1


def _lookahead(gc, x: int, y: int, depth: int = 4) -> str:
    """Room types reachable in the `depth` floors after (x, y), counted over distinct nodes."""
    seen: dict[tuple[int, int], str] = {}
    frontier = {x}
    for row in range(y + 1, min(y + 1 + depth, 15)):
        frontier = {nx for fx in frontier for nx in gc.map.edges(fx, row - 1)}
        for fx in frontier:
            seen[(fx, row)] = _room(gc, fx, row)
    counts = collections.Counter(seen.values())
    return ", ".join(f"{n} {room}" for room, n in counts.most_common()) or "the boss"


def describe_map_option(gc, action) -> str:
    x, y = action.idx1, _next_row(gc)
    if y >= 15:
        return "Go to the boss."
    return f"Go to a {_room(gc, x, y)} (column {x}); the next 4 floors along it can reach: {_lookahead(gc, x, y)}."


# --- rewards / shop / rest / chests -------------------------------------------

def describe_reward_option(gc, action) -> str:
    r = gc.screen_state_info.rewards_container
    kind = action.rewards_action_type
    if kind == RAT.CARD:
        if action.idx2 == 5:  # GameAction::SINGING_BOWL_CARD_IDX
            return "Skip this card reward and gain 2 Max HP (Singing Bowl)."
        return "Take card " + deck_card_text(r.cards[action.idx1][action.idx2])
    if kind == RAT.GOLD:
        return f"Take {r.gold[action.idx1]} gold."
    if kind == RAT.POTION:
        return "Take potion " + potion_text(r.potions[action.idx1])
    if kind == RAT.RELIC:
        return "Take relic " + relic_text(r.relics[action.idx1])
    if kind == RAT.KEY:
        if r.sapphire_key:
            return "Take the Sapphire Key (needed for Act 4) instead of the relic in this chest."
        return "Take the Emerald Key (needed for Act 4)."
    if kind == RAT.SKIP:
        return "Skip all remaining rewards on this screen and leave."
    return action.getDesc(gc)


def describe_shop_option(gc, action) -> str:
    shop = gc.screen_state_info.shop
    kind, i = action.rewards_action_type, action.idx1
    if kind == RAT.CARD:
        return f"Buy for {shop.prices[i]} gold: {deck_card_text(shop.cards[i])}"
    if kind == RAT.RELIC:
        return f"Buy for {shop.prices[7 + i]} gold: {relic_text(shop.relics[i])}"
    if kind == RAT.POTION:
        return f"Buy for {shop.prices[10 + i]} gold: {potion_text(shop.potions[i])}"
    if kind == RAT.CARD_REMOVE:
        return f"Pay {shop.remove_cost} gold to remove a card from the deck."
    if kind == RAT.SKIP:
        return "Leave the shop."
    return action.getDesc(gc)


def describe_rest_option(gc, action) -> str:
    heal = int(gc.max_hp * 0.3)
    return {
        0: f"Rest: heal {min(heal, gc.max_hp - gc.cur_hp)} HP.",
        1: "Smith: upgrade a card.",
        2: "Recall: take the Ruby Key (needed for Act 4) instead of resting.",
        3: "Lift (Girya): gain 1 Strength permanently.",
        4: "Toke (Peace Pipe): remove a card from the deck.",
        5: "Dig (Shovel): obtain a random relic.",
        6: "Leave the rest site without doing anything.",
    }.get(action.idx1, action.getDesc(gc))


def describe_boss_relic_option(gc, action) -> str:
    if action.rewards_action_type == RAT.SKIP:
        return "Take no boss relic."
    return "Take boss relic " + relic_text(gc.screen_state_info.boss_relics[action.idx1])


_SELECT_VERBS = {"TRANSFORM": "Transform", "TRANSFORM_UPGRADE": "Transform and upgrade", "UPGRADE": "Upgrade",
                 "REMOVE": "Remove from the deck", "DUPLICATE": "Duplicate", "OBTAIN": "Obtain",
                 "BOTTLE": "Bottle (starts every fight in hand)", "BONFIRE_SPIRITS": "Offer to the bonfire"}


def describe_card_select_option(gc, action) -> str:
    info = gc.screen_state_info
    verb = _SELECT_VERBS.get(_name(info.select_screen_type), _name(info.select_screen_type).title())
    card = info.to_select_cards[action.idx1]
    return f"{verb}: {deck_card_text(card)}"


def screen_context(gc) -> str:
    screen = _name(gc.screen_state)
    if screen == "EVENT_SCREEN":
        from .describe_events import describe_event_context
        return describe_event_context(gc)
    if screen == "CARD_SELECT":
        info = gc.screen_state_info
        verb = _SELECT_VERBS.get(_name(info.select_screen_type), _name(info.select_screen_type).title()).lower()
        return f"Choose a card to {verb}."
    if screen == "MAP_SCREEN":
        return f"Choose the next room on the map (floor {gc.floor_num + 1})."
    return {
        "REWARDS": "Rewards.",
        "BOSS_RELIC_REWARDS": "Boss chest: choose one boss relic.",
        "TREASURE_ROOM": "Treasure room with a chest.",
        "REST_ROOM": "Rest site.",
        "SHOP_ROOM": f"Shop (you have {gc.gold} gold).",
    }.get(screen, screen)


def describe_option(gc, action) -> str:
    screen = _name(gc.screen_state)
    if screen == "EVENT_SCREEN":
        from .describe_events import describe_event_option
        return describe_event_option(gc, action)
    if screen == "REWARDS":
        return describe_reward_option(gc, action)
    if screen == "SHOP_ROOM":
        return describe_shop_option(gc, action)
    if screen == "REST_ROOM":
        return describe_rest_option(gc, action)
    if screen == "MAP_SCREEN":
        return describe_map_option(gc, action)
    if screen == "BOSS_RELIC_REWARDS":
        return describe_boss_relic_option(gc, action)
    if screen == "CARD_SELECT":
        return describe_card_select_option(gc, action)
    if screen == "TREASURE_ROOM":
        return "Open the chest." if action.idx1 == 0 else "Leave the chest closed."
    return action.getDesc(gc)


# --- battle -------------------------------------------------------------------

@functools.cache
def _monster_moves() -> dict[str, dict[str, dict]]:
    """norm(monster id/name) -> {norm(move name): move} from the dataset."""
    table: dict[str, dict[str, dict]] = {}
    for m in json.loads((DATA_DIR / "monsters.json").read_text()):
        moves = {norm(mv["name"]): mv for mv in m["moves"] if mv.get("name")}
        for key in (m["id"], m["name"]):
            table.setdefault(norm(key), moves)
    return table


def _intent_kind(monster, move_id: str) -> str | None:
    """Dataset intent (ATTACK_DEBUFF, BUFF, DEFEND, ...) whose move name ends the engine move id."""
    moves = _monster_moves().get(norm(_name(monster.id))) or _monster_moves().get(norm(monster.getName()))
    if not moves:
        return None
    key = norm(move_id)
    hits = [mv for name, mv in moves.items() if name and key.endswith(name)]
    return max(hits, key=lambda mv: len(norm(mv["name"])))["intent"] if hits else None


_STATUS_SKIP = {"INVALID"}

# What an enemy power does, written against the engine (the dataset text has unfilled X
# placeholders). Strength, Vulnerable and Weak are left out as common knowledge.
_ENEMY_POWER_NOTES = {
    "ANGRY": "whenever it takes attack damage, it gains that much Strength",
    "ARTIFACT": "negates that many debuffs applied to it",
    "ASLEEP": "asleep; wakes up when it loses HP or after 3 turns, and then loses 8 Metallicize",
    "BARRICADE": "its Block is not removed at the start of its turn",
    "BEAT_OF_DEATH": "whenever you play a card, you take that much damage",
    "BLOCK_RETURN": "whenever you attack it, you gain that much Block",
    "CHOKED": "whenever you play a card this turn, it loses that much HP",
    "CORPSE_EXPLOSION": "when it dies, it deals damage equal to its Max HP to all other enemies",
    "CURIOSITY": "whenever you play a Power, it gains that much Strength",
    "CURL_UP": "the first time it takes attack damage, it gains that much Block (once per combat)",
    "ENRAGE": "whenever you play a Skill, it gains that much Strength",
    "FADING": "dies in that many turns",
    "FLIGHT": "takes 50% less attack damage; loses Flight after that many hits in one turn",
    "GENERIC_STRENGTH_UP": "gains that much Strength every turn",
    "INTANGIBLE": "all damage and HP loss it takes is reduced to 1",
    "INVINCIBLE": "can lose at most that much more HP this turn",
    "LOCK_ON": "takes 50% more damage from Orbs",
    "MALLEABLE": "whenever it takes attack damage, it gains that much Block, 1 more for each later hit this turn",
    "MARK": "whenever you play Pressure Points, it loses that much HP",
    "METALLICIZE": "gains that much Block at the end of each turn",
    "MINION": "flees when its leader dies",
    "MODE_SHIFT": "after taking that much more damage, it switches to a defensive mode",
    "PAINFUL_STABS": "whenever its attack deals you unblocked damage, a Wound is added to your discard pile",
    "PLATED_ARMOR": "gains that much Block at the end of each turn; unblocked attack damage reduces it by 1",
    "POISON": "loses that much HP each turn, then Poison drops by 1",
    "REACTIVE": "changes its intent whenever it takes attack damage",
    "REGEN": "heals that much HP each turn, then Regen drops by 1",
    "REGROW": "revives after dying while another enemy with Regrow is alive",
    "RITUAL": "gains that much Strength at the end of each of its turns",
    "SHACKLED": "regains that much Strength at the end of its turn",
    "SHARP_HIDE": "whenever you play an Attack, you take that much damage",
    "SHIFTING": "whenever it loses HP, it loses that much Strength until the end of the turn",
    "SLOW": "takes 10% more attack damage for each card you have played this turn",
    "SPORE_CLOUD": "when it dies, you gain that much Vulnerable",
    "STASIS": "holds one of your cards; it returns to your hand when this enemy dies",
    "THIEVERY": "steals that much Gold with each attack",
    "THORNS": "whenever you attack it, you take that much damage",
    "TIME_WARP": "counts the cards you play; at 12 your turn ends and it gains 2 Strength",
}


def _statuses(obj, enum) -> list[str]:
    out = []
    for name, value in enum.__members__.items():
        if name in _STATUS_SKIP:
            continue
        try:
            amount = obj.getStatus(value)
        except Exception:
            continue
        if amount:
            out.append(f"{name.replace('_', ' ').title()} {amount}")
    return out


def _move_label(monster, move: str) -> str:
    """'GREEN_LOUSE_SPIT_WEB' -> 'Spit Web' (drops the monster prefix the engine puts on every move)."""
    prefix = _name(monster.id) + "_"
    words = move[len(prefix):] if move.startswith(prefix) else "_".join(move.split("_")[-2:])
    return words.replace("_", " ").title()


def _intent(bc, m) -> str:
    if bc.intents_hidden:
        return "intent hidden"
    move = _name(sts.MonsterMoveId(m.moveHistory[0]))  # moveHistory holds raw ints
    if move == "INVALID":
        return "intent not yet known"
    base, hits = m.get_move_base_damage(bc)
    kind = _intent_kind(m, move) or ""
    parts = []
    if hits > 0:
        dmg = base + m.strength
        if m.weak:
            dmg = int(dmg * 0.75)
        if bc.player.getStatus(sts.PlayerStatus.VULNERABLE):
            dmg = int(dmg * 1.5)
        parts.append(f"attack {max(dmg, 0)}" + (f"x{hits}" if hits > 1 else ""))
    words = {"DEFEND": "block", "BUFF": "buff", "DEBUFF": "debuff", "STRONG": "strong debuff",
             "ESCAPE": "escape", "SLEEP": "sleep", "STUN": "stunned"}
    tokens = kind.split("_")
    parts += [w for t, w in words.items() if t in tokens and not (t == "DEBUFF" and "STRONG" in tokens)]
    return f"{_move_label(m, move)} (" + (", ".join(dict.fromkeys(parts)) or "no attack") + ")"


def monster_name(m) -> str:
    data = lookup("monsters", _name(m.id)) or lookup("monsters", m.getName())
    return data["name"] if data else m.getName()


def _monster_line(bc, i: int) -> str:
    m = bc.monsters[i]
    bits = [f"HP {m.curHp}/{m.maxHp}"]
    if m.block:
        bits.append(f"block {m.block}")
    bits += _statuses(m, sts.MonsterStatus)
    return f"#{i} {monster_name(m)}: " + ", ".join(bits) + f"; intends {_intent(bc, m)}"


def _enemy_power_notes(bc) -> str | None:
    """One line explaining every noted power on a living enemy, each power once."""
    seen: dict[str, str] = {}
    for i in range(bc.monsters.monsterCount):
        m = bc.monsters[i]
        if not m.isAlive():
            continue
        for name, value in sts.MonsterStatus.__members__.items():
            if name in _ENEMY_POWER_NOTES and name not in seen and m.getStatus(value):
                seen[name] = f"{name.replace('_', ' ').title()}: {_ENEMY_POWER_NOTES[name]}"
    return "Enemy powers: " + "; ".join(seen.values()) + "." if seen else None


def battle_state(bc, power_notes: bool = False) -> str:
    p = bc.player
    pbits = [f"HP {p.curHp}/{p.maxHp}", f"block {p.block}", f"energy {p.energy}/{p.energyPerTurn}"]
    pbits += _statuses(p, sts.PlayerStatus)
    cards = bc.cards
    hand = [card_label(c.id, c.upgraded) + f"({c.costForTurn})" for c in cards.hand[:cards.cardsInHand]]
    potions = [potion_label(q) for q in bc.potions if _name(q) != "EMPTY_POTION_SLOT"]
    monsters = [_monster_line(bc, i) for i in range(bc.monsters.monsterCount) if bc.monsters[i].isAlive()]
    lines = [
        f"Battle turn {bc.turn + 1}. Player: " + ", ".join(pbits) + ".",
        "Enemies: " + " | ".join(monsters) + ".",
        f"Hand: {', '.join(hand) or 'empty'}. Draw pile {len(cards.drawPile)}, discard {len(cards.discardPile)}, exhaust {len(cards.exhaustPile)}.",
    ]
    if power_notes and (notes := _enemy_power_notes(bc)):
        lines.insert(2, notes)
    if potions:
        lines.append(f"Potions: {', '.join(potions)}.")
    return "\n".join(lines)


# In-combat card selects: (pile the select index points into, what picking a card does).
_SELECT_TASKS = {
    "ARMAMENTS": ("hand", "Upgrade for this combat"),
    "DUAL_WIELD": ("hand", "Copy into hand"),
    "EXHAUST_ONE": ("hand", "Exhaust"),
    "EXHAUST_MANY": ("hand", "Exhaust"),
    "FORETHOUGHT": ("hand", "Put at the bottom of the draw pile; it costs 0 next play"),
    "WARCRY": ("hand", "Put on top of the draw pile"),
    "SETUP": ("hand", "Put on top of the draw pile; it costs 0 next play"),
    "GAMBLE": ("hand", "Discard, then redraw as many"),
    "NIGHTMARE": ("hand", "Add 3 copies to hand next turn"),
    "RECYCLE": ("hand", "Exhaust for energy equal to its cost"),
    "HEADBUTT": ("discard", "Put on top of the draw pile"),
    "HOLOGRAM": ("discard", "Return to hand"),
    "LIQUID_MEMORIES_POTION": ("discard", "Return to hand; it costs 0 this turn"),
    "MEDITATE": ("discard", "Return to hand"),
    "EXHUME": ("exhaust", "Return to hand"),
    "SECRET_TECHNIQUE": ("draw", "Put into hand"),
    "SECRET_WEAPON": ("draw", "Put into hand"),
    "SEEK": ("draw", "Put into hand"),
    "DISCOVERY": ("generated", "Add to hand"),
    "CODEX": ("generated", "Shuffle into the draw pile"),
}


def _select_card_text(bc, pile: str, idx: int) -> str:
    if pile == "generated":
        return card_text(bc.card_select_generated_cards[idx], False)
    cards = {"hand": bc.cards.hand[:bc.cards.cardsInHand], "discard": bc.cards.discardPile,
             "exhaust": bc.cards.exhaustPile, "draw": bc.cards.drawPile}[pile]
    c = cards[idx]
    return card_text(c.id, c.upgraded, c.costForTurn)


def battle_select_context(bc) -> str:
    task = _name(bc.card_select_task)
    pile, verb = _SELECT_TASKS.get(task, ("hand", task.title()))
    return f"Card choice ({task.replace('_', ' ').title()}): pick a card from your {pile} pile to: {verb}."


def _target_text(bc, t: int) -> str:
    # The engine can offer a targeted action with no enemy to target (e.g. while the Awakened One
    # revives, every enemy slot is dead and the target index is a sentinel).
    if 0 <= t < len(bc.monsters):
        return f" -> target #{t} {monster_name(bc.monsters[t])}"
    return " (no enemy to target)"


def describe_battle_action(bc, action) -> str:
    kind = _name(action.get_action_type())
    if kind in ("SINGLE_CARD_SELECT", "MULTI_CARD_SELECT"):
        pile, verb = _SELECT_TASKS.get(_name(bc.card_select_task), ("hand", "Choose"))
        idxs = [action.get_select_idx()] if kind == "SINGLE_CARD_SELECT" else action.get_selected_idxs()
        if not idxs:
            return f"{verb}: no card."
        if pile == "generated" and idxs[0] >= len(bc.card_select_generated_cards):
            return "Skip: take none of the offered cards."   # Nilry's Codex lets the player skip
        return f"{verb}: " + "; ".join(_select_card_text(bc, pile, i) for i in idxs)
    if kind == "POTION":
        potion = bc.potions[action.get_source_idx()]
        t = action.get_target_idx()
        if t == -1:
            return f"Discard potion {potion_label(potion)} (frees the slot)."
        text = "Drink " + potion_text(potion)
        if sts.potion_requires_target(potion):
            text += _target_text(bc, t)
        return text
    if kind == "CARD":
        c = bc.cards.hand[action.get_source_idx()]
        text = card_text(c.id, c.upgraded, c.costForTurn)
        if c.requiresTarget():
            text += _target_text(bc, action.get_target_idx())
        dmg = bc.get_card_damage_display(c)
        if dmg >= 0 and dmg != bc.get_card_base_damage(c):
            text += f" (currently {dmg} damage per hit before the target's modifiers)"
        return "Play " + text
    if kind == "END_TURN":
        return f"End turn ({bc.player.energy} energy unused)."
    return re.sub(r"[{}]", "", action.print_desc(bc)).strip()
