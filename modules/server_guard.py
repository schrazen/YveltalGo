from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger("pokegrinder.server_guard")


def get_required_server_id(bot: Any) -> int:
    """Retrieve the configured RequiredServerID for the bot instance."""
    if bot is None:
        return 0

    req_id = getattr(bot, "required_server_id", 0)
    if req_id and int(req_id) > 0:
        return int(req_id)

    config = getattr(bot, "config", None)
    if config is not None:
        cfg_req = getattr(config, "required_server_id", 0)
        if cfg_req and int(cfg_req) > 0:
            return int(cfg_req)

    return 0


def extract_guild_id(target: Any) -> int:
    """Safely extract the Discord guild (server) ID from a message, channel, or guild object."""
    if target is None:
        return 0

    if isinstance(target, int):
        return target

    # 1. Message or Channel with .guild attribute
    guild = getattr(target, "guild", None)
    if guild is not None:
        gid = getattr(guild, "id", None)
        if gid is not None:
            try:
                val = int(gid)
                if val > 0:
                    return val
            except (ValueError, TypeError):
                pass

    # 2. Object with .guild_id attribute
    guild_id = getattr(target, "guild_id", None)
    if guild_id is not None:
        try:
            val = int(guild_id)
            if val > 0:
                return val
        except (ValueError, TypeError):
            pass

    # 3. Message object where channel has the guild (.channel.guild)
    channel = getattr(target, "channel", None)
    if channel is not None:
        ch_guild = getattr(channel, "guild", None)
        if ch_guild is not None:
            gid = getattr(ch_guild, "id", None)
            if gid is not None:
                try:
                    val = int(gid)
                    if val > 0:
                        return val
                except (ValueError, TypeError):
                    pass
        ch_gid = getattr(channel, "guild_id", None)
        if ch_gid is not None:
            try:
                val = int(ch_gid)
                if val > 0:
                    return val
            except (ValueError, TypeError):
                pass

    # 4. Guild object itself (cls_name == "Guild")
    cls_name = getattr(getattr(target, "__class__", None), "__name__", "")
    if cls_name == "Guild":
        try:
            return int(getattr(target, "id", 0) or 0)
        except (ValueError, TypeError):
            pass

    return 0


def is_server_allowed(bot: Any, target: Any) -> bool:
    """Verify if a message, channel, or interaction originates from the user's RequiredServerID.

    If RequiredServerID is set (> 0), ANY interaction outside this server (including DMs
    or other mutual Discord servers) is strictly blocked.
    """
    required_server_id = get_required_server_id(bot)
    if required_server_id <= 0:
        return True

    # If target is a raw channel ID (int or numeric str), look up channel in bot cache
    if isinstance(target, (int, str)) and bot is not None:
        try:
            cid = int(target)
            ch = getattr(bot, "get_channel", None)
            if callable(ch):
                resolved = bot.get_channel(cid)
                if resolved is not None:
                    target = resolved
        except (ValueError, TypeError):
            pass

    guild_id = extract_guild_id(target)
    if guild_id <= 0:
        # DMs or channels with no guild are strictly rejected when locked to a server
        return False

    return guild_id == required_server_id


def is_message_in_required_server(bot: Any, message: Any) -> bool:
    """Check if a Discord Message belongs to the authorized RequiredServerID."""
    return is_server_allowed(bot, message)


def is_channel_in_required_server(bot: Any, channel: Any) -> bool:
    """Check if a Discord Channel belongs to the authorized RequiredServerID."""
    return is_server_allowed(bot, channel)


def assert_server_allowed(bot: Any, target: Any, operation: str = "operation") -> None:
    """Raise a PermissionError if the target does not belong to the RequiredServerID."""
    if not is_server_allowed(bot, target):
        req_id = get_required_server_id(bot)
        target_guild = extract_guild_id(target)
        msg = f"[SECURITY] Blocked {operation}: target guild {target_guild} does not match RequiredServerID {req_id}!"
        logger.critical(msg)
        raise PermissionError(msg)


def install_server_firewall(bot: Any) -> None:
    """Hook the low-level Discord HTTP client so that NO outgoing message, command,
    or component interaction can EVER be dispatched to any guild outside RequiredServerID.
    """
    required_server_id = get_required_server_id(bot)
    if required_server_id <= 0:
        return

    http = getattr(bot, "http", None)
    if http is None:
        return

    if getattr(http, "_server_firewall_installed", None) is True:
        return

    orig_send_message = getattr(http, "send_message", None)
    orig_interact = getattr(http, "interact", None)

    if callable(orig_send_message):
        async def guarded_send_message(channel_id, *args, **kwargs):
            ch = bot.get_channel(int(channel_id))
            guild_id = extract_guild_id(ch)
            if ch is not None and guild_id > 0 and guild_id != required_server_id:
                logger.critical(
                    "[SECURITY BLOCKED] Intercepted send_message to channel %s in unauthorized server %s (RequiredServerID: %s)",
                    channel_id,
                    guild_id,
                    required_server_id,
                )
                print(
                    f"\n[SECURITY FIREWALL BLOCKED] Attempted message send to channel {channel_id} in unauthorized server {guild_id}! (Required: {required_server_id})\n"
                )
                return None
            return await orig_send_message(channel_id, *args, **kwargs)

        http.send_message = guarded_send_message

    if callable(orig_interact):
        async def guarded_interact(type_, data, channel, *args, **kwargs):
            ch_obj = channel if hasattr(channel, "guild") else bot.get_channel(int(getattr(channel, "id", 0) or 0))
            guild_id = extract_guild_id(ch_obj)
            if ch_obj is not None and guild_id > 0 and guild_id != required_server_id:
                logger.critical(
                    "[SECURITY BLOCKED] Intercepted interaction to channel %s in unauthorized server %s (RequiredServerID: %s)",
                    getattr(channel, "id", 0),
                    guild_id,
                    required_server_id,
                )
                print(
                    f"\n[SECURITY FIREWALL BLOCKED] Attempted interaction to channel {getattr(channel, 'id', 0)} in unauthorized server {guild_id}! (Required: {required_server_id})\n"
                )
                return None
            return await orig_interact(type_, data, channel, *args, **kwargs)

        http.interact = guarded_interact

    http._server_firewall_installed = True
    logger.info("Installed Discord HTTP server firewall for RequiredServerID %s", required_server_id)

