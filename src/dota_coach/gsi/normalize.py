from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from dota_coach.constants import NPC_TO_ID, normalize_item_name
from dota_coach.data.heroes import npc_to_hero_id

_TEAM_KEY_RE = re.compile(r"^team\d+$")
_PICK_ID_RE = re.compile(r"^pick(\d+)_id$")


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _is_hero_npc(name: str) -> bool:
    return name.startswith("npc_dota_hero_")


def _is_nested_gsi(node: Any) -> bool:
    """True only for spectator team2/team3 trees — never for flat `team_name`."""
    return any(_TEAM_KEY_RE.fullmatch(str(key)) for key in _as_dict(node))


def _nested_blocks(node: Any) -> dict[tuple[str, str], dict[str, Any]]:
    data = _as_dict(node)
    if not data:
        return {}
    if _is_nested_gsi(data):
        out: dict[tuple[str, str], dict[str, Any]] = {}
        for team_key, team in data.items():
            if not _TEAM_KEY_RE.fullmatch(str(team_key)):
                continue
            for slot_key, block in _as_dict(team).items():
                player = _as_dict(block)
                if player:
                    out[(str(team_key), str(slot_key))] = player
        return out
    return {("local", "local"): data}


def _local_steamid(payload: dict[str, Any]) -> str:
    return str(_as_dict(payload.get("provider")).get("steamid") or "")


def _local_slot(payload: dict[str, Any]) -> tuple[str, str] | None:
    steam = _local_steamid(payload)
    raw = payload.get("player")
    players = _nested_blocks(raw)
    if steam:
        for key, block in players.items():
            if str(block.get("steamid") or "") == steam:
                return key
    if _is_nested_gsi(raw):
        for key, block in players.items():
            if str(block.get("activity") or "").lower() == "playing":
                return key
        return None
    return next(iter(players), None)


def _local_player(payload: dict[str, Any]) -> dict[str, Any]:
    blocks = _nested_blocks(payload.get("player"))
    slot = _local_slot(payload)
    if slot is not None:
        return blocks.get(slot, {})
    return {}


def _local_hero(payload: dict[str, Any], _player: dict[str, Any]) -> dict[str, Any]:
    heroes = _nested_blocks(payload.get("hero"))
    slot = _local_slot(payload)
    if slot is not None and slot in heroes:
        hero = heroes[slot]
    elif not _is_nested_gsi(payload.get("hero")):
        hero = next(iter(heroes.values()), {})
    else:
        return {}
    name = str(hero.get("name") or "")
    hid = int(hero.get("id") or 0)
    if hid > 0 or _is_hero_npc(name) or not name:
        return hero
    return {}


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).lower() in {"true", "1", "yes"}


def _item_name(slot: Any) -> str:
    data = _as_dict(slot)
    return normalize_item_name(str(data.get("name") or ""))


def _collect_items(payload: dict[str, Any]) -> tuple[list[str], bool, int]:
    """Инвентарь + рюкзак + стан. Третий элемент — занятые основные слоты 0–5."""
    node = payload.get("items")
    data = _as_dict(node)
    if _is_nested_gsi(data):
        slot = _local_slot(payload)
        blocks = _nested_blocks(node)
        data = blocks.get(slot, {}) if slot is not None else {}
    names: list[str] = []
    has_tp = False
    inventory_slots = 0
    for key, slot in data.items():
        key_l = str(key).lower()
        name = _item_name(slot)
        if "teleport" in key_l or name == "tpscroll":
            has_tp = True
            continue
        if not name:
            continue
        if key_l.startswith("slot") and key_l[4:].isdigit() and int(key_l[4:]) <= 5:
            inventory_slots += 1
        if name not in names:
            names.append(name)
    hero = _local_hero(payload, _local_player(payload))
    if _truthy(hero.get("aghanims_shard")) and "aghanims_shard" not in names:
        names.append("aghanims_shard")
    if _truthy(hero.get("aghanims_scepter")) and "ultimate_scepter" not in names:
        names.append("ultimate_scepter")
    return names, has_tp, inventory_slots


