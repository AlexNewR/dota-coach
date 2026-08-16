from __future__ import annotations

from dataclasses import dataclass

from dota_coach.constants import hero_display, item_display, normalize_item_name
from dota_coach.gsi.normalize import GameState

# Апгрейды считают как базовый контр-предмет.
_UPGRADES: dict[str, str] = {
    "wind_waker": "cyclone",
    "hurricane_pike": "force_staff",
    "bloodthorn": "orchid",
    "spirit_vessel": "urn_of_shadows",
    "disperser": "diffusal_blade",
    "mjollnir": "maelstrom",
    "abyssal_blade": "basher",
    "travel_boots_2": "travel_boots",
    "overwhelming_blink": "blink",
    "swift_blink": "blink",
    "arcane_blink": "blink",
}


@dataclass(frozen=True)
class CounterHit:
    item: str
    enemy_id: int
    enemy: str
    reason: str
    instead: tuple[str, ...] = ()


def _canon(name: str) -> str:
    key = normalize_item_name(name)
    return _UPGRADES.get(key, key)


def _owned(state: GameState) -> set[str]:
    names = {normalize_item_name(item) for item in state.items}
    names.discard("")
    return names | {_canon(item) for item in names}


# Теги героев → типичные контры. Конкретные герои ниже перекрывают.
_TAG_PREFER: dict[str, dict[str, str]] = {
    "fury": {
        "cyclone": "сбивает прыжок и останавливает стаки ударов",
        "ghost": "Ursa/Troll не могут бить, пока ты эфирный",
        "ethereal_blade": "то же, что Ghost, плюс замедление",
        "force_staff": "вытолкнуть из Overpower / ближнего боя",
        "aeon_disk": "переживает первый размен, пока висит Enrage",
    },
    "jump": {
        "cyclone": "сбивает инициацию и даёт время на отход",
        "ghost": "прыжок в пустоту: бить тебя нельзя",
        "force_staff": "выйти из радиуса после прыжка",
        "blink": "сбросить дистанцию после ганка",
    },
    "rightclick": {
        "ghost": "физический керри не бьёт эфирную цель",
        "cyclone": "сбросить бафы и остановить хит-трейн",
        "ethereal_blade": "выключить автоатаки",
        "aeon_disk": "страховка от критов и бурста",
        "sheepstick": "жёсткий контроль керри",
    },
    "magic": {
        "black_king_bar": "пережить магический бурст",
        "glimmer_cape": "дешёвая защита от спеллов",
        "pipe": "щит команде против магии",
        "lotus_orb": "отражает одиночные касты",
        "aeon_disk": "второй шанс после комбо",
    },
    "silence": {
        "black_king_bar": "BKB снимает сайленс и даёт кастовать",
        "lotus_orb": "отражает Orchid / Hex / саппорт-лок",
        "manta": "диспелл сайленса, если не пробивает BKB",
        "sphere": "блок первого таргета (Hex, Orchid, Doom)",
    },
    "heal": {
        "spirit_vessel": "режет реген Huskar / Alch / Morph / WW",
        "skadi": "сильный антиреген на правой кнопке",
        "shivas_guard": "аурой режет хил в драке",
    },
    "illusion": {
        "maelstrom": "клир иллюзий через прыжки молнии",
        "radiance": "аурой жжёт иллюзии",
        "shivas_guard": "волна и аура по иллюзиям",
        "bfury": "клир крипов и иллюзий",
    },
    "invis": {
        "gem": "постоянное зрение против инвиза",
        "silver_edge": "брейк пассивок + свой инвиз на отход",
    },
    "break": {
        "silver_edge": "брейк пассивки (Fury, Blur, Dispersion, Rage)",
        "nullifier": "снимает эфир / глиммер / призрака",
    },
}

_TAG_AVOID: dict[str, dict[str, str]] = {
    "fury": {
        "heart": "Heart не спасает: Fury Swipes копятся с каждым ударом, реген не успевает",
        "satanic": "лifesteal не останавливает стаки; тебя убивают быстрее, чем ты отхиливаешься",
        "assault": "броня слабо помогает против накопительного физического урона Ursa/Troll",
    },
    "heal": {
        "heart": "против сильного регена врага твоё HP ничего не решает — нужен Vessel / Skadi",
    },
}

