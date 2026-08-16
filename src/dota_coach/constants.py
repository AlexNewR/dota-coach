from __future__ import annotations

HEROES: dict[int, dict[str, str]] = {
    80: {
        "npc": "npc_dota_hero_lone_druid",
        "name": "lone_druid",
        "en": "Lone Druid",
        "ru": "Лон Друид",
    },
    91: {
        "npc": "npc_dota_hero_wisp",
        "name": "wisp",
        "en": "Io",
        "ru": "Ио",
    },
    90: {
        "npc": "npc_dota_hero_keeper_of_the_light",
        "name": "keeper_of_the_light",
        "en": "Keeper of the Light",
        "ru": "Хранитель Света",
    },
    107: {
        "npc": "npc_dota_hero_earth_spirit",
        "name": "earth_spirit",
        "en": "Earth Spirit",
        "ru": "Земляной Дух",
    },
}

NPC_TO_ID = {meta["npc"]: hid for hid, meta in HEROES.items()}
NAME_TO_ID = {meta["name"]: hid for hid, meta in HEROES.items()}
NAME_TO_ID["io"] = 91
NAME_TO_ID["kotl"] = 90
NAME_TO_ID["ld"] = 80
NAME_TO_ID["es"] = 107
NAME_TO_ID["earthspirit"] = 107

ROLE_RU = {
    1: "керри",
    2: "мид",
    3: "оффлейн",
    4: "саппорт",
    5: "полная поддержка",
}

ITEM_RU: dict[str, str] = {
    "magic_wand": "Magic Wand",
    "bottle": "Bottle",
    "null_talisman": "Null Talisman",
    "bracer": "Bracer",
    "wraith_band": "Wraith Band",
    "power_treads": "Power Treads",
    "phase_boots": "Phase Boots",
    "arcane_boots": "Arcane Boots",
    "travel_boots": "Boots of Travel",
    "travel_boots_2": "Boots of Travel 2",
    "urn_of_shadows": "Urn of Shadows",
    "spirit_vessel": "Spirit Vessel",
    "soul_ring": "Soul Ring",
    "aether_lens": "Aether Lens",
    "force_staff": "Force Staff",
    "glimmer_cape": "Glimmer Cape",
    "ghost": "Ghost Scepter",
    "mekansm": "Mekansm",
    "guardian_greaves": "Guardian Greaves",
    "holy_locket": "Holy Locket",
    "orchid": "Orchid Malevolence",
    "bloodthorn": "Bloodthorn",
    "dagon": "Dagon",
    "dagon_5": "Dagon 5",
    "cyclone": "Eul's Scepter",
    "wind_waker": "Wind Waker",
    "sheepstick": "Scythe of Vyse",
    "octarine_core": "Octarine Core",
    "ultimate_scepter": "Aghanim's Scepter",
    "aghanims_shard": "Aghanim's Shard",
    "black_king_bar": "Black King Bar",
    "blink": "Blink Dagger",
    "sphere": "Linken's Sphere",
    "lotus_orb": "Lotus Orb",
    "aeon_disk": "Aeon Disk",
    "heart": "Heart of Tarrasque",
    "satanic": "Satanic",
    "skadi": "Eye of Skadi",
    "hurricane_pike": "Hurricane Pike",
    "manta": "Manta Style",
    "blade_mail": "Blade Mail",
    "crimson_guard": "Crimson Guard",
    "shivas_guard": "Shiva's Guard",
    "bfury": "Battle Fury",
    "gem": "Gem of True Sight",
    "kaya": "Kaya",
    "yasha": "Yasha",
    "kaya_and_sange": "Kaya and Sange",
    "maelstrom": "Maelstrom",
    "mjollnir": "Mjollnir",
    "diffusal_blade": "Diffusal Blade",
    "disperser": "Disperser",
    "invis_sword": "Shadow Blade",
    "silver_edge": "Silver Edge",
    "orb_of_corrosion": "Orb of Corrosion",
    "monkey_king_bar": "Monkey King Bar",
    "butterfly": "Butterfly",
    "abyssal_blade": "Abyssal Blade",
    "basher": "Skull Basher",
    "desolator": "Desolator",
    "radiance": "Radiance",
    "assault": "Assault Cuirass",
    "mask_of_madness": "Mask of Madness",
    "helm_of_the_dominator": "Helm of the Dominator",
    "helm_of_the_overlord": "Helm of the Overlord",
    "pavise": "Pavise",
    "solar_crest": "Solar Crest",
    "pipe": "Pipe of Insight",
    "vladmir": "Vladmir's Offering",
    "ethereal_blade": "Ethereal Blade",
    "meteor_hammer": "Meteor Hammer",
    "hand_of_midas": "Hand of Midas",
    "refresher": "Refresher Orb",
    "nullifier": "Nullifier",
    "swift_blink": "Swift Blink",
    "tranquil_boots": "Tranquil Boots",
    "echo_sabre": "Echo Sabre",
    "harpoon": "Harpoon",
    "witch_blade": "Witch Blade",
    "bloodstone": "Bloodstone",
    "rod_of_atos": "Rod of Atos",
    "veil_of_discord": "Veil of Discord",
    "shivas_guard": "Shiva's Guard",
    "sange": "Sange",
    "yasha": "Yasha",
    "sange_and_yasha": "Sange and Yasha",
    "dragon_lance": "Dragon Lance",
    "overwhelming_blink": "Overwhelming Blink",
    "arcane_blink": "Arcane Blink",
}

