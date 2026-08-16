from __future__ import annotations

import threading
from typing import Any

from dota_coach.data.heroes import hero_english_name
from dota_coach.data.protracker import fetch_hero_page, parse_hero_html
from dota_coach.data.synthetic import rows_from_hero_stats
from dota_coach.models.deaths import DeathBenchmarks, build_death_benchmarks
from dota_coach.models.farm import FarmBenchmarks, build_farm_benchmarks
from dota_coach.models.lookup import ItemLookup, build_item_lookup


class LiveHeroBook:
    """Подгружает mid-статы D2PT для героя, которого GSI только что увидел."""

    def __init__(self, lock: threading.RLock | None = None) -> None:
        self._ready: set[int] = set()
        self._pending: set[int] = set()
        self._lock = lock if lock is not None else threading.RLock()
        self.status: dict[int, str] = {}

    def knows(self, hero_id: int, farm: FarmBenchmarks) -> bool:
        with self._lock:
            return farm.lookup(hero_id, 8) is not None or hero_id in self._ready

    def ensure(
        self,
        hero_id: int,
        farm: FarmBenchmarks,
        deaths: DeathBenchmarks,
        lookup: ItemLookup,
        npc: str = "",
    ) -> None:
        if hero_id <= 0:
            return
        with self._lock:
            if hero_id in self._ready or hero_id in self._pending or self.knows(hero_id, farm):
                if self.knows(hero_id, farm):
                    self._ready.add(hero_id)
                return
            self._pending.add(hero_id)
            self.status[hero_id] = "loading"
        thread = threading.Thread(
            target=self._load,
            args=(hero_id, npc, farm, deaths, lookup),
            daemon=True,
            name=f"d2pt-hero-{hero_id}",
        )
        thread.start()

    def _load(
        self,
        hero_id: int,
        npc: str,
        farm: FarmBenchmarks,
        deaths: DeathBenchmarks,
        lookup: ItemLookup,
    ) -> None:
        name = hero_english_name(hero_id, npc)
        try:
            html = fetch_hero_page(name, role="Mid")
            hero = parse_hero_html(html, hero_id, name)
            rows = rows_from_hero_stats(hero, copies=24)
            new_farm = build_farm_benchmarks(rows)
            new_deaths = build_death_benchmarks(rows)
            new_lookup = build_item_lookup(rows)
            with self._lock:
                farm.table.update(new_farm)
                deaths.table.update(new_deaths)
                lookup.table.update(new_lookup)
                self._ready.add(hero_id)
                self.status[hero_id] = "ready"
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                self.status[hero_id] = f"error:{type(exc).__name__}"
        finally:
            with self._lock:
                self._pending.discard(hero_id)
