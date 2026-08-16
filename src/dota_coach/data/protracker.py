from __future__ import annotations

import json
import re
import time
from typing import Any
from urllib.parse import quote

import httpx

from dota_coach.config import (
    DEFAULT_HERO_IDS,
    PROTRACKER_BASE,
    PROTRACKER_HERO_SLUGS,
    PROTRACKER_REQUEST_GAP,
)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _item_mapping(html: str) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    pattern = re.compile(
        r'"(\d+)":\{item_id:(\d+),name:"([^"]+)",displayName:"([^"]+)",'
        r'shortName:"([^"]+)",neutral_item_tier:(-?\d+),price:(\d+)'
    )
    for match in pattern.finditer(html):
        item_id = int(match.group(2))
        out[item_id] = {
            "item_id": item_id,
            "name": match.group(3),
            "display_name": match.group(4),
            "short_name": match.group(5),
            "price": int(match.group(7)),
        }
    return out


def _item_stats_blob(html: str) -> str:
    for match in re.finditer(r"item_stats:\{", html):
        chunk = html[match.end() - 1 : match.end() + 400]
        if "pr:" in chunk:
            return html[match.end() - 1 :]
    return ""


def _parse_item_stats(html: str) -> list[dict[str, Any]]:
    blob = _item_stats_blob(html)
    if not blob:
        return []
    names = _item_mapping(html)
    stats: list[dict[str, Any]] = []
    pattern = re.compile(
        r'"(\d+)":\{pr:([0-9.]+),wins:(\d+),win_rate:([0-9.]+),'
        r"purchases:(\d+),avg_minute:(-?[0-9.]+),max_minute:(-?[0-9.]+),"
        r"min_minute:(-?[0-9.]+)"
    )
    seen: set[int] = set()
    for match in pattern.finditer(blob[:250000]):
        item_id = int(match.group(1))
        if item_id in seen:
            break
        seen.add(item_id)
        meta = names.get(item_id, {})
        stats.append(
            {
                "item_id": item_id,
                "name": str(meta.get("name") or f"item_{item_id}"),
                "display_name": str(meta.get("display_name") or item_id),
                "price": int(meta.get("price") or 0),
                "purchase_rate": float(match.group(2)),
                "wins": int(match.group(3)),
                "win_rate": float(match.group(4)),
                "purchases": int(match.group(5)),
                "avg_minute": float(match.group(6)),
                "max_minute": float(match.group(7)),
                "min_minute": float(match.group(8)),
            }
        )
    stats.sort(key=lambda row: row["avg_minute"])
    return stats


def _first_float(html: str, key: str, default: float = 0.0) -> float:
    match = re.search(rf"{key}:(-?[0-9.]+)", html)
    return float(match.group(1)) if match else default


def _role_counts(html: str) -> dict[str, dict[str, float]]:
    roles: dict[str, dict[str, float]] = {}
    pattern = re.compile(
        r"(Carry|Mid|Offlane|Support|Hard Support)\s+(\d[\d,]*)\s+matches\s+(\d+)%\s+win rate",
        re.I,
    )
    for match in pattern.finditer(html):
        roles[match.group(1).title()] = {
            "matches": float(match.group(2).replace(",", "")),
            "win_rate": float(match.group(3)) / 100.0,
        }
    return roles


def parse_hero_html(html: str, hero_id: int, hero_name: str) -> dict[str, Any]:
    gpm = _first_float(html, "avg_gpm") or _first_float(html, "gpm")
    xpm = _first_float(html, "avg_xpm")
    deaths = _first_float(html, "avg_deaths")
    last_hits = _first_float(html, "avg_last_hits")
    net_worth = _first_float(html, "avg_net_worth")
    denies = _first_float(html, "avg_denies")
    kills = _first_float(html, "avg_kills")
    nw10 = _first_float(html, "networth_10")
    duration = (net_worth / gpm) if gpm else 36.0
    duration = max(28.0, min(50.0, duration))
    return {
        "source": "dota2protracker",
        "hero_id": hero_id,
        "hero_name": hero_name,
        "lane_role": 2,
        "avg_gpm": gpm,
        "avg_xpm": xpm,
        "avg_deaths": deaths,
        "avg_last_hits": last_hits,
        "avg_net_worth": net_worth,
        "avg_denies": denies,
        "avg_kills": kills,
        "networth_10": nw10,
        "duration_min": round(duration, 1),
        "roles": _role_counts(html),
        "item_stats": _parse_item_stats(html),
        "item_mapping": {
            str(item_id): meta for item_id, meta in _item_mapping(html).items()
        },
    }


def hero_url(hero_name: str, role: str = "Mid") -> str:
    return f"{PROTRACKER_BASE}/hero/{quote(hero_name)}?role={quote(role)}"


def fetch_hero_page(hero_name: str, role: str = "Mid", timeout: float = 25.0) -> str:
    url = hero_url(hero_name, role)
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Referer": f"{PROTRACKER_BASE}/",
    }
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text


def collect_protracker(
    hero_ids: tuple[int, ...] = DEFAULT_HERO_IDS,
    role: str = "Mid",
) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for index, hero_id in enumerate(hero_ids):
        name = PROTRACKER_HERO_SLUGS[hero_id]
        html = fetch_hero_page(name, role=role)
        result[hero_id] = parse_hero_html(html, hero_id, name)
        if index + 1 < len(hero_ids):
            time.sleep(PROTRACKER_REQUEST_GAP)
    return result