ITEM_COSTS: dict[str, int] = {
    "magic_wand": 450,
    "bottle": 675,
    "null_talisman": 505,
    "bracer": 505,
    "wraith_band": 505,
    "power_treads": 1400,
    "phase_boots": 1500,
    "arcane_boots": 1300,
    "travel_boots": 2500,
    "urn_of_shadows": 880,
    "spirit_vessel": 2780,
    "soul_ring": 805,
    "aether_lens": 2275,
    "force_staff": 2200,
    "glimmer_cape": 2150,
    "ghost": 1500,
    "mekansm": 1775,
    "guardian_greaves": 4950,
    "holy_locket": 2400,
    "orchid": 3275,
    "bloodthorn": 6625,
    "dagon": 2850,
    "dagon_5": 5250,
    "cyclone": 2625,
    "wind_waker": 6825,
    "sheepstick": 5175,
    "octarine_core": 4600,
    "ultimate_scepter": 4200,
    "aghanims_shard": 1400,
    "black_king_bar": 4050,
    "blink": 2250,
    "sphere": 4600,
    "lotus_orb": 3850,
    "aeon_disk": 3000,
    "heart": 5100,
    "kaya": 2100,
    "maelstrom": 2950,
    "mjollnir": 5500,
    "diffusal_blade": 2500,
    "disperser": 6100,
    "invis_sword": 3000,
    "silver_edge": 5450,
    "orb_of_corrosion": 925,
    "monkey_king_bar": 4975,
    "butterfly": 5450,
    "abyssal_blade": 6250,
    "basher": 2875,
    "desolator": 3500,
    "radiance": 4700,
    "assault": 5125,
    "mask_of_madness": 2700,
    "helm_of_the_dominator": 2625,
    "pavise": 1400,
    "solar_crest": 2700,
    "pipe": 3725,
    "ethereal_blade": 4650,
    "meteor_hammer": 2850,
    "hand_of_midas": 2200,
    "refresher": 5000,
    "nullifier": 4375,
    "tranquil_boots": 925,
    "echo_sabre": 2700,
    "harpoon": 4700,
    "witch_blade": 2775,
    "bloodstone": 4400,
    "rod_of_atos": 2250,
    "veil_of_discord": 1725,
    "shivas_guard": 5175,
    "sange": 2100,
    "yasha": 2100,
    "sange_and_yasha": 4100,
    "kaya_and_sange": 4100,
    "dragon_lance": 1900,
    "overwhelming_blink": 6800,
    "arcane_blink": 6800,
    "travel_boots_2": 4500,
    "wind_waker": 6825,
    "lotus_orb": 3850,
}

