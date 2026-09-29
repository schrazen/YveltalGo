import sys
from pathlib import Path
import asyncio

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from modules.captcha_gate import is_captcha_active, is_in_battle, can_dispatch_command
from cogs.quest import QuestManager


class DummyConfig:
    def __init__(self):
        self.quest_auto_reset_enabled = True
        self.quest_auto_battle_enabled = True
        self.quest_auto_buy_scroll = True
        self.quest_impossible_keywords = ["mega chamber", "megachamber"]
        self.autofight_channel_id = 1488006398255300658
        self.hunting_channel_id = 1213138761370574858
        self.fishing_channel_id = 1213138761370574858


class DummyBot:
    def __init__(self):
        self.config = DummyConfig()
        self.captcha_active = False
        self.hunting_captcha_active = False
        self.fishing_captcha_active = False
        self.autofight_captcha_active = False
        self.autofight_active = False
        self.pause_hunting = False
        self.pause_fishing = False
        self.hunting_status = "Running"
        self.fishing_status = "Running"
        self.autofight_status = "Ready"
        self.hunting_channel = DummyChannel(1213138761370574858)
        self.autofight_channel = DummyChannel(1488006398255300658)
        self.hunting_channel_commands = {}
        self.quest_data = {
            "next_quest": "",
            "active_quests": [],
            "last_completed": {},
            "last_updated_utc": "",
        }
        self._cogs = {}

    def get_cog(self, name):
        return self._cogs.get(name)

    def is_ready(self):
        return True

    async def log(self):
        pass


class DummyChannel:
    def __init__(self, ch_id):
        self.id = ch_id
        self.sent_messages = []

    async def send(self, content):
        self.sent_messages.append(content)
        return content


class DummyAutoFightCog:
    def __init__(self, bot):
        self.bot = bot
        self.started_runs = []

    async def start_battle_run(self, channel, count=1, mode="", strategy="standard"):
        self.started_runs.append({"channel": getattr(channel, "id", None), "count": count, "mode": mode})
        self.bot.autofight_active = True
        self.bot.pause_hunting = True
        self.bot.pause_fishing = True
        return True


def test_quest_classification():
    bot = DummyBot()
    # Suppress loop startup in test
    qm = QuestManager.__new__(QuestManager)
    qm.bot = bot
    qm.config = bot.config
    qm._last_reset_per_slot = {}
    qm._last_battle_quest_dispatch_at = 0.0
    qm._eval_lock = asyncio.Lock()
    qm._last_scroll_buy_at = 0.0
    qm._pending_scroll_buy_for_slot = None

    # 1. Impossible quest checks
    assert qm.is_impossible_quest("Complete the Mega Chamber") is True
    assert qm.is_impossible_quest("Win 3 Mega Chamber battles") is True
    assert qm.is_impossible_quest("Defeat 5 MegaChamber enemies") is True
    assert qm.is_impossible_quest("Encounter 500 Pokemon in wild") is False
    assert qm.is_impossible_quest("Defeat 3 Challengers in battle") is False
    assert qm.is_impossible_quest("Catch 50 Grass-type Pokemon") is False

    # 2. Battle quest classification
    # Challenger
    is_battle, mode = qm.classify_battle_quest("Defeat 1 Challenger in battle")
    assert is_battle is True
    assert mode == "npc 210"

    is_battle, mode = qm.classify_battle_quest("Win 3 Challenger battles")
    assert is_battle is True
    assert mode == "npc 210"

    # General NPC / Trainer
    is_battle, mode = qm.classify_battle_quest("Defeat 5 Pokemon in battle")
    assert is_battle is True
    assert mode == "npc 1"

    is_battle, mode = qm.classify_battle_quest("Win 3 trainer battles")
    assert is_battle is True
    assert mode == "npc 1"

    is_battle, mode = qm.classify_battle_quest("Defeat 3 NPCs")
    assert is_battle is True
    assert mode == "npc 1"

    # Impossible quests should NOT classify as doable battle quests
    is_battle, mode = qm.classify_battle_quest("Complete the Mega Chamber")
    assert is_battle is False

    # Wild / Catch / Fish quests should NOT classify as battle quests
    is_battle, mode = qm.classify_battle_quest("Catch 50 Pokemon in water")
    assert is_battle is False

    is_battle, mode = qm.classify_battle_quest("Encounter 500 Pokemon in wild")
    assert is_battle is False

    print("Quest classification tests passed!")


