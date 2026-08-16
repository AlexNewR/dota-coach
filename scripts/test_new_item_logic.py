from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dota_coach.coach.engine import CoachEngine
from dota_coach.constants import (
    EARLY_ONLY_ITEMS,
    HERO_SKIP_ITEMS,
    UPGRADE_COMPONENTS,
    UPGRADE_PREREQUISITES,
    is_base_component_superseded,
    item_allowed_for_hero,
    item_timing_ok,
    resolve_upgrade_prerequisite,
)
from dota_coach.gsi.normalize import GameState
from dota_coach.models.deaths import DeathBenchmarks
from dota_coach.models.farm import FarmBenchmarks
from dota_coach.models.items import ItemMLP, ItemModel, ItemVocab, _should_recommend, ensure_early_boots
from dota_coach.models.lookup import ItemLookup


def test_kotl_hero_skips() -> None:
    print("--- Test 1: KotL Hero Skips (Right-click carry items & support boots) ---")
    kotl_id = 90
    assert not item_allowed_for_hero(kotl_id, "silver_edge"), "KotL must skip silver_edge"
    assert not item_allowed_for_hero(kotl_id, "invis_sword"), "KotL must skip invis_sword / shadow_blade"
    assert not item_allowed_for_hero(kotl_id, "desolator"), "KotL must skip desolator"
    assert not item_allowed_for_hero(kotl_id, "arcane_boots"), "KotL must skip arcane_boots"
    assert not item_allowed_for_hero(kotl_id, "tranquil_boots"), "KotL must skip tranquil_boots"
    assert not item_allowed_for_hero(kotl_id, "daedalus"), "KotL must skip greater_crit"
    assert not item_allowed_for_hero(kotl_id, "butterfly"), "KotL must skip butterfly"
    assert not item_allowed_for_hero(kotl_id, "satanic"), "KotL must skip satanic"

    # Valid caster items for KotL
    assert item_allowed_for_hero(kotl_id, "dagon"), "KotL allows dagon"
    assert item_allowed_for_hero(kotl_id, "spirit_vessel"), "KotL allows spirit_vessel"
    assert item_allowed_for_hero(kotl_id, "travel_boots"), "KotL allows travel_boots"
    assert item_allowed_for_hero(kotl_id, "octarine_core"), "KotL allows octarine_core"
    assert item_allowed_for_hero(kotl_id, "black_king_bar"), "KotL allows black_king_bar"
    print("PASS: KotL hero skips properly configured.")


def test_upgrade_hierarchy() -> None:
    print("--- Test 2: Item Upgrade Hierarchy (Silver Edge / Shadow Blade, Vessel / Urn) ---")
    
    # 1. Base component superseded check
    owned_with_vessel = {"spirit_vessel", "travel_boots"}
    assert is_base_component_superseded("urn_of_shadows", owned_with_vessel), "Urn is superseded by Spirit Vessel"
    assert not is_base_component_superseded("spirit_vessel", owned_with_vessel)

    owned_with_silver_edge = {"silver_edge", "power_treads"}
    assert is_base_component_superseded("invis_sword", owned_with_silver_edge), "Invis sword is superseded by Silver Edge"
    assert not is_base_component_superseded("silver_edge", owned_with_silver_edge)

    owned_with_mjollnir = {"mjollnir", "power_treads"}
    assert is_base_component_superseded("maelstrom", owned_with_mjollnir), "Maelstrom is superseded by Mjollnir"

    # 2. Upgrade prerequisite resolution
    owned_empty = set()
    assert resolve_upgrade_prerequisite("silver_edge", owned_empty) == "invis_sword", "Silver Edge maps to Invis Sword first"
    assert resolve_upgrade_prerequisite("wind_waker", owned_empty) == "cyclone", "Wind Waker maps to Cyclone first"
    assert resolve_upgrade_prerequisite("mjollnir", owned_empty) == "maelstrom", "Mjollnir maps to Maelstrom first"
    assert resolve_upgrade_prerequisite("spirit_vessel", owned_empty) == "urn_of_shadows", "Spirit Vessel maps to Urn first"

    owned_with_urn = {"urn_of_shadows"}
    assert resolve_upgrade_prerequisite("spirit_vessel", owned_with_urn) == "spirit_vessel", "With Urn, Spirit Vessel is kept"

    # 3. _should_recommend checks
    st = GameState(hero_id=80, clock_time=15 * 60, items=["spirit_vessel", "power_treads"])
    assert not _should_recommend("urn_of_shadows", st, {"spirit_vessel", "power_treads"}), "Should not recommend Urn when Vessel owned"
    print("PASS: Upgrade hierarchy and component suppression verified.")