SKIP_ITEMS = {
    "tango",
    "tpscroll",
    "clarity",
    "flask",
    "enchanted_mango",
    "faerie_fire",
    "ward_observer",
    "ward_sentry",
    "smoke_of_deceit",
    "dust",
    "blood_grenade",
    "great_famango",
    "famango",
    "cheese",
    "healing_lotus",
    "greater_healing_lotus",
    "tome_of_knowledge",
    "branches",
    "circlet",
    "gauntlets",
    "slippers",
    "mantle",
    "belt_of_strength",
    "boots_of_elves",
    "robe",
    "boots",
    "magic_stick",
    "blight_stone",
    "blades_of_attack",
    "mithril_hammer",
    "javelin",
    "quarterstaff",
    "eagle",
    "reaver",
    "mystic_staff",
    "ultimate_orb",
    "point_booster",
    "energy_booster",
    "vitality_booster",
    "void_stone",
    "staff_of_wizardry",
    "ogre_axe",
    "blade_of_alacrity",
    "lifesteal",
    "cloak",
    "headdress",
    "buckler",
    "ring_of_basilius",
    "sobi_mask",
    "infused_raindrop",
    "wind_lace",
    "fluffy_hat",
    "crown",
    "diadem",
    "cornucopia",
    # Компоненты / нейтралы — в лайве советуем только готовый слот
    "tiara_of_selemene",
    "gloves",
    "platemail",
    "splintmail",
    "soul_booster",
    "chasm_stone",
    "blitz_knuckles",
    "claymore",
    "chainmail",
    "oblivion_staff",
    "wizard_hat",
    "voodoo_mask",
    "hyperstone",
    "ring_of_tarrasque",
    "ring_of_health",
    "ring_of_protection",
    "ring_of_regen",
    "pers",
    "helm_of_iron_will",
    "shadow_amulet",
    "orb_of_frost",
    "shawl",
    "demon_edge",
    "greater_famango",
    "consecrated_wraps",
    "essence_distiller",
    "relic",
    "talisman_of_evasion",
    "crellas_crozier",
    "broadsword",
    "orb_of_venom",
}

BOOT_ITEMS = {
    "power_treads",
    "phase_boots",
    "arcane_boots",
    "tranquil_boots",
    "travel_boots",
    "travel_boots_2",
    "guardian_greaves",
}

ITEM_UPGRADES: dict[str, str] = {
    "travel_boots": "travel_boots_2",
    "maelstrom": "mjollnir",
    "orchid": "bloodthorn",
    "invis_sword": "silver_edge",
    "kaya": "kaya_and_sange",
    "sange": "kaya_and_sange",
    "yasha": "sange_and_yasha",
    "basher": "abyssal_blade",
    "diffusal_blade": "disperser",
    "helm_of_the_dominator": "helm_of_the_overlord",
    "cyclone": "wind_waker",
    "force_staff": "hurricane_pike",
    "urn_of_shadows": "spirit_vessel",
    "pavise": "solar_crest",
    "mekansm": "guardian_greaves",
    "echo_sabre": "harpoon",
    "dragon_lance": "hurricane_pike",
    "blink": "overwhelming_blink",
}

INVENTORY_SLOT_LIMIT = 6
BOOT_LATE_MINUTE = 18

# Компоненты улучшений: если у игрока есть апгрейд (ключ),
# все базовые предметы (значение) считаются уже купленными / поглощенными апгрейдом.
UPGRADE_COMPONENTS: dict[str, set[str]] = {
    "silver_edge": {"invis_sword"},
    "spirit_vessel": {"urn_of_shadows"},
    "mjollnir": {"maelstrom"},
    "bloodthorn": {"orchid", "mage_slayer"},
    "abyssal_blade": {"basher"},
    "disperser": {"diffusal_blade"},
    "hurricane_pike": {"force_staff", "dragon_lance"},
    "wind_waker": {"cyclone"},
    "harpoon": {"echo_sabre"},
    "guardian_greaves": {"mekansm", "arcane_boots"},
    "solar_crest": {"pavise"},
    "travel_boots_2": {"travel_boots"},
    "travel_boots": {"boots"},
    "power_treads": {"boots"},
    "phase_boots": {"boots"},
    "tranquil_boots": {"boots"},
    "boots_of_bearing": {"tranquil_boots", "drums", "boots"},
    "kaya_and_sange": {"kaya", "sange"},
    "sange_and_yasha": {"sange", "yasha"},
    "yasha_and_kaya": {"yasha", "kaya"},
    "overwhelming_blink": {"blink"},
    "swift_blink": {"blink"},
    "arcane_blink": {"blink"},
    "helm_of_the_overlord": {"helm_of_the_dominator", "vladmir"},
    "gleipnir": {"rod_of_atos", "maelstrom"},
    "khanda": {"phylactery", "crystalys"},
    "parasma": {"witch_blade"},
}