# id героя → теги. Неполный список: неизвестный герой просто не даёт контров.
_HERO_TAGS: dict[int, tuple[str, ...]] = {
    70: ("fury", "jump", "rightclick"),  # Ursa
    95: ("fury", "rightclick"),  # Troll
    54: ("rightclick", "heal", "break"),  # Lifestealer
    44: ("rightclick",),  # PA
    1: ("rightclick",),  # AM
    8: ("rightclick", "break"),  # Juggernaut
    18: ("rightclick",),  # Sven
    42: ("rightclick", "break"),  # Wraith King
    6: ("rightclick", "silence"),  # Drow
    35: ("rightclick",),  # Sniper
    94: ("rightclick", "break"),  # Medusa
    109: ("rightclick", "illusion", "break"),  # Terrorblade
    10: ("rightclick", "heal"),  # Morphling
    48: ("rightclick",),  # Luna
    72: ("rightclick",),  # Gyro
    114: ("rightclick",),  # Monkey King
    12: ("illusion",),  # Phantom Lancer
    89: ("illusion",),  # Naga
    81: ("illusion", "rightclick"),  # Chaos Knight
    67: ("illusion", "break"),  # Spectre
    93: ("jump", "rightclick", "break"),  # Slark
    71: ("jump",),  # Spirit Breaker
    51: ("jump",),  # Clockwerk
    104: ("jump", "silence"),  # Legion
    17: ("jump", "magic", "silence"),  # Storm
    39: ("jump", "magic"),  # QoP
    13: ("jump", "magic"),  # Puck
    88: ("jump", "magic", "silence"),  # Nyx
    11: ("magic", "rightclick"),  # SF
    74: ("magic", "invis"),  # Invoker
    25: ("magic",),  # Lina
    52: ("magic",),  # Leshrac
    22: ("magic",),  # Zeus
    76: ("magic", "silence"),  # OD
    34: ("magic",),  # Tinker
    101: ("magic", "silence"),  # Skywrath
    26: ("silence", "magic"),  # Lion
    27: ("silence", "magic"),  # Shadow Shaman
    75: ("silence",),  # Silencer
    69: ("silence", "heal"),  # Doom
    32: ("invis", "silence", "jump"),  # Riki
    62: ("invis",),  # Bounty
    56: ("invis", "rightclick"),  # Clinkz
    63: ("invis", "rightclick"),  # Weaver
    46: ("invis", "rightclick"),  # TA
    21: ("invis",),  # Windranger
    59: ("heal", "rightclick"),  # Huskar
    73: ("heal",),  # Alchemist
    36: ("heal", "magic"),  # Necrophos
    112: ("heal",),  # Winter Wyvern
    50: ("heal",),  # Dazzle
    111: ("heal",),  # Oracle
    102: ("heal",),  # Abaddon
    57: ("heal",),  # Omniknight
    2: ("jump",),  # Axe
    14: ("jump",),  # Pudge
    99: ("rightclick", "break"),  # Bristleback
    47: ("rightclick",),  # Viper
}

# Точечные причины, важнее тегов. Пример из запроса: Heart vs Ursa.
_HERO_PREFER: dict[int, dict[str, str]] = {
    70: {
        "cyclone": "Eul's против Ursa: сбивает Earthshock, стопает Overpower и даёт Enrage истечь",
        "ghost": "Ghost: Ursa не бьёт, стаки Fury Swipes не растут",
        "ethereal_blade": "Ethereal Blade выключает автоатаки Ursa",
        "force_staff": "Force/Pike: выйти из ближнего боя после прыжка",
    },
    95: {
        "cyclone": "Eul's стопает Troll в melee и сбивает баф скорости атаки",
        "ghost": "Ghost против ярости Troll",
    },
    44: {
        "ghost": "Ghost против crit PA — она не может тебя бить",
        "ethereal_blade": "Ethereal Blade то же + замедление",
        "aeon_disk": "Aeon Disk переживает Dagger + crit",
    },
    59: {
        "spirit_vessel": "Vessel режет реген Huskar — без него он не умирает",
        "skadi": "Skadi дополнительно душит хил",
    },
    1: {
        "black_king_bar": "BKB, чтобы AM не выжег ману и не разобрал в ближнем бою",
        "sheepstick": "Hex на AM, пока нет своего Manta/BKB",
    },
}

