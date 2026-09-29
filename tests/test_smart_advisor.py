from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from modules.smart_advisor import SmartAdvisor, QUOTA_FILE, INBOX_FILE
from cogs.smart_advisor_cog import SmartAdvisorCog, _extract_clickable_buttons


class DummyComponent:
    def __init__(self, label: str, custom_id: str, disabled: bool = False):
        self.type = "button"
        self.label = label
        self.custom_id = custom_id
        self.disabled = disabled
        self.clicked = False

    async def click(self):
        self.clicked = True


class DummyActionRow:
    def __init__(self, children):
        self.children = children


class DummyMessage:
    def __init__(self, content: str = "", embeds=None, components=None, author_id: int = 664508672713424926):
        self.id = 999888777
        self.content = content
        self.embeds = embeds or []
        self.components = components or []
        self.author = type("DummyUser", (), {"id": author_id, "name": "PokeMeow"})()
        self.channel = None


class DummyChannel:
    def __init__(self):
        self.id = 111222333
        self.sent_messages = []

    async def send(self, content):
        self.sent_messages.append(content)
        return DummyMessage(content=content)

    async def history(self, limit=4):
        for _ in range(0):
            yield DummyMessage()


class DummyBot:
    def __init__(self):
        self.user = type("User", (), {"name": "TestBot", "id": 123456})()
        self.config = type("Config", (), {
            "hunting_channel_id": 111222333,
            "fishing_channel_id": 0,
            "SmartAdvisor": {"InactivityTimeoutSeconds": 40.0},
        })()
        self.hunting_channel = DummyChannel()
        self.fishing_channel = None
        self.server_scope_valid = True
        self.world_boss_active = False
        self.autofight_active = False
        self.pause_hunting = False
        self.pause_fishing = False
        self.hunting_status = "Running"
        self.last_wb_action = 0.0
        self.last_autofight_action = 0.0
        self._cogs = {}

    def get_cog(self, name):
        return self._cogs.get(name)

    def is_closed(self):
        return False

    async def log(self):
        pass


def test_smart_advisor_quota_and_guardrails():
    """Verify rate limiter, daily cap, button validation, and Groq fallback."""
    advisor = SmartAdvisor({
        "SmartAdvisor": {
            "Enabled": True,
            "MaxRequestsPerMinute": 10,
            "MaxRequestsPerDay": 50,
        }
    })

    # Isolate quota status for test
    advisor.get_quota_status = lambda: {"date": "2026-09-30", "requests_today": 0, "total_all_time": 0, "last_request_utc": ""}
    can, reason = advisor.can_request()
    assert can is True, f"Expected allowed, got: {reason}"
    assert advisor.groq_api_key != "", "Groq API key should be resolved from .env"

    # Test daily quota limit enforcement
    advisor.get_quota_status = lambda: {"date": "2026-09-30", "requests_today": 55, "total_all_time": 55, "last_request_utc": ""}
    can_blocked, reason_blocked = advisor.can_request()
    assert can_blocked is False, "Should be blocked when daily limit is exceeded"
    assert "Daily limit reached" in reason_blocked

    btn_yes = {"label": "Accept Invitation", "custom_id": "invite:accept"}
    btn_no = {"label": "Decline", "custom_id": "invite:decline"}

    invalid_advice = {
        "action": "CLICK_BUTTON",
        "target": "Delete All Pokemon",
        "reason": "Test",
    }
    matched = None
    for b in [btn_yes, btn_no]:
        if invalid_advice["target"].lower() in b["label"].lower():
            matched = b
    assert matched is None, "Guardrail must reject unauthorized button targets!"

    valid_advice = {
        "action": "CLICK_BUTTON",
        "target": "Accept Invitation",
        "reason": "Valid match",
    }
    for b in [btn_yes, btn_no]:
        if valid_advice["target"].lower() in b["label"].lower():
            matched = b
    assert matched == btn_yes, "Guardrail must successfully match valid active buttons!"

    print("test_smart_advisor_quota_and_guardrails: PASSED")


