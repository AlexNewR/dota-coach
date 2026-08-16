from __future__ import annotations

from typing import Any

from dota_coach.constants import CORE_PURCHASE_RATE, item_allowed_for_hero, normalize_item_name

# Снимок mid-билдов Dota2ProTracker (7.41e), если сайт недоступен.
PROTRACKER_SNAPSHOT: dict[int, dict[str, Any]] = {
    90: {
        "source": "synthetic_protracker",
        "hero_id": 90,
        "hero_name": "Keeper of the Light",
        "lane_role": 2,
        "avg_gpm": 527.0,
        "avg_xpm": 670.0,
        "avg_deaths": 5.7,
        "avg_last_hits": 223.1,
        "avg_net_worth": 17601.0,
        "avg_denies": 2.0,
        "avg_kills": 6.6,
        "networth_10": 3476.0,
        "duration_min": 33.4,
        "item_stats": [
            {"name": "item_urn_of_shadows", "purchase_rate": 100.0, "avg_minute": 4.1, "price": 880},
            {"name": "item_magic_wand", "purchase_rate": 49.2, "avg_minute": 5.2, "price": 450},
            {"name": "item_spirit_vessel", "purchase_rate": 100.0, "avg_minute": 9.3, "price": 2780},
            {"name": "item_travel_boots", "purchase_rate": 100.0, "avg_minute": 12.9, "price": 2500},
            {"name": "item_orchid", "purchase_rate": 25.2, "avg_minute": 15.5, "price": 3275},
            {"name": "item_octarine_core", "purchase_rate": 100.0, "avg_minute": 23.4, "price": 4600},
            {"name": "item_dagon", "purchase_rate": 20.2, "avg_minute": 23.6, "price": 2850},
            {"name": "item_ethereal_blade", "purchase_rate": 12.0, "avg_minute": 26.0, "price": 4650},
            {"name": "item_black_king_bar", "purchase_rate": 33.0, "avg_minute": 28.6, "price": 4050},
            {"name": "item_aghanims_shard", "purchase_rate": 48.8, "avg_minute": 29.8, "price": 1400},
            {"name": "item_ultimate_scepter", "purchase_rate": 31.0, "avg_minute": 31.1, "price": 4200},
            {"name": "item_sheepstick", "purchase_rate": 25.3, "avg_minute": 36.5, "price": 5175},
            {"name": "item_blink", "purchase_rate": 5.8, "avg_minute": 28.0, "price": 2250},
        ],
    },
    80: {
        "source": "synthetic_protracker",
        "hero_id": 80,
        "hero_name": "Lone Druid",
        "lane_role": 2,
        "avg_gpm": 694.0,
        "avg_xpm": 705.0,
        "avg_deaths": 3.6,
        "avg_last_hits": 411.8,
        "avg_net_worth": 25149.0,
        "avg_denies": 12.6,
        "avg_kills": 7.4,
        "networth_10": 4450.0,
        "duration_min": 36.2,
        "item_stats": [
            {"name": "item_power_treads", "purchase_rate": 100.0, "avg_minute": 4.6, "price": 1400},
            {"name": "item_orb_of_corrosion", "purchase_rate": 23.3, "avg_minute": 5.4, "price": 925},
            {"name": "item_diffusal_blade", "purchase_rate": 100.0, "avg_minute": 14.5, "price": 2500},
            {"name": "item_maelstrom", "purchase_rate": 100.0, "avg_minute": 14.9, "price": 2950},
            {"name": "item_mjollnir", "purchase_rate": 101.1, "avg_minute": 19.7, "price": 5500},
            {"name": "item_ultimate_scepter", "purchase_rate": 100.0, "avg_minute": 25.2, "price": 4200},
            {"name": "item_aghanims_shard", "purchase_rate": 101.1, "avg_minute": 25.2, "price": 1400},
            {"name": "item_invis_sword", "purchase_rate": 73.3, "avg_minute": 30.3, "price": 3000},
            {"name": "item_silver_edge", "purchase_rate": 63.3, "avg_minute": 32.5, "price": 5450},
            {"name": "item_disperser", "purchase_rate": 36.7, "avg_minute": 35.9, "price": 6100},
            {"name": "item_black_king_bar", "purchase_rate": 40.0, "avg_minute": 37.1, "price": 4050},
            {"name": "item_monkey_king_bar", "purchase_rate": 18.9, "avg_minute": 36.7, "price": 4975},
            {"name": "item_radiance", "purchase_rate": 8.0, "avg_minute": 18.0, "price": 4700},
            {"name": "item_desolator", "purchase_rate": 8.0, "avg_minute": 20.0, "price": 3500},
        ],
    },
    91: {
        "source": "synthetic_protracker",
        "hero_id": 91,
        "hero_name": "Io",
        "lane_role": 2,
        "avg_gpm": 485.0,
        "avg_xpm": 683.0,
        "avg_deaths": 6.6,
        "avg_last_hits": 204.4,
        "avg_net_worth": 15690.0,
        "avg_denies": 3.9,
        "avg_kills": 5.3,
        "networth_10": 3089.0,
        "duration_min": 32.4,
        "item_stats": [
            {"name": "item_bottle", "purchase_rate": 100.0, "avg_minute": 1.5, "price": 675},
            {"name": "item_magic_wand", "purchase_rate": 100.0, "avg_minute": 4.3, "price": 450},
            {"name": "item_null_talisman", "purchase_rate": 47.9, "avg_minute": 4.4, "price": 505},
            {"name": "item_soul_ring", "purchase_rate": 5.6, "avg_minute": 7.2, "price": 805},
            {"name": "item_aether_lens", "purchase_rate": 12.0, "avg_minute": 12.0, "price": 2275},
            {"name": "item_ultimate_scepter", "purchase_rate": 100.0, "avg_minute": 15.0, "price": 4200},
            {"name": "item_mekansm", "purchase_rate": 10.0, "avg_minute": 16.0, "price": 1775},
            {"name": "item_black_king_bar", "purchase_rate": 47.2, "avg_minute": 22.9, "price": 4050},
            {"name": "item_lotus_orb", "purchase_rate": 8.6, "avg_minute": 23.2, "price": 3850},
            {"name": "item_glimmer_cape", "purchase_rate": 12.0, "avg_minute": 24.0, "price": 2150},
            {"name": "item_spirit_vessel", "purchase_rate": 10.0, "avg_minute": 14.0, "price": 2780},
            {"name": "item_guardian_greaves", "purchase_rate": 8.0, "avg_minute": 28.0, "price": 4950},
        ],
    },
    107: {
        "source": "synthetic_protracker",
        "hero_id": 107,
        "hero_name": "Earth Spirit",
        "lane_role": 2,
        "avg_gpm": 420.0,
        "avg_xpm": 620.0,
        "avg_deaths": 6.2,
        "avg_last_hits": 120.0,
        "avg_net_worth": 14500.0,
        "avg_denies": 4.0,
        "avg_kills": 8.0,
        "networth_10": 2800.0,
        "duration_min": 34.0,
        "item_stats": [
            {"name": "item_bottle", "purchase_rate": 80.0, "avg_minute": 1.8, "price": 675},
            {"name": "item_magic_wand", "purchase_rate": 90.0, "avg_minute": 4.0, "price": 450},
            {"name": "item_power_treads", "purchase_rate": 85.0, "avg_minute": 5.5, "price": 1400},
            {"name": "item_urn_of_shadows", "purchase_rate": 70.0, "avg_minute": 6.5, "price": 880},
            {"name": "item_spirit_vessel", "purchase_rate": 65.0, "avg_minute": 12.0, "price": 2780},
            {"name": "item_blink", "purchase_rate": 85.0, "avg_minute": 14.0, "price": 2250},
            {"name": "item_veil_of_discord", "purchase_rate": 40.0, "avg_minute": 16.0, "price": 1725},
            {"name": "item_aether_lens", "purchase_rate": 35.0, "avg_minute": 18.0, "price": 2275},
            {"name": "item_black_king_bar", "purchase_rate": 55.0, "avg_minute": 24.0, "price": 4050},
            {"name": "item_ultimate_scepter", "purchase_rate": 50.0, "avg_minute": 26.0, "price": 4200},
            {"name": "item_octarine_core", "purchase_rate": 30.0, "avg_minute": 32.0, "price": 4600},
            {"name": "item_sheepstick", "purchase_rate": 25.0, "avg_minute": 36.0, "price": 5175},
        ],
    },
}


