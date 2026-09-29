import sys
from pathlib import Path
import time

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from modules.challenge_manager import parse_challenges_text, find_eligible_npc_for_quest
from cogs.quest import QuestManager


def test_parse_challenges_text_basic():
    sample_text = """
    Available Battling Challenges in PokeMeow
    ## Basic Challenges
    1. <:trainer_steven:1372554426228674612> `trainer_steven` • `ID: 210`
    ## Master Challenges
    1. <:trainer_cynthia:1372554426228674612> **trainer_cynthia** • `ID: 215`
    """
    data = parse_challenges_text(sample_text)
    assert len(data["basic"]) == 1
    assert data["basic"][0]["id"] == 210
    assert data["basic"][0]["name"] == "trainer_steven"
    assert len(data["master"]) == 1
    assert data["master"][0]["id"] == 215
    print("test_parse_challenges_text_basic: PASSED")


def test_parse_challenges_invitations():
    # 1. With invitations
    sample_invites = """
    Battle Invitations
    1. <:trainer_cynthia:1372554426228674612> trainer_cynthia • ID: 215
    2. <:trainer_lance:1372554426228674612> trainer_lance • ID: 220
    """
    data = parse_challenges_text(sample_invites)
    assert len(data["invitations"]) == 2
    assert data["invitations"][0]["id"] == 215
    assert data["invitations"][0]["name"] == "trainer_cynthia"
    assert data["has_no_invites"] is False

    # 2. No invitations
    sample_empty = "You do not have any battle invitations at this time."
    data_empty = parse_challenges_text(sample_empty)
    assert len(data_empty["invitations"]) == 0
    assert data_empty["has_no_invites"] is True
    print("test_parse_challenges_invitations: PASSED")


def test_find_eligible_npc():
    # Case 1: Master challenger quest with no invites held
    doable, mode, reason = find_eligible_npc_for_quest("Defeat a Master Challenger", {"invitations": [], "master": []})
    assert doable is False
    assert reason == "no_master_invite"

    # Case 2: Master challenger quest with Cynthia invite held
    challenge_data = {
        "invitations": [{"name": "trainer_cynthia", "id": 215, "tier": "master"}],
        "master": [],
        "basic": [{"name": "trainer_steven", "id": 210, "tier": "basic"}],
    }
    doable, mode, reason = find_eligible_npc_for_quest("Defeat a Master Challenger!", challenge_data)
    assert doable is True
    assert mode == "npc 215"
    assert "master_invite" in reason

    # Case 3: Basic challenger quest
    doable, mode, reason = find_eligible_npc_for_quest("Defeat a Basic Challenger", challenge_data)
    assert doable is True
    assert mode == "npc 210"
    assert reason == "basic_challenger"

    # Case 4: General challenger quest
    doable, mode, reason = find_eligible_npc_for_quest("Defeat 2 Challengers in battle", challenge_data)
    assert doable is True
    assert mode == "npc 210"
    assert reason == "general_challenger"

    # Case 5: Standard NPC / trainer battle
    doable, mode, reason = find_eligible_npc_for_quest("Defeat 5 Pokemon in battle", challenge_data)
    assert doable is True
    assert mode == "npc 1"

    print("test_find_eligible_npc: PASSED")


def test_quest_manager_integration():
    class DummyConfig:
        quest_auto_reset_enabled = True
        quest_auto_battle_enabled = True
        quest_impossible_keywords = ["mega chamber"]
        autofight_channel_id = 1488006398255300658

    class DummyBot:
        def __init__(self):
            self.config = DummyConfig()
            self.quest_data = {"active_quests": []}
            self.challenge_data = {
                "basic": [{"name": "trainer_steven", "id": 210, "tier": "basic"}],
                "invitations": [],
                "master": [],
                "has_no_invites": True,
            }

    bot = DummyBot()
    # Mocking QuestManager without discord task loop
    qm = QuestManager.__new__(QuestManager)
    qm.bot = bot
    qm.config = bot.config
    qm._last_challenge_sync_at = 0.0

    # 1. Master challenger with no invites is detected as impossible (auto-reset)
    assert qm.is_impossible_quest("Defeat a Master Challenger") is True
    is_battle, mode = qm.classify_battle_quest("Defeat a Master Challenger")
    assert is_battle is False

    # 2. Mega Chamber is always impossible
    assert qm.is_impossible_quest("Complete the Mega Chamber") is True

    # 3. Basic Challenger is always doable
    assert qm.is_impossible_quest("Defeat a Basic Challenger") is False
    is_battle, mode = qm.classify_battle_quest("Defeat a Basic Challenger")
    assert is_battle is True
    assert mode == "npc 210"

    # 4. Now grant a Master invitation
    bot.challenge_data["invitations"] = [{"name": "trainer_cynthia", "id": 215, "tier": "master"}]
    assert qm.is_impossible_quest("Defeat a Master Challenger") is False
    is_battle, mode = qm.classify_battle_quest("Defeat a Master Challenger")
    assert is_battle is True
    assert mode == "npc 215"

    print("test_quest_manager_integration: PASSED")


if __name__ == "__main__":
    test_parse_challenges_text_basic()
    test_parse_challenges_invitations()
    test_find_eligible_npc()
    test_quest_manager_integration()
    print("ALL CHALLENGE MANAGER TESTS COMPLETED SUCCESSFULLY!")
