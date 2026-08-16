from __future__ import annotations

import threading
import time
from typing import Any

from dota_coach.coach.counters import analyze, mistake_for_purchase
from dota_coach.coach.hints import Hint
from dota_coach.coach.live_book import LiveHeroBook
from dota_coach.coach.policy import HintPolicy
from dota_coach.config import DEFAULT_HERO_IDS, DEFAULT_LANE_ROLE, FARM_BELOW_P25_SECONDS, ITEM_HINT_GOLD_RATIO
from dota_coach.constants import (
    ITEM_COSTS,
    INVENTORY_SLOT_LIMIT,
    hero_display,
    inventory_free_actions,
    is_finished_item,
    is_upgrade_of_owned,
    item_allowed_for_hero,
    item_display,
    normalize_item_name,
)
from dota_coach.gsi.normalize import GameState
from dota_coach.models.deaths import DeathBenchmarks
from dota_coach.models.farm import FarmBenchmarks
from dota_coach.models.items import ItemModel, ensure_early_boots
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
        self._lock = threading.RLock()
        self.policy = HintPolicy()
        self.prev: GameState | None = None
        self.below_since: float | None = None
        self.last_inventory: set[str] = set()
        self.previously_owned_items: set[str] = set()
        self.sold_items: set[str] = set()
        self.prev_recommended: list[str] = []
        self.current_hero_id = 0
        self.current_hero_npc = ""
        self.known_match_id = ""
        self.known_enemies: list[int] = []
        self.known_allies: list[int] = []
        self.book = LiveHeroBook(lock=self._lock)

    def reset_match_state(
        self,
        new_match_id: str = "",
        new_hero_id: int = 0,
        new_hero_npc: str = "",
    ) -> None:
        """Сбрасывает историю подсказок, инвентарь и кэши при начале нового матча."""
        with self._lock:
            self.policy = HintPolicy()
            self.last_inventory = set()
            self.previously_owned_items = set()
            self.sold_items = set()
            self.prev_recommended = []
            self.below_since = None
            self.known_enemies = []
            self.known_allies = []
            if new_match_id:
                self.known_match_id = new_match_id
            if new_hero_id > 0:
                self.current_hero_id = new_hero_id
                self.current_hero_npc = new_hero_npc
            elif not self.current_hero_id:
                self.current_hero_id = 0
                self.current_hero_npc = ""

    def _is_new_match(self, state: GameState) -> bool:
        """Определяет смену или начало нового матча даже для того же героя."""
        if self.prev is None:
            return False
        # 1. Сменился идентификатор матча
        if state.match_id and self.known_match_id and state.match_id != self.known_match_id:
            return True
        # 2. Сменился герой
        if state.hero_id > 0 and self.current_hero_id > 0 and state.hero_id != self.current_hero_id:
            return True
        # 3. Переход из пост-игры / дисконнекта в новую игру
        if (
            self.prev.game_state == "DOTA_GAMERULES_STATE_POST_GAME"
            and state.game_state != "DOTA_GAMERULES_STATE_POST_GAME"
        ):
            return True
        # 4. Переход in_game с False на True (новый вход в игру с ранним временем или наличием старого инвентаря)
        if not self.prev.in_game and state.in_game:
            if (
                state.clock_time <= 180
                or self.prev.clock_time > 180
                or bool(self.last_inventory)
                or bool(self.policy.history)
            ):
                return True
        # 5. Сброс игрового таймера (предыдущий матч был в разгаре >30с, а сейчас докриповое время или скачок назад)
        if self.prev.clock_time > 30 and (state.clock_time <= 0 or state.clock_time < self.prev.clock_time - 60):
            return True
        # 6. Переход из активной игры обратно в прегейм
        if (
            self.prev.game_state == "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS"
            and state.game_state == "DOTA_GAMERULES_STATE_PRE_GAME"
        ):
            return True
        return False

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
                    title="Отстаёшь по крипам",
                    body=(
                        f"К {cmp['minute']} мин на {hero} у про обычно около "
                        f"{int(cmp['lh_p50'])} крипов, у тебя {state.last_hits}. "
                        f"Добивай волну и не уходи с линии без причины."
                    ),
                    severity="warn",
                    key=f"farm-{state.minute // 2}",
                )
        else:
            self.below_since = None
        return None

    def _counter_boost(
        self,
        state: GameState,
        pairs: list[tuple[str, float | None]],
    ) -> list[tuple[str, float | None]]:
        """Поднимает контр-предметы vs текущего драфта в список следующих слотов."""
        if not state.enemy_heroes:
            return pairs
        matchup = analyze(state)
        owned = {normalize_item_name(item) for item in state.items}
        owned.discard("")
        prefer: list[str] = []
        for row in matchup.get("suggestions") or []:
            name = normalize_item_name(str(row.get("item") or ""))
            if not name or name in owned or name in prefer:
                continue
            if not item_allowed_for_hero(state.hero_id, name):
                continue
            prefer.append(name)
        if not prefer:
            return pairs
        top_prefer = prefer[:2]
        prefer_set = set(top_prefer)
        by_name = {normalize_item_name(name): (name, prob) for name, prob in pairs}
        front: list[tuple[str, float | None]] = []
        for name in top_prefer:
            if name in by_name:
                front.append(by_name[name])
            else:
                front.append((name, None))
        rest = [
            (name, prob)
            for name, prob in pairs
            if normalize_item_name(name) not in prefer_set
        ]
        return (front + rest)[: max(3, len(pairs) or 3)]

    def _recommend_items(self, state: GameState) -> tuple[list[tuple[str, float | None]], str]:
        """Плавный ансамбль NN + D2PT/OpenDota lookup по минутам и уверенности."""
        lookup_ranked = self.lookup.get_ranked_items(state, self.role, sold_items=self.sold_items)
        lookup_pairs = [(name, float(p)) for name, p in lookup_ranked]
        pairs: list[tuple[str, float | None]] = []
        source = "none"

        if self.items is not None and state.hero_id in DEFAULT_HERO_IDS:
            nn = self.items.recommend(state, self.role, top_k=6, sold_items=self.sold_items)
            if nn:
                top_p = float(nn[0][1]) if nn[0][1] is not None else 0.0
                # Плавный переход по времени (от минут 3 до 15)
                alpha = max(0.0, min(1.0, (state.minute - 3.0) / 12.0))
                # Взвешивание уверенности нейросети
                conf = max(0.0, min(1.0, top_p / 0.12))
                w_nn = alpha * conf if lookup_ranked else 1.0
                w_lookup = 1.0 - w_nn if lookup_ranked else 0.0

                if w_nn >= 0.85 or not lookup_ranked:
                    pairs = [(name, float(p) if p is not None else None) for name, p in nn[:3]]
                    source = "nn"
                elif w_nn <= 0.15:
                    pairs = [(name, float(p) if p is not None else None) for name, p in lookup_pairs[:3]]
                    source = "lookup"
                else:
                    # Плавный бленд распределений вероятностей
                    nn_dict = {normalize_item_name(n): (n, float(p) if p is not None else 0.0) for n, p in nn}
                    lk_dict = {normalize_item_name(n): (n, float(p) if p is not None else 0.0) for n, p in lookup_pairs}
                    all_keys = list(dict.fromkeys(list(lk_dict.keys()) + list(nn_dict.keys())))
                    scored: list[tuple[str, float]] = []
                    for k in all_keys:
                        display_n = nn_dict[k][0] if k in nn_dict else lk_dict[k][0]
                        p_nn = nn_dict.get(k, ("", 0.0))[1]
                        p_lk = lk_dict.get(k, ("", 0.0))[1]
                        comb = w_nn * p_nn + w_lookup * p_lk
                        scored.append((display_n, comb))
                    scored.sort(key=lambda item: -item[1])
                    pairs = [(name, round(score, 3)) for name, score in scored[:3]]
                    source = "blend"
            elif lookup_pairs:
                pairs = [(name, float(p) if p is not None else None) for name, p in lookup_pairs[:3]]
                source = "lookup"
        elif lookup_pairs:
            pairs = [(name, float(p) if p is not None else None) for name, p in lookup_pairs[:3]]
            source = "lookup"

        ensured = ensure_early_boots(pairs, state, sold_items=self.sold_items)
        if ensured and not pairs:
            source = "boots"
        merged = self._counter_boost(state, ensured)
        before = [normalize_item_name(name) for name, _ in ensured]
        after = [normalize_item_name(name) for name, _ in merged]
        if after != before:
            if source in {"none", "boots"}:
                source = "counter"
            else:
                source = f"{source}+counter"
        return merged, source

    def _inventory_tip(self, state: GameState) -> str:
        slots = int(getattr(state, "inventory_slots", 0) or 0)
        if slots < INVENTORY_SLOT_LIMIT and slots > 0:
            return ""
        if slots == 0 and len([n for n in state.items if n and n != "aghanims_shard"]) < INVENTORY_SLOT_LIMIT:
            return ""
        actions = inventory_free_actions(
            state.items,
            scepter_consumed=bool(getattr(state, "scepter_consumed", False)),
        )
        if not actions:
            return ""
        return "Освободи слот: " + "; ".join(actions) + "."

    def _item_hint(self, state: GameState, new_items: set[str]) -> Hint | None:
        pairs, source = self._recommend_items(state)
        recommended = [name for name, _ in pairs]
        recently_ok = {normalize_item_name(name) for name in self.prev_recommended}
        bought_norm = {normalize_item_name(name) for name in new_items if name}
        # Не ругаем покупку того, что сами только что советовали (после покупки
        # предмет выпадает из top-k как owned — иначе противоречие «купи → плохо»).
        # Не ругаем расходники и стартовые предметы (до 3 мин или дешевле 1000g).
        major_bought = [
            name
            for name in bought_norm
            if is_finished_item(name) and ITEM_COSTS.get(name, 0) >= 1000
        ]
        if (
            state.minute >= 3
            and major_bought
            and bought_norm.isdisjoint(recently_ok)
            and bought_norm.isdisjoint(
                {normalize_item_name(name) for name in recommended[:3]}
            )
        ):
            bought = item_display(major_bought[0])
            top = recommended[0] if recommended else ""
            if top:
                return Hint(
                    kind="item",
                    title="Другой предмет",
                    body=f"Ты купил {bought}. Лучше {item_display(top)} в этой ситуации.",
                    severity="warn",
                    key=f"item-bought-{state.minute}",
                    instead=item_display(top),
                )
        top = recommended[0] if recommended else ""
        if not top:
            return None
        cost = ITEM_COSTS.get(top, 2500)
        owned = set(state.items)
        if top not in owned and state.gold >= cost * ITEM_HINT_GOLD_RATIO and state.minute >= 3:
            extra = ", ".join(item_display(name) for name in recommended[1:3])
            tail = f" Ещё: {extra}." if extra else ""
            tip = self._inventory_tip(state)
            if tip:
                tail = f" {tip}{tail}"
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
                instead="",
            )
        return None

    def _counter_hint(self, state: GameState, new_items: set[str]) -> Hint | None:
        ignore = {normalize_item_name(name) for name in self.prev_recommended}
        hit = mistake_for_purchase(state, new_items, ignore_items=ignore)
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
            self.reset_match_state(
                new_match_id=state.match_id,
                new_hero_id=state.hero_id,
                new_hero_npc=state.hero_name,
            )
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
        with self._lock:
            now = time.time() if now is None else now
            if self._is_new_match(state):
                self.reset_match_state(
                    new_match_id=state.match_id,
                    new_hero_id=state.hero_id,
                    new_hero_npc=state.hero_name,
                )
            if state.match_id and not self.known_match_id:
                self.known_match_id = state.match_id
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
            current_normalized = {normalize_item_name(x) for x in state.items if x}
            if getattr(state, "scepter_consumed", False) or getattr(state, "has_scepter", False):
                current_normalized.add("ultimate_scepter")
            if getattr(state, "has_shard", False):
                current_normalized.add("aghanims_shard")
            if getattr(state, "moon_shard_consumed", False):
                current_normalized.add("moon_shard")
            if self.previously_owned_items:
                disappeared = self.previously_owned_items - current_normalized
                for item in disappeared:
                    if not is_upgrade_of_owned(item, current_normalized):
                        self.sold_items.add(item)
            self.previously_owned_items.update(current_normalized)

            new_items = owned - self.last_inventory
            pairs, _rec_source = self._recommend_items(state)
            recommended_now = [name for name, _ in pairs]
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
            self.prev_recommended = recommended_now
            self.prev = state
            if not candidates:
                return None
            order = {"death": 0, "counter": 1, "item": 2, "farm": 3}
            candidates.sort(key=lambda hint: order.get(hint.kind, 9))
            return self.policy.push(candidates[0], now)

    def snapshot(self, state: GameState | None) -> dict[str, Any]:
        with self._lock:
            farm = self.farm.compare(state, self.role) if state else None
            recs = []
            rec_source = "none"
            matchup: dict[str, Any] = {
                "enemies": [],
                "mistakes": [],
                "suggestions": [],
                "tips": [],
            }
            if state:
                # GSI часто теряет draft после пиков — восстанавливаем roster до analyze.
                self._remember_roster(state)
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
            endorsed = {normalize_item_name(name) for name in self.prev_recommended}
            endorsed.update(normalize_item_name(str(row["name"])) for row in recs)
            bad_items = {
                str(row["item"])
                for row in matchup["mistakes"]
                if normalize_item_name(str(row["item"])) not in endorsed
            }
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
                "inventory_tip": self._inventory_tip(state) if state else "",
                "enemies": matchup["enemies"],
                "counters": matchup["suggestions"],
                "counter_tips": matchup.get("tips") or [],
                "mistakes": matchup["mistakes"],
                "hint": latest.to_dict() if latest else None,
                "history": [hint.to_dict() for hint in self.policy.history[-6:]],
            }