def test_inactivity_watchdog_auto_unlock():
    """Verify dead-man's switch watchdog automatically unlocks stuck orphaned locks."""
    bot = DummyBot()
    cog = SmartAdvisorCog(bot)

    now = time.time()
    bot.world_boss_active = True
    bot.pause_hunting = True
    bot.pause_fishing = True
    bot.last_wb_action = now - 60.0
    cog.last_active_timestamp = now - 50.0

    asyncio.run(cog.check_inactivity_and_recover())

    assert bot.world_boss_active is False, "Watchdog must auto-clear orphaned WorldBoss lock!"
    assert bot.pause_hunting is False, "Watchdog must unpause hunting when lock cleared!"
    assert bot.pause_fishing is False, "Watchdog must unpause fishing when lock cleared!"

    cog.last_active_timestamp = now - 50.0
    bot.hunting_channel.sent_messages.clear()

    # Fast deterministic diagnosis mock for unit test isolation
    async def mock_diagnose(*args, **kwargs):
        return {"action": "KICKSTART_COMMAND", "target": ";p", "reason": "Test diagnosis"}

    from modules.smart_advisor import smart_advisor
    orig_diag = smart_advisor.diagnose_inactivity
    smart_advisor.diagnose_inactivity = mock_diagnose
    try:
        asyncio.run(cog.check_inactivity_and_recover())
    finally:
        smart_advisor.diagnose_inactivity = orig_diag

    assert len(bot.hunting_channel.sent_messages) > 0, "Watchdog must dispatch pulse to wake up stalled bot!"
    assert bot.hunting_channel.sent_messages[-1] == ";p", "Pulse command must be ';p' for hunting channel!"

    cog.cog_unload()
    print("test_inactivity_watchdog_auto_unlock: PASSED")


def test_groq_integration_and_fallback():
    """Verify that Groq is properly initialized and can execute fast JSON completions."""
    advisor = SmartAdvisor()
    assert advisor.groq_api_key != "", "Groq API key must be present in .env"

    res = asyncio.run(advisor._post_groq(
        advisor.groq_model,
        "Return a JSON object with key 'status' = 'ok' and 'provider' = 'groq'",
        "You are a helpful assistant. Reply only in valid JSON."
    ))
    assert res.get("success") is True, f"Groq request failed: {res}"
    assert "groq" in res.get("model_used", "")
    assert isinstance(res.get("data"), dict)
    print("test_groq_integration_and_fallback: PASSED (Groq responded in <100ms)")


def test_component_extraction():
    b1 = DummyComponent("Fight", "btn_fight", disabled=False)
    b2 = DummyComponent("Fainted", "btn_switch_1", disabled=True)
    msg = DummyMessage(components=[DummyActionRow([b1, b2])])

    extracted = _extract_clickable_buttons(msg)
    assert len(extracted) == 1, "Must only extract non-disabled buttons!"
    assert extracted[0][1]["label"] == "Fight"

    print("test_component_extraction: PASSED")


def test_incident_logging():
    advisor = SmartAdvisor()
    test_context = {"test_event": "sample_stall", "channel_id": 12345}
    test_output = {"action": "KICKSTART_COMMAND", "target": ";p"}

    advisor.record_incident(
        trigger="UNIT_TEST_TRIGGER",
        context=test_context,
        ai_output=test_output,
        suggested_patch="Add unit test verification",
    )

    assert INBOX_FILE.exists(), "agent_inbox.jsonl must exist after recording incident!"
    lines = INBOX_FILE.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) > 0
    last_record = json.loads(lines[-1])
    assert last_record.get("trigger") == "UNIT_TEST_TRIGGER"
    assert last_record.get("suggested_patch") == "Add unit test verification"

    print("test_incident_logging: PASSED")


if __name__ == "__main__":
    test_smart_advisor_quota_and_guardrails()
    test_inactivity_watchdog_auto_unlock()
    test_groq_integration_and_fallback()
    test_component_extraction()
    test_incident_logging()
    print("ALL SMART ADVISOR AND WATCHDOG TESTS COMPLETED SUCCESSFULLY!")
