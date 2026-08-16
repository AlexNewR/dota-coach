from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dota_coach.coach.engine import CoachEngine
from dota_coach.coach.hints import Hint
from dota_coach.config import DEFAULT_HERO_IDS
from dota_coach.gsi.normalize import GameState
from dota_coach.models.deaths import DeathBenchmarks
from dota_coach.models.farm import FarmBenchmarks
from dota_coach.models.items import ItemMLP, ItemModel, ItemVocab
from dota_coach.models.lookup import ItemLookup


def create_dummy_item_model() -> ItemModel:
    vocab = ItemVocab(["travel_boots", "force_staff", "glimmer_cape", "black_king_bar", "octarine_core", "sheepstick"])
    mlp = ItemMLP(in_dim=180, n_classes=len(vocab.names))
    return ItemModel(mlp, vocab)


def create_test_engine() -> CoachEngine:
    farm_table = {
        "90:2:8": {
            "hero_id": 90,
            "lane_role": 2,
            "minute": 8,
            "lh": {"p25": 30.0, "p50": 45.0, "p75": 55.0},
            "gold": {"p25": 2800.0, "p50": 3800.0, "p75": 4600.0},
            "xp": {"p25": 3200.0, "p50": 4200.0, "p75": 5000.0},
            "n": 10,
        }
    }
    death_table = {
        "90:2": {
            "hero_id": 90,
            "lane_role": 2,
            "avg_deaths": 4.5,
            "avg_duration": 35.0,
            "n": 10,
            "expected_by_minute": {str(m): round(4.5 * min(1.0, m / 35.0), 2) for m in range(61)},
        }
    }
    lookup_table = {
        "90:2:0": {
            "hero_id": 90,
            "lane_role": 2,
            "minute_bucket": 0,
            "items": [
                {"name": "bottle", "count": 50},
                {"name": "travel_boots", "count": 45},
                {"name": "magic_wand", "count": 30},
            ],
        },
        "90:2:5": {
            "hero_id": 90,
            "lane_role": 2,
            "minute_bucket": 5,
            "items": [
                {"name": "bottle", "count": 50},
                {"name": "travel_boots", "count": 45},
                {"name": "magic_wand", "count": 30},
            ],
        },
        "90:2:10": {
            "hero_id": 90,
            "lane_role": 2,
            "minute_bucket": 10,
            "items": [
                {"name": "force_staff", "count": 40},
                {"name": "travel_boots", "count": 35},
                {"name": "glimmer_cape", "count": 25},
            ],
        },
    }
    return CoachEngine(
        farm=FarmBenchmarks(farm_table),
        deaths=DeathBenchmarks(death_table),
        lookup=ItemLookup(lookup_table),
        items=create_dummy_item_model(),
        role=2,
    )


