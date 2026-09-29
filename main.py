import json
import asyncio
import os
import sys
import threading
import logging
import inspect
import base64
from contextlib import suppress
from time import time
from typing import List
from datetime import datetime
from pathlib import Path

import discord
from discord.ext.commands import Bot

from cogs.fishing import Fishing
from cogs.captcha import Captcha
from cogs.hunting import Hunting
from cogs.egg import Egg
from cogs.berry import BerryGarden
from cogs.catchbot import CatchBot
from cogs.autofight import AutoFight
from cogs.limited_events import LimitedEvents
from modules.logging import logger
from modules.stats_store import get_stats_key, load_stats_for_key, persist_bot_stats, ensure_day_mode_window
from cogs.startup import Startup, Config
from modules.humanizer import Humanizer
from modules.break_coordinator import BreakCoordinator
from modules.runtime_file_log import info as runtime_info_log
from modules.runtime_file_log import log_exception as runtime_log_exception
from modules.runtime_file_log import setup_runtime_file_logging, tail_log_file, RUNTIME_LOG_PATH
from ui.server import configure_diagnostics_provider, configure_runtime_handlers, run_dashboard

start_time = datetime.now()
if hasattr(discord.utils, "setup_logging"):
    discord.utils.setup_logging()
else:
    logging.basicConfig(level=logging.INFO)
BASE_DIR = Path(__file__).resolve().parent


