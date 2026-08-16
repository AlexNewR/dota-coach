from __future__ import annotations

import json
from collections import Counter, defaultdict
from typing import Any

import httpx

from dota_coach.config import (
    DEFAULT_HERO_IDS,
    PARSE_API_BASE,
    PARSE_API_KEY,
    PARSE_SCRAPER_ID,
    PROTRACKER_HERO_SLUGS,
    RAW_DIR,
    ensure_data_dirs,
)
from dota_coach.constants import HEROES, normalize_item_name

MID_POSITION = 2


class ParseConfigError(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    if not PARSE_API_KEY:
        raise ParseConfigError("Нет PARSE_API_KEY в .env")
    return {
        "X-API-Key": PARSE_API_KEY,
        "Accept": "application/json",
    }


def _endpoint(name: str) -> str:
    return f"{PARSE_API_BASE.rstrip('/')}/scraper/{PARSE_SCRAPER_ID}/{name}"


def parse_get(name: str, params: dict[str, Any] | None = None, timeout: float = 90.0) -> Any:
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=_headers()) as client:
        response = client.get(_endpoint(name), params=params or {})
        response.raise_for_status()
        return response.json()


def fetch_heroes() -> Any:
    return parse_get("get_heroes")


def fetch_matches(days: int | None = None, limit: int | None = None, offset: int = 0) -> Any:
    # days/limit/offset дают пустой matches[] на текущем каноническом API.
    params: dict[str, Any] = {}
    if days is not None:
        params["days"] = days
    if limit is not None:
        params["limit"] = limit
    if offset:
        params["offset"] = offset
    return parse_get("get_matches", params=params or None)


def fetch_search(query: str = "") -> Any:
    params = {"query": query} if query else None
    return parse_get("search", params=params)


def _as_list(payload: Any, *keys: str) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    nested = payload.get("data")
    if isinstance(nested, dict):
        found = _as_list(nested, *keys)
        if found:
            return found
    if isinstance(nested, list):
        return nested
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return value
    for value in payload.values():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            return value
    return []


def _hero_id(row: dict[str, Any]) -> int | None:
    for key in ("hero_id", "heroId", "id"):
        value = row.get(key)
        if isinstance(value, int) and value > 0:
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    name = str(row.get("displayName") or row.get("display_name") or row.get("name") or "").lower()
    npc = str(row.get("npc") or "").lower()
    for hid, meta in HEROES.items():
        if name in {meta["en"].lower(), meta["name"], meta["ru"].lower()}:
            return hid
        if npc and npc == meta["npc"]:
            return hid
    aliases = {"io": 91, "wisp": 91, "lone druid": 80, "keeper of the light": 90, "kotl": 90}
    return aliases.get(name)


def _position_block(row: dict[str, Any], position: int = MID_POSITION) -> dict[str, Any]:
    flat = {
        "elo": row.get(f"pos {position} elo"),
        "matches": row.get(f"pos {position} matches"),
        "winrate": row.get(f"pos {position} winrate"),
        "win_rate": row.get(f"pos {position} winrate"),
    }
    if any(value not in (None, 0, 0.0) for value in flat.values()):
        return {key: value for key, value in flat.items() if value is not None}
    aliases = (
        f"pos_{position}",
        f"position_{position}",
        f"pos{position}",
        f"pos {position}",
        str(position),
        "mid" if position == 2 else "",
    )
    positions = row.get("positions") or row.get("position") or row
    if isinstance(positions, dict):
        for alias in aliases:
            if alias and isinstance(positions.get(alias), dict):
                return positions[alias]
    return {}


def _num(row: dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        value = row.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.replace("%", "").replace(",", ""))
            except ValueError:
                continue
    return default