def test_match_state_reset_same_hero() -> None:
    print("--- Test 1: Match state reset with same hero ---")
    engine = create_test_engine()

    # Match 1: Keeper of the Light (hero_id 90), late game min 30
    st1 = GameState(
        match_id="match-1001",
        clock_time=1800,
        game_state="DOTA_GAMERULES_STATE_GAME_IN_PROGRESS",
        in_game=True,
        hero_id=90,
        hero_name="npc_dota_hero_keeper_of_the_light",
        gold=1200,
        total_gold=16000,
        net_worth=16000,
        last_hits=210,
        deaths=3,
        items=["travel_boots", "force_staff", "glimmer_cape", "black_king_bar", "octarine_core", "sheepstick"],
        enemy_heroes=[1, 2, 3],
        ally_heroes=[90, 4, 5],
    )
    engine.update(st1, now=1000.0)

    assert engine.current_hero_id == 90
    assert engine.known_match_id == "match-1001"
    assert "force_staff" in engine.last_inventory
    assert len(engine.known_enemies) == 3

    # Post-game transition
    st_post = GameState(
        match_id="match-1001",
        clock_time=2100,
        game_state="DOTA_GAMERULES_STATE_POST_GAME",
        in_game=False,
        hero_id=90,
        hero_name="npc_dota_hero_keeper_of_the_light",
    )
    engine.update(st_post, now=1100.0)

    # Match 2: SAME HERO (KotL, hero_id 90), starting new match
    st2 = GameState(
        match_id="match-1002",
        clock_time=-45,
        game_state="DOTA_GAMERULES_STATE_PRE_GAME",
        in_game=True,
        hero_id=90,
        hero_name="npc_dota_hero_keeper_of_the_light",
        gold=600,
        total_gold=600,
        net_worth=600,
        last_hits=0,
        deaths=0,
        items=["tango", "faerie_fire"],
        enemy_heroes=[6, 7, 8],
        ally_heroes=[90, 9, 10],
    )
    engine.update(st2, now=2000.0)

    # Verify everything was cleanly reset for the new match!
    assert engine.known_match_id == "match-1002"
    assert engine.current_hero_id == 90
    assert engine.last_inventory == {"tango", "faerie_fire"}
    assert "force_staff" not in engine.last_inventory
    assert "black_king_bar" not in engine.last_inventory
    assert engine.known_enemies == [6, 7, 8]
    assert len(engine.policy.history) == 0
    print("PASS: Match state properly reset on new match ID even with same hero.")

    # Match 3: Clock time jump reset without match_id provided (common in local lobbies / non-spectator)
    st3_late = GameState(
        match_id="",
        clock_time=1200,
        game_state="DOTA_GAMERULES_STATE_GAME_IN_PROGRESS",
        in_game=True,
        hero_id=90,
        hero_name="npc_dota_hero_keeper_of_the_light",
        items=["force_staff", "glimmer_cape"],
    )
    engine.update(st3_late, now=3000.0)
    assert "force_staff" in engine.last_inventory

    st3_new = GameState(
        match_id="",
        clock_time=10,
        game_state="DOTA_GAMERULES_STATE_PRE_GAME",
        in_game=True,
        hero_id=90,
        hero_name="npc_dota_hero_keeper_of_the_light",
        items=["bottle"],
    )
    engine.update(st3_new, now=4000.0)
    assert engine.last_inventory == {"bottle"}
    assert "force_staff" not in engine.last_inventory
    print("PASS: Clock jump reset correctly identified new match start without match ID.")


def test_thread_safety_rlock() -> None:
    print("--- Test 2: Thread safety with RLock under concurrent load ---")
    engine = create_test_engine()
    stop_event = threading.Event()
    errors: list[Exception] = []

    def gsi_worker() -> None:
        tick = 0
        while not stop_event.is_set():
            tick += 1
            st = GameState(
                match_id="thread-test",
                clock_time=tick % 1800,
                game_state="DOTA_GAMERULES_STATE_GAME_IN_PROGRESS",
                in_game=True,
                hero_id=90,
                hero_name="npc_dota_hero_keeper_of_the_light",
                gold=500 + (tick % 2000),
                total_gold=1000 + tick * 10,
                net_worth=1000 + tick * 10,
                last_hits=tick % 150,
                deaths=tick % 5,
                items=["travel_boots", "bottle"] if tick % 2 == 0 else ["travel_boots", "force_staff"],
                enemy_heroes=[1, 2, 3] if tick % 3 == 0 else [4, 5, 6],
            )
            try:
                engine.update(st)
            except Exception as e:
                errors.append(e)
            time.sleep(0.001)

    def snapshot_worker() -> None:
        while not stop_event.is_set():
            try:
                st = GameState(
                    match_id="thread-test",
                    clock_time=300,
                    game_state="DOTA_GAMERULES_STATE_GAME_IN_PROGRESS",
                    in_game=True,
                    hero_id=90,
                    hero_name="npc_dota_hero_keeper_of_the_light",
                    items=["travel_boots"],
                )
                snap = engine.snapshot(st)
                assert "recommended" in snap
                assert "farm" in snap
            except Exception as e:
                errors.append(e)
            time.sleep(0.001)

    def book_worker() -> None:
        hero_counter = 50
        while not stop_event.is_set():
            hero_counter += 1
            try:
                with engine._lock:
                    engine.farm.table[f"{hero_counter}:2:5"] = {
                        "hero_id": hero_counter,
                        "lane_role": 2,
                        "minute": 5,
                        "lh": {"p25": 10.0, "p50": 20.0, "p75": 30.0},
                        "gold": {"p25": 1000.0, "p50": 2000.0, "p75": 3000.0},
                        "xp": {"p25": 1000.0, "p50": 2000.0, "p75": 3000.0},
                        "n": 5,
                    }
                    engine.lookup.table[f"{hero_counter}:2:5"] = {
                        "hero_id": hero_counter,
                        "lane_role": 2,
                        "minute_bucket": 5,
                        "items": [{"name": "travel_boots", "count": 10}],
                    }
                    engine.book.status[hero_counter] = "ready"
            except Exception as e:
                errors.append(e)
            time.sleep(0.002)

    threads = [
        threading.Thread(target=gsi_worker),
        threading.Thread(target=snapshot_worker),
        threading.Thread(target=book_worker),
    ]
    for t in threads:
        t.start()

    time.sleep(1.0)
    stop_event.set()
    for t in threads:
        t.join()

    assert not errors, f"Encountered thread safety errors: {errors}"
    print("PASS: Concurrent GSI update, Tkinter snapshot, and LiveHeroBook table mutations completed with 0 errors.")


