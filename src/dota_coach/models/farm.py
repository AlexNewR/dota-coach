from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from dota_coach.config import DEFAULT_LANE_ROLE, FARM_BENCHMARKS_PATH
from dota_coach.gsi.normalize import GameState


def _percentiles(values: list[float]) -> dict[str, float]:
    if not values:
        return {"p25": 0.0, "p50": 0.0, "p75": 0.0}
    ordered = sorted(values)
    def at(q: float) -> float:
        index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * q))))
        return float(ordered[index])
    return {"p25": at(0.25), "p50": at(0.50), "p75": at(0.75)}


def build_farm_benchmarks(rows: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[tuple[int, int, int], dict[str, list[float]]] = defaultdict(
        lambda: {"lh": [], "gold": [], "xp": []}
    )
    for row in rows:
        hero_id = int(row.get("hero_id") or 0)
        role = int(row.get("lane_role") or DEFAULT_LANE_ROLE)
        lh_t = list(row.get("lh_t") or [])
        gold_t = list(row.get("gold_t") or [])
        xp_t = list(row.get("xp_t") or [])
        for minute, lh in enumerate(lh_t):
            key = (hero_id, role, minute)
            buckets[key]["lh"].append(float(lh))
            if minute < len(gold_t):
                buckets[key]["gold"].append(float(gold_t[minute]))
            if minute < len(xp_t):
                buckets[key]["xp"].append(float(xp_t[minute]))
    table: dict[str, Any] = {}
    for (hero_id, role, minute), series in buckets.items():
        table[f"{hero_id}:{role}:{minute}"] = {
            "hero_id": hero_id,
            "lane_role": role,
            "minute": minute,
            "lh": _percentiles(series["lh"]),
            "gold": _percentiles(series["gold"]),
            "xp": _percentiles(series["xp"]),
            "n": len(series["lh"]),
        }
    return table


def save_farm_benchmarks(table: dict[str, Any], path: Path | None = None) -> Path:
    target = path or FARM_BENCHMARKS_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(table), encoding="utf-8")
    return target


def load_farm_benchmarks(path: Path | None = None) -> dict[str, Any]:
    target = path or FARM_BENCHMARKS_PATH
    if not target.exists():
        return {}
    return json.loads(target.read_text(encoding="utf-8"))


class FarmBenchmarks:
    def __init__(self, table: dict[str, Any] | None = None) -> None:
        self.table = table if table is not None else load_farm_benchmarks()

    def lookup(self, hero_id: int, minute: int, role: int = DEFAULT_LANE_ROLE) -> dict[str, Any] | None:
        for key in (
            f"{hero_id}:{role}:{minute}",
            f"{hero_id}:{DEFAULT_LANE_ROLE}:{minute}",
        ):
            if key in self.table:
                return self.table[key]
        return None

    def compare(self, state: GameState, role: int = DEFAULT_LANE_ROLE) -> dict[str, Any] | None:
        row = self.lookup(state.hero_id, state.minute, role)
        if not row:
            return None
        lh = row["lh"]
        gold = row["gold"]
        xp = row["xp"]
        minute = max(1, state.minute)
        earned = state.earned_gold
        # GPM из GSI — уже «всего добыто / минуты»; если нет, считаем из total gold.
        gpm = state.gpm if state.gpm > 0 else int(earned / minute)
        gpm_p50 = int(gold["p50"] / minute)
        gpm_p25 = int(gold["p25"] / minute)
        xpm_p50 = int(xp["p50"] / minute)
        xpm_p25 = int(xp["p25"] / minute)
        return {
            "minute": state.minute,
            "lh": state.last_hits,
            "lh_p25": lh["p25"],
            "lh_p50": lh["p50"],
            "lh_p75": lh["p75"],
            "gold": earned,
            "gold_p25": gold["p25"],
            "gold_p50": gold["p50"],
            "gold_p75": gold["p75"],
            "gpm": gpm,
            "gpm_p25": gpm_p25,
            "gpm_p50": gpm_p50,
            "xpm": state.xpm,
            "xpm_p25": xpm_p25,
            "xpm_p50": xpm_p50,
            "below_p25": state.last_hits < lh["p25"],
            "below_p50": state.last_hits < lh["p50"],
            "gold_below_p50": earned < gold["p50"] if earned else False,
            "gpm_below_p50": gpm < gpm_p50 if gpm else False,
        }