def _item_entries(player: dict[str, Any]) -> list[dict[str, Any]]:
    raw = (
        player.get("items")
        or player.get("item_build")
        or player.get("itemBuild")
        or player.get("inventory")
        or []
    )
    entries: list[dict[str, Any]] = []
    if isinstance(raw, dict):
        raw = list(raw.values())
    if not isinstance(raw, list):
        return entries
    for index, item in enumerate(raw):
        if isinstance(item, str):
            name = normalize_item_name(item)
            if name:
                entries.append({"name": f"item_{name}", "avg_minute": float(index * 4 + 4)})
            continue
        if not isinstance(item, dict):
            continue
        name = normalize_item_name(
            item.get("name") or item.get("shortName") or item.get("key") or item.get("item")
        )
        if not name:
            continue
        minute = _num(item, "avg_minute", "minute", "time", "purchase_time")
        if minute > 200:
            minute = minute / 60.0
        entries.append(
            {
                "name": f"item_{name}",
                "display_name": str(item.get("displayName") or item.get("display_name") or name),
                "avg_minute": minute or float(index * 4 + 4),
                "price": int(_num(item, "price")),
            }
        )
    return entries


def _player_hero_id(player: dict[str, Any]) -> int | None:
    hid = _hero_id(player)
    if hid:
        return hid
    hero = player.get("hero")
    if isinstance(hero, dict):
        return _hero_id(hero)
    return None


def _player_role(player: dict[str, Any]) -> int | None:
    for key in ("position", "lane_role", "role", "pos"):
        value = player.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
        text = str(value or "").lower().replace("_", " ").strip()
        mapping = {
            "mid": 2,
            "middle": 2,
            "pos 1": 1,
            "pos 2": 2,
            "pos 3": 3,
            "pos 4": 4,
            "pos 5": 5,
            "pos1": 1,
            "pos2": 2,
            "pos3": 3,
            "pos4": 4,
            "pos5": 5,
            "position 2": 2,
        }
        if text in mapping:
            return mapping[text]
    return None


def _nw10(player: dict[str, Any]) -> float:
    timeline = player.get("networth") or player.get("net_worth_t") or player.get("nw_t") or []
    if isinstance(timeline, list) and len(timeline) > 10:
        value = timeline[10]
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, dict):
            return _num(value, "net_worth", "nw", "value")
    return _num(player, "networth_10", "nw10", "net_worth")