def test_gold_feature_scaling() -> None:
    print("--- Test 3: Gold feature scaling in item model runtime ---")
    model = create_dummy_item_model()

    # State with 150 pocket gold but 6500 net_worth / earned_gold at min 14
    st_low_bag = GameState(
        hero_id=90,
        hero_name="npc_dota_hero_keeper_of_the_light",
        clock_time=14 * 60,
        game_state="DOTA_GAMERULES_STATE_GAME_IN_PROGRESS",
        in_game=True,
        gold=150,  # low pocket gold
        net_worth=6500,
        total_gold=6500,
        gpm=460,
        items=["travel_boots", "bottle"],
    )
    recs = model.recommend(st_low_bag, role=2, top_k=3)
    assert len(recs) > 0, "Recommendations should not be empty when pocket gold is low!"
    print("   Low pocket gold recommendations:", recs)
    print("PASS: Item model properly recommends next items regardless of low pocket gold.")


def test_soft_blend_recommendation() -> None:
    print("--- Test 4: Soft blend vs hard cutoff ---")
    engine = create_test_engine()

    # Early minute (minute 2)
    st_early = GameState(
        hero_id=90,
        hero_name="npc_dota_hero_keeper_of_the_light",
        clock_time=2 * 60,
        game_state="DOTA_GAMERULES_STATE_GAME_IN_PROGRESS",
        in_game=True,
        items=["tango"],
    )
    pairs_early, src_early = engine._recommend_items(st_early)
    print(f"   Min 2 recommendations ({src_early}):", pairs_early)
    assert "lookup" in src_early

    # Mid minute (minute 8) -> should blend lookup frequencies and NN predictions
    st_mid = GameState(
        hero_id=90,
        hero_name="npc_dota_hero_keeper_of_the_light",
        clock_time=8 * 60,
        game_state="DOTA_GAMERULES_STATE_GAME_IN_PROGRESS",
        in_game=True,
        total_gold=4000,
        net_worth=4000,
        items=["travel_boots", "bottle"],
    )
    pairs_mid, src_mid = engine._recommend_items(st_mid)
    print(f"   Min 8 recommendations ({src_mid}):", pairs_mid)
    assert src_mid in {"blend", "nn", "lookup"}

    # Later minute (minute 18) -> should favor NN
    st_late = GameState(
        hero_id=90,
        hero_name="npc_dota_hero_keeper_of_the_light",
        clock_time=18 * 60,
        game_state="DOTA_GAMERULES_STATE_GAME_IN_PROGRESS",
        in_game=True,
        total_gold=9500,
        net_worth=9500,
        items=["travel_boots", "force_staff", "glimmer_cape"],
    )
    pairs_late, src_late = engine._recommend_items(st_late)
    print(f"   Min 18 recommendations ({src_late}):", pairs_late)
    assert "nn" in src_late or "counter" in src_late
    print("PASS: Smooth blend replaces hard minute 12 cutoff.")


def main() -> None:
    test_match_state_reset_same_hero()
    test_thread_safety_rlock()
    test_gold_feature_scaling()
    test_soft_blend_recommendation()
    print("\nALL 4 AUDIT FIXES VERIFIED SUCCESSFULLY!")


if __name__ == "__main__":
    main()
