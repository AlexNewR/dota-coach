from __future__ import annotations

import time
from typing import Any

from dota_coach.coach.counters import analyze, mistake_for_purchase
from dota_coach.coach.hints import Hint
from dota_coach.coach.live_book import LiveHeroBook
from dota_coach.coach.policy import HintPolicy
from dota_coach.config import DEFAULT_HERO_IDS, DEFAULT_LANE_ROLE, FARM_BELOW_P25_SECONDS, ITEM_HINT_GOLD_RATIO
from dota_coach.constants import ITEM_COSTS, hero_display, item_display
from dota_coach.gsi.normalize import GameState
from dota_coach.models.deaths import DeathBenchmarks
from dota_coach.models.farm import FarmBenchmarks
from dota_coach.models.items import ItemModel
from dota_coach.models.lookup import ItemLookup


class CoachEngine:
    def __init__(
        self,
        farm: FarmBenchmarks,
        deaths: DeathBenchmarks,
        lookup: ItemLookup,
        items: ItemModel | None = None,
        role: int = DEFAULT_LANE_ROLE,
    ) -> None:
        self.farm = farm
        self.deaths = deaths
        self.lookup = lookup
        self.items = items
        self.role = role
        self.policy = HintPolicy()
        self.prev: GameState | None = None
        self.below_since: float | None = None
        self.last_inventory: set[str] = set()
        self.current_hero_id = 0
        self.current_hero_npc = ""
        self.known_match_id = ""
        self.known_enemies: list[int] = []
        self.known_allies: list[int] = []
        self.book = LiveHeroBook()

    def _farm_hint(self, state: GameState, now: float) -> Hint | None:
        cmp = self.farm.compare(state, self.role)
        if not cmp:
            return None
        if cmp["below_p25"] and state.minute >= 4:
            if self.below_since is None:
                self.below_since = now
            elif now - self.below_since >= FARM_BELOW_P25_SECONDS:
                hero = hero_display(state.hero_id, state.hero_name)
                return Hint(
                    kind="farm",
                    title="Отстаёшь по фарму",
                    body=(
                        f"На {cmp['minute']} мин у про-мидера на {hero} медиана "
                        f"{int(cmp['lh_p50'])} LH, у тебя {state.last_hits} "
                        f"(p25={int(cmp['lh_p25'])}). Добивай крипов и не теряй волны."
                    ),
                    severity="warn",
                    key=f"farm-{state.minute // 2}",
                )
        else:
            self.below_since = None
        return None

    def _recommend_items(self, state: GameState) -> tuple[list[tuple[str, float | None]], str]:
        """Для DEFAULT_HERO_IDS — сначала NN; lookup только если NN пустая/нет модели."""
        if self.items is not None and state.hero_id in DEFAULT_HERO_IDS:
            nn = self.items.recommend(state, self.role)
            if nn:
                return [(name, float(p)) for name, p in nn], "nn"
        lookup = self.lookup.recommend(state, self.role)
        if lookup:
            return [(name, None) for name in lookup], "lookup"
        return [], "none"

    def _item_hint(self, state: GameState, new_items: set[str]) -> Hint | None:
        pairs, source = self._recommend_items(state)
        recommended = [name for name, _ in pairs]
        if not recommended:
            return None
        top = recommended[0]
        if new_items and new_items.isdisjoint(set(recommended[:3])):
            bought = item_display(next(iter(new_items)))
            return Hint(
                kind="item",
                title="Другой предмет",
                body=f"Ты купил {bought}. Лучше {item_display(top)} в этой ситуации.",
                severity="warn",
                key=f"item-bought-{state.minute}",
                instead=item_display(top),
            )
        cost = ITEM_COSTS.get(top, 2500)
        owned = set(state.items)
        if top not in owned and state.gold >= cost * ITEM_HINT_GOLD_RATIO and state.minute >= 3:
            extra = ", ".join(item_display(name) for name in recommended[1:3])
            tail = f" Ещё: {extra}." if extra else ""
            return Hint(
                kind="item",
                title="Следующий предмет",
                body=(
                    f"На {state.minute} мин для "
                    f"{hero_display(state.hero_id, state.hero_name)}: "
                    f"{item_display(top)} (~{cost} золота). В рюкзаке {state.gold}.{tail}"
                ),
                severity="info",
                key=f"item-next-{top}-{state.minute // 4}",
                instead=item_display(top),
            )
        return None

    def _counter_hint(self, state: GameState, new_items: set[str]) -> Hint | None:
        hit = mistake_for_purchase(state, new_items)
        if not hit:
            return None
        instead = ", ".join(item_display(name) for name in hit.instead[:2]) or "контр-предмет"
        return Hint(
            kind="counter",
            title=f"Плохой выбор против {hit.enemy}",
            body=hit.reason,
            severity="bad",
            key=f"counter-{hit.item}-{hit.enemy_id}",
            instead=instead,
            enemy=hit.enemy,
        )

    def _death_hint(self, state: GameState) -> Hint | None:
        prev = self.prev
        if prev is None or not (prev.alive and not state.alive):
            return None
        cmp = self.deaths.compare(state, self.role)
        bits = [
            f"{state.deaths}-я смерть к {state.minute} мин, у про-мидера норма ≈ {cmp['expected']:.1f}."
        ]
        if state.gold >= 1200:
            bits.append(f"Умер с {state.gold} незатраченного золота — потрать перед дракой.")
        if not state.has_tp:
            bits.append("Не было TP: на миде без свитка тебя легко ловят.")
        return Hint(
            kind="death",
            title="Смерть",
            body=" ".join(bits),
            severity="bad",
            key=f"death-{state.deaths}-{state.minute}",
        )

    def _bind_hero(self, state: GameState) -> None:
        if state.hero_id <= 0:
            return
        if state.hero_id != self.current_hero_id:
            self.current_hero_id = state.hero_id
            self.current_hero_npc = state.hero_name
            self.policy = HintPolicy()
            self.last_inventory = set()
            self.below_since = None
            self.known_enemies = []
            self.known_allies = []
        self.book.ensure(state.hero_id, self.farm, self.deaths, self.lookup, state.hero_name)

    def _remember_roster(self, state: GameState) -> None:
        if state.match_id and state.match_id != self.known_match_id:
            self.known_match_id = state.match_id
            self.known_enemies = []
            self.known_allies = []
        if state.enemy_heroes:
            self.known_enemies = list(dict.fromkeys(state.enemy_heroes))
        elif self.known_enemies:
            state.enemy_heroes = list(self.known_enemies)
        if state.ally_heroes:
            self.known_allies = list(dict.fromkeys(state.ally_heroes))
        elif self.known_allies:
            state.ally_heroes = list(self.known_allies)

    def update(self, state: GameState, now: float | None = None) -> Hint | None:
        now = time.time() if now is None else now
        if state.hero_id <= 0 and self.current_hero_id:
            state.hero_id = self.current_hero_id
            state.hero_name = self.current_hero_npc
        if state.hero_id > 0:
            self._bind_hero(state)
        self._remember_roster(state)
        if not state.in_game:
            self.prev = state
            return None
        if state.hero_id <= 0:
            self.prev = state
            return None
        owned = set(state.items)
        new_items = owned - self.last_inventory
        candidates = [
            hint
            for hint in (
                self._death_hint(state),
                self._counter_hint(state, new_items),
                self._item_hint(state, new_items),
                self._farm_hint(state, now),
            )
            if hint is not None
        ]
        self.last_inventory = owned
        self.prev = state
        if not candidates:
            return None
        order = {"death": 0, "counter": 1, "item": 2, "farm": 3}
        candidates.sort(key=lambda hint: order.get(hint.kind, 9))
        return self.policy.push(candidates[0], now)

    def snapshot(self, state: GameState | None) -> dict[str, Any]:
        farm = self.farm.compare(state, self.role) if state else None
        recs = []
        rec_source = "none"
        matchup = {"enemies": [], "mistakes": [], "suggestions": []}
        if state:
            matchup = analyze(state)
            pairs, rec_source = self._recommend_items(state)
            recs = [
                {
                    "name": name,
                    "label": item_display(name),
                    "p": round(prob, 3) if prob is not None else None,
                    "source": rec_source,
                }
                for name, prob in pairs
            ]
        latest = self.policy.history[-1] if self.policy.history else None
        hero_id = state.hero_id if state else self.current_hero_id
        npc = state.hero_name if state else self.current_hero_npc
        book_status = self.book.status.get(hero_id, "idle") if hero_id else "idle"
        bad_items = {str(row["item"]) for row in matchup["mistakes"]}
        return {
            "connected": state is not None,
            "in_game": bool(state and state.in_game),
            "hero": hero_display(hero_id, npc) if hero_id else "",
            "hero_id": hero_id,
            "hero_detected": bool(hero_id),
            "book_status": book_status,
            "role": "мид",
            "clock": state.clock_time if state else 0,
            "minute": state.minute if state else 0,
            "kda": [state.kills, state.deaths, state.assists] if state else [0, 0, 0],
            "last_hits": state.last_hits if state else 0,
            "denies": state.denies if state else 0,
            "gpm": state.gpm if state else 0,
            "xpm": state.xpm if state else 0,
            "gold": state.earned_gold if state else 0,
            "gold_bag": state.gold if state else 0,
            "net_worth": state.net_worth if state else 0,
            "alive": state.alive if state else True,
            "items": [
                {
                    "name": name,
                    "label": item_display(name),
                    "bad": name in bad_items,
                }
                for name in (state.items if state else [])
            ],
            "farm": farm,
            "recommended": recs,
            "recommend_source": rec_source,
            "enemies": matchup["enemies"],
            "counters": matchup["suggestions"],
            "mistakes": matchup["mistakes"],
            "hint": latest.to_dict() if latest else None,
            "history": [hint.to_dict() for hint in self.policy.history[-6:]],
        }