def test_early_starting_items_timing() -> None:
    print("--- Test 3: Early Items Timing (No Wand / Null after minute 8-10 or after major items) ---")
    # Early game: minute 2, 0 major items -> Wand is ok
    st_early = GameState(hero_id=90, clock_time=2 * 60, items=["bottle"])
    assert item_timing_ok("magic_wand", 2, {"bottle"}), "Wand ok at minute 2"
    assert item_timing_ok("null_talisman", 2, {"bottle"}), "Null ok at minute 2"

    # Mid game: minute 15, or has major items -> Wand is NOT ok
    assert not item_timing_ok("magic_wand", 15, {"travel_boots", "spirit_vessel"}), "Wand NOT ok at minute 15 with majors"
    assert not item_timing_ok("null_talisman", 12, {"travel_boots"}), "Null NOT ok at minute 12 with travels"
    assert not item_timing_ok("magic_stick", 10, {"power_treads"}), "Stick NOT ok at minute 10"

    # Boots of travel at min 0 with starting items: do not push travels to #1 over bottle/null
    st_start = GameState(hero_id=90, clock_time=0, items=[])
    pairs = [("bottle", 0.45), ("null_talisman", 0.35)]
    ensured = ensure_early_boots(pairs, st_start, top_k=3)
    assert ensured[0][0] == "bottle", f"Expected bottle #1, got {ensured[0][0]}"
    assert ensured[1][0] == "travel_boots", f"Expected travels #2, got {ensured[1][0]}"
    print("PASS: Early item timings and starting boots ordering verified.")


def test_sold_and_consumed_cycle() -> None:
    print("--- Test 4: Sold & Consumed Items Loop (No 'buy stick / buy aghs' after sell/consume) ---")
    lookup_table = {
        "90:2:20": {
            "hero_id": 90,
            "lane_role": 2,
            "minute_bucket": 20,
            "items": [
                {"name": "magic_wand", "count": 50},
                {"name": "ultimate_scepter", "count": 45},
                {"name": "octarine_core", "count": 40},
                {"name": "dagon", "count": 35},
            ],
        }
    }
    engine = CoachEngine(
        farm=FarmBenchmarks({}),
        deaths=DeathBenchmarks({}),
        lookup=ItemLookup(lookup_table),
        items=None,
        role=2,
    )

    # Player had Magic Wand & Aghanim's Scepter in inventory
    st1 = GameState(
        match_id="match-loop",
        clock_time=1200,
        game_state="DOTA_GAMERULES_STATE_GAME_IN_PROGRESS",
        in_game=True,
        hero_id=90,
        hero_name="npc_dota_hero_keeper_of_the_light",
        items=["travel_boots", "dagon", "spirit_vessel", "magic_wand", "ultimate_scepter", "blink"],
        inventory_slots=6,
        scepter_consumed=False,
        has_scepter=True,
    )
    engine.update(st1, now=100.0)

    # Coach advises: Free slot: consume Aghanim's Scepter; sell Magic Wand.
    tip = engine._inventory_tip(st1)
    assert "съешь Aghanim's Scepter" in tip, f"Expected consume tip, got {tip}"
    assert "продай Magic Wand" in tip, f"Expected sell wand tip, got {tip}"

    # Player sells Magic Wand and consumes Aghanim's Scepter!
    st2 = GameState(
        match_id="match-loop",
        clock_time=1230,
        game_state="DOTA_GAMERULES_STATE_GAME_IN_PROGRESS",
        in_game=True,
        hero_id=90,
        hero_name="npc_dota_hero_keeper_of_the_light",
        items=["travel_boots", "dagon", "spirit_vessel", "blink"],
        inventory_slots=4,
        scepter_consumed=True,
        has_scepter=True,
    )
    engine.update(st2, now=130.0)

    # Next recommendations MUST NOT include magic_wand or ultimate_scepter!
    pairs, _ = engine._recommend_items(st2)
    rec_names = [name for name, _ in pairs]
    print(f"   Post-sale & consume recommendations: {rec_names}")

    assert "magic_wand" not in rec_names, "magic_wand must NOT be recommended after being sold!"
    assert "ultimate_scepter" not in rec_names, "ultimate_scepter must NOT be recommended after being consumed!"
    assert "octarine_core" in rec_names or "dagon" in rec_names, "Valid late items must be recommended"
    print("PASS: Sold & consumed loop completely prevented.")


if __name__ == "__main__":
    test_kotl_hero_skips()
    test_upgrade_hierarchy()
    test_early_starting_items_timing()
    test_sold_and_consumed_cycle()
    print("\nALL 4 NEW LOGIC TESTS PASSED SUCCESSFULLY!")
