"""Centralized, rock-solid captcha interlocking gate.

Ensures zero background probes, routine checks, or automated commands can dispatch
messages while a captcha is pending, active, or solving across any channel or account.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("pokegrinder.captcha_gate")


def is_captcha_active(bot: Any, channel_id: int | None = None) -> bool:
    """Return True if any captcha is active globally or on the specified channel.
    
    Verifies:
      1. bot.captcha_active (global flag set by Captcha cog)
      2. bot.hunting_captcha_active, bot.fishing_captcha_active, bot.autofight_captcha_active
      3. Bot runtime status strings (e.g. 'Paused (captcha...')
      4. Active non-terminal states in the Captcha cog channel_attempt_state dictionary
    """
    if bot is None:
        return False

    # 1. Global boolean flag
    if bool(getattr(bot, "captcha_active", False)):
        return True

    # 2. Channel-specific active flags
    hunt_active = bool(getattr(bot, "hunting_captcha_active", False))
    fish_active = bool(getattr(bot, "fishing_captcha_active", False))
    af_active = bool(getattr(bot, "autofight_captcha_active", False))

    if hunt_active or fish_active or af_active:
        return True

    # 3. Status string indicators
    for attr in ("hunting_status", "fishing_status", "autofight_status"):
        val = str(getattr(bot, attr, "") or "").lower()
        if "captcha" in val and "failed" not in val:
            return True

    # 4. Deep check into Captcha cog state if present
    get_cog = getattr(bot, "get_cog", None)
    if callable(get_cog):
        captcha_cog = get_cog("Captcha")
        if captcha_cog is not None:
            attempt_state = getattr(captcha_cog, "channel_attempt_state", {})
            if isinstance(attempt_state, dict):
                if channel_id is not None:
                    st = attempt_state.get(int(channel_id))
                    if isinstance(st, dict) and not bool(st.get("terminal_failure", False)):
                        if int(st.get("captcha_message_id", 0) or 0) > 0 or float(st.get("detected_at", 0.0) or 0.0) > 0.0:
                            return True
                else:
                    for cid, st in attempt_state.items():
                        if isinstance(st, dict) and not bool(st.get("terminal_failure", False)):
                            if int(st.get("captcha_message_id", 0) or 0) > 0 or float(st.get("detected_at", 0.0) or 0.0) > 0.0:
                                return True

    return False


def is_in_battle(bot: Any, channel_id: int | None = None) -> bool:
    """Return True if the bot is currently engaged in an active PokéMeow battle."""
    if bot is None:
        return False
    if bool(getattr(bot, "autofight_active", False)):
        return True
    if bool(getattr(bot, "world_boss_active", False)):
        return True
    if bool(getattr(bot, "npc_battle_active", False)):
        return True

    import time
    now = time.time()
    last_action = float(getattr(bot, "last_battle_activity_at", 0.0) or 0.0)
    if last_action > 0.0 and (now - last_action) < 15.0:
        return True

    last_wb_action = float(getattr(bot, "last_wb_action", 0.0) or 0.0)
    if last_wb_action > 0.0 and (now - last_wb_action) < 15.0:
        return True

    get_cog = getattr(bot, "get_cog", None)
    if callable(get_cog):
        af_cog = get_cog("AutoFight")
        if af_cog is not None:
            if getattr(af_cog, "_active_pokemon", "") and getattr(af_cog, "_enemy_active_pokemon", ""):
                return True

    return False


def can_dispatch_command(bot: Any, channel_id: int | None = None, require_out_of_battle: bool = False) -> bool:
    """Check if commands are safe to dispatch (no captcha active, bot ready, optionally not in battle)."""
    if bot is None:
        return False
    if is_captcha_active(bot, channel_id=channel_id):
        return False
    if require_out_of_battle and is_in_battle(bot):
        return False
    is_ready = getattr(bot, "is_ready", None)
    if callable(is_ready) and not is_ready():
        return False
    return True


def assert_no_captcha(bot: Any, channel_id: int | None = None, context: str = "") -> None:
    """Raise RuntimeError if any captcha is active."""
    if is_captcha_active(bot, channel_id=channel_id):
        ctx_msg = f" [{context}]" if context else ""
        raise RuntimeError(f"Message dispatch blocked: captcha is active{ctx_msg}")