# Прямое требование базы: если игрок хочет апгрейд (ключ), но базы (значение) нет,
# советуем сначала базу.
UPGRADE_PREREQUISITES: dict[str, str] = {
    "silver_edge": "invis_sword",
    "spirit_vessel": "urn_of_shadows",
    "mjollnir": "maelstrom",
    "bloodthorn": "orchid",
    "abyssal_blade": "basher",
    "disperser": "diffusal_blade",
    "wind_waker": "cyclone",
    "harpoon": "echo_sabre",
    "guardian_greaves": "mekansm",
    "solar_crest": "pavise",
    "travel_boots_2": "travel_boots",
    "gleipnir": "rod_of_atos",
    "khanda": "phylactery",
    "parasma": "witch_blade",
    "overwhelming_blink": "blink",
    "swift_blink": "blink",
    "arcane_blink": "blink",
}

# Ранний мусор / слабые слоты: в лейте продаём, чтобы влез новый айтем.
EARLY_SELL_ITEMS: tuple[str, ...] = (
    "magic_wand",
    "magic_stick",
    "null_talisman",
    "bracer",
    "wraith_band",
    "orb_of_corrosion",
    "soul_ring",
    "bottle",
)

# Предметы, которые покупаются строго на линии / в ранней игре.
# В мид/лейте (или при наличии готовых слотов) их никогда не рекомендуем.
EARLY_ONLY_ITEMS: dict[str, int] = {
    "magic_wand": 8,
    "magic_stick": 6,
    "null_talisman": 8,
    "bracer": 8,
    "wraith_band": 8,
    "soul_ring": 10,
    "orb_of_corrosion": 12,
    "bottle": 10,
    "orb_of_venom": 8,
    "blight_stone": 10,
    "infused_raindrop": 14,
}

# Предпочтительные ботинки на миде (пока нет своей пары).
HERO_PREFERRED_BOOTS: dict[int, str] = {
    80: "power_treads",
    107: "power_treads",
    90: "travel_boots",
    91: "travel_boots",
}

CONSUMABLE_PREFIXES = ("recipe_", "item_recipe_")
CORE_PURCHASE_RATE = 45.0

# Саппорт-предметы, которые никогда не советуем mid-коучу (LD / Io / KotL / ES).
# Фильтруются в NN, lookup, counters, синтетике через item_allowed_for_hero.
MID_SKIP_ITEMS: frozenset[str] = frozenset(
    {
        "arcane_boots",
    }
)

# Профильные бан-листы: отсекают чуждые архетипы (напр. кэрри-предметы магам или кастер-предметы мишке).
HERO_SKIP_ITEMS: dict[int, set[str]] = {
    80: {
        # Caster-luxury с KotL/Io/ES — в OpenDota mid-LD их нет, NN иначе тащит кросс-героем.
        "octarine_core",
        "dagon",
        "bottle",
        "urn_of_shadows",
        "spirit_vessel",
        "aether_lens",
        "sheepstick",
        "kaya",
        "kaya_and_sange",
        "rod_of_atos",
        "bloodstone",
        "ethereal_blade",
        "cyclone",
        "wind_waker",
    },
    90: {
        # Keeper of the Light: кастер-мидер — физические автоатакерские / кэрри предметы запрещены.
        "silver_edge",
        "invis_sword",
        "desolator",
        "satanic",
        "butterfly",
        "monkey_king_bar",
        "greater_crit",
        "lesser_crit",
        "abyssal_blade",
        "basher",
        "diffusal_blade",
        "disperser",
        "harpoon",
        "echo_sabre",
        "armlet",
        "battlefury",
        "mask_of_madness",
        "skadi",
        "sange_and_yasha",
        "manta",
        "yasha",
        "mage_slayer",
        "phylactery",
        "khanda",
        "radiance",
        "dragon_lance",
        "assault",
        "heavens_halberd",
        "maelstrom",
        "mjollnir",
        "nullifier",
        "holy_locket",
        "guardian_greaves",
        "mekansm",
        "pavise",
        "solar_crest",
        "pipe",
        "vladmir",
        "arcane_boots",
        "tranquil_boots",
    },
    91: {
        "urn_of_shadows",
        "spirit_vessel",
        "mekansm",
        "guardian_greaves",
        "helm_of_the_dominator",
        "helm_of_the_overlord",
        "holy_locket",
        "pavise",
        "solar_crest",
        "pipe",
        "vladmir",
        "glimmer_cape",
        "arcane_boots",
    },
    107: {
        # Earth Spirit: силовик-инициатор — исключаем физический кэрри мусор и саппорт-обувь.
        "desolator",
        "butterfly",
        "greater_crit",
        "lesser_crit",
        "mask_of_madness",
        "battlefury",
        "bloodstone",
        "ethereal_blade",
        "arcane_boots",
        "tranquil_boots",
        "holy_locket",
        "diffusal_blade",
        "disperser",
        "silver_edge",
        "invis_sword",
    },
}