def _load_runtime_config(default: dict | None = None) -> dict:
    fallback = dict(default or {})
    try:
        loaded = json.loads((BASE_DIR / "config.json").read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[Runtime] Failed to load config.json: {exc}")
        return fallback
    if not isinstance(loaded, dict):
        print("[Runtime] config.json root is not an object; using defaults.")
        return fallback
    return loaded


config = _load_runtime_config({})
setup_runtime_file_logging()
runtime_info_log("PokeGrinder starting (cwd=%s, python=%s)", os.getcwd(), sys.executable)
bots: List[Bot] = []
background_bot_tasks: set[asyncio.Task] = set()
startup_failures: dict[str, str] = {}
main_loop: asyncio.AbstractEventLoop | None = None
shutdown_event: asyncio.Event | None = None
dashboard_thread: threading.Thread | None = None


def reload_runtime_config_from_disk() -> None:
    global config
    loaded = _load_runtime_config(config)
    if isinstance(loaded, dict):
        config = loaded


async def log_function():
    """Refresh the Rich dashboard; must not use asyncio.to_thread (Rich + Windows console → OSError 22 under Electron)."""
    try:
        logger(bots, start_time, bool(config.get("ClearConsole", False)))
    except OSError as exc:
        if getattr(exc, "errno", None) != 22:
            raise
        try:
            logger(bots, start_time, False)
        except OSError:
            pass


async def add_cog_compat(bot: Bot, cog) -> None:
    result = bot.add_cog(cog)
    if inspect.isawaitable(result):
        await result


def is_account_config(value: object) -> bool:
    if not isinstance(value, dict):
        return False

    return "HuntingChannel" in value and "FishingChannel" in value


def get_accounts_map() -> dict[str, dict]:
    accounts = config.get("Accounts")
    if isinstance(accounts, dict):
        return {
            str(token): value
            for token, value in accounts.items()
            if is_account_config(value)
        }

    return {
        str(token): value
        for token, value in config.items()
        if is_account_config(value)
    }


def get_account_config(token: str) -> dict | None:
    account = get_accounts_map().get(str(token))
    return account if isinstance(account, dict) else None


def token_user_mention(token: str) -> str:
    token_text = str(token or "").strip()
    if not token_text:
        return ""

    head = token_text.split(".", 1)[0].strip()
    if not head:
        return ""

    # Discord token head is base64(urlsafe) encoded user id.
    padded = head + "=" * (-len(head) % 4)
    try:
        decoded = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""

    if decoded.isdigit() and int(decoded) > 0:
        return f"<@{decoded}>"

    return ""


def _capture_speed_defaults(bot: Bot) -> dict[str, object]:
    cfg = getattr(bot, "config", None)
    if cfg is None:
        return {}

    return {
        "retry_cooldown": float(getattr(cfg, "retry_cooldown", 0.0) or 0.0),
        "hunting_cooldown": float(getattr(cfg, "hunting_cooldown", 0.0) or 0.0),
        "fishing_cooldown": float(getattr(cfg, "fishing_cooldown", 0.0) or 0.0),
        "suspicion_avoidance": int(getattr(cfg, "suspicion_avoidance", 0) or 0),
        "hunting_delay_min": float(getattr(cfg, "hunting_delay_min", 0.0) or 0.0),
        "hunting_delay_max": float(getattr(cfg, "hunting_delay_max", 0.0) or 0.0),
        "fishing_delay_min": float(getattr(cfg, "fishing_delay_min", 0.0) or 0.0),
        "fishing_delay_max": float(getattr(cfg, "fishing_delay_max", 0.0) or 0.0),
        "post_catch_delay_min": float(getattr(cfg, "post_catch_delay_min", 0.0) or 0.0),
        "post_catch_delay_max": float(getattr(cfg, "post_catch_delay_max", 0.0) or 0.0),
        "enable_anti_detection": bool(getattr(cfg, "enable_anti_detection", False)),
        "min_action_delay_seconds": float(getattr(cfg, "min_action_delay_seconds", 0.0) or 0.0),
        "human_breaks_enabled": bool(getattr(cfg, "human_breaks_enabled", False)),
        "short_break_every_min_seconds": int(getattr(cfg, "short_break_every_min_seconds", 0) or 0),
        "short_break_every_max_seconds": int(getattr(cfg, "short_break_every_max_seconds", 0) or 0),
        "short_break_duration_min_seconds": int(getattr(cfg, "short_break_duration_min_seconds", 0) or 0),
        "short_break_duration_max_seconds": int(getattr(cfg, "short_break_duration_max_seconds", 0) or 0),
        "long_break_every_min_seconds": int(getattr(cfg, "long_break_every_min_seconds", 0) or 0),
        "long_break_every_max_seconds": int(getattr(cfg, "long_break_every_max_seconds", 0) or 0),
        "long_break_duration_min_seconds": int(getattr(cfg, "long_break_duration_min_seconds", 0) or 0),
        "long_break_duration_max_seconds": int(getattr(cfg, "long_break_duration_max_seconds", 0) or 0),
    }


def _apply_max_speed_runtime(bot: Bot) -> None:
    cfg = getattr(bot, "config", None)
    if cfg is None:
        return

    cfg.retry_cooldown = 0.0
    cfg.suspicion_avoidance = 0
    cfg.hunting_delay_min = 0.0
    cfg.hunting_delay_max = 0.0
    cfg.fishing_delay_min = 0.0
    cfg.fishing_delay_max = 0.0
    cfg.post_catch_delay_min = 0.0
    cfg.post_catch_delay_max = 0.0
    cfg.enable_anti_detection = False
    cfg.min_action_delay_seconds = 0.0
    cfg.human_breaks_enabled = False


def _apply_standard_runtime(bot: Bot) -> None:
    """Apply standard (conservative) profile with balanced delays and protection."""
    cfg = getattr(bot, "config", None)
    if cfg is None:
        return

    cfg.retry_cooldown = max(float(getattr(cfg, "retry_cooldown", 0.0) or 0.0), 3.0)
    cfg.hunting_cooldown = max(float(getattr(cfg, "hunting_cooldown", 0.0) or 0.0), 4.0)
    cfg.fishing_cooldown = max(float(getattr(cfg, "fishing_cooldown", 0.0) or 0.0), 4.5)
    cfg.suspicion_avoidance = max(int(getattr(cfg, "suspicion_avoidance", 0) or 0), 12)

    cfg.hunting_delay_min = max(float(getattr(cfg, "hunting_delay_min", 0.0) or 0.0), 4.0)
    cfg.hunting_delay_max = max(float(getattr(cfg, "hunting_delay_max", 0.0) or 0.0), 9.0, cfg.hunting_delay_min)
    cfg.fishing_delay_min = max(float(getattr(cfg, "fishing_delay_min", 0.0) or 0.0), 5.0)
    cfg.fishing_delay_max = max(float(getattr(cfg, "fishing_delay_max", 0.0) or 0.0), 10.0, cfg.fishing_delay_min)
    cfg.post_catch_delay_min = max(float(getattr(cfg, "post_catch_delay_min", 0.0) or 0.0), 3.0)
    cfg.post_catch_delay_max = max(float(getattr(cfg, "post_catch_delay_max", 0.0) or 0.0), 6.0, cfg.post_catch_delay_min)

    cfg.enable_anti_detection = True
    cfg.min_action_delay_seconds = max(float(getattr(cfg, "min_action_delay_seconds", 0.0) or 0.0), 2.5)
    cfg.human_breaks_enabled = True

    cfg.short_break_every_min_seconds = min(int(getattr(cfg, "short_break_every_min_seconds", 90) or 90), 60)
    cfg.short_break_every_max_seconds = min(int(getattr(cfg, "short_break_every_max_seconds", 180) or 180), 120)
    cfg.short_break_duration_min_seconds = max(int(getattr(cfg, "short_break_duration_min_seconds", 30) or 30), 90)
    cfg.short_break_duration_max_seconds = max(int(getattr(cfg, "short_break_duration_max_seconds", 90) or 90), 240)
    cfg.long_break_every_min_seconds = min(int(getattr(cfg, "long_break_every_min_seconds", 300) or 300), 240)
    cfg.long_break_every_max_seconds = min(int(getattr(cfg, "long_break_every_max_seconds", 600) or 600), 420)
    cfg.long_break_duration_min_seconds = max(int(getattr(cfg, "long_break_duration_min_seconds", 120) or 120), 300)
    cfg.long_break_duration_max_seconds = max(int(getattr(cfg, "long_break_duration_max_seconds", 300) or 300), 720)


def _apply_super_low_risk_runtime(bot: Bot) -> None:
    """Apply extreme defensive profile with maximum delays and breaks."""
    cfg = getattr(bot, "config", None)
    if cfg is None:
        return

    cfg.retry_cooldown = max(float(getattr(cfg, "retry_cooldown", 0.0) or 0.0), 5.0)
    cfg.hunting_cooldown = max(float(getattr(cfg, "hunting_cooldown", 0.0) or 0.0), 6.0)
    cfg.fishing_cooldown = max(float(getattr(cfg, "fishing_cooldown", 0.0) or 0.0), 7.0)
    cfg.suspicion_avoidance = max(int(getattr(cfg, "suspicion_avoidance", 0) or 0), 20)

    cfg.hunting_delay_min = max(float(getattr(cfg, "hunting_delay_min", 0.0) or 0.0), 6.5)
    cfg.hunting_delay_max = max(float(getattr(cfg, "hunting_delay_max", 0.0) or 0.0), 14.0, cfg.hunting_delay_min)
    cfg.fishing_delay_min = max(float(getattr(cfg, "fishing_delay_min", 0.0) or 0.0), 8.0)
    cfg.fishing_delay_max = max(float(getattr(cfg, "fishing_delay_max", 0.0) or 0.0), 16.0, cfg.fishing_delay_min)
    cfg.post_catch_delay_min = max(float(getattr(cfg, "post_catch_delay_min", 0.0) or 0.0), 5.0)
    cfg.post_catch_delay_max = max(float(getattr(cfg, "post_catch_delay_max", 0.0) or 0.0), 10.0, cfg.post_catch_delay_min)

    cfg.enable_anti_detection = True
    cfg.min_action_delay_seconds = max(float(getattr(cfg, "min_action_delay_seconds", 0.0) or 0.0), 4.0)
    cfg.human_breaks_enabled = True

    # Super low risk should be mostly idle: frequent long AFK windows.
    cfg.short_break_every_min_seconds = min(int(getattr(cfg, "short_break_every_min_seconds", 90) or 90), 120)
    cfg.short_break_every_max_seconds = min(int(getattr(cfg, "short_break_every_max_seconds", 180) or 180), 300)
    cfg.short_break_duration_min_seconds = max(int(getattr(cfg, "short_break_duration_min_seconds", 30) or 30), 300)
    cfg.short_break_duration_max_seconds = max(int(getattr(cfg, "short_break_duration_max_seconds", 90) or 90), 900)
    cfg.long_break_every_min_seconds = min(int(getattr(cfg, "long_break_every_min_seconds", 300) or 300), 300)
    cfg.long_break_every_max_seconds = min(int(getattr(cfg, "long_break_every_max_seconds", 600) or 600), 600)
    cfg.long_break_duration_min_seconds = max(int(getattr(cfg, "long_break_duration_min_seconds", 120) or 120), 900)
    cfg.long_break_duration_max_seconds = max(int(getattr(cfg, "long_break_duration_max_seconds", 300) or 300), 1800)


def _restore_speed_defaults(bot: Bot) -> None:
    cfg = getattr(bot, "config", None)
    defaults = getattr(bot, "speed_mode_defaults", {}) or {}
    if cfg is None or not isinstance(defaults, dict):
        return

    for key, value in defaults.items():
        if hasattr(cfg, key):
            setattr(cfg, key, value)


async def start_bots(token: str) -> None:
    startup_failures.pop(str(token), None)
    account_id = get_stats_key(token)
    runtime_info_log("start_bots: entered account_id=%s", account_id)
    account = get_account_config(token)
    if account is None:
        runtime_info_log("start_bots: abort — no account block in config for this token (account_id=%s)", account_id)
        print(f"[Runtime] Account config not found for token: {token}")
        return
    wb_defaults = config.get("WorldBossDefaults", {})
    account_wb = account.get("WorldBoss", {})
    berry_defaults = config.get("BerryDefaults", {})
    account_berry = account.get("Berry", {})
    delay_defaults = config.get("Delays", {})
    captcha_answerer = config.get("CaptchaAnswerer", {})
    account_captcha_answerer = account.get("CaptchaAnswerer", {}) if isinstance(account.get("CaptchaAnswerer", {}), dict) else {}
    captcha_alerts = config.get("CaptchaAlerts", {})
    account_captcha_alerts = account.get("CaptchaAlerts", {}) if isinstance(account.get("CaptchaAlerts", {}), dict) else {}
    anti_detection = config.get("AntiDetection", {})
    human_breaks = config.get("HumanBreaks", {})
    cooldowns = config.get("Cooldowns", {}) if isinstance(config.get("Cooldowns", {}), dict) else {}
    catchbot_defaults = config.get("CatchBotDefaults", {})
    account_catchbot = account.get("CatchBot", {}) if isinstance(account.get("CatchBot", {}), dict) else {}
    autofight_defaults = config.get("AutoFightDefaults", {})
    account_autofight = account.get("AutoFight", {}) if isinstance(account.get("AutoFight", {}), dict) else {}
    custom_delays = account.get("CustomDelays", {})
    hunting_channel_id = int(account.get("HuntingChannel", 0) or 0)
    fishing_channel_id = int(account.get("FishingChannel", 0) or 0)
    catchbot_channel_id = int(
        account_catchbot.get(
            "Channel",
            catchbot_defaults.get("Channel", account.get("HuntingChannel", 0)),
        )
        or 0
    )
    if catchbot_channel_id == 0:
        catchbot_channel_id = int(account.get("HuntingChannel", 0) or 0)

    autofight_channel_id = int(
        account_autofight.get(
            "Channel",
            autofight_defaults.get("Channel", account.get("HuntingChannel", 0)),
        )
        or 0
    )

    raw_manual_ids = account_captcha_answerer.get(
        "ManualAnswerAllowedUserIDs",
        captcha_answerer.get("ManualAnswerAllowedUserIDs", []),
    )
    manual_allowed_user_ids: list[int] = []
    if isinstance(raw_manual_ids, list):
        for raw in raw_manual_ids:
            try:
                value = int(str(raw).strip())
            except Exception:
                continue
            if value > 0:
                manual_allowed_user_ids.append(value)

    # Preserve order and remove duplicates.
    seen_manual_ids: set[int] = set()
    manual_allowed_user_ids = [
        user_id
        for user_id in manual_allowed_user_ids
        if not (user_id in seen_manual_ids or seen_manual_ids.add(user_id))
    ]

    if (
        token == ""
        or hunting_channel_id == 0
        and fishing_channel_id == 0
    ):
        runtime_info_log(
            "start_bots: abort — empty token or both HuntingChannel and FishingChannel are 0 (account_id=%s)",
            account_id,
        )
        return

    # Resolve delay values: account-specific overrides or global defaults.
    def resolve_delay(custom_key: str, default_key: str, fallback: float) -> float:
        custom_val = custom_delays.get(custom_key)
        if custom_val is not None:
            return float(custom_val)
        return float(delay_defaults.get(default_key, fallback))

    bot = Bot(command_prefix=token)
    bot.account_token = token
    bot.required_server_id = int(account.get("RequiredServerID", config.get("RequiredServerID", 0)) or 0)
    bot.server_scope_valid = True
    bot.request_system_shutdown = request_system_shutdown
    bot.stats_key = get_stats_key(token)
    persisted_stats = load_stats_for_key(bot.stats_key)
    bot.log = log_function
    bot.hunting_status = ""
    bot.fishing_status = ""
    bot.autofight_guard_status = ""
    bot.config = Config(
        hunting_channel_id,
        fishing_channel_id,
        account_wb.get("Channel", wb_defaults.get("Channel", 0)),
        account_berry.get("Channel", berry_defaults.get("Channel", 0)),
        account.get("ExceptionBalls", {}),
        account.get("Balls", {}),
        account.get("FishBalls", {}),
        account.get("AutoBuy", {}),
        int(account.get("AutoReleaseDuplicates", 0) or 0),
        float(cooldowns.get("RetryCooldown", 3.0)),
        float(cooldowns.get("HuntingCooldown", 8.0)),
        float(cooldowns.get("FishingCooldown", 22.0)),
        bool(account_captcha_answerer.get("AutoAnswerEnabled", captcha_answerer.get("AutoAnswerEnabled", True))),
        max(1, int(account_captcha_answerer.get("MaxAutoAttempts", captcha_answerer.get("MaxAutoAttempts", 3)))),
        manual_allowed_user_ids,
        int(config.get("SuspicionAvoidance", 250) or 250),
        bool(account_captcha_alerts.get("Enabled", captcha_alerts.get("Enabled", False))),
        int(account_captcha_alerts.get("ChannelID", captcha_alerts.get("ChannelID", 0)) or 0),
        str(account_captcha_alerts.get("WebhookURL", captcha_alerts.get("WebhookURL", ""))),
        str(account_captcha_alerts.get("Ping", captcha_alerts.get("Ping", "@everyone"))),
        max(0, int(account_captcha_alerts.get("CooldownSeconds", captcha_alerts.get("CooldownSeconds", 60)))),
        account.get("EggHatching", True),
        account.get("AutoHoldEgg", True),
        account_wb.get("Enabled", wb_defaults.get("Enabled", False)),
        account_wb.get("DangerHPPercent", wb_defaults.get("DangerHPPercent", 40)),
        account_wb.get("MaxIdleSeconds", wb_defaults.get("MaxIdleSeconds", 120)),
        account_wb.get("DryRun", wb_defaults.get("DryRun", False)),
        account_berry.get("Enabled", berry_defaults.get("Enabled", False)),
        resolve_delay("HuntingDelayMin", "HuntingDelayMin", 0.5),
        resolve_delay("HuntingDelayMax", "HuntingDelayMax", 2.0),
        resolve_delay("FishingDelayMin", "FishingDelayMin", 1.0),
        resolve_delay("FishingDelayMax", "FishingDelayMax", 3.5),
        resolve_delay("PostCatchDelayMin", "PostCatchDelayMin", 0.8),
        resolve_delay("PostCatchDelayMax", "PostCatchDelayMax", 1.5),
        bool(anti_detection.get("EnableAntiDetectionMode", False)),
        float(anti_detection.get("MinActionDelaySeconds", 0.1)),
        bool(human_breaks.get("Enabled", True)),
        int(human_breaks.get("ShortBreakEveryMinSeconds", 90)),
        int(human_breaks.get("ShortBreakEveryMaxSeconds", 180)),
        int(human_breaks.get("ShortBreakDurationMinSeconds", 30)),
        int(human_breaks.get("ShortBreakDurationMaxSeconds", 90)),
        int(human_breaks.get("LongBreakEveryMinSeconds", 300)),
        int(human_breaks.get("LongBreakEveryMaxSeconds", 600)),
        int(human_breaks.get("LongBreakDurationMinSeconds", 120)),
        int(human_breaks.get("LongBreakDurationMaxSeconds", 300)),
        bool(account.get("MaxSpeedMode", False)),
        bool(account.get("SuperLowRiskMode", False)),
        bool(account_catchbot.get("Enabled", catchbot_defaults.get("Enabled", False))),
        catchbot_channel_id,
        max(
            120,
            int(
                account_catchbot.get(
                    "CheckIntervalSeconds",
                    catchbot_defaults.get("CheckIntervalSeconds", 900),
                )
                or 900
            ),
        ),
        bool(account_autofight.get("Enabled", autofight_defaults.get("Enabled", False))),
        autofight_channel_id,
        str(account_autofight.get("OnCommand", autofight_defaults.get("OnCommand", ";autofight on"))),
        str(account_autofight.get("OffCommand", autofight_defaults.get("OffCommand", ";autofight off"))),
    )
    bot.speed_mode_defaults = _capture_speed_defaults(bot)
    bot.humanizer = Humanizer(bot)
    # WorldBoss system has been removed from runtime.
    bot.config.world_boss_enabled = False
    if bool(getattr(bot.config, "max_speed_mode_enabled", False)) and bool(getattr(bot.config, "super_low_risk_mode_enabled", False)):
        # Safety-first conflict resolution when both flags are set in config.
        bot.config.max_speed_mode_enabled = False
    if bool(getattr(bot.config, "max_speed_mode_enabled", False)):
        _apply_max_speed_runtime(bot)
    elif bool(getattr(bot.config, "super_low_risk_mode_enabled", False)):
        _apply_super_low_risk_runtime(bot)
    else:
        _apply_standard_runtime(bot)

    # Day-mode stats persist across restarts and reset at 12:00 local time.
    bot.day_mode_anchor_local = str(persisted_stats.get("day_mode_anchor_local", ""))
    bot.encounters = int(persisted_stats.get("day_encounters", 0))
    bot.catches = int(persisted_stats.get("day_catches", 0))
    bot.fish_encounters = int(persisted_stats.get("day_fish_encounters", 0))
    bot.fish_catches = int(persisted_stats.get("day_fish_catches", 0))
    bot.coins_earned = int(persisted_stats.get("day_coins_earned", 0))
    bot.hunt_rarity_catches = dict(persisted_stats.get("day_hunt_rarity_catches", {}))
    bot.fish_rarity_catches = dict(persisted_stats.get("day_fish_rarity_catches", {}))
    ensure_day_mode_window(bot, persist_on_reset=False)

    # Lifetime stats persist across restarts.
    bot.lifetime_encounters = persisted_stats["lifetime_encounters"]
    bot.lifetime_catches = persisted_stats["lifetime_catches"]
    bot.lifetime_fish_encounters = persisted_stats["lifetime_fish_encounters"]
    bot.lifetime_fish_catches = persisted_stats["lifetime_fish_catches"]
    bot.lifetime_coins_earned = persisted_stats["lifetime_coins_earned"]
    bot.lifetime_hunt_rarity_catches = persisted_stats["lifetime_hunt_rarity_catches"]
    bot.lifetime_fish_rarity_catches = persisted_stats["lifetime_fish_rarity_catches"]

    bot.duplicates = 0
    bot.last_hunt = time()
    bot.last_fish = time()
    bot.auto_buy_queued = False
    bot.limit = False
    bot.captcha_active = False
    bot.hunting_captcha_active = False
    bot.fishing_captcha_active = False
    bot.autofight_captcha_active = False
    bot.pause_hunting = False
    bot.pause_fishing = False
    bot.autofight_active = False
    bot.autofight_status = "Disabled"
    bot.last_stats_save = 0.0
    bot.limited_events = {
        "status": "pending",
        "interval_seconds": 1800,
        "last_checked_utc": "",
        "next_check_utc": "",
        "source": "init",
        "bonus": {"ok": False, "headline": "", "event_end": "", "important_lines": [], "raw_preview": "", "error": "Not checked yet", "jump_url": ""},
        "events": {"ok": False, "headline": "", "event_end": "", "important_lines": [], "raw_preview": "", "error": "Not checked yet", "jump_url": ""},
        "unlocks": {"ok": False, "headline": "", "event_end": "", "important_lines": [], "raw_preview": "", "error": "Not checked yet", "jump_url": ""},
    }

    bots.append(bot)
    await add_cog_compat(bot, Startup(bot))

    # Create shared break coordinator for hunting and fishing to pause together
    break_coordinator = BreakCoordinator(bot.config)

    if bot.config.fishing_channel_id != 0:
        bot.fishing_status = "Starting..."
        await add_cog_compat(bot, Fishing(bot, break_coordinator))
    else:
        bot.fishing_status = "Disabled"

    if bot.config.hunting_channel_id != 0:
        bot.hunting_status = "Starting..."
        await add_cog_compat(bot, Hunting(bot, break_coordinator))
    else:
        bot.hunting_status = "Disabled"

    if bot.config.berry_enabled and bot.config.berry_channel_id != 0:
        await add_cog_compat(bot, BerryGarden(bot))

    if bool(getattr(bot.config, "catchbot_enabled", False)) and int(getattr(bot.config, "catchbot_channel_id", 0) or 0) != 0:
        bot.catchbot_status = "Starting..."
        await add_cog_compat(bot, CatchBot(bot))
    else:
        bot.catchbot_status = "Disabled"

    if bool(getattr(bot.config, "autofight_enabled", False)) and int(getattr(bot.config, "autofight_channel_id", 0) or 0) != 0:
        bot.autofight_status = "Ready"
        bot.autofight_guard_status = ""
        await add_cog_compat(bot, AutoFight(bot))
    else:
        bot.autofight_status = "Disabled"
        bot.autofight_guard_status = ""

    await add_cog_compat(bot, LimitedEvents(bot))
    await add_cog_compat(bot, Captcha(bot))
    await add_cog_compat(bot, Egg(bot))

    runtime_info_log("start_bots: all cogs loaded; awaiting bot.start (Discord gateway) account_id=%s", account_id)
    try:
        print(f"[Runtime] Opening Discord gateway for {get_stats_key(token)}…")
        await bot.start(token=token)
    except Exception as exc:
        err_text = str(exc) or exc.__class__.__name__
        startup_failures[str(token)] = err_text
        runtime_log_exception(f"bot.start() account={get_stats_key(token)}", exc)
        if bot.config.fishing_channel_id != 0:
            bot.fishing_status = f"Error: {err_text}"
        if bot.config.hunting_channel_id != 0:
            bot.hunting_status = f"Error: {err_text}"
        print(f"[Runtime] Failed to start bot for {get_stats_key(token)}: {err_text}")
        with suppress(Exception):
            await bot.log()
        with suppress(Exception):
            await bot.close()
        prune_closed_bots()


def configured_tokens() -> list[str]:
    return list(get_accounts_map().keys())


def running_tokens() -> set[str]:
    active: set[str] = set()
    for bot in bots:
        token = getattr(bot, "account_token", None)
        if token and not bot.is_closed():
            active.add(str(token))
    return active


def resolve_configured_token(target: str) -> str | None:
    lookup = str(target or "").strip().lower()
    if not lookup:
        return None

    for token in configured_tokens():
        if token.lower() == lookup:
            return token

    for token in configured_tokens():
        if get_stats_key(token).lower() == lookup:
            return token

    for idx, token in enumerate(configured_tokens(), start=1):
        if f"account#{idx}" == lookup:
            return token

    return None


def _persist_runtime_config() -> tuple[bool, str]:
    try:
        (BASE_DIR / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _update_account_config(token: str, updater) -> tuple[bool, str]:
    account = get_account_config(token)
    if not isinstance(account, dict):
        return False, "Configured account not found in config."

    updater(account)
    ok, err = _persist_runtime_config()
    if not ok:
        return False, err
    return True, ""


def find_bot_by_token(token: str) -> Bot | None:
    for bot in bots:
        if getattr(bot, "account_token", None) == token and not bot.is_closed():
            return bot
    return None


async def start_account_bot(target: str) -> tuple[bool, str]:
    reload_runtime_config_from_disk()
    prune_closed_bots()

    token = resolve_configured_token(target)
    if token is None:
        runtime_info_log("start_account_bot: could not resolve target=%r to a configured token", str(target)[:80])
        return False, f"Configured account not found for target: {target}"

    existing = find_bot_by_token(token)
    if existing is not None:
        runtime_info_log(
            "start_account_bot: skip — bot already in memory account_id=%s ready=%s closed=%s",
            get_stats_key(token),
            existing.is_ready(),
            existing.is_closed(),
        )
        if existing.is_ready():
            return True, "Account is already running."
        return True, "Account is already connecting."

    runtime_info_log("start_account_bot: scheduling start_bots task account_id=%s", get_stats_key(token))
    task = asyncio.create_task(start_bots(token))
    _track_bot_task(task, token)
    return True, "Account start requested."


def prune_closed_bots() -> None:
    bots[:] = [bot for bot in bots if not bot.is_closed()]


def _track_bot_task(task: asyncio.Task, token: str | None = None) -> None:
    background_bot_tasks.add(task)

    def _cleanup(done_task: asyncio.Task) -> None:
        if not done_task.cancelled():
            try:
                exc = done_task.exception()
            except Exception as task_error:
                print(f"[Runtime] Background bot task inspection failed: {task_error}")
            else:
                if exc is not None:
                    err_text = str(exc) or exc.__class__.__name__
                    if token:
                        startup_failures[str(token)] = err_text
                        runtime_log_exception(f"start_bots task account={get_stats_key(token)}", exc)
                    else:
                        runtime_log_exception("start_bots task", exc)
                    print(f"[Runtime] Background bot task failed: {err_text}")
        background_bot_tasks.discard(done_task)

    task.add_done_callback(_cleanup)


async def start_all_bots() -> int:
    reload_runtime_config_from_disk()
    prune_closed_bots()
    tokens = configured_tokens()

    # Restart tokens that are present but stuck in a non-ready state.
    stale_bots = [
        bot
        for bot in bots
        if getattr(bot, "account_token", None) in tokens
        and not bot.is_closed()
        and not bot.is_ready()
    ]
    for bot in stale_bots:
        token = getattr(bot, "account_token", "<unknown>")
        try:
            account_index = configured_tokens().index(token) + 1
            label = f"account#{account_index}"
        except ValueError:
            label = "unknown-account"
        print(f"[Runtime] Restarting stale bot session for {label}...")
        try:
            await bot.close()
        except Exception as exc:
            print(f"[Runtime] Failed closing stale bot cleanly: {exc}")

    prune_closed_bots()
    to_start = [token for token in tokens if token not in running_tokens()]
    for token in to_start:
        startup_failures.pop(str(token), None)
        task = asyncio.create_task(start_bots(token))
        _track_bot_task(task, token)
    return len(to_start)


def print_control_help() -> None:
    print("\nTerminal controls:")
    print("  help           Show this help")
    print("  status         Show pause states")
    print("  pause          Pause hunting + fishing")
    print("  resume         Resume hunting + fishing")
    print("  pause hunt     Pause only hunting")
    print("  resume hunt    Resume only hunting")
    print("  pause fish     Pause only fishing")
    print("  resume fish    Resume only fishing")
    print("  clear limit    Clear daily limit latch and resume hunting")
    print("  start all      Start/reconnect all configured bots")
    print("  exit           Save stats and stop all bots")


async def apply_pause_state(hunting: bool | None = None, fishing: bool | None = None) -> None:
    for bot in bots:
        if hunting is not None:
            bot.pause_hunting = hunting

            if bot.config.hunting_channel_id != 0:
                bot.hunting_status = "Paused (manual)" if hunting else "Grinding..."

        if fishing is not None:
            bot.pause_fishing = fishing

            if bot.config.fishing_channel_id != 0:
                bot.fishing_status = "Paused (manual)" if fishing else "Grinding..."

        if bot.is_ready():
            await bot.log()


async def clear_hunting_limit() -> None:
    for bot in bots:
        bot.limit = False
        bot.pause_hunting = False

        if bot.config.hunting_channel_id != 0:
            bot.hunting_status = "Grinding..."

        if bot.is_ready():
            await bot.log()


def print_runtime_status() -> None:
    if not bots:
        print("No active bots.")
        return

    print("\nBot runtime status:")
    for bot in bots:
        username = str(bot.user) if bot.is_ready() and bot.user else "Not ready"
        print(
            f"- {username}: hunt_paused={bot.pause_hunting}, "
            f"fish_paused={bot.pause_fishing}, "
            f"hunt_captcha={bool(getattr(bot, 'hunting_captcha_active', False))}, "
            f"fish_captcha={bool(getattr(bot, 'fishing_captcha_active', False))}, "
            f"captcha_active={bot.captcha_active}, limit={bot.limit}, "
            f"day_mode_catches={bot.catches}, lifetime_catches={bot.lifetime_catches}"
        )


async def stop_all_bots() -> None:
    for bot in bots:
        persist_bot_stats(bot, force=True)

    for bot in bots:
        if bot.is_closed():
            continue

        try:
            await bot.close()
        except Exception as exc:
            print(f"Warning: failed to close bot cleanly ({exc}).")

    prune_closed_bots()


async def stop_bot(target_bot: Bot) -> None:
    persist_bot_stats(target_bot, force=True)

    if not target_bot.is_closed():
        with suppress(Exception):
            await target_bot.close()

    prune_closed_bots()


def find_bot_by_target(target: str) -> Bot | None:
    lookup = str(target or "").strip().lower()
    if not lookup:
        return None

    for bot in bots:
        if str(getattr(bot, "stats_key", "")).lower() == lookup:
            return bot

    for bot in bots:
        if str(getattr(bot, "account_token", "")).lower() == lookup:
            return bot

    for bot in bots:
        username = str(bot.user) if bot.is_ready() and bot.user else "not ready"
        if username.lower() == lookup:
            return bot

    return None


async def request_system_shutdown(reason: str) -> None:
    print(f"[Safety] {reason}")
    await stop_all_bots()
    if shutdown_event is not None:
        shutdown_event.set()


def get_runtime_snapshot() -> dict:
    snapshot = []
    for bot in bots:
        ensure_day_mode_window(bot, persist_on_reset=False)
        berry_cog = bot.get_cog("BerryGarden")
        catchbot_cog = bot.get_cog("CatchBot")
        berry_info = {
            "enabled": bool(getattr(getattr(bot, "config", None), "berry_enabled", False)),
            "channel_id": int(getattr(getattr(bot, "config", None), "berry_channel_id", 0) or 0),
            "water_in_progress": bool(getattr(berry_cog, "water_in_progress", False)) if berry_cog else False,
            "pending_water_slots": list(getattr(berry_cog, "pending_water_slots", [])) if berry_cog else [],
            "slot_states": list(getattr(berry_cog, "last_slot_states", [])) if berry_cog else [],
            "last_check_trigger_time": float(getattr(berry_cog, "last_check_trigger_time", 0.0)) if berry_cog else 0.0,
            "last_check_source": str(getattr(berry_cog, "last_check_source", "none")) if berry_cog else "none",
        }
        catchbot_info = {
            "enabled": bool(getattr(getattr(bot, "config", None), "catchbot_enabled", False)),
            "channel_id": int(getattr(getattr(bot, "config", None), "catchbot_channel_id", 0) or 0),
            "running": bool(getattr(catchbot_cog, "catchbot_running", False)) if catchbot_cog else False,
            "next_expected_return_at": float(getattr(catchbot_cog, "next_expected_return_at", 0.0)) if catchbot_cog else 0.0,
            "next_expected_return_text": str(getattr(catchbot_cog, "next_expected_return_text", "") or "") if catchbot_cog else "",
            "last_check_at": float(getattr(catchbot_cog, "last_check_at", 0.0)) if catchbot_cog else 0.0,
            "check_interval_seconds": int(getattr(getattr(bot, "config", None), "catchbot_check_interval_seconds", 900) or 900),
        }

        day_payload = {
            "encounters": int(getattr(bot, "encounters", 0)),
            "catches": int(getattr(bot, "catches", 0)),
            "fish_encounters": int(getattr(bot, "fish_encounters", 0)),
            "fish_catches": int(getattr(bot, "fish_catches", 0)),
            "coins": int(getattr(bot, "coins_earned", 0)),
            "hunt_rarity_catches": dict(getattr(bot, "hunt_rarity_catches", {})),
            "fish_rarity_catches": dict(getattr(bot, "fish_rarity_catches", {})),
            "window_anchor_local": str(getattr(bot, "day_mode_anchor_local", "") or ""),
            "reset_time_local": "12:00",
        }

        snapshot.append(
            {
                "id": str(getattr(bot, "stats_key", "")),
                "username": str(bot.user) if bot.is_ready() and bot.user else "Not ready",
                "ready": bot.is_ready(),
                "hunt_paused": bool(getattr(bot, "pause_hunting", False)),
                "fish_paused": bool(getattr(bot, "pause_fishing", False)),
                "hunt_captcha_active": bool(getattr(bot, "hunting_captcha_active", False)),
                "fish_captcha_active": bool(getattr(bot, "fishing_captcha_active", False)),
                "captcha_active": bool(getattr(bot, "captcha_active", False)),
                "limit": bool(getattr(bot, "limit", False)),
                "hunting_status": str(getattr(bot, "hunting_status", "")),
                "fishing_status": str(getattr(bot, "fishing_status", "")),
                "catchbot_status": str(getattr(bot, "catchbot_status", "Disabled")),
                "berry": berry_info,
                "catchbot": catchbot_info,
                "automations": {
                    "egg_hatching": bool(getattr(getattr(bot, "config", None), "egg_hatching", False)),
                    "auto_hold_egg": bool(getattr(getattr(bot, "config", None), "auto_hold_egg", False)),
                    "berry_enabled": bool(getattr(getattr(bot, "config", None), "berry_enabled", False)),
                    "catchbot_enabled": bool(getattr(getattr(bot, "config", None), "catchbot_enabled", False)),
                    "anti_detection_enabled": bool(getattr(getattr(bot, "config", None), "enable_anti_detection", False)),
                    "human_breaks_enabled": bool(getattr(getattr(bot, "config", None), "human_breaks_enabled", False)),
                    "captcha_auto_answer_enabled": bool(getattr(getattr(bot, "config", None), "captcha_auto_answer_enabled", True)),
                    "captcha_auto_max_attempts": int(getattr(getattr(bot, "config", None), "captcha_auto_max_attempts", 3) or 3),
                    "captcha_manual_allowed_user_ids": list(getattr(getattr(bot, "config", None), "captcha_manual_allowed_user_ids", [])),
                    "captcha_alerts_enabled": bool(getattr(getattr(bot, "config", None), "captcha_alerts_enabled", False)),
                    "captcha_alert_ping": str(getattr(getattr(bot, "config", None), "captcha_alert_ping", "") or ""),
                    "captcha_alert_channel_id": int(getattr(getattr(bot, "config", None), "captcha_alert_channel_id", 0) or 0),
                    "captcha_alert_cooldown_seconds": int(getattr(getattr(bot, "config", None), "captcha_alert_cooldown_seconds", 60) or 60),
                    "max_speed_mode_enabled": bool(getattr(getattr(bot, "config", None), "max_speed_mode_enabled", False)),
                    "super_low_risk_mode_enabled": bool(getattr(getattr(bot, "config", None), "super_low_risk_mode_enabled", False)),
                },
                "captcha": bot.get_cog("Captcha").get_live_state_snapshot() if bot.get_cog("Captcha") is not None else {
                    "hunting": {},
                    "fishing": {},
                    "active_count": 0,
                    "any_active": False,
                },
                "limited_events": dict(getattr(bot, "limited_events", {}) or {}),
                "day": day_payload,
                # Keep legacy key for backward compatibility with existing UI consumers.
                "session": day_payload,
                "lifetime": {
                    "encounters": int(getattr(bot, "lifetime_encounters", 0)),
                    "catches": int(getattr(bot, "lifetime_catches", 0)),
                    "fish_encounters": int(getattr(bot, "lifetime_fish_encounters", 0)),
                    "fish_catches": int(getattr(bot, "lifetime_fish_catches", 0)),
                    "coins": int(getattr(bot, "lifetime_coins_earned", 0)),
                    "hunt_rarity_catches": dict(getattr(bot, "lifetime_hunt_rarity_catches", {})),
                    "fish_rarity_catches": dict(getattr(bot, "lifetime_fish_rarity_catches", {})),
                },
            }
        )

    configured = []
    for idx, token in enumerate(configured_tokens(), start=1):
        account_cfg = get_account_config(token) or {}
        bot = find_bot_by_token(token)
        ready_user = bot.user if bot is not None and bot.is_ready() and bot.user else None
        account_alerts = account_cfg.get("CaptchaAlerts") if isinstance(account_cfg.get("CaptchaAlerts"), dict) else {}
        global_alerts = config.get("CaptchaAlerts") if isinstance(config.get("CaptchaAlerts"), dict) else {}
        configured_ping = str(account_alerts.get("Ping", "") or global_alerts.get("Ping", "")).strip()
        configured_name = str(account_cfg.get("DisplayName", "") or account_cfg.get("Name", "")).strip()
        token_mention = token_user_mention(token)
        display_name = str(ready_user) if ready_user else configured_ping or configured_name or token_mention
        if not display_name:
            display_name = f"account#{idx}"

        configured.append(
            {
                "id": get_stats_key(token),
                "label": display_name,
                "display_name": display_name,
                "mention_name": ready_user.mention if ready_user is not None else configured_ping or token_mention,
                "token_suffix": token[-6:] if len(token) >= 6 else token,
                "hunting_channel_id": int(account_cfg.get("HuntingChannel", 0) or 0),
                "fishing_channel_id": int(account_cfg.get("FishingChannel", 0) or 0),
                "running": bool(bot is not None and bot.is_ready()),
                "connecting": bool(bot is not None and not bot.is_ready() and str(startup_failures.get(token, "")).strip() == ""),
                "username": str(ready_user) if ready_user is not None else "Not ready",
                "last_error": str(startup_failures.get(token, "")),
            }
        )

    return {
        "bots": snapshot,
        "bot_count": len(snapshot),
        "accounts": configured,
        "account_count": len(configured),
    }


async def runtime_action(action: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    target = str(payload.get("target", "")).strip()

    if action == "start_bot":
        ok, message = await start_account_bot(target)
        if not ok:
            return {"ok": False, "error": message}
        return {"ok": True, "message": message}

    # Backward-compatible global actions.
    if not target:
        return await runtime_action_legacy(action)

    token = resolve_configured_token(target)

    if action == "stop_bot":
        if token is None:
            return {"ok": False, "error": f"Configured account not found: {target}"}
        bot = find_bot_by_token(token)
        if bot is None:
            return {"ok": True, "message": "Account is already stopped."}
        username = str(bot.user) if bot.is_ready() and bot.user else "Not ready"
        await stop_bot(bot)
        return {"ok": True, "message": f"Stopped bot for {username}."}

    bot = find_bot_by_target(target)
    if bot is None and token is not None:
        bot = find_bot_by_token(token)
    if bot is None:
        return {"ok": False, "error": f"Bot target not found: {target}"}

    username = str(bot.user) if bot.is_ready() and bot.user else "Not ready"

    if action == "pause_hunt_bot":
        bot.pause_hunting = True
        if bot.config.hunting_channel_id != 0:
            bot.hunting_status = "Paused (manual)"
        if bot.is_ready():
            await bot.log()
        return {"ok": True, "message": f"Paused hunting for {username}."}

    if action == "resume_hunt_bot":
        bot.pause_hunting = False
        if bot.config.hunting_channel_id != 0:
            bot.hunting_status = "Grinding..."
        if bot.is_ready():
            await bot.log()
        return {"ok": True, "message": f"Resumed hunting for {username}."}

    if action == "pause_fish_bot":
        bot.pause_fishing = True
        if bot.config.fishing_channel_id != 0:
            bot.fishing_status = "Paused (manual)"
        if bot.is_ready():
            await bot.log()
        return {"ok": True, "message": f"Paused fishing for {username}."}

    if action == "resume_fish_bot":
        bot.pause_fishing = False
        if bot.config.fishing_channel_id != 0:
            bot.fishing_status = "Grinding..."
        if bot.is_ready():
            await bot.log()
        return {"ok": True, "message": f"Resumed fishing for {username}."}

    if action == "toggle_egg_hatching":
        desired_state_raw = payload.get("enabled")
        if desired_state_raw is None:
            return {"ok": False, "error": "Missing 'enabled' for toggle action."}
        enabled = bool(desired_state_raw)
        bot.config.egg_hatching = enabled
        return {"ok": True, "message": f"Egg hatching {'enabled' if enabled else 'disabled'} for {username}."}

    if action == "toggle_auto_hold_egg":
        desired_state_raw = payload.get("enabled")
        if desired_state_raw is None:
            return {"ok": False, "error": "Missing 'enabled' for toggle action."}
        enabled = bool(desired_state_raw)
        bot.config.auto_hold_egg = enabled
        return {"ok": True, "message": f"Auto hold egg {'enabled' if enabled else 'disabled'} for {username}."}

    if action == "toggle_berry":
        desired_state_raw = payload.get("enabled")
        if desired_state_raw is None:
            return {"ok": False, "error": "Missing 'enabled' for toggle action."}
        enabled = bool(desired_state_raw)
        bot.config.berry_enabled = enabled
        return {"ok": True, "message": f"Berry automation {'enabled' if enabled else 'disabled'} for {username}."}

    if action == "toggle_catchbot":
        desired_state_raw = payload.get("enabled")
        if desired_state_raw is None:
            return {"ok": False, "error": "Missing 'enabled' for toggle action."}
        enabled = bool(desired_state_raw)
        bot.config.catchbot_enabled = enabled

        if enabled and int(getattr(bot.config, "catchbot_channel_id", 0) or 0) == 0:
            bot.config.catchbot_channel_id = int(getattr(bot.config, "hunting_channel_id", 0) or 0)

        if enabled:
            if bot.get_cog("CatchBot") is None:
                await add_cog_compat(bot, CatchBot(bot))
            bot.catchbot_status = "CatchBot enabled"
        else:
            with suppress(Exception):
                removed = bot.remove_cog("CatchBot")
                if inspect.isawaitable(removed):
                    await removed
            bot.catchbot_status = "Disabled"

        ok, err = _update_account_config(
            token,
            lambda account: account.setdefault("CatchBot", {}).update(
                {
                    "Enabled": bool(enabled),
                    "Channel": int(getattr(bot.config, "catchbot_channel_id", 0) or 0),
                    "CheckIntervalSeconds": int(getattr(bot.config, "catchbot_check_interval_seconds", 900) or 900),
                }
            ),
        )
        if not ok:
            return {"ok": False, "error": f"Updated runtime but failed to persist config: {err}"}

        return {"ok": True, "message": f"CatchBot automation {'enabled' if enabled else 'disabled'} for {username}."}

    if action == "toggle_anti_detection":
        desired_state_raw = payload.get("enabled")
        if desired_state_raw is None:
            return {"ok": False, "error": "Missing 'enabled' for toggle action."}
        enabled = bool(desired_state_raw)
        bot.config.enable_anti_detection = enabled
        return {"ok": True, "message": f"Anti-detection {'enabled' if enabled else 'disabled'} for {username}."}

    if action == "toggle_human_breaks":
        desired_state_raw = payload.get("enabled")
        if desired_state_raw is None:
            return {"ok": False, "error": "Missing 'enabled' for toggle action."}
        enabled = bool(desired_state_raw)
        bot.config.human_breaks_enabled = enabled
        return {"ok": True, "message": f"Human breaks {'enabled' if enabled else 'disabled'} for {username}."}

    if action == "toggle_max_speed_mode":
        desired_state_raw = payload.get("enabled")
        if desired_state_raw is None:
            return {"ok": False, "error": "Missing 'enabled' for toggle action."}
        enabled = bool(desired_state_raw)
        bot.config.max_speed_mode_enabled = enabled
        if enabled:
            bot.config.super_low_risk_mode_enabled = False

        if bot.config.max_speed_mode_enabled:
            _apply_max_speed_runtime(bot)
        elif bool(getattr(bot.config, "super_low_risk_mode_enabled", False)):
            _apply_super_low_risk_runtime(bot)
        else:
            _apply_standard_runtime(bot)

        ok, err = _update_account_config(
            token,
            lambda account: account.update(
                {
                    "MaxSpeedMode": bool(bot.config.max_speed_mode_enabled),
                    "SuperLowRiskMode": bool(getattr(bot.config, "super_low_risk_mode_enabled", False)),
                }
            ),
        )
        if not ok:
            return {"ok": False, "error": f"Updated runtime but failed to persist config: {err}"}

        return {
            "ok": True,
            "message": (
                f"Max speed mode {'enabled' if enabled else 'disabled'} for {username}. "
                "Expect more captcha checks when enabled."
            ),
        }

    if action == "toggle_super_low_risk_mode":
        desired_state_raw = payload.get("enabled")
        if desired_state_raw is None:
            return {"ok": False, "error": "Missing 'enabled' for toggle action."}
        enabled = bool(desired_state_raw)
        bot.config.super_low_risk_mode_enabled = enabled
        if enabled:
            bot.config.max_speed_mode_enabled = False

        if bool(getattr(bot.config, "max_speed_mode_enabled", False)):
            _apply_max_speed_runtime(bot)
        elif bot.config.super_low_risk_mode_enabled:
            _apply_super_low_risk_runtime(bot)
        else:
            _apply_standard_runtime(bot)

        ok, err = _update_account_config(
            token,
            lambda account: account.update(
                {
                    "SuperLowRiskMode": bool(bot.config.super_low_risk_mode_enabled),
                    "MaxSpeedMode": bool(getattr(bot.config, "max_speed_mode_enabled", False)),
                }
            ),
        )
        if not ok:
            return {"ok": False, "error": f"Updated runtime but failed to persist config: {err}"}

        return {
            "ok": True,
            "message": (
                f"Super low-risk mode {'enabled' if enabled else 'disabled'} for {username}. "
                "This extreme mode minimizes detection risk at the cost of speed."
            ),
        }

    if action == "toggle_captcha_auto_answer":
        desired_state_raw = payload.get("enabled")
        if desired_state_raw is None:
            return {"ok": False, "error": "Missing 'enabled' for toggle action."}
        enabled = bool(desired_state_raw)
        bot.config.captcha_auto_answer_enabled = enabled
        ok, err = _update_account_config(token, lambda account: account.setdefault("CaptchaAnswerer", {}).update({"AutoAnswerEnabled": bool(enabled)}))
        if not ok:
            return {"ok": False, "error": f"Updated runtime but failed to persist config: {err}"}
        return {"ok": True, "message": f"Captcha auto answer {'enabled' if enabled else 'disabled'} for {username}."}

    if action == "toggle_captcha_alerts":
        desired_state_raw = payload.get("enabled")
        if desired_state_raw is None:
            return {"ok": False, "error": "Missing 'enabled' for toggle action."}
        enabled = bool(desired_state_raw)
        bot.config.captcha_alerts_enabled = enabled
        ok, err = _update_account_config(token, lambda account: account.setdefault("CaptchaAlerts", {}).update({"Enabled": bool(enabled)}))
        if not ok:
            return {"ok": False, "error": f"Updated runtime but failed to persist config: {err}"}
        return {"ok": True, "message": f"Captcha alerts {'enabled' if enabled else 'disabled'} for {username}."}

    if action == "refresh_limited_events":
        limited_cog = bot.get_cog("LimitedEvents")
        if limited_cog is None:
            return {"ok": False, "error": "Limited events cog is unavailable."}
        ok, message = await limited_cog.trigger_manual_refresh(source="runtime_action")
        if not ok:
            return {"ok": False, "error": message}
        return {"ok": True, "message": f"{message} ({username})"}

    if action == "set_captcha_max_attempts":
        raw = payload.get("max_attempts")
        try:
            max_attempts = int(raw)
        except Exception:
            return {"ok": False, "error": "max_attempts must be an integer."}
        if max_attempts <= 0:
            return {"ok": False, "error": "max_attempts must be greater than 0."}

        bot.config.captcha_auto_max_attempts = max_attempts
        captcha_cog = bot.get_cog("Captcha")
        if captcha_cog is not None:
            captcha_cog.max_auto_attempts = max(1, int(max_attempts))

        ok, err = _update_account_config(token, lambda account: account.setdefault("CaptchaAnswerer", {}).update({"MaxAutoAttempts": int(max_attempts)}))
        if not ok:
            return {"ok": False, "error": f"Updated runtime but failed to persist config: {err}"}
        return {"ok": True, "message": f"Captcha max attempts set to {max_attempts} for {username}."}

    if action == "set_captcha_manual_allowed_user_ids":
        raw = payload.get("manual_allowed_user_ids")
        if isinstance(raw, list):
            parts = [str(value).strip() for value in raw]
        else:
            parts = [part.strip() for part in str(raw or "").split(",")]

        parsed: list[int] = []
        for part in parts:
            if not part:
                continue
            if not part.isdigit() or int(part) <= 0:
                return {"ok": False, "error": "manual_allowed_user_ids must be comma-separated positive user IDs."}
            parsed.append(int(part))

        seen: set[int] = set()
        deduped = [uid for uid in parsed if not (uid in seen or seen.add(uid))]
        bot.config.captcha_manual_allowed_user_ids = deduped

        ok, err = _update_account_config(token, lambda account: account.setdefault("CaptchaAnswerer", {}).update({"ManualAnswerAllowedUserIDs": deduped}))
        if not ok:
            return {"ok": False, "error": f"Updated runtime but failed to persist config: {err}"}
        return {"ok": True, "message": f"Captcha manual allowed user IDs updated for {username}."}

    if action == "set_captcha_alert_ping":
        ping = str(payload.get("ping", "") or "").strip()
        bot.config.captcha_alert_ping = ping
        ok, err = _update_account_config(token, lambda account: account.setdefault("CaptchaAlerts", {}).update({"Ping": ping}))
        if not ok:
            return {"ok": False, "error": f"Updated runtime but failed to persist config: {err}"}
        return {"ok": True, "message": f"Captcha alert ping updated for {username}."}

    if action == "captcha_manual_answer":
        answer_text = str(payload.get("answer", "") or "").strip()
        channel_hint = str(payload.get("channel_hint", "") or "").strip()
        captcha_cog = bot.get_cog("Captcha")
        if captcha_cog is None:
            return {"ok": False, "error": "Captcha cog is unavailable."}

        ok, message = await captcha_cog.submit_manual_answer_from_dashboard(answer_text, channel_hint=channel_hint)
        if not ok:
            return {"ok": False, "error": message}
        return {"ok": True, "message": f"{message} ({username})"}

    if action == "captcha_mark_resolved":
        channel_hint = str(payload.get("channel_hint", "") or "").strip()
        captcha_cog = bot.get_cog("Captcha")
        if captcha_cog is None:
            return {"ok": False, "error": "Captcha cog is unavailable."}

        ok, message = await captcha_cog.submit_manual_resolution_from_dashboard(channel_hint=channel_hint)
        if not ok:
            return {"ok": False, "error": message}
        return {"ok": True, "message": f"{message} ({username})"}

    return {"ok": False, "error": f"Unknown targeted action '{action}'."}


async def runtime_action_legacy(action: str) -> dict:
    if action == "pause_all":
        await apply_pause_state(hunting=True, fishing=True)
        return {"ok": True, "message": "Paused hunting and fishing."}

    if action == "resume_all":
        await apply_pause_state(hunting=False, fishing=False)
        return {"ok": True, "message": "Resumed hunting and fishing."}

    if action == "pause_hunt":
        await apply_pause_state(hunting=True)
        return {"ok": True, "message": "Paused hunting."}

    if action == "resume_hunt":
        await apply_pause_state(hunting=False)
        return {"ok": True, "message": "Resumed hunting."}

    if action == "pause_fish":
        await apply_pause_state(fishing=True)
        return {"ok": True, "message": "Paused fishing."}

    if action == "resume_fish":
        await apply_pause_state(fishing=False)
        return {"ok": True, "message": "Resumed fishing."}

    if action == "clear_limit":
        await clear_hunting_limit()
        return {"ok": True, "message": "Cleared limit latch and resumed hunting."}

    if action == "force_hunt":
        dispatched = 0
        for bot in bots:
            if bool(getattr(bot, "hunting_captcha_active", False)) or bot.pause_hunting or bot.limit:
                continue
            command_map = getattr(bot, "hunting_channel_commands", None)
            if not command_map:
                continue
            command = command_map.get("pokemon")
            if command is None:
                continue
            try:
                await command()
                dispatched += 1
            except Exception:
                pass

        return {"ok": True, "message": f"Dispatched hunt command on {dispatched} bot(s)."}

    if action == "force_fight":
        dispatched = 0
        skipped = 0
        inspected = 0
        detected_names: list[str] = []

        exact_priority = [
            "battle",
            "duel",
            "fight",
            "trainer battle",
            "npc battle",
            "battle npc",
            "battle trainer",
        ]
        keyword_priority = ["battle", "duel", "fight", "trainer", "npc"]

        for bot in bots:
            if bool(getattr(bot, "hunting_captcha_active", False)) or bot.pause_hunting or bot.limit:
                skipped += 1
                continue

            command_map = getattr(bot, "hunting_channel_commands", None)
            if not command_map:
                skipped += 1
                continue

            inspected += 1
            selected_command = None

            for command_name in exact_priority:
                candidate = command_map.get(command_name)
                if candidate is not None:
                    selected_command = candidate
                    detected_names.append(command_name)
                    break

            if selected_command is None:
                available_names = [str(name) for name in command_map.keys()]
                for keyword in keyword_priority:
                    matched_name = next((name for name in available_names if keyword in name.lower()), None)
                    if not matched_name:
                        continue
                    candidate = command_map.get(matched_name)
                    if candidate is not None:
                        selected_command = candidate
                        detected_names.append(matched_name)
                        break

            if selected_command is None:
                continue

            try:
                await selected_command()
                dispatched += 1
            except Exception:
                pass

        if dispatched > 0:
            unique_detected = sorted({name for name in detected_names})
            used_preview = ", ".join(unique_detected[:4]) if unique_detected else "unknown"
            return {
                "ok": True,
                "message": (
                    f"Fight probe dispatched on {dispatched} bot(s). "
                    f"Detected commands: {used_preview}."
                ),
            }

        if inspected <= 0:
            return {
                "ok": False,
                "error": (
                    "Fight probe did not run. No eligible bots had usable hunting command maps "
                    f"(skipped: {skipped})."
                ),
            }

        return {
            "ok": False,
            "error": (
                "Fight probe found no battle/fight-like commands in current hunting slash commands. "
                "Open Startup logs and inspect the command list for your target channel."
            ),
        }

    if action == "force_fish":
        dispatched = 0
        for bot in bots:
            if bool(getattr(bot, "fishing_captcha_active", False)) or bot.pause_fishing:
                continue
            command_map = getattr(bot, "fishing_channel_commands", None)
            if not command_map:
                continue
            command = command_map.get("fish spawn")
            if command is None:
                continue
            try:
                await command()
                dispatched += 1
            except Exception:
                pass

        return {"ok": True, "message": f"Dispatched fish command on {dispatched} bot(s)."}

    if action == "force_berry_check":
        dispatched = 0
        for bot in bots:
            if not getattr(bot.config, "berry_enabled", False):
                continue

            try:
                berry_cog = bot.get_cog("BerryGarden")
                if berry_cog is not None and hasattr(berry_cog, "trigger_berry_check"):
                    ok = await berry_cog.trigger_berry_check(source="runtime_action")
                    if ok:
                        dispatched += 1
                    continue

                # Fallback path if cog wasn't loaded but channel exists.
                berry_channel = getattr(bot, "berry_channel", None)
                if berry_channel is not None:
                    await berry_channel.send(";berry")
                    dispatched += 1
            except Exception:
                pass

        return {"ok": True, "message": f"Dispatched berry check on {dispatched} bot(s)."}

    if action == "force_catchbot_check":
        dispatched = 0
        for bot in bots:
            if not bool(getattr(getattr(bot, "config", None), "catchbot_enabled", False)):
                continue

            try:
                cb_cog = bot.get_cog("CatchBot")
                if cb_cog is not None and hasattr(cb_cog, "trigger_catchbot_check"):
                    ok = await cb_cog.trigger_catchbot_check(source="runtime_action")
                    if ok:
                        dispatched += 1
                    continue

                catchbot_channel = getattr(bot, "catchbot_channel", None)
                if catchbot_channel is not None:
                    await catchbot_channel.send(";cb")
                    dispatched += 1
            except Exception:
                pass

        return {"ok": True, "message": f"Dispatched catchbot check on {dispatched} bot(s)."}

    if action == "force_limited_events":
        dispatched = 0
        for bot in bots:
            limited_cog = bot.get_cog("LimitedEvents")
            if limited_cog is None:
                continue
            try:
                ok, _ = await limited_cog.trigger_manual_refresh(source="runtime_action")
                if ok:
                    dispatched += 1
            except Exception:
                pass

        return {"ok": True, "message": f"Triggered limited-events refresh on {dispatched} bot(s)."}

    if action == "stop_all":
        await stop_all_bots()
        return {"ok": True, "message": "Stopped all bots. Use Start All to reconnect."}

    if action == "start_all":
        started = await start_all_bots()
        if started == 0:
            return {"ok": True, "message": "All configured bots are already running."}
        return {"ok": True, "message": f"Starting {started} bot(s)."}

    return {"ok": False, "error": f"Unknown action '{action}'."}


def runtime_action_sync(action: str, payload: dict | None = None) -> dict:
    if main_loop is None:
        return {"ok": False, "error": "Main event loop unavailable."}

    future = asyncio.run_coroutine_threadsafe(runtime_action(action, payload), main_loop)
    try:
        return future.result(timeout=15)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def headless_desktop_mode() -> bool:
    """Electron-spawned Python: stdin is not a real console; interactive Command> will break or spin."""
    if os.environ.get("POKEGRINDER_SKIP_TERMINAL") == "1":
        return True
    if os.environ.get("ELECTRON_MANAGE_BACKEND") == "1":
        return True
    try:
        return not sys.stdin.isatty()
    except (AttributeError, ValueError, OSError):
        return True


def get_diagnostics_payload() -> dict:
    """Safe for JSON: no raw tokens (keys are stats_key hashes)."""
    from datetime import timezone

    setup_runtime_file_logging()
    failures = {get_stats_key(t): msg for t, msg in startup_failures.items()}
    return {
        "ok": True,
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "executable": sys.executable,
        "cwd": os.getcwd(),
        "headless": headless_desktop_mode(),
        "main_loop_ready": main_loop is not None,
        "bots_count": len(bots),
        "env": {
            "ELECTRON_MANAGE_BACKEND": os.environ.get("ELECTRON_MANAGE_BACKEND"),
            "POKEGRINDER_SKIP_TERMINAL": os.environ.get("POKEGRINDER_SKIP_TERMINAL"),
        },
        "runtime_log_path": str(RUNTIME_LOG_PATH.resolve()),
        "log_tail": tail_log_file(100),
        "startup_failures_by_account_id": failures,
    }


def ensure_dashboard_started() -> None:
    global dashboard_thread
    if dashboard_thread and dashboard_thread.is_alive():
        return

    configure_diagnostics_provider(get_diagnostics_payload)
    configure_runtime_handlers(get_runtime_snapshot, runtime_action_sync)
    import ui.server as _ui_server_mod

    runtime_info_log("ui.server loaded from %s (if /api/diagnostics 404s, another app may own port 8787)", _ui_server_mod.__file__)
    dashboard_thread = threading.Thread(
        target=run_dashboard,
        kwargs={"host": "127.0.0.1", "port": 8787},
        daemon=True,
    )
    dashboard_thread.start()
    print("Dashboard running at http://127.0.0.1:8787")
    runtime_info_log("HTTP dashboard thread started (Flask on 127.0.0.1:8787)")


async def terminal_controls() -> None:
    print_control_help()

    while True:
        if shutdown_event is not None and shutdown_event.is_set():
            return

        try:
            raw = await asyncio.to_thread(input, "\nCommand> ")
        except EOFError:
            await asyncio.sleep(1)
            continue

        command = raw.strip().lower()

        if command in {"", "help", "h", "?"}:
            print_control_help()
            continue

        if command in {"status", "s"}:
            print_runtime_status()
            continue

        if command in {"pause", "p"}:
            await apply_pause_state(hunting=True, fishing=True)
            print("Paused hunting and fishing.")
            continue

        if command in {"resume", "r"}:
            await apply_pause_state(hunting=False, fishing=False)
            print("Resumed hunting and fishing.")
            continue

        if command in {"pause hunt", "ph"}:
            await apply_pause_state(hunting=True)
            print("Paused hunting.")
            continue

        if command in {"resume hunt", "rh"}:
            await apply_pause_state(hunting=False)
            print("Resumed hunting.")
            continue

        if command in {"pause fish", "pf"}:
            await apply_pause_state(fishing=True)
            print("Paused fishing.")
            continue

        if command in {"resume fish", "rf"}:
            await apply_pause_state(fishing=False)
            print("Resumed fishing.")
            continue

        if command in {"clear limit", "cl"}:
            await clear_hunting_limit()
            print("Cleared limit latch and resumed hunting.")
            continue

        if command in {"start all", "sa"}:
            started = await start_all_bots()
            if started == 0:
                print("All configured bots are already running.")
            else:
                print(f"Starting {started} bot(s).")
            continue

        if command in {"exit", "quit", "q", "stop"}:
            print("Stopping bots and saving stats...")
            await stop_all_bots()
            return

        print("Unknown command. Type 'help' to see available commands.")


async def start() -> None:
    global main_loop, shutdown_event
    main_loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()
    ensure_dashboard_started()
    hl = headless_desktop_mode()
    runtime_info_log("Main asyncio loop running; headless=%s (if true, use dashboard to Start bot)", hl)
    if hl:
        print(
            "[Runtime] Headless mode (no terminal commands). "
            "Control the bot from the dashboard at http://127.0.0.1:8787 — start/stop accounts there."
        )
        await shutdown_event.wait()
        return
    await terminal_controls()


# ProactorEventLoop + Discord websockets sometimes raises OSError(22) on Windows.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

asyncio.run(start())
