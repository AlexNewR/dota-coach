from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dota_coach.config import (
    DEFAULT_HERO_IDS,
    OPENDOTA_MAX_AGE_DAYS,
    OPENDOTA_MIN_RANK,
    OPENDOTA_PER_HERO_DEFAULT,
    PLAYER_ROWS_PATH,
    PROCESSED_DIR,
    RAW_DIR,
    ensure_data_dirs,
)
from dota_coach.data.opendota import collect_from_match_cache, collect_hero_opendota, collect_opendota_fallback
from dota_coach.data.parse_api import ParseConfigError, collect_parse
from dota_coach.data.protracker import collect_protracker
from dota_coach.data.synthetic import PROTRACKER_SNAPSHOT, synthetic_dataset


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _collect_meta_heroes(hero_ids: tuple[int, ...]) -> tuple[dict[int, dict[str, Any]], str]:
    source = "synthetic"
    heroes: dict[int, dict[str, Any]] = {}
    try:
        heroes = collect_parse(hero_ids=hero_ids)
        if heroes:
            source = "parse_dota2protracker"
            for hid, hero in heroes.items():
                snap = PROTRACKER_SNAPSHOT.get(hid) or {}
                if not hero.get("item_stats") and snap.get("item_stats"):
                    hero["item_stats"] = list(snap["item_stats"])
                for key in (
                    "avg_gpm",
                    "avg_xpm",
                    "avg_deaths",
                    "avg_last_hits",
                    "avg_net_worth",
                    "networth_10",
                    "duration_min",
                ):
                    if not hero.get(key) and snap.get(key):
                        hero[key] = snap[key]
    except ParseConfigError:
        heroes = {}
    except Exception as exc:  # noqa: BLE001
        source = f"parse_failed ({type(exc).__name__})"
        heroes = {}

    if not heroes:
        try:
            html_heroes = collect_protracker(hero_ids=hero_ids, role="Mid")
            if any(hero.get("item_stats") for hero in html_heroes.values()):
                heroes = html_heroes
                source = "dota2protracker_html"
        except Exception as exc:  # noqa: BLE001
            if not heroes:
                source = f"synthetic ({exc})"

    if not heroes:
        heroes = {hid: dict(PROTRACKER_SNAPSHOT[hid]) for hid in hero_ids if hid in PROTRACKER_SNAPSHOT}
        source = "synthetic"
    return heroes, source