# Поздние luxury: не советуем как 1–2-й крупный слот / до типичной минуты.
LATE_LUXURY_ITEMS: dict[str, int] = {
    "octarine_core": 20,
    "sheepstick": 26,
    "refresher": 28,
    "bloodthorn": 26,
    "butterfly": 28,
    "heart": 26,
    "assault": 24,
    "satanic": 28,
    "abyssal_blade": 26,
    "nullifier": 24,
    "ethereal_blade": 22,
    "overwhelming_blink": 28,
    "arcane_blink": 28,
    "wind_waker": 26,
    "bloodstone": 22,
    "skadi": 26,
    "monkey_king_bar": 26,
    "disperser": 26,
    "silver_edge": 24,
}

MAJOR_ITEM_MIN_COST = 1400


def normalize_item_name(raw: str | None) -> str:
    if not raw:
        return ""
    name = raw.strip().lower()
    if name in {"empty", "item_empty", "unknown"}:
        return ""
    if name.startswith("item_"):
        name = name[5:]
    if name.startswith("recipe_") or name in SKIP_ITEMS:
        return ""
    if name.startswith("dagon_"):
        return "dagon"
    aliases = {
        "invis_sword": "invis_sword",
        "shadow_blade": "invis_sword",
        "sb": "invis_sword",
        "silver": "silver_edge",
        "ultimate_scepter_2": "ultimate_scepter",
        "ultimate_scepter_roshan": "ultimate_scepter",
        "aghanims_scepter": "ultimate_scepter",
        "aghs": "ultimate_scepter",
        "shard": "aghanims_shard",
        "ghost_scepter": "ghost",
        "euls_scepter": "cyclone",
        "euls": "cyclone",
        "eul": "cyclone",
        "sheep": "sheepstick",
        "vyse": "sheepstick",
        "scythe": "sheepstick",
        "scythe_of_vyse": "sheepstick",
        "bkb": "black_king_bar",
        "vessel": "spirit_vessel",
        "urn": "urn_of_shadows",
        "greaves": "guardian_greaves",
        "travels": "travel_boots",
        "boots_of_travel": "travel_boots",
        "travel_boot": "travel_boots",
        "treads": "power_treads",
        "arcanes": "arcane_boots",
        "mana_boots": "arcane_boots",
        "wand": "magic_wand",
        "stick": "magic_stick",
        "null": "null_talisman",
        "wraith": "wraith_band",
        "daedalus": "greater_crit",
        "crit": "greater_crit",
        "crystalys": "lesser_crit",
        "crystalis": "lesser_crit",
        "deso": "desolator",
        "cuirass": "assault",
        "ac": "assault",
        "octarine": "octarine_core",
    }
    return aliases.get(name, name)


def item_allowed_for_hero(hero_id: int, name: str) -> bool:
    key = normalize_item_name(name)
    if not key:
        return False
    if key in MID_SKIP_ITEMS:
        return False
    return key not in HERO_SKIP_ITEMS.get(hero_id, set())


def is_finished_item(name: str) -> bool:
    key = normalize_item_name(name)
    return bool(key) and key in ITEM_RU


def owned_boots(owned: set[str]) -> set[str]:
    names = {normalize_item_name(item) for item in owned}
    return names & BOOT_ITEMS


def is_upgrade_of_owned(name: str, owned: set[str]) -> bool:
    key = normalize_item_name(name)
    have = {normalize_item_name(item) for item in owned}
    for base, upgrade in ITEM_UPGRADES.items():
        if upgrade == key and base in have:
            return True
    return False


def is_base_component_superseded(name: str, owned: set[str]) -> bool:
    """Если у игрока уже есть улучшенная версия предмета (напр. spirit_vessel или silver_edge),
    базовый предмет (urn_of_shadows или invis_sword) считается уже купленным/улучшенным и не рекомендуется."""
    key = normalize_item_name(name)
    have = {normalize_item_name(item) for item in owned}
    have.discard("")
    for upgrade, bases in UPGRADE_COMPONENTS.items():
        if key in bases and upgrade in have:
            return True
    return False


def resolve_upgrade_prerequisite(name: str, owned: set[str], minute: int = 0) -> str:
    """Если предложен апгрейд (напр. silver_edge или wind_waker), но у игрока ещё нет
    базового предмета (invis_sword или cyclone), рекомендуем сначала базовый предмет."""
    key = normalize_item_name(name)
    have = {normalize_item_name(item) for item in owned}
    have.discard("")
    prereq = UPGRADE_PREREQUISITES.get(key)
    if prereq and prereq not in have:
        return prereq
    return key


