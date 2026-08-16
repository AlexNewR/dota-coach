from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from dota_coach.config import DEFAULT_LANE_ROLE, ITEM_LOOKUP_PATH
from dota_coach.constants import normalize_item_name, resolve_upgrade_prerequisite
from dota_coach.gsi.normalize import GameState
from dota_coach.models.items import _should_recommend, ensure_early_boots


def _bucket(minute: int) -> int:
    return max(0, minute) // 5 * 5


def build_item_lookup(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[tuple[int, int, int], Counter[str]] = defaultdict(Counter)
    for row in rows:
        hero_id = int(row.get("hero_id") or 0)
        role = int(row.get("lane_role") or DEFAULT_LANE_ROLE)
        owned: list[str] = []
        for event in row.get("purchase_log") or []:
            name = normalize_item_name(event.get("key"))
            if not name:
                continue
            minute = int(event.get("time") or 0) // 60
            key = (hero_id, role, _bucket(minute))
            counts[key][name] += 1
            owned.append(name)
    table: dict[str, Any] = {}
    for (hero_id, role, bucket), counter in counts.items():
        ranked = counter.most_common(8)
        table[f"{hero_id}:{role}:{bucket}"] = {
            "hero_id": hero_id,
            "lane_role": role,
            "minute_bucket": bucket,
            "items": [{"name": name, "count": count} for name, count in ranked],
        }
    return table


def save_item_lookup(table: dict[str, Any], path: Path | None = None) -> Path:
    target = path or ITEM_LOOKUP_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(table), encoding="utf-8")
    return target


def load_item_lookup(path: Path | None = None) -> dict[str, Any]:
    target = path or ITEM_LOOKUP_PATH
    if not target.exists():
        return {}
    return json.loads(target.read_text(encoding="utf-8"))


class ItemLookup:
    def __init__(self, table: dict[str, Any] | None = None) -> None:
        self.table = table if table is not None else load_item_lookup()

    def get_ranked_items(
        self,
        state: GameState,
        role: int = DEFAULT_LANE_ROLE,
        sold_items: set[str] | None = None,
    ) -> list[tuple[str, float]]:
        """Возвращает список (item_name, norm_frequency) для текущего состояния."""
        owned = {normalize_item_name(item) for item in state.items}
        bucket = _bucket(state.minute)
        for key in (
            f"{state.hero_id}:{role}:{bucket}",
            f"{state.hero_id}:{DEFAULT_LANE_ROLE}:{bucket}",
            f"{state.hero_id}:{role}:{max(0, bucket - 5)}",
        ):
            row = self.table.get(key)
            if not row or not row.get("items"):
                continue
            valid_map: dict[str, int] = {}
            for it in row["items"]:
                raw_name = str(it.get("name") or "")
                name = resolve_upgrade_prerequisite(raw_name, owned, minute=state.minute)
                if not _should_recommend(name, state, owned, sold_items=sold_items):
                    continue
                cnt = int(it.get("count", 1))
                valid_map[name] = valid_map.get(name, 0) + cnt
            if not valid_map:
                continue
            total = sum(valid_map.values()) or 1
            sorted_items = sorted(valid_map.items(), key=lambda x: -x[1])
            return [(name, float(cnt) / float(total)) for name, cnt in sorted_items]
        return []

    def recommend(
        self,
        state: GameState,
        role: int = DEFAULT_LANE_ROLE,
        top_k: int = 3,
        sold_items: set[str] | None = None,
    ) -> list[str]:
        ranked = self.get_ranked_items(state, role, sold_items=sold_items)
        if ranked:
            pairs = ensure_early_boots([(n, p) for n, p in ranked], state, top_k=top_k, sold_items=sold_items)
            if pairs:
                return [name for name, _ in pairs]
        # Нет частотных айтемов в бакете — всё равно попробуем ботинки.
        pairs = ensure_early_boots([], state, top_k=top_k, sold_items=sold_items)
        return [name for name, _ in pairs]
