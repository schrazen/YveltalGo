import sys
from pathlib import Path
import json

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from modules.quest_catalog import quest_catalog, DEFAULT_QUEST_CATALOG
import ui.server


def test_quest_catalog_basics():
    # 1. Verify default templates count and integrity
    catalog = quest_catalog.get_catalog()
    assert len(catalog) >= 30, f"Expected at least 30 default templates, got {len(catalog)}"

    # Check categories
    categories = {it["category"] for it in catalog}
    assert "mega_chamber" in categories
    assert "battle" in categories
    assert "wild_catch" in categories
    assert "fishing" in categories
    assert "eggs" in categories
    assert "economy" in categories

    stats = quest_catalog.get_stats()
    assert stats["total_quests"] == len(catalog)
    assert stats["auto_complete_count"] > 0
    assert stats["auto_reset_count"] > 0
    assert stats["ignore_count"] > 0
    print("test_quest_catalog_basics: PASSED")


def test_quest_matching_and_resolution():
    # 1. Mega Chamber -> auto_reset
    res = quest_catalog.resolve_quest_action("Defeat 5 Mega Chambers")
    assert res["action"] == "auto_reset"
    assert res["is_impossible"] is True
    assert res["category"] == "mega_chamber"

    # 2. Basic Challenger -> auto_complete, battle_mode: npc 210
    res = quest_catalog.resolve_quest_action("Defeat a Basic Challenger")
    assert res["action"] == "auto_complete"
    assert res["battle_mode"] == "npc 210"
    assert res["category"] == "battle"

    # 3. Master Challenger -> auto_complete, battle_mode: npc 210
    res = quest_catalog.resolve_quest_action("Defeat a Master Challenger")
    assert res["action"] == "auto_complete"
    assert res["battle_mode"] == "npc 210"

    # 4. Defeat 3 NPCs -> auto_complete, battle_mode: npc 1
    res = quest_catalog.resolve_quest_action("Defeat 3 NPCs in battle")
    assert res["action"] == "auto_complete"
    assert res["battle_mode"] == "npc 1"

    # 5. Wild Catch -> auto_complete
    res = quest_catalog.resolve_quest_action("Catch 15 Water-type Pokemon")
    assert res["action"] == "auto_complete"
    assert res["category"] == "wild_catch"

    # 6. Shiny Pokemon -> auto_reset (impossible RNG)
    res = quest_catalog.resolve_quest_action("Catch 2 Shiny Pokemon")
    assert res["action"] == "auto_reset"

    # 7. Release Pokemon -> ignore (manual)
    res = quest_catalog.resolve_quest_action("Release 10 Pokemon")
    assert res["action"] == "ignore"

    print("test_quest_matching_and_resolution: PASSED")


def test_rule_toggle_and_custom_rules():
    # Update rule for Defeat a Basic Challenger to auto_reset temporarily
    ok = quest_catalog.update_rule("defeat_basic_challenger", "auto_reset")
    assert ok is True

    res = quest_catalog.resolve_quest_action("Defeat a Basic Challenger")
    assert res["action"] == "auto_reset", f"Expected rule update to reflect auto_reset, got {res['action']}"

    # Revert back to auto_complete
    quest_catalog.update_rule("defeat_basic_challenger", "auto_complete")
    res = quest_catalog.resolve_quest_action("Defeat a Basic Challenger")
    assert res["action"] == "auto_complete"

    # Add custom rule
    custom = quest_catalog.add_custom_rule(
        title="Custom Raid Boss Test",
        pattern=r"\braid\s*boss\b",
        category="battle",
        action="auto_complete",
        battle_mode="npc 210",
    )
    assert custom is not None
    assert custom["is_custom"] is True

    # Test custom rule matching
    res = quest_catalog.resolve_quest_action("Defeat the special Raid Boss")
    assert res["action"] == "auto_complete"
    assert res["battle_mode"] == "npc 210"
    assert res["category"] == "battle"

    # Delete custom rule
    del_ok = quest_catalog.delete_rule(custom["id"])
    assert del_ok is True
    print("test_rule_toggle_and_custom_rules: PASSED")


def test_log_harvesting():
    scan_res = quest_catalog.scan_historical_logs()
    assert scan_res["ok"] is True
    assert scan_res["harvested_count"] > 0
    assert scan_res["unique_harvested_count"] >= 4
    print(f"Harvested {scan_res['unique_harvested_count']} unique quests: {scan_res['unique_samples']}")
    print("test_log_harvesting: PASSED")


def test_flask_api_endpoints():
    client = ui.server.app.test_client()

    # 1. GET /api/quest-catalog
    resp = client.get("/api/quest-catalog")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert len(data["catalog"]) >= 30
    assert "stats" in data
    assert "categories" in data

    # 2. POST /api/quest-catalog/update
    resp = client.post("/api/quest-catalog/update", json={
        "id": "mega_chamber_defeat",
        "action": "auto_reset",
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True

    # 3. POST /api/quest-catalog/scan-logs
    resp = client.post("/api/quest-catalog/scan-logs", json={})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["unique_harvested_count"] >= 4

    print("test_flask_api_endpoints: PASSED")


if __name__ == "__main__":
    test_quest_catalog_basics()
    test_quest_matching_and_resolution()
    test_rule_toggle_and_custom_rules()
    test_log_harvesting()
    test_flask_api_endpoints()
    print("ALL QUEST CATALOG & API TESTS COMPLETED SUCCESSFULLY!")