def _hero_id_from(hero: dict[str, Any]) -> int:
    raw_id = hero.get("id")
    if isinstance(raw_id, int) and raw_id > 0:
        return raw_id
    npc = str(hero.get("name") or "")
    return npc_to_hero_id(npc) or NPC_TO_ID.get(npc, 0)


def _side_from_team_key(key: str) -> str:
    raw = str(key or "").lower()
    if raw in {"team2", "2", "radiant"}:
        return "radiant"
    if raw in {"team3", "3", "dire"}:
        return "dire"
    return raw if raw in {"radiant", "dire"} else ""


def _player_side(player: dict[str, Any]) -> str:
    name = str(player.get("team_name") or "").lower()
    if name in {"radiant", "dire"}:
        return name
    return _side_from_team_key(str(player.get("team") or ""))


def _picks_from_block(block: Any) -> list[int]:
    data = _as_dict(block)
    ids: dict[int, int] = {}
    extra: list[int] = []
    for key, value in data.items():
        match = _PICK_ID_RE.fullmatch(str(key))
        if match:
            hid = int(value or 0)
            if hid > 0:
                ids[int(match.group(1))] = hid
            continue
        nested = _as_dict(value)
        if str(key).startswith("pick") and nested:
            hid = int(nested.get("id") or 0)
            if hid > 0:
                extra.append(hid)
    return [ids[index] for index in sorted(ids)] + extra


def _roster_from_nested_players(payload: dict[str, Any]) -> tuple[list[int], list[int]]:
    raw_players = payload.get("player")
    if not _is_nested_gsi(raw_players):
        return [], []
    local_side = _player_side(_local_player(payload))
    local_slot = _local_slot(payload)
    heroes = _nested_blocks(payload.get("hero"))
    allies: list[int] = []
    enemies: list[int] = []
    for slot, player in _nested_blocks(raw_players).items():
        hero = heroes.get(slot, {})
        hid = int(hero.get("id") or 0) or npc_to_hero_id(str(hero.get("name") or ""))
        if hid <= 0:
            continue
        side = _player_side(player)
        if slot == local_slot or (local_side and side == local_side):
            if hid not in allies:
                allies.append(hid)
        elif local_side and side and side != local_side:
            if hid not in enemies:
                enemies.append(hid)
    return allies, enemies


def _draft_heroes(payload: dict[str, Any], local_team: str) -> tuple[list[int], list[int]]:
    nested_allies, nested_enemies = _roster_from_nested_players(payload)
    if nested_enemies:
        return nested_allies, nested_enemies

    draft = _as_dict(payload.get("draft"))
    local = _side_from_team_key(local_team) or (local_team or "").lower()
    allies: list[int] = []
    enemies: list[int] = []

    for team_key, team in draft.items():
        side = _side_from_team_key(str(team_key))
        picks = _picks_from_block(team)
        if not side:
            continue
        target = enemies if local and side != local else allies
        for hid in picks:
            if hid not in target:
                target.append(hid)

    if not allies and not enemies:
        picks: list[tuple[str, int]] = []
        for key, value in draft.items():
            if not str(key).startswith("pick"):
                continue
            block = _as_dict(value)
            hid = int(block.get("id") or 0)
            if hid <= 0:
                continue
            team = str(block.get("team") or block.get("team_name") or "")
            picks.append((_side_from_team_key(team) or team.lower(), hid))
        for team, hid in picks:
            if local and team and team != local:
                if hid not in enemies:
                    enemies.append(hid)
            elif hid not in allies:
                allies.append(hid)
        if not enemies and len(picks) >= 10:
            enemies = [hid for _, hid in picks[5:]]
            allies = [hid for _, hid in picks[:5]]

    if nested_allies and not allies:
        allies = nested_allies
    return allies, enemies