_HERO_AVOID: dict[int, dict[str, str]] = {
    70: {
        "heart": "Heart против Ursa — плохой выбор: Fury Swipes копятся с ударами, HP-реген не успевает. Нужен Eul's или Ghost",
        "satanic": "Satanic против Ursa не останавливает стаки. Сначала Eul's / Ghost",
    },
    95: {
        "heart": "Heart против Troll слабо: он ускоряется и стакает урон. Нужен Eul's / Ghost",
    },
    44: {
        "heart": "Heart плохо держит crit PA. Бери Ghost или Aeon Disk",
    },
    59: {
        "heart": "Heart не лечит гонку регена с Huskar. Бери Spirit Vessel",
    },
}


def _rules_for(hero_id: int) -> tuple[dict[str, str], dict[str, str]]:
    prefer: dict[str, str] = {}
    avoid: dict[str, str] = {}
    for tag in _HERO_TAGS.get(hero_id, ()):
        prefer.update(_TAG_PREFER.get(tag, {}))
        avoid.update(_TAG_AVOID.get(tag, {}))
    prefer.update(_HERO_PREFER.get(hero_id, {}))
    avoid.update(_HERO_AVOID.get(hero_id, {}))
    return prefer, avoid


def analyze(state: GameState) -> dict[str, list[dict[str, object]]]:
    enemies = [hid for hid in state.enemy_heroes if hid and hid != state.hero_id]
    owned = _owned(state)
    mistakes: list[CounterHit] = []
    suggestions: list[CounterHit] = []
    seen_suggest: set[str] = set()

    for hid in enemies:
        prefer, avoid = _rules_for(hid)
        enemy = hero_display(hid)
        instead = tuple(item for item in prefer if _canon(item) not in owned)[:3]
        for item, reason in avoid.items():
            if item in owned or _canon(item) in owned:
                mistakes.append(
                    CounterHit(
                        item=item,
                        enemy_id=hid,
                        enemy=enemy,
                        reason=reason,
                        instead=instead or tuple(prefer.keys())[:3],
                    )
                )
        for item, reason in prefer.items():
            if _canon(item) in owned or item in seen_suggest:
                continue
            seen_suggest.add(item)
            suggestions.append(
                CounterHit(item=item, enemy_id=hid, enemy=enemy, reason=reason)
            )

    def as_dict(hit: CounterHit) -> dict[str, object]:
        return {
            "item": hit.item,
            "label": item_display(hit.item),
            "enemy_id": hit.enemy_id,
            "enemy": hit.enemy,
            "reason": hit.reason,
            "instead": [
                {"name": name, "label": item_display(name)} for name in hit.instead
            ],
        }

    return {
        "enemies": [{"id": hid, "name": hero_display(hid)} for hid in enemies],
        "mistakes": [as_dict(hit) for hit in mistakes],
        "suggestions": [as_dict(hit) for hit in suggestions[:4]],
    }


def mistake_for_purchase(state: GameState, new_items: set[str]) -> CounterHit | None:
    bought = {_canon(item) for item in new_items if item}
    if not bought:
        return None
    for hid in state.enemy_heroes:
        if not hid or hid == state.hero_id:
            continue
        prefer, avoid = _rules_for(hid)
        enemy = hero_display(hid)
        instead = tuple(prefer.keys())[:3]
        for item in bought:
            if item in avoid:
                return CounterHit(
                    item=item,
                    enemy_id=hid,
                    enemy=enemy,
                    reason=avoid[item],
                    instead=instead,
                )
    return None