def collect_parse(
    hero_ids: tuple[int, ...] = DEFAULT_HERO_IDS,
    days: int | None = None,
    match_pages: int = 1,
    page_size: int | None = None,
) -> dict[int, dict[str, Any]]:
    ensure_data_dirs()
    heroes_payload = fetch_heroes()
    (RAW_DIR / "parse_heroes.json").write_text(
        json.dumps(heroes_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    matches: list[dict[str, Any]] = []
    match_payloads: list[Any] = []
    for page in range(match_pages):
        offset = (page * page_size) if page and page_size else 0
        payload = fetch_matches(days=days, limit=page_size, offset=offset)
        match_payloads.append(payload)
        chunk = [row for row in _as_list(payload, "matches", "data", "results") if isinstance(row, dict)]
        matches.extend(chunk)
        if page_size and len(chunk) < page_size:
            break
    (RAW_DIR / "parse_matches.json").write_text(
        json.dumps(match_payloads, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    by_id: dict[int, dict[str, Any]] = {}
    for row in _as_list(heroes_payload, "heroes", "data", "results"):
        if not isinstance(row, dict):
            continue
        hid = _hero_id(row)
        if hid not in hero_ids:
            continue
        mid = _position_block(row, MID_POSITION)
        merged = {**row, **mid}
        by_id[hid] = {
            "source": "parse_dota2protracker",
            "hero_id": hid,
            "hero_name": PROTRACKER_HERO_SLUGS.get(hid, str(row.get("displayName") or hid)),
            "lane_role": MID_POSITION,
            "avg_gpm": _num(merged, "avg_gpm", "gpm"),
            "avg_xpm": _num(merged, "avg_xpm", "xpm"),
            "avg_deaths": _num(merged, "avg_deaths", "deaths"),
            "avg_last_hits": _num(merged, "avg_last_hits", "last_hits", "lh"),
            "avg_net_worth": _num(merged, "avg_net_worth", "net_worth", "networth"),
            "avg_denies": _num(merged, "avg_denies", "denies"),
            "avg_kills": _num(merged, "avg_kills", "kills"),
            "networth_10": _num(merged, "networth_10", "nw10"),
            "duration_min": 36.0,
            "elo": _num(merged, "elo", "rating"),
            "matches": _num(merged, "matches", "match_count", "games"),
            "win_rate": _num(merged, "winrate", "win_rate", "wr"),
            "roles": {
                "Mid": {
                    "matches": _num(mid, "matches", "match_count", "games"),
                    "win_rate": _num(mid, "winrate", "win_rate", "wr"),
                    "elo": _num(mid, "elo", "rating"),
                }
            },
            "item_stats": [],
        }

    item_acc: dict[int, dict[str, list[float]]] = {hid: defaultdict(list) for hid in hero_ids}
    death_acc: dict[int, list[float]] = {hid: [] for hid in hero_ids}
    gpm_acc: dict[int, list[float]] = {hid: [] for hid in hero_ids}
    lh_acc: dict[int, list[float]] = {hid: [] for hid in hero_ids}
    nw10_acc: dict[int, list[float]] = {hid: [] for hid in hero_ids}
    duration_acc: dict[int, list[float]] = {hid: [] for hid in hero_ids}

    for match in matches:
        duration = _num(match, "duration")
        duration_min = duration / 60.0 if duration > 90 else duration
        for player in _as_list(match, "players"):
            if not isinstance(player, dict):
                continue
            hid = _player_hero_id(player)
            if hid not in hero_ids:
                continue
            role = _player_role(player)
            if role not in {None, MID_POSITION}:
                continue
            death_acc[hid].append(_num(player, "deaths"))
            gpm_acc[hid].append(_num(player, "gold_per_min", "gpm"))
            lh_acc[hid].append(_num(player, "last_hits", "lh"))
            nw = _nw10(player)
            if nw:
                nw10_acc[hid].append(nw)
            if duration_min:
                duration_acc[hid].append(duration_min)
            for item in _item_entries(player):
                item_acc[hid][item["name"]].append(float(item["avg_minute"]))

    for hid in hero_ids:
        hero = by_id.setdefault(
            hid,
            {
                "source": "parse_dota2protracker",
                "hero_id": hid,
                "hero_name": PROTRACKER_HERO_SLUGS[hid],
                "lane_role": MID_POSITION,
                "item_stats": [],
                "roles": {},
            },
        )
        if gpm_acc[hid] and not hero.get("avg_gpm"):
            hero["avg_gpm"] = sum(gpm_acc[hid]) / len(gpm_acc[hid])
        if death_acc[hid] and not hero.get("avg_deaths"):
            hero["avg_deaths"] = sum(death_acc[hid]) / len(death_acc[hid])
        if lh_acc[hid] and not hero.get("avg_last_hits"):
            hero["avg_last_hits"] = sum(lh_acc[hid]) / len(lh_acc[hid])
        if nw10_acc[hid] and not hero.get("networth_10"):
            hero["networth_10"] = sum(nw10_acc[hid]) / len(nw10_acc[hid])
        if duration_acc[hid]:
            hero["duration_min"] = round(sum(duration_acc[hid]) / len(duration_acc[hid]), 1)
        counts = Counter({name: len(minutes) for name, minutes in item_acc[hid].items()})
        total_games = max(len(death_acc[hid]), 1)
        stats = []
        for name, minutes in item_acc[hid].items():
            stats.append(
                {
                    "name": name,
                    "display_name": name.replace("item_", ""),
                    "purchase_rate": 100.0 * counts[name] / total_games,
                    "avg_minute": sum(minutes) / len(minutes),
                    "purchases": counts[name],
                }
            )
        stats.sort(key=lambda row: row["avg_minute"])
        if stats:
            hero["item_stats"] = stats
        hero["parse_match_samples"] = len(death_acc[hid])

    return by_id