@dataclass
class GameState:
    match_id: str = ""
    clock_time: int = 0
    game_time: int = 0
    game_state: str = ""
    paused: bool = False
    hero_id: int = 0
    hero_name: str = ""
    level: int = 0
    alive: bool = True
    respawn_seconds: int = 0
    health_percent: int = 100
    mana_percent: int = 100
    gold: int = 0
    gold_reliable: int = 0
    gold_unreliable: int = 0
    gpm: int = 0
    xpm: int = 0
    last_hits: int = 0
    denies: int = 0
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    net_worth: int = 0
    total_gold: int = 0
    buyback_cost: int = 0
    buyback_cooldown: int = 0
    items: list[str] = field(default_factory=list)
    inventory_slots: int = 0
    has_shard: bool = False
    has_scepter: bool = False
    has_tp: bool = True
    xpos: int | None = None
    ypos: int | None = None
    enemy_heroes: list[int] = field(default_factory=list)
    ally_heroes: list[int] = field(default_factory=list)
    player_name: str = ""
    team_name: str = ""
    in_game: bool = False

    @property
    def minute(self) -> int:
        return max(0, int(self.clock_time // 60))

    @property
    def earned_gold(self) -> int:
        """Общее добытое золото (не остаток в рюкзаке)."""
        if self.total_gold > 0:
            return self.total_gold
        if self.net_worth > 0:
            return self.net_worth
        if self.gpm > 0 and self.clock_time > 0:
            return int(self.gpm * self.clock_time / 60)
        return 0


def normalize_gsi(payload: dict[str, Any]) -> GameState:
    mapping = _as_dict(payload.get("map"))
    player = _local_player(payload)
    hero = _local_hero(payload, player)
    items, has_tp, inventory_slots = _collect_items(payload)
    game_state = str(mapping.get("game_state") or "")
    in_game = game_state in {
        "DOTA_GAMERULES_STATE_PRE_GAME",
        "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS",
    }
    team = _player_side(player) or str(player.get("team_name") or player.get("team") or "")
    allies, enemies = _draft_heroes(payload, team)
    xpos = hero.get("xpos")
    ypos = hero.get("ypos")
    gold = int(player.get("gold") or 0)
    gpm = int(player.get("gpm") or 0)
    clock_time = int(mapping.get("clock_time") or 0)
    game_time = int(mapping.get("game_time") or 0)
    net_worth = int(player.get("net_worth") or 0)
    # В обычном клиенте net_worth часто пустой. Не подставляем gold из рюкзака —
    # общее добытое ≈ GPM × минуты игры (как gold_t у OpenDota).
    elapsed = max(0, clock_time if clock_time > 0 else game_time)
    total_gold = net_worth if net_worth > 0 else int(gpm * elapsed / 60) if gpm > 0 else 0
    if net_worth <= 0:
        net_worth = total_gold
    return GameState(
        match_id=str(mapping.get("matchid") or ""),
        clock_time=clock_time,
        game_time=game_time,
        game_state=game_state,
        paused=bool(mapping.get("paused")),
        hero_id=_hero_id_from(hero),
        hero_name=str(hero.get("name") or ""),
        level=int(hero.get("level") or 0),
        alive=bool(hero.get("alive", True)),
        respawn_seconds=int(hero.get("respawn_seconds") or 0),
        health_percent=int(hero.get("health_percent") or 0),
        mana_percent=int(hero.get("mana_percent") or 0),
        gold=gold,
        gold_reliable=int(player.get("gold_reliable") or 0),
        gold_unreliable=int(player.get("gold_unreliable") or 0),
        gpm=gpm,
        xpm=int(player.get("xpm") or 0),
        last_hits=int(player.get("last_hits") or 0),
        denies=int(player.get("denies") or 0),
        kills=int(player.get("kills") or 0),
        deaths=int(player.get("deaths") or 0),
        assists=int(player.get("assists") or 0),
        net_worth=net_worth,
        total_gold=total_gold,
        buyback_cost=int(hero.get("buyback_cost") or 0),
        buyback_cooldown=int(hero.get("buyback_cooldown") or 0),
        items=items,
        inventory_slots=inventory_slots,
        has_shard="aghanims_shard" in items,
        has_scepter="ultimate_scepter" in items,
        has_tp=has_tp or "tpscroll" in items,
        xpos=int(xpos) if isinstance(xpos, int) else None,
        ypos=int(ypos) if isinstance(ypos, int) else None,
        enemy_heroes=enemies,
        ally_heroes=allies,
        player_name=str(player.get("name") or ""),
        team_name=team,
        in_game=in_game,
    )