async def test_quest_evaluation_and_actions():
    bot = DummyBot()
    af_cog = DummyAutoFightCog(bot)
    bot._cogs["AutoFight"] = af_cog

    qm = QuestManager.__new__(QuestManager)
    qm.bot = bot
    qm.config = bot.config
    qm._last_reset_per_slot = {}
    qm._last_battle_quest_dispatch_at = 0.0
    qm._eval_lock = asyncio.Lock()
    qm._last_scroll_buy_at = 0.0
    qm._pending_scroll_buy_for_slot = None

    # Test 1: Impossible quest auto-reset
    bot.quest_data["active_quests"] = [
        {"id": 1, "title": "Encounter 500 Pokemon in wild", "progress_current": 10, "progress_total": 500},
        {"id": 2, "title": "Complete the Mega Chamber", "progress_current": 0, "progress_total": 1},
        {"id": 3, "title": "Catch 20 Water-type Pokemon", "progress_current": 5, "progress_total": 20},
    ]

    res = await qm.evaluate_and_process_quests(source="test")
    assert res.get("ok") is True
    assert res.get("action") == "reset_impossible_quest"
    assert res.get("slot") == 2
    # Verify command was dispatched
    assert any(";quest reset 2" in msg for msg in bot.hunting_channel.sent_messages)

    # Test 2: Doable Challenger Quest Auto-Fight
    bot.quest_data["active_quests"] = [
        {"id": 1, "title": "Encounter 500 Pokemon in wild", "progress_current": 10, "progress_total": 500},
        {"id": 2, "title": "Defeat 2 Challengers in battle", "progress_current": 0, "progress_total": 2},
    ]
    # Mark slot 2 reset cooldown as recent so it doesn't trigger reset
    qm._last_reset_per_slot[2] = 9999999999.0

    res = await qm.evaluate_and_process_quests(source="test")
    assert res.get("ok") is True
    assert res.get("action") == "started_autofight_quest"
    assert res.get("mode") == "npc 210"
    assert res.get("battles") == 2
    # Check that AutoFight cog was triggered in the autobattle channel 1488006398255300658
    assert len(af_cog.started_runs) == 1
    assert af_cog.started_runs[0]["channel"] == 1488006398255300658
    assert af_cog.started_runs[0]["mode"] == "npc 210"
    assert af_cog.started_runs[0]["count"] == 2

    # Check mutual exclusion: bot is now in battle, so hunting & fishing are paused
    assert bot.autofight_active is True
    assert bot.pause_hunting is True
    assert is_in_battle(bot) is True
    assert can_dispatch_command(bot, require_out_of_battle=True) is False

    # Test 3: While in battle, further evaluations don't trigger overlapping battles
    res2 = await qm.evaluate_and_process_quests(source="test")
    assert res2.get("ok") is False
    assert res2.get("reason") == "bot_already_in_battle"

    # Test 4: Captcha active blocks evaluation completely
    bot.autofight_active = False
    bot.captcha_active = True
    res3 = await qm.evaluate_and_process_quests(source="test")
    assert res3.get("ok") is False
    assert res3.get("reason") == "captcha_active"

    print("Quest evaluation and action tests passed!")


if __name__ == "__main__":
    test_quest_classification()
    asyncio.run(test_quest_evaluation_and_actions())
    print("ALL QUEST AUTOMATION TESTS COMPLETED SUCCESSFULLY!")
