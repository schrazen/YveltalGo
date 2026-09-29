import sys
from pathlib import Path
import asyncio

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from modules.captcha_gate import is_captcha_active, can_dispatch_command, assert_no_captcha
from modules.pokemeow_reader import parse_quest_board_payload, parse_quest_complete_payload, parse_pokemeow_response
from cogs.hunting import safe_request_quest_info


class DummyBot:
    def __init__(self):
        self.captcha_active = False
        self.hunting_captcha_active = False
        self.fishing_captcha_active = False
        self.autofight_captcha_active = False
        self.pause_hunting = False
        self.pause_fishing = False
        self.hunting_status = "Running"
        self.fishing_status = "Running"
        self.autofight_status = "Ready"
        self._cogs = {}

    def get_cog(self, name):
        return self._cogs.get(name)

    def is_ready(self):
        return True


class DummyChannel:
    def __init__(self, ch_id=123):
        self.id = ch_id
        self.sent_messages = []

    async def send(self, content):
        self.sent_messages.append(content)
        return content


def test_captcha_gate():
    bot = DummyBot()
    # 1. Clean state
    assert is_captcha_active(bot) is False
    assert can_dispatch_command(bot) is True

    # 2. Global captcha active
    bot.captcha_active = True
    assert is_captcha_active(bot) is True
    assert can_dispatch_command(bot) is False
    bot.captcha_active = False

    # 3. Channel specific flag
    bot.hunting_captcha_active = True
    assert is_captcha_active(bot) is True
    bot.hunting_captcha_active = False

    bot.fishing_captcha_active = True
    assert is_captcha_active(bot) is True
    bot.fishing_captcha_active = False

    # 4. Status string indicator
    bot.hunting_status = "Paused (captcha)"
    assert is_captcha_active(bot) is True
    bot.hunting_status = "Running"

    # 5. Captcha Cog attempt state
    class DummyCaptchaCog:
        def __init__(self):
            self.channel_attempt_state = {
                123: {"terminal_failure": False, "captcha_message_id": 9999, "detected_at": 12345.0}
            }

    bot._cogs["Captcha"] = DummyCaptchaCog()
    assert is_captcha_active(bot, channel_id=123) is True
    assert is_captcha_active(bot) is True

    # Terminal failure should NOT block as active captcha (it means already failed, manual intervention needed)
    bot._cogs["Captcha"].channel_attempt_state[123]["terminal_failure"] = True
    assert is_captcha_active(bot, channel_id=123) is False

    # 6. assert_no_captcha
    bot.captcha_active = True
    try:
        assert_no_captcha(bot, context="test")
        assert False, "Should have raised RuntimeError"
    except RuntimeError:
        pass

    print("Captcha gate tests passed!")


def test_quest_board_and_complete():
    # 1. Quest board parsing
    board_text = (
        "🆕 Your next quest is 🗒️ ⚔️ Defeat a Master Challenger! Complete your quests for rewards! "
        "Quest #1: ⚔️ Defeat a Basic Challenger > 💰 Rewards: 1x 🎁, 2x 📦, 3x 🎟️ > 🗒️ Progress: 0 out of 1 "
        "Quest #2: ⚔️ Defeat 5 Mega Chambers > 💰 Rewards: 1x 📦, 2x 🪙 > 🗒️ Progress: 2 / 5"
    )
    parsed = parse_quest_board_payload(board_text)
    assert "Defeat a Master Challenger" in parsed["next_quest"], f"Got: {parsed['next_quest']}"
    assert len(parsed["active_quests"]) == 2, f"Got: {parsed['active_quests']}"
    q1 = parsed["active_quests"][0]
    assert q1["id"] == 1
    assert "Defeat a Basic Challenger" in q1["title"]
    assert q1["progress_current"] == 0
    assert q1["progress_total"] == 1

    q2 = parsed["active_quests"][1]
    assert q2["id"] == 2
    assert "Defeat 5 Mega Chambers" in q2["title"]
    assert q2["progress_current"] == 2
    assert q2["progress_total"] == 5

    # 2. Quest complete parsing
    comp_text = (
        "🗒️ schrazen completed the quest Encounter 500 Pokemon in the wild and received: "
        "8x 🎁, 2x 📦, 2x 🎟️, 10,000! mewy gained 2,500 EXP!"
    )
    parsed_comp = parse_quest_complete_payload(comp_text)
    assert parsed_comp["quest_name"] == "Encounter 500 Pokemon in the wild"
    assert "8x" in parsed_comp["rewards"]
    assert "2,500 EXP" in parsed_comp["exp"]

    print("Quest board & complete parsing tests passed!")


def test_safe_quest_dispatch():
    bot = DummyBot()
    channel = DummyChannel(ch_id=456)
    bot.captcha_active = True

    # When captcha is active, safe_request_quest_info must return False immediately and send 0 messages
    res = asyncio.run(safe_request_quest_info(bot, channel, None, source="test"))
    assert res is False
    assert len(channel.sent_messages) == 0

    bot.captcha_active = False
    # Clear debounce
    bot._last_quest_info_request_at = 0.0

    # With dummy slash command
    called = []
    async def dummy_quest_info():
        called.append(True)

    cmd_map = {"quest info": dummy_quest_info}
    res = asyncio.run(safe_request_quest_info(bot, channel, cmd_map, source="test"))
    assert res is True
    assert len(called) == 1
    assert len(channel.sent_messages) == 0

    # Test debounce: immediate second call must return False
    res2 = asyncio.run(safe_request_quest_info(bot, channel, cmd_map, source="test"))
    assert res2 is False

    print("Safe quest dispatch tests passed!")


if __name__ == "__main__":
    test_captcha_gate()
    test_quest_board_and_complete()
    test_safe_quest_dispatch()
    print("ALL CAPTCHA GATE AND QUEST TESTS COMPLETED SUCCESSFULLY!")
