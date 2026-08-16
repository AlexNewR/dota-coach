from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from dota_coach.config import DEATH_BENCHMARKS_PATH, DEFAULT_LANE_ROLE
from dota_coach.gsi.normalize import GameState


def build_death_benchmarks(rows: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[tuple[int, int], list[tuple[float, float]]] = defaultdict(list)
    for row in rows:
        hero_id = int(row.get("hero_id") or 0)
        role = int(row.get("lane_role") or DEFAULT_LANE_ROLE)
        duration = float(row.get("duration") or 0) / 60.0
        deaths = float(row.get("deaths") or 0)
        if duration <= 0:
            continue
        buckets[(hero_id, role)].append((deaths, duration))
    table: dict[str, Any] = {}
    for (hero_id, role), pairs in buckets.items():
        avg_deaths = sum(d for d, _ in pairs) / len(pairs)
        avg_duration = sum(t for _, t in pairs) / len(pairs)
        by_minute: dict[str, float] = {}
        for minute in range(0, 61):
            by_minute[str(minute)] = round(avg_deaths * min(1.0, minute / max(avg_duration, 1.0)), 2)
        table[f"{hero_id}:{role}"] = {
            "hero_id": hero_id,
            "lane_role": role,
            "avg_deaths": round(avg_deaths, 2),
            "avg_duration": round(avg_duration, 1),
            "n": len(pairs),
            "expected_by_minute": by_minute,
        }
    return table


def save_death_benchmarks(table: dict[str, Any], path: Path | None = None) -> Path:
    target = path or DEATH_BENCHMARKS_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(table), encoding="utf-8")
    return target


def load_death_benchmarks(path: Path | None = None) -> dict[str, Any]:
    target = path or DEATH_BENCHMARKS_PATH
    if not target.exists():
        return {}
    return json.loads(target.read_text(encoding="utf-8"))


class DeathBenchmarks:
    def __init__(self, table: dict[str, Any] | None = None) -> None:
        self.table = table if table is not None else load_death_benchmarks()

    def expected(self, hero_id: int, minute: int, role: int = DEFAULT_LANE_ROLE) -> float:
        row = self.table.get(f"{hero_id}:{role}") or self.table.get(f"{hero_id}:{DEFAULT_LANE_ROLE}")
        if not row:
            return max(0.3, minute / 12.0)
        return float(row["expected_by_minute"].get(str(minute), row["avg_deaths"]))

    def compare(self, state: GameState, role: int = DEFAULT_LANE_ROLE) -> dict[str, Any]:
        expected = self.expected(state.hero_id, state.minute, role)
        return {
            "deaths": state.deaths,
            "expected": expected,
            "over": state.deaths > expected + 0.7,
            "gold": state.gold,
            "has_tp": state.has_tp,
        }