def major_item_count(owned: set[str] | list[str]) -> int:
    total = 0
    for raw in owned:
        key = normalize_item_name(raw)
        if not key or not is_finished_item(key):
            continue
        if key == "aghanims_shard":
            continue
        if ITEM_COSTS.get(key, 0) >= MAJOR_ITEM_MIN_COST:
            total += 1
    return total


def item_timing_ok(name: str, minute: int, owned: set[str] | list[str]) -> bool:
    """Блокирует late luxury слишком рано / early trash слишком поздно (все герои)."""
    key = normalize_item_name(name)
    if not key:
        return False
    have = {normalize_item_name(item) for item in owned}
    have.discard("")
    if is_upgrade_of_owned(key, have):
        return True
    majors = major_item_count(have)

    # 1. Проверка раннего мусора: не советовать стики/нули/брейсеры после тайминга или при наличии мейджоров
    max_minute = EARLY_ONLY_ITEMS.get(key)
    if max_minute is not None:
        if minute > max_minute or majors >= 1:
            return False

    # 2. Проверка лейт-люксури: не советовать до тайминга
    min_minute = LATE_LUXURY_ITEMS.get(key)
    if min_minute is not None:
        if minute < min_minute and majors < 2:
            return False
        if minute < max(8, min_minute - 10) and majors < 1:
            return False
    cost = ITEM_COSTS.get(key, 0)
    if cost >= 4000 and minute < 10 and majors < 1:
        return False
    return True


def item_takes_inventory_slot(name: str) -> bool:
    key = normalize_item_name(name)
    if key in {"aghanims_shard"}:
        return False
    return True


def inventory_sell_candidates(owned: set[str] | list[str]) -> list[str]:
    """Низкоценные слоты, которые разумно продать под следующий крупный предмет."""
    have = {normalize_item_name(item) for item in owned}
    have.discard("")
    return [key for key in EARLY_SELL_ITEMS if key in have]


def can_consume_aghanims(owned: set[str] | list[str], scepter_consumed: bool = False) -> bool:
    """Физический Aghanim's в сумке можно съесть и освободить слот."""
    if scepter_consumed:
        return False
    have = {normalize_item_name(item) for item in owned}
    return "ultimate_scepter" in have


def can_free_inventory_slot(
    owned: set[str] | list[str],
    *,
    scepter_consumed: bool = False,
) -> bool:
    return bool(inventory_sell_candidates(owned) or can_consume_aghanims(owned, scepter_consumed))


def inventory_free_actions(
    owned: set[str] | list[str],
    *,
    scepter_consumed: bool = False,
) -> list[str]:
    """Человекочитаемые действия: продать X / съесть Aghs."""
    actions: list[str] = []
    if can_consume_aghanims(owned, scepter_consumed):
        actions.append(f"съешь {item_display('ultimate_scepter')}")
    for key in inventory_sell_candidates(owned):
        actions.append(f"продай {item_display(key)}")
    return actions


def preferred_boots_for_hero(hero_id: int) -> str:
    """Finished boots goal for mid hero; never returns MID_SKIP / hero-skip boots."""
    hid = int(hero_id) or 0
    boot = HERO_PREFERRED_BOOTS.get(hid, "power_treads")
    if item_allowed_for_hero(hid, boot):
        return boot
    for fallback in ("travel_boots", "power_treads", "phase_boots"):
        if item_allowed_for_hero(hid, fallback):
            return fallback
    return "travel_boots"


def item_display(name: str) -> str:
    key = normalize_item_name(name) or name
    return ITEM_RU.get(key, key.replace("_", " ").title())


def hero_display(hero_id: int, npc: str = "") -> str:
    if hero_id in HEROES:
        return HEROES[hero_id]["ru"]
    try:
        from dota_coach.data.heroes import hero_english_name

        name = hero_english_name(hero_id, npc)
        if name and not name.startswith("Hero "):
            return name
    except Exception:
        pass
    if npc:
        slug = npc.replace("npc_dota_hero_", "").replace("_", " ").title()
        return "Io" if slug.lower() == "wisp" else slug
    return f"Герой {hero_id}"


def hero_id_from_npc(npc: str) -> int:
    return NPC_TO_ID.get(npc, 0)