def _curve(avg_end: float, duration: float, power: float = 1.05) -> list[int]:
    minutes = max(20, int(round(duration)))
    values = []
    for minute in range(minutes + 1):
        ratio = (minute / duration) ** power if duration else 0
        values.append(int(round(avg_end * min(1.0, ratio))))
    return values


def rows_from_hero_stats(hero: dict[str, Any], copies: int = 40) -> list[dict[str, Any]]:
    duration = float(hero.get("duration_min") or 36)
    gpm = float(hero.get("avg_gpm") or 500)
    xpm = float(hero.get("avg_xpm") or 600)
    lh = float(hero.get("avg_last_hits") or 200)
    deaths = float(hero.get("avg_deaths") or 5)
    nw10 = float(hero.get("networth_10") or gpm * 10)
    items = sorted(hero.get("item_stats") or [], key=lambda row: row.get("avg_minute", 0))
    gold_t = []
    for minute in range(int(duration) + 1):
        if minute <= 10:
            gold_t.append(int(nw10 * (minute / 10 if minute else 0)))
        else:
            gold_t.append(int(gpm * minute))
    lh_t = _curve(lh, duration)
    xp_t = _curve(xpm * duration, duration)
    purchase_log = []
    hero_id = int(hero.get("hero_id") or 0)
    for item in items:
        name = normalize_item_name(item.get("name"))
        rate = float(item.get("purchase_rate") or 0)
        if not name or rate < CORE_PURCHASE_RATE:
            continue
        if not item_allowed_for_hero(hero_id, name):
            continue
        purchase_log.append({"key": name, "time": int(float(item.get("avg_minute") or 0) * 60)})
    death_times = [
        int(duration * 60 * (i + 1) / (deaths + 1)) for i in range(max(1, int(round(deaths))))
    ]
    rows = []
    for copy in range(copies):
        shifted = []
        for entry in purchase_log:
            jitter = ((copy * 7) % 40) - 20
            shifted.append({"key": entry["key"], "time": max(20, entry["time"] + jitter)})
        if copy % 7 == 0 and hero["hero_id"] == 80:
            shifted = [e for e in shifted if e["key"] not in {"maelstrom", "mjollnir"}]
            shifted.append({"key": "radiance", "time": 18 * 60})
        if copy % 9 == 0 and hero["hero_id"] == 80:
            shifted.append({"key": "desolator", "time": 20 * 60})
        rows.append(
            {
                "source": hero.get("source") or "synthetic",
                "match_id": 1_000_000 + hero["hero_id"] * 1000 + copy,
                "hero_id": hero["hero_id"],
                "lane_role": 2,
                "duration": int(duration * 60),
                "gold_t": gold_t,
                "lh_t": lh_t,
                "xp_t": xp_t,
                "purchase_log": shifted,
                "deaths": int(round(deaths)),
                "death_times": death_times,
                "enemy_heroes": [74, 11, 1, 2, 14][(copy % 3) :] + [8],
                "gpm": int(gpm),
                "xpm": int(xpm),
            }
        )
    return rows


def synthetic_dataset(heroes: dict[int, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    table = heroes or PROTRACKER_SNAPSHOT
    rows: list[dict[str, Any]] = []
    for hero in table.values():
        rows.extend(rows_from_hero_stats(hero))
    return rows
