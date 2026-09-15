from __future__ import annotations

import time
from typing import Any


def is_cloudflare_1015_error(error_text: str) -> bool:
    lowered = str(error_text or "").lower()
    return "429 too many requests" in lowered and "1015" in lowered


async def notify_cloudflare_in_channel(
    bot: Any,
    *,
    channel_id: int,
    module_name: str,
    error_text: str,
    cooldown_seconds: float = 60.0,
    wait_seconds: float | None = None,
) -> bool:
    if bot is None:
        return False

    cid = int(channel_id or 0)
    if cid <= 0:
        return False

    now = time.monotonic()
    state = getattr(bot, "_cloudflare_indicator_last_at", None)
    if not isinstance(state, dict):
        state = {}
        setattr(bot, "_cloudflare_indicator_last_at", state)

    key = f"{module_name.lower()}:{cid}"
    last_sent = float(state.get(key, 0.0) or 0.0)
    if now - last_sent < float(cooldown_seconds or 0.0):
        return False

    channel = bot.get_channel(cid)
    if channel is None:
        try:
            channel = await bot.fetch_channel(cid)
        except Exception:
            return False

    wait_hint = ""
    if isinstance(wait_seconds, (int, float)) and float(wait_seconds) > 0:
        wait_hint = f" | wait ~{int(wait_seconds)}s"

    msg = (
        f"Cloudflare 1015 detected ({module_name}). "
        f"Pausing/retrying to avoid rate-limit spam{wait_hint}. "
        "If actions are missed right now, it is likely Cloudflare rather than strategy logic."
    )

    try:
        await channel.send(msg)
        state[key] = now
        return True
    except Exception:
        return False
