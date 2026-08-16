from __future__ import annotations

import json
from typing import Any

import httpx

from dota_coach.config import PROCESSED_DIR, ensure_data_dirs
from dota_coach.constants import HEROES, NPC_TO_ID

CACHE = PROCESSED_DIR / "hero_constants.json"
OPENDOTA_HEROES = "https://api.opendota.com/api/constants/heroes"

_catalog: dict[int, dict[str, str]] | None = None


def _from_opendota(raw: dict[str, Any]) -> dict[int, dict[str, str]]:
    out: dict[int, dict[str, str]] = {}
    for item in raw.values():
        if not isinstance(item, dict):
            continue
        hid = int(item.get("id") or 0)
        npc = str(item.get("name") or "")
        en = str(item.get("localized_name") or "")
        if hid <= 0 or not npc:
            continue
        out[hid] = {"npc": npc, "en": en, "name": npc.replace("npc_dota_hero_", "")}
    return out


def _builtin() -> dict[int, dict[str, str]]:
    return {
        hid: {"npc": meta["npc"], "en": meta["en"], "name": meta["name"]}
        for hid, meta in HEROES.items()
    }


def load_hero_catalog(refresh: bool = False) -> dict[int, dict[str, str]]:
    global _catalog
    if _catalog is not None and not refresh:
        return _catalog
    ensure_data_dirs()
    catalog = _builtin()
    if CACHE.exists() and not refresh:
        try:
            cached = json.loads(CACHE.read_text(encoding="utf-8"))
            catalog.update({int(k): v for k, v in cached.items()})
        except (OSError, ValueError, TypeError):
            pass
    else:
        try:
            response = httpx.get(OPENDOTA_HEROES, timeout=20.0)
            response.raise_for_status()
            fetched = _from_opendota(response.json())
            if fetched:
                catalog.update(fetched)
                CACHE.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
        except Exception:
            if CACHE.exists():
                try:
                    cached = json.loads(CACHE.read_text(encoding="utf-8"))
                    catalog.update({int(k): v for k, v in cached.items()})
                except (OSError, ValueError, TypeError):
                    pass
    _catalog = catalog
    return catalog


def hero_meta(hero_id: int) -> dict[str, str]:
    return load_hero_catalog().get(hero_id, {})


def hero_english_name(hero_id: int, npc: str = "") -> str:
    meta = hero_meta(hero_id)
    if meta.get("en"):
        return meta["en"]
    if npc:
        slug = npc.replace("npc_dota_hero_", "").replace("_", " ").title()
        if slug.lower() == "wisp":
            return "Io"
        return slug
    return f"Hero {hero_id}"


def npc_to_hero_id(npc: str) -> int:
    if npc in NPC_TO_ID:
        return NPC_TO_ID[npc]
    for hid, meta in load_hero_catalog().items():
        if meta.get("npc") == npc:
            return hid
    return 0
