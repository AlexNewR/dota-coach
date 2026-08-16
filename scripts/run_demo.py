from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

os.environ.setdefault("DOTA_COACH_HINT_COOLDOWN", "6")
os.environ.setdefault("DOTA_COACH_FARM_SECONDS", "2")
os.environ.setdefault("DOTA_COACH_DEATH_COOLDOWN", "3")

from fastapi.testclient import TestClient  # noqa: E402

from dota_coach.coach.engine import CoachEngine  # noqa: E402
from dota_coach.config import DEFAULT_HERO_IDS, ITEM_MODEL_PATH, ITEM_VOCAB_PATH  # noqa: E402
from dota_coach.data.collect import collect  # noqa: E402
from dota_coach.gsi.normalize import GameState, normalize_gsi  # noqa: E402
from dota_coach.gsi.server import app, set_engine  # noqa: E402
from dota_coach.models.deaths import DeathBenchmarks  # noqa: E402
from dota_coach.models.farm import FarmBenchmarks  # noqa: E402
from dota_coach.models.items import ItemModel, ItemVocab, load_item_model  # noqa: E402
from dota_coach.models.lookup import ItemLookup  # noqa: E402
from dota_coach.models.train import train_all  # noqa: E402


def gsi_payload(
    *,
    clock: int,
    last_hits: int,
    gold: int,
    deaths: int,
    alive: bool,
    items: list[str],
    hero_id: int = 90,
    hero: str = "npc_dota_hero_keeper_of_the_light",
    gpm: int = 320,
    has_tp: bool = True,
) -> dict:
    slots = {}
    for i in range(9):
        name = items[i] if i < len(items) else "empty"
        if name and not name.startswith("item_") and name != "empty":
            name = f"item_{name}"
        slots[f"slot{i}"] = {"name": name}
    slots["teleport0"] = {"name": "item_tpscroll" if has_tp else "empty"}
    return {
        "auth": {"token": "dota_coach_local"},
        "map": {
            "matchid": "demo-kotl",
            "clock_time": clock,
            "game_time": clock + 90,
            "game_state": "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS",
            "paused": False,
        },
        "player": {
            "name": "Alex",
            "team_name": "radiant",
            "kills": 1,
            "deaths": deaths,
            "assists": 2,
            "last_hits": last_hits,
            "denies": 1,
            "gold": gold,
            "gpm": gpm,
            "xpm": 400,
            "net_worth": gold + 1200,
        },
        "hero": {
            "id": hero_id,
            "name": hero,
            "level": max(1, clock // 90),
            "alive": alive,
            "respawn_seconds": 0 if alive else 20,
            "health_percent": 80 if alive else 0,
            "mana_percent": 50,
        },
        "items": slots,
    }


def check_gsi_normalize() -> None:
    """Flat playing GSI must not be mistaken for nested team2/player0."""
    flat = {
        "provider": {"steamid": "76561198000000002"},
        "map": {
            "matchid": "flat-check",
            "clock_time": 300,
            "game_time": 390,
            "game_state": "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS",
            "paused": False,
        },
        "player": {
            "steamid": "76561198000000002",
            "name": "Alex",
            "activity": "playing",
            "team_name": "radiant",
            "kills": 3,
            "deaths": 1,
            "assists": 2,
            "last_hits": 40,
            "denies": 4,
            "gold": 800,
            "gpm": 500,
            "xpm": 420,
        },
        "hero": {
            "id": 74,
            "name": "npc_dota_hero_invoker",
            "level": 8,
            "alive": True,
            "health_percent": 80,
            "mana_percent": 50,
        },
        "items": {"slot0": {"name": "item_bottle"}},
    }
    state = normalize_gsi(flat)
    assert state.kills == 3, f"flat kills: {state.kills}"
    assert state.last_hits == 40, f"flat last_hits: {state.last_hits}"
    assert state.gpm == 500, f"flat gpm: {state.gpm}"
    assert state.hero_id == 74, f"flat hero_id: {state.hero_id}"
    assert state.items == ["bottle"], f"flat items: {state.items}"

    nested = {
        "provider": {"steamid": "76561198000000002"},
        "map": {
            "matchid": "nested-check",
            "clock_time": 300,
            "game_time": 390,
            "game_state": "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS",
            "paused": False,
        },
        "player": {
            "team2": {
                "player0": {
                    "steamid": "76561198000000001",
                    "name": "Teammate",
                    "team_name": "radiant",
                    "kills": 9,
                    "deaths": 0,
                    "assists": 0,
                    "last_hits": 99,
                    "gpm": 900,
                },
                "player1": {
                    "steamid": "76561198000000002",
                    "name": "Alex",
                    "team_name": "radiant",
                    "kills": 3,
                    "deaths": 1,
                    "assists": 2,
                    "last_hits": 40,
                    "gpm": 500,
                },
            }
        },
        "hero": {
            "team2": {
                "player0": {
                    "id": 1,
                    "name": "npc_dota_hero_antimage",
                    "level": 12,
                    "alive": True,
                },
                "player1": {
                    "id": 74,
                    "name": "npc_dota_hero_invoker",
                    "level": 8,
                    "alive": True,
                },
            }
        },
        "items": {
            "team2": {
                "player0": {"slot0": {"name": "item_bfury"}},
                "player1": {"slot0": {"name": "item_bottle"}},
            }
        },
    }
    nested_state = normalize_gsi(nested)
    assert nested_state.kills == 3, f"nested kills (must not be teammate 9): {nested_state.kills}"
    assert nested_state.last_hits == 40, f"nested last_hits: {nested_state.last_hits}"
    assert nested_state.gpm == 500, f"nested gpm: {nested_state.gpm}"
    assert nested_state.hero_id == 74, f"nested hero_id: {nested_state.hero_id}"
    assert nested_state.items == ["bottle"], f"nested items: {nested_state.items}"

    class _Boom:
        def predict_proba(self, _x):
            raise AssertionError("NN must not run for unknown heroes")

    unknown = GameState(hero_id=74, hero_name="npc_dota_hero_invoker")
    assert 74 not in DEFAULT_HERO_IDS
    assert ItemModel(_Boom(), ItemVocab(["bottle"])).recommend(unknown) == []  # type: ignore[arg-type]
    print("OK: GSI normalize reads local player (flat + nested steamid).")
    check_inventory_and_boots()


def check_inventory_and_boots() -> None:
    """Полный инвентарь + sell/consume; ES без ботинок → Power Treads."""
    from dota_coach.constants import can_free_inventory_slot, inventory_free_actions
    from dota_coach.models.items import _should_recommend, ensure_early_boots

    # Consumed Aghs: флаг есть, слота нет.
    consumed = {
        "auth": {"token": "dota_coach_local"},
        "map": {
            "matchid": "aghs-check",
            "clock_time": 40 * 60,
            "game_time": 40 * 60 + 90,
            "game_state": "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS",
            "paused": False,
        },
        "player": {
            "name": "Alex",
            "team_name": "radiant",
            "kills": 10,
            "deaths": 3,
            "assists": 12,
            "last_hits": 180,
            "denies": 5,
            "gold": 5000,
            "gpm": 550,
            "xpm": 700,
            "net_worth": 28000,
        },
        "hero": {
            "id": 107,
            "name": "npc_dota_hero_earth_spirit",
            "level": 25,
            "alive": True,
            "aghanims_scepter": True,
            "aghanims_shard": True,
        },
        "items": {
            "slot0": {"name": "item_octarine_core"},
            "slot1": {"name": "item_spirit_vessel"},
            "slot2": {"name": "item_black_king_bar"},
            "slot3": {"name": "item_shivas_guard"},
            "slot4": {"name": "item_magic_wand"},
            "slot5": {"name": "item_blink"},
            "teleport0": {"name": "item_tpscroll"},
        },
    }
    state = normalize_gsi(consumed)
    assert state.scepter_consumed is True, state
    assert state.has_scepter is True
    assert state.inventory_slots == 6
    assert "ultimate_scepter" in state.items
    assert "aghanims_shard" in state.items
    owned = set(state.items)
    assert can_free_inventory_slot(owned, scepter_consumed=True)
    actions = inventory_free_actions(owned, scepter_consumed=True)
    assert any("Wand" in a or "wand" in a.lower() for a in actions), actions
    assert _should_recommend("sheepstick", state, owned), "полный бэг + wand → можно советовать next"

    # Физический Aghs в слоте — можно съесть.
    physical = gsi_payload(
        clock=35 * 60,
        last_hits=160,
        gold=4500,
        deaths=2,
        alive=True,
        items=[
            "octarine_core",
            "ultimate_scepter",
            "spirit_vessel",
            "black_king_bar",
            "shivas_guard",
            "magic_wand",
        ],
        hero_id=107,
        hero="npc_dota_hero_earth_spirit",
    )
    physical["hero"]["aghanims_scepter"] = True
    bag = normalize_gsi(physical)
    assert bag.scepter_consumed is False
    assert bag.inventory_slots == 6
    free = inventory_free_actions(bag.items, scepter_consumed=False)
    assert any("Aghanim" in a for a in free), free
    assert any("Wand" in a or "wand" in a.lower() for a in free), free

    # ES mid без ботинок при почти полном инвентаре — PT не блокируется.
    early = normalize_gsi(
        gsi_payload(
            clock=8 * 60,
            last_hits=40,
            gold=1600,
            deaths=1,
            alive=True,
            items=["bottle", "magic_wand", "urn_of_shadows", "null_talisman", "bracer"],
            hero_id=107,
            hero="npc_dota_hero_earth_spirit",
        )
    )
    assert early.inventory_slots == 5
    assert _should_recommend("power_treads", early, set(early.items))
    boots = ensure_early_boots([("blink", None), ("spirit_vessel", None)], early)
    assert boots[0][0] == "power_treads", boots
    print("OK: inventory sell/consume + ES Power Treads gates.")


def main() -> None:
    check_gsi_normalize()
    print("1) Сбор статистики мида с Dota2ProTracker...")
    summary = collect(use_opendota=False)
    print("   источник:", summary["primary_source"], "строк:", summary["player_rows"])

    print("2) Обучение фарм/смерти/item-NN...")
    stats = train_all(allow_synthetic_nn=True)
    print("   ", stats)
    assert ITEM_MODEL_PATH.exists() and ITEM_VOCAB_PATH.exists()

    engine = CoachEngine(
        farm=FarmBenchmarks(),
        deaths=DeathBenchmarks(),
        lookup=ItemLookup(),
        items=load_item_model(),
    )
    assert engine.items is not None
    set_engine(engine)
    client = TestClient(app)

    overlay = client.get("/")
    assert overlay.status_code == 200
    assert overlay.json()["ui"] == "desktop"

    print("3) GSI-эндпоинт принимает тики...")
    ping = client.post("/gsi", json=gsi_payload(clock=120, last_hits=8, gold=400, deaths=0, alive=True, items=["bottle"]))
    assert ping.status_code == 200
    state = client.get("/api/state").json()
    assert state["connected"] is True

    engine.policy.last_time = 0.0
    engine.policy.last_death_time = 0.0
    engine.policy.last_keys.clear()
    engine.policy.history.clear()
    engine.below_since = None
    engine.last_inventory = set()
    engine.prev = None

    print("4) Фарм ниже p25 — одна-две подсказки, без спама...")
    t0 = 10_000.0
    farm_hits = 0
    for tick in range(25):
        payload = gsi_payload(
            clock=8 * 60 + tick,
            last_hits=10,
            gold=700,
            deaths=0,
            alive=True,
            items=["magic_wand", "urn_of_shadows"],
        )
        hint = engine.update(normalize_gsi(payload), now=t0 + tick)
        if hint and hint.kind == "farm":
            farm_hits += 1
    assert 1 <= farm_hits <= 3, f"ожидали 1-3 фарм-подсказки, получили {farm_hits}"

    print("5) Смерть с золотом без TP...")
    live = normalize_gsi(gsi_payload(clock=10 * 60, last_hits=18, gold=2200, deaths=0, alive=True, items=["magic_wand"], has_tp=False))
    dead = normalize_gsi(gsi_payload(clock=10 * 60 + 3, last_hits=18, gold=2200, deaths=1, alive=False, items=["magic_wand"], has_tp=False))
    engine.update(live, now=t0 + 40)
    death = engine.update(dead, now=t0 + 48)
    assert death is not None and death.kind == "death", "не поймали смерть"

    print("6) Покупка не того предмета...")
    before = normalize_gsi(
        gsi_payload(
            clock=16 * 60,
            last_hits=90,
            gold=600,
            deaths=1,
            alive=True,
            items=["magic_wand", "urn_of_shadows", "spirit_vessel"],
        )
    )
    after = normalize_gsi(
        gsi_payload(
            clock=16 * 60 + 5,
            last_hits=90,
            gold=200,
            deaths=1,
            alive=True,
            items=["magic_wand", "urn_of_shadows", "spirit_vessel", "bfury"],
        )
    )
    engine.update(before, now=t0 + 70)
    item_hint = engine.update(after, now=t0 + 80)
    kinds = [h.kind for h in engine.policy.history]
    print("   подсказки:", [(h.kind, h.title) for h in engine.policy.history])
    print("   NN next:", engine.items.recommend(after) if engine.items else [])
    assert "farm" in kinds and "death" in kinds
    assert item_hint is None or item_hint.kind in {"item", "farm"}
    print("OK: GSI работает, модели с диска, фарм не спамит.")


if __name__ == "__main__":
    if "--check-only" in sys.argv:
        check_gsi_normalize()
    else:
        main()