def _row_filter_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    starts = [int(r.get("start_time") or 0) for r in rows if int(r.get("start_time") or 0) > 0]
    ranks = [int(r["rank_tier"]) for r in rows if r.get("rank_tier")]
    leagues = sum(1 for r in rows if int(r.get("leagueid") or 0) > 0)
    lanes: dict[str, int] = {}
    for row in rows:
        key = str(row.get("lane_role"))
        lanes[key] = lanes.get(key, 0) + 1
    return {
        "start_time_min": min(starts) if starts else None,
        "start_time_max": max(starts) if starts else None,
        "rank_tier_median": sorted(ranks)[len(ranks) // 2] if ranks else None,
        "league_rows": leagues,
        "ranked_rows": len(ranks),
        "lane_role_counts": lanes,
        "mid_rows": lanes.get("2", 0),
    }


def collect(
    hero_ids: tuple[int, ...] = DEFAULT_HERO_IDS,
    use_opendota: bool = True,
    opendota_matches: int = 15,
    opendota_primary: bool = False,
    per_hero: int | None = None,
    min_rank: int | None = None,
    max_age_days: int | None = None,
    allow_league: bool = True,
) -> dict[str, Any]:
    ensure_data_dirs()
    heroes, meta_source = _collect_meta_heroes(hero_ids)
    raw_path = RAW_DIR / "protracker_heroes.json"
    _write_json(raw_path, {str(hid): hero for hid, hero in heroes.items()})

    target_per_hero = OPENDOTA_PER_HERO_DEFAULT if per_hero is None else per_hero
    rank = OPENDOTA_MIN_RANK if min_rank is None else min_rank
    age = OPENDOTA_MAX_AGE_DAYS if max_age_days is None else max_age_days

    rows: list[dict[str, Any]] = []
    opendota_note = "skipped"
    if opendota_primary:
        try:
            rows = collect_hero_opendota(
                hero_ids=hero_ids,
                per_hero=target_per_hero,
                min_rank=rank,
                max_age_days=age,
                allow_league=allow_league,
            )
            if not rows:
                rows = collect_from_match_cache(
                    hero_ids=hero_ids,
                    per_hero=target_per_hero,
                    min_rank=rank,
                    max_age_days=age,
                    allow_league=allow_league,
                )
                opendota_note = (
                    f"cache mid {len(rows)} rows (API empty/limit; "
                    f"age<={age}d, rank>={rank}, league={allow_league})"
                )
            else:
                opendota_note = (
                    f"primary {len(rows)} rows (~{target_per_hero}/hero, "
                    f"age<={age}d, rank>={rank}, league={allow_league})"
                )
            primary_source = "opendota"
        except Exception as exc:  # noqa: BLE001
            try:
                rows = collect_from_match_cache(
                    hero_ids=hero_ids,
                    per_hero=target_per_hero,
                    min_rank=rank,
                    max_age_days=age,
                    allow_league=allow_league,
                )
                opendota_note = f"cache mid after API error ({exc}): {len(rows)} rows"
                primary_source = "opendota"
            except Exception as cache_exc:  # noqa: BLE001
                opendota_note = f"opendota primary failed ({exc}); cache failed ({cache_exc})"
                rows = synthetic_dataset(heroes)
                primary_source = meta_source
    else:
        rows = synthetic_dataset(heroes)
        primary_source = meta_source
        if use_opendota:
            try:
                if opendota_matches >= 40:
                    extra = collect_hero_opendota(
                        hero_ids=hero_ids,
                        per_hero=max(10, opendota_matches // max(1, len(hero_ids))),
                        min_rank=rank,
                        max_age_days=age,
                        allow_league=allow_league,
                    )
                else:
                    extra = collect_opendota_fallback(
                        hero_ids=hero_ids,
                        max_matches=opendota_matches,
                        min_rank=rank,
                        max_age_days=age,
                    )
                if extra:
                    rows.extend(extra)
                    opendota_note = f"opendota {len(extra)} rows"
            except Exception as exc:  # noqa: BLE001
                opendota_note = f"opendota failed ({exc})"

    _write_jsonl(PLAYER_ROWS_PATH, rows)
    by_hero: dict[str, int] = {}
    for row in rows:
        key = str(row.get("hero_id"))
        by_hero[key] = by_hero.get(key, 0) + 1
    summary = {
        "primary_source": primary_source,
        "meta_source": meta_source,
        "heroes": {
            str(hid): {
                "name": hero.get("hero_name"),
                "items": len(hero.get("item_stats") or []),
                "gpm": hero.get("avg_gpm"),
                "last_hits": hero.get("avg_last_hits"),
                "deaths": hero.get("avg_deaths"),
                "rows": by_hero.get(str(hid), 0),
            }
            for hid, hero in heroes.items()
        },
        "player_rows": len(rows),
        "opendota": opendota_note,
        "opendota_primary": opendota_primary,
        "filters": {
            "per_hero": target_per_hero,
            "min_rank": rank,
            "max_age_days": age,
            "allow_league": allow_league,
            **_row_filter_stats(rows),
        },
        "raw": str(raw_path),
        "rows": str(PLAYER_ROWS_PATH),
    }
    _write_json(PROCESSED_DIR / "collect_summary.json", summary)
    return summary


def load_player_rows(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or PLAYER_ROWS_PATH
    if not target.exists():
        return synthetic_dataset()
    rows = []
    for line in target.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows or synthetic_dataset()


def load_protracker_heroes() -> dict[int, dict[str, Any]]:
    path = RAW_DIR / "protracker_heroes.json"
    if not path.exists():
        return dict(PROTRACKER_SNAPSHOT)
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {int(key): value for key, value in raw.items()}
