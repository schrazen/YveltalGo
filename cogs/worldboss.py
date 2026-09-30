import asyncio
import json
import re
import sqlite3
from pathlib import Path
from random import randint
from time import time
from typing import Any, Dict, List, Optional

from discord import InvalidData, Message
from discord.ext import commands, tasks

from cogs.startup import Config
from modules.battle_state import ParsedBattleState, normalize, parse_battle_state
from modules.captcha_gate import is_captcha_active, is_in_battle
from modules.server_guard import is_channel_in_required_server, is_message_in_required_server
from modules.pokemeow_battle_parser import parse_pokemeow_battle_events
from modules.worldboss_estimator import (
    WorldBossEstimator,
    parse_eternamax_progress,
    parse_future_boss_seconds,
    parse_last_defeated_seconds,
    parse_vote_progress,
)
from modules.worldboss_strategies import (
    WORLD_BOSS_STRATEGIES,
    WorldBossActionDecider,
    WorldBossTeamBuilder,
    get_boss_strategy,
)
from modules.smart_advisor import smart_advisor

POKEMEOW_APP_ID = 664508672713424926
MIN_WB_FIGHT_START_BUFFER_SECONDS = 4.0
WB_TOO_EARLY_RETRY_SECONDS = 8.0
WB_FIGHT_REFRESH_COOLDOWN_SECONDS = 10.0

_WB_COUNTDOWN_IN_PATTERN = re.compile(
    r"\bbattle begins(?:\s+automatically)?\s+in\s+(\d+)\s+minutes?\b",
    re.IGNORECASE,
)
_WB_COUNTDOWN_AGO_PATTERN = re.compile(
    r"\bbattle begins(?:\s+automatically)?\s+(\d+)\s+minutes?\s+ago\b",
    re.IGNORECASE,
)
_WB_COUNTDOWN_STARTS_PATTERN = re.compile(
    r"\bbattle starts automatically in\s+(\d+)\s+minutes?\b",
    re.IGNORECASE,
)
_WB_COUNTDOWN_APPROX_PATTERN = re.compile(
    r"\bin\s+approx\.?\s+(?:(\d+)\s+minutes?\s+)?(\d+)\s+seconds?\b",
    re.IGNORECASE,
)
_WB_COUNTDOWN_TIMER_PATTERN = re.compile(
    r"worldboss fight in:\s*\*\*(\d+)s\*\*",
    re.IGNORECASE,
)


class WorldBoss(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.config: Config = bot.config
        self.decider = WorldBossActionDecider(
            danger_hp_percent=int(getattr(self.config, "wb_danger_hp_percent", 40) or 40)
        )
        self.estimator = WorldBossEstimator()
        self.last_action_signature = ""
        self.last_action_at = 0.0
        self.last_fight_attempt_at = 0.0
        self.last_fight_refresh_at = 0.0
        self.last_world_boss_probe_at = 0.0
        self.restart_requested = False
        self.last_rejoin_at = 0.0
        self.last_forfeit_at = 0.0
        self.last_fight_request_message_id = 0
        self.pending_fight_task: Optional[asyncio.Task] = None
        self.pending_fight_message_id = 0
        self.pending_fight_due_at = 0.0
        self.pending_countdown_message: Optional[Message] = None
        self.pending_countdown_task: Optional[asyncio.Task] = None
        self.last_enemy_name = ""
        self.last_enemy_types: List[str] = []
        self._pokemon_type_cache: Dict[str, List[str]] = {}
        self._pokeapi_db_path = Path(__file__).resolve().parents[1] / "pokeapi_cache.sqlite3"
        self.bot.world_boss_active = False
        self.config.world_boss_enabled = True
        self.bot.world_boss_status = "WorldBoss auto: ON"

        if self._get_target_channel_id() != 0:
            try:
                self.adaptive_probe_loop.start()
            except RuntimeError:
                pass

    def _get_target_channel_id(self) -> int:
        return int(
            getattr(self.config, "world_boss_channel_id", 0)
            or getattr(self.config, "hunting_channel_id", 0)
            or getattr(self.config, "fishing_channel_id", 0)
            or 0
        )

    def cog_unload(self) -> None:
        if self.adaptive_probe_loop.is_running():
            self.adaptive_probe_loop.cancel()
        self._cancel_pending_fight_task()

    @tasks.loop(seconds=15.0)
    async def adaptive_probe_loop(self) -> None:
        """Periodic loop that dynamically evaluates if an adaptive maintenance probe (;wb) should be dispatched."""
        if not bool(getattr(self.config, "world_boss_enabled", False)):
            return

        channel_id = self._get_target_channel_id()
        if channel_id == 0:
            return

        if getattr(self.bot, "world_boss_active", False):
            return

        if is_captcha_active(self.bot, channel_id):
            return

        if is_in_battle(self.bot) or bool(getattr(self.bot, "autofight_active", False)):
            return

        now = time()
        should_probe, reason = self.estimator.should_probe(now)
        if not should_probe:
            return

        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except Exception:
                return

        if channel is None:
            return

        if not is_channel_in_required_server(self.bot, channel):
            return

        self.estimator.record_probe(now)
        jitter = randint(500, max(600, int(getattr(self.config, "suspicion_avoidance", 250) or 250))) / 1000.0
        await asyncio.sleep(jitter)
        try:
            print(f"[WorldBoss] Adaptive maintenance probe sent (;wb) -> {reason} | {self.estimator.get_status_summary(now)}")
            if not self.config.wb_dry_run:
                await channel.send(";wb")
        except Exception as exc:
            pass

    @adaptive_probe_loop.before_loop
    async def before_adaptive_probe_loop(self) -> None:
        if hasattr(self.bot, "wait_until_ready"):
            await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        self.config.world_boss_enabled = True
        self.bot.world_boss_status = "WorldBoss auto: ON"
        target_channel = self._get_target_channel_id()
        if (
            target_channel != 0
            and not self.adaptive_probe_loop.is_running()
        ):
            print(f"[WorldBoss] Adaptive estimation & probe loop started for channel {target_channel}...")
            try:
                self.adaptive_probe_loop.start()
            except RuntimeError:
                pass

    def _in_world_boss_channel(self, channel_id: int) -> bool:
        target_id = self._get_target_channel_id()
        return target_id != 0 and channel_id == target_id

    @staticmethod
    def _is_pokemeow_message(message: Message) -> bool:
        if not message.author:
            return False
        return message.author.id == POKEMEOW_APP_ID

    @staticmethod
    def _toggle_command(content: str) -> str:
        lowered = normalize(content)
        if lowered in {";wb auto on", ";wba on", ";worldboss on"}:
            return "on"
        if lowered in {";wb auto off", ";wba off", ";worldboss off"}:
            return "off"
        if lowered in {";wb auto", ";wb auto status", ";wba status", ";worldboss status"}:
            return "status"
        if lowered.startswith(";wb team") or lowered.startswith(";wba team") or lowered.startswith(";wb comp"):
            return "team"
        if lowered.startswith(";wb equip") or lowered.startswith(";wba equip"):
            return "equip"
        return ""

    @staticmethod
    def _log_check(step: str, **details) -> None:
        payload = {k: v for k, v in details.items() if v is not None}
        try:
            print(f"[WorldBoss] {step}: {payload}")
        except Exception:
            pass

    async def _resolve_actionable_message(self, message: Message) -> Message:
        """Return message carrying action buttons if available."""
        if getattr(message, "components", None):
            return message

        try:
            fresh_copy = await message.channel.fetch_message(int(getattr(message, "id", 0) or 0))
            if isinstance(fresh_copy, Message) and getattr(fresh_copy, "components", None):
                return fresh_copy
        except Exception:
            pass

        reference = getattr(message, "reference", None)
        if reference is not None:
            resolved = getattr(reference, "resolved", None)
            if isinstance(resolved, Message) and getattr(resolved, "components", None):
                return resolved

            referenced_id = int(getattr(reference, "message_id", 0) or 0)
            if referenced_id > 0:
                try:
                    fetched = await message.channel.fetch_message(referenced_id)
                    if isinstance(fetched, Message) and getattr(fetched, "components", None):
                        return fetched
                except Exception:
                    pass

        return message

    def _cancel_pending_fight_task(self) -> None:
        task = self.pending_fight_task
        if task is not None and not task.done():
            task.cancel()
        self.pending_fight_task = None
        self.pending_fight_message_id = 0
        self.pending_fight_due_at = 0.0
        self._cancel_pending_countdown_task()

    def _cancel_pending_countdown_task(self) -> None:
        task = self.pending_countdown_task
        if task is not None and not task.done():
            task.cancel()
        self.pending_countdown_task = None
        self.pending_countdown_message = None

    def _reset_fight(self) -> None:
        self.decider.reset()
        self.last_action_signature = ""
        self.restart_requested = False
        self.last_fight_request_message_id = 0
        self.last_fight_attempt_at = 0.0
        self.last_world_boss_probe_at = 0.0
        self.bot.world_boss_active = False
        self.bot.pause_hunting = False
        self.bot.pause_fishing = False
        self._cancel_pending_fight_task()

    def _extract_enemy_name(self, worldboss: dict, message_blob: str) -> str:
        raw = normalize(str(worldboss.get("boss_name", "") or ""))
        if raw and raw not in {"current health", "boss", ""}:
            return raw

        title = normalize(str(worldboss.get("title", "") or ""))
        if title:
            title = re.sub(r"\bchallenge$", "", title).strip()
            title = re.sub(r"^<:[^>]+>\s*", "", title).strip()
            title = re.sub(r"\s+", " ", title).strip()
            if title:
                return title

        match = re.search(r"world boss challenge:\s*([a-z0-9\- ]+)", message_blob)
        if match:
            return normalize(match.group(1))

        # Check against all known 34 bosses
        for b_key, b_strat in WORLD_BOSS_STRATEGIES.items():
            if b_key in message_blob or b_strat.boss_name.lower() in message_blob:
                return b_strat.boss_name

        return ""

    def _extract_fight_delay_seconds(self, message_blob: str) -> Optional[int]:
        lowered = normalize(message_blob)

        # Timer format e.g. "WorldBoss fight in: **78s**"
        timer_match = _WB_COUNTDOWN_TIMER_PATTERN.search(lowered)
        if timer_match:
            try:
                return int(timer_match.group(1))
            except Exception:
                pass

        approx_match = _WB_COUNTDOWN_APPROX_PATTERN.search(lowered)
        if approx_match:
            minutes_text = approx_match.group(1)
            seconds_text = approx_match.group(2)
            try:
                minutes = int(minutes_text) if minutes_text is not None else 0
                seconds = int(seconds_text)
            except Exception:
                minutes = 0
                seconds = 0
            return max(0, minutes * 60 + seconds)

        for pattern in (_WB_COUNTDOWN_IN_PATTERN, _WB_COUNTDOWN_STARTS_PATTERN, _WB_COUNTDOWN_AGO_PATTERN):
            match = pattern.search(lowered)
            if not match:
                continue
            try:
                minutes = int(match.group(1))
            except Exception:
                continue
            if pattern is _WB_COUNTDOWN_AGO_PATTERN:
                return 0
            return max(0, minutes * 60)

        return None

    async def _dispatch_fight_after_delay(self, channel, message_id: int, delay_seconds: int) -> None:
        try:
            self._log_check("fight_schedule", matched=True, message_id=message_id, delay_seconds=delay_seconds)
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds)

            if not bool(getattr(self.config, "world_boss_enabled", False)):
                return
            if message_id != int(self.pending_fight_message_id or 0):
                return

            await asyncio.sleep(randint(0, self.config.suspicion_avoidance) / 1000)
            self.last_fight_attempt_at = time()
            self.bot.world_boss_active = True
            self.bot.pause_hunting = True
            self.bot.pause_fishing = True

            if not is_channel_in_required_server(self.bot, channel):
                self._log_check("fight_schedule", matched=False, reason="channel_not_in_required_server")
                return

            wb_team = getattr(self.config, "world_boss_team_preset", "wb") or "wb"
            if not self.config.wb_dry_run:
                try:
                    await channel.send(f";team use {wb_team}")
                    await asyncio.sleep(1.2)
                except Exception:
                    pass
                await channel.send(";wb fight")

            self.bot.last_wb_action = time()
            self.bot.world_boss_status = "Starting WorldBoss fight"
            self.last_fight_request_message_id = message_id
            self.pending_fight_task = None
            self.pending_fight_message_id = 0
            self.pending_fight_due_at = 0.0
            self._cancel_pending_countdown_task()
            await self.bot.log()
            self._log_check("fight_schedule", matched=True, reason="sent_command", message_id=message_id)
        except asyncio.CancelledError:
            self._log_check("fight_schedule", matched=False, reason="cancelled", message_id=message_id)
        except Exception as exc:
            self._log_check("fight_schedule", matched=False, reason="send_failed", error=str(exc))

    def _schedule_fight_start(self, message: Message, message_blob: str) -> bool:
        countdown_seconds = self._extract_fight_delay_seconds(message_blob)
        if countdown_seconds is None:
            return False

        message_id = int(getattr(message, "id", 0) or 0)
        if message_id > 0 and message_id == int(self.last_fight_request_message_id or 0):
            return True

        self._cancel_pending_fight_task()
        self.pending_fight_message_id = message_id
        self.pending_fight_due_at = time() + float(countdown_seconds)
        self.pending_fight_task = asyncio.create_task(
            self._dispatch_fight_after_delay(message.channel, message_id, countdown_seconds)
        )
        self.bot.last_wb_action = time()
        return True

    def _find_register_button(self, message: Message):
        buttons = []
        for component in getattr(message, "components", []) or []:
            nested = getattr(component, "children", None) or getattr(component, "items", None)
            for child in nested or []:
                if not bool(getattr(child, "disabled", False)):
                    buttons.append(child)

        for button in buttons:
            label = normalize(str(getattr(button, "label", "") or ""))
            custom_id = normalize(str(getattr(button, "custom_id", "") or ""))
            # Exclude donation, patron, perk, vote reward buttons completely
            if any(bad in label or bad in custom_id for bad in ("support", "perk", "gift", "subscription", "vote")):
                continue
            if any(tok in label or tok in custom_id for tok in ("register", "join", "fight", "world_boss", "wb_")):
                return button

        return None

    async def _try_start_fight(self, message: Message, message_blob: str) -> bool:
        trigger_texts = (
            "successfully registered your",
            "the battle starts automatically in 5 minutes",
            "type ;wb fight to start",
            "you are registered for this fight",
            "battle begins in 5 minutes",
            "start the battle using ;wb fight",
            "the battle is underway",
            "a world boss fight is underway",
            "fight is underway",
            "challenge is underway",
            "world boss challenge:",
            "get ready!",
        )
        matched_trigger = next((token for token in trigger_texts if token in message_blob), "")
        if not matched_trigger:
            return False

        message_id = int(getattr(message, "id", 0) or 0)
        if message_id > 0 and message_id == int(self.last_fight_request_message_id or 0):
            return False

        countdown_seconds = self._extract_fight_delay_seconds(message_blob)
        if countdown_seconds is not None:
            delay_seconds = max(MIN_WB_FIGHT_START_BUFFER_SECONDS, float(countdown_seconds) + MIN_WB_FIGHT_START_BUFFER_SECONDS)
        elif "underway" in matched_trigger or "challenge:" in matched_trigger:
            # Battle is actively underway: enter immediately
            delay_seconds = 1.0
        else:
            delay_seconds = MIN_WB_FIGHT_START_BUFFER_SECONDS

        self.bot.world_boss_active = True
        self.bot.pause_hunting = True
        self.bot.pause_fishing = True

        self._cancel_pending_fight_task()
        self.pending_fight_message_id = message_id
        self.pending_fight_due_at = time() + delay_seconds
        self.pending_fight_task = asyncio.create_task(
            self._dispatch_fight_after_delay(message.channel, message_id, int(delay_seconds))
        )
        self.last_fight_request_message_id = message_id
        self.bot.last_wb_action = time()
        self.bot.world_boss_status = "WorldBoss fight scheduled"
        await self.bot.log()
        return True

    @staticmethod
    def _collect_all_text(message: Message) -> str:
        parts: list[str] = []
        if getattr(message, "content", None):
            parts.append(message.content)
        for embed in getattr(message, "embeds", []) or []:
            if getattr(embed, "title", None):
                parts.append(embed.title)
            if getattr(embed, "description", None):
                parts.append(embed.description)
            if getattr(embed, "author", None) and getattr(embed.author, "name", None):
                parts.append(embed.author.name)
            if getattr(embed, "footer", None) and getattr(embed.footer, "text", None):
                parts.append(embed.footer.text)
            for f in getattr(embed, "fields", []) or []:
                if getattr(f, "name", None):
                    parts.append(f.name)
                if getattr(f, "value", None):
                    parts.append(f.value)
        return " ".join(parts)

    def _looks_like_world_boss(self, message: Message) -> bool:
        if not is_message_in_required_server(self.bot, message):
            return False

        channel_id = int(getattr(getattr(message, "channel", None), "id", 0) or 0)
        if not self._in_world_boss_channel(channel_id):
            return False

        all_text = normalize(self._collect_all_text(message))
        if any(
            token in all_text
            for token in (
                "world boss",
                ";wb",
                "boss challenge",
                "spawn requirement",
                "last defeated",
                "eternamax",
                "select a pokemon switch button to complete baton pass",
            )
        ):
            return True

        if getattr(message, "components", None):
            for component in message.components:
                nested = getattr(component, "children", None) or getattr(component, "items", None)
                for child in nested or []:
                    if not bool(getattr(child, "disabled", False)):
                        label = normalize(str(getattr(child, "label", "") or ""))
                        custom_id = normalize(str(getattr(child, "custom_id", "") or ""))
                        if "wb" in custom_id or "world_boss" in custom_id:
                            return True

        return False

    async def _handle_candidate_message(self, message: Message) -> None:
        if not message or not message.channel:
            return

        # STRICT ISOLATION GUARD: Reject messages from any other server or channel immediately!
        if not is_message_in_required_server(self.bot, message):
            return

        channel_id = int(getattr(message.channel, "id", 0) or 0)
        if not self._in_world_boss_channel(channel_id):
            return

        if message.content:
            toggle = self._toggle_command(message.content)
            if toggle == "on":
                self.config.world_boss_enabled = True
                self.restart_requested = False
                self.bot.world_boss_status = "WorldBoss auto: ON"
                await self.bot.log()
                if (
                    int(getattr(self.config, "world_boss_channel_id", 0) or 0) != 0
                    and not self.adaptive_probe_loop.is_running()
                ):
                    try:
                        self.adaptive_probe_loop.start()
                    except RuntimeError:
                        pass
                await message.channel.send("WorldBoss auto: ON")
                return
            if toggle == "off":
                self.config.world_boss_enabled = False
                self.restart_requested = False
                self._reset_fight()
                self.bot.world_boss_status = "WorldBoss auto: OFF"
                await self.bot.log()
                await message.channel.send("WorldBoss auto: OFF")
                return
            if toggle == "status":
                status = "ON" if bool(getattr(self.config, "world_boss_enabled", False)) else "OFF"
                boss = self.decider.current_boss_name or "None"
                active = self.decider.active_pokemon_name or "None"
                est_summary = self.estimator.get_status_summary()
                await message.channel.send(
                    f"WorldBoss auto: {status} | Boss: {boss} | Active: {active}\n"
                    f"Estimation: {est_summary}"
                )
                return
            if toggle == "team":
                parts = message.content.strip().split(maxsplit=2)
                target_boss = parts[2].strip() if len(parts) > 2 else (self.last_enemy_name or "Gigantamax-Pikachu")
                guide = WorldBossTeamBuilder.format_team_guide(target_boss)
                wb_team = getattr(self.config, "world_boss_team_preset", "wb")
                guide += f"\n*To quickly equip your favorite team, type:* `;team use {wb_team}`"
                await message.channel.send(guide)
                return
            if toggle == "equip":
                parts = message.content.strip().split(maxsplit=2)
                wb_team = getattr(self.config, "world_boss_team_preset", "wb")
                target_team = parts[2].strip() if len(parts) > 2 else wb_team
                if not self.config.wb_dry_run:
                    await message.channel.send(f";team use {target_team}")
                else:
                    await message.channel.send(f"[Dry Run] Would execute: ;team use {target_team}")
                return

        if not self._is_pokemeow_message(message):
            return

        if not self._looks_like_world_boss(message):
            return

        self.bot.last_wb_action = time()
        actionable_message = await self._resolve_actionable_message(message)

        message_blob = normalize(self._collect_all_text(actionable_message or message))

        enemy_name = self._extract_enemy_name({}, message_blob)
        if enemy_name:
            self.last_enemy_name = enemy_name

        # Check vote progress (e.g. 201 / 250 ;votes)
        vote_data = parse_vote_progress(message_blob)
        et_data = parse_eternamax_progress(message_blob)
        if vote_data:
            curr_v, targ_v = vote_data
            self.estimator.record_vote_status(curr_v, targ_v, eternamax_data=et_data)
            print(f"[WorldBoss] Updated vote telemetry: {curr_v}/{targ_v} votes | {self.estimator.get_status_summary()}")

        # Check last defeated time (e.g. 37 minutes ago)
        last_def_secs = parse_last_defeated_seconds(message_blob)
        if last_def_secs is not None:
            self.estimator.record_last_defeated(last_def_secs)
            print(f"[WorldBoss] Calibrated last defeated time: {last_def_secs // 60}m ago")

        # Check for explicit future countdown from PokéMeow status response
        future_secs = parse_future_boss_seconds(message_blob)
        if future_secs:
            self.estimator.record_explicit_countdown(future_secs)

        # Explicit confirmation: no boss is active. Do not trigger false spawn, registration, or wipe votes.
        if "there is no active world boss" in message_blob or "no active world boss" in message_blob:
            self.bot.world_boss_active = False
            self.bot.world_boss_status = f"Tracking ({self.estimator.get_status_summary()})"
            await self.bot.log()
            return

        # Only proceed to automated battle actions (register, fight, move select) if world_boss_enabled is True
        if not bool(getattr(self.config, "world_boss_enabled", False)):
            return

        # Check for pending rewards needing to be claimed before registration
        if "rewards to claim" in message_blob or "claim your rewards" in message_blob:
            now = time()
            if now - getattr(self, "last_claim_attempt_at", 0.0) > 10.0:
                self.last_claim_attempt_at = now
                print("[WorldBoss] Pending rewards detected. Sending ';wb claim'...")
                try:
                    await asyncio.sleep(randint(600, 1500) / 1000.0)
                    await message.channel.send(";wb claim")
                    self.bot.world_boss_status = "Claimed WB rewards"
                    await self.bot.log()
                except Exception as exc:
                    print(f"[WorldBoss] Failed claiming rewards: {exc}")

        # Check if vote threshold is met (e.g. 250 / 250 ;votes)
        if vote_data and vote_data[0] >= vote_data[1] and vote_data[1] > 0:
            now = time()
            if now - getattr(self, "last_threshold_sign_in_at", 0.0) > 25.0:
                self.last_threshold_sign_in_at = now
                print(f"[WorldBoss] Vote threshold achieved ({vote_data[0]}/{vote_data[1]})! Locking grinding and initiating sign in...")
                self.bot.world_boss_active = True
                self.bot.pause_hunting = True
                self.bot.pause_fishing = True
                self.bot.world_boss_status = f"Threshold Met ({vote_data[0]}/{vote_data[1]}) - Registering"
                await self.bot.log()
                reg_button = self._find_register_button(actionable_message)
                if reg_button is not None and not self.config.wb_dry_run:
                    try:
                        await asyncio.sleep(randint(500, 1500) / 1000.0)
                        await reg_button.click()
                    except Exception:
                        pass
                elif not self.config.wb_dry_run:
                    try:
                        await asyncio.sleep(randint(800, 1800) / 1000.0)
                        await message.channel.send(";wb fight")
                    except Exception:
                        pass

        # 1. Registration prompts
        if any(
            token in message_blob
            for token in (
                "register now",
                "you have not yet registered",
                "you are not registered",
                "registration is open",
                "register for this fight",
                "register to fight",
                "a world boss has spawned",
                "a new world boss has appeared",
                "spawn requirement has been met",
            )
        ):
            self.estimator.record_spawn(self.last_enemy_name or "WorldBoss")
            self.bot.world_boss_active = True
            self.bot.pause_hunting = True
            self.bot.pause_fishing = True
            register_button = self._find_register_button(actionable_message)
            if register_button is not None and not self.config.wb_dry_run:
                try:
                    await asyncio.sleep(randint(500, 1500) / 1000.0)
                    await register_button.click()
                    self.bot.world_boss_status = "Registering for WorldBoss"
                    await self.bot.log()
                except (InvalidData, Exception):
                    pass
            elif not self.config.wb_dry_run:
                try:
                    await asyncio.sleep(randint(800, 1800) / 1000.0)
                    await message.channel.send(";wb fight")
                    self.bot.world_boss_status = "Sent ;wb fight to register"
                    await self.bot.log()
                except Exception:
                    pass

        # 2. Countdown parsing & Scheduling
        if self._schedule_fight_start(message, message_blob):
            countdown_seconds = self._extract_fight_delay_seconds(message_blob)
            self.estimator.record_spawn(self.last_enemy_name or "WorldBoss", countdown_seconds)
            self.bot.world_boss_status = "WorldBoss fight scheduled"
            await self.bot.log()
            return

        if await self._try_start_fight(message, message_blob):
            return

        # 3. Terminal detection without buttons
        if "your team has been defeated" in message_blob or "you lost the battle" in message_blob:
            self._log_check("terminal", matched=True, outcome="loss")
            self.estimator.record_completion(self.last_enemy_name or "WorldBoss", "loss")
            self.bot.world_boss_status = "WorldBoss battle lost"
            self._reset_fight()
            await self.bot.log()
            return

        if "world boss has been defeated" in message_blob or "you won the battle" in message_blob:
            self._log_check("terminal", matched=True, outcome="win")
            self.estimator.record_completion(self.last_enemy_name or "WorldBoss", "win")
            self.bot.world_boss_status = "WorldBoss defeated!"
            self._reset_fight()
            await self.bot.log()
            return

        # 4. Check for active battle state
        all_known_names = [
            "Smeargle", "Shiny Smeargle", "Mega-Gardevoir", "Mega Gardevoir",
            "Swoobat", "Necrozma-Ultra", "Necrozma Ultra", "Mega-Mewtwo-Y", "Mega Mewtwo Y",
            "Poliwrath", "Mew", "Malamar", "Shuckle", "Vaporeon", "Gliscor",
            "Jolteon", "Lanturn", "Tapu Lele", "Tapu-Lele", "Krookodile", "Sylveon", "Corviknight", "Blaziken",
            "Incineroar", "Umbreon", "Bellossom", "Gmax-Inteleon", "Gmax-Charizard",
            "Calyrex-Shadow", "Rayquaza-Mega", "Groudon-Primal", "Kyogre-Primal"
        ]
        state = parse_battle_state(actionable_message, all_known_names)
        events, summary = parse_pokemeow_battle_events(actionable_message)
        worldboss = summary.get("worldboss", {}) if isinstance(summary, dict) else {}

        boss_name = self._extract_enemy_name(worldboss, message_blob)
        if boss_name:
            self.last_enemy_name = boss_name

        if state.terminal_win:
            self.estimator.record_completion(self.last_enemy_name or "WorldBoss", "win")
            self.bot.world_boss_status = "WorldBoss defeated!"
            self._reset_fight()
            await self.bot.log()
            return

        if state.terminal_loss:
            self.estimator.record_completion(self.last_enemy_name or "WorldBoss", "loss")
            self.bot.world_boss_status = "WorldBoss battle lost"
            self._reset_fight()
            await self.bot.log()
            return

        # If we have move buttons or switch buttons, we are in an active combat turn!
        if state.move_buttons or state.switch_buttons:
            self._cancel_pending_fight_task()
            self.bot.world_boss_active = True
            self.bot.pause_hunting = True
            self.bot.pause_fishing = True

            active_pokemon = state.active_pokemon or worldboss.get("active_pokemon") or "Pokemon"
            self.decider.update_context(self.last_enemy_name, active_pokemon)

            is_baton_pass_prompt = "complete baton pass" in message_blob

            move_list = list(state.move_buttons.values()) if isinstance(state.move_buttons, dict) else list(state.move_buttons or [])
            switch_list = list(state.switch_buttons.values()) if isinstance(state.switch_buttons, dict) else list(state.switch_buttons or [])

            # Filter out forfeit / cancel buttons completely
            move_list = [
                b for b in move_list
                if not any(token in (str(getattr(b, "label", "") or "") + " " + str(getattr(b, "custom_id", "") or "")).lower() for token in ["forfeit", "cancel", "run", "surrender"])
            ]

            button, action_name, reason = self.decider.decide_action(
                move_buttons=move_list,
                switch_buttons=switch_list,
                ally_hp_percent=state.ally_hp_percent,
                is_baton_pass_prompt=is_baton_pass_prompt,
            )

            if button is None and (move_list or switch_list):
                move_names = [str(getattr(b, "label", "") or getattr(b, "custom_id", "")) for b in move_list]
                switch_names = [str(getattr(b, "label", "") or getattr(b, "custom_id", "")) for b in switch_list]
                ai_adv = await smart_advisor.advise_combat_action(
                    boss_name=self.last_enemy_name,
                    active_pokemon=active_pokemon,
                    ally_hp_percent=state.ally_hp_percent,
                    available_moves=move_names,
                    available_switches=switch_names,
                    recent_log=message_blob[-200:],
                )
                target = str(ai_adv.get("target", "")).lower()
                for b in (move_list + switch_list):
                    label = str(getattr(b, "label", "") or "").lower()
                    cid = str(getattr(b, "custom_id", "") or "").lower()
                    if (target and target in label) or (target and target in cid) or (label and label in target):
                        button = b
                        action_name = f"AI_{ai_adv.get('type', 'action')}:{getattr(b, 'label', '')}"
                        reason = ai_adv.get("reason", "AI tactical decision")
                        break

            if button is not None:
                # Include boss HP and ally HP in signature to prevent dropping consecutive turns with same move!
                action_signature = f"{actionable_message.id}:{state.boss_hp_percent}:{state.ally_hp_percent}:{action_name}"
                now = time()
                if action_signature == self.last_action_signature and (now - self.last_action_at) < 1.5:
                    return

                self.last_action_signature = action_signature
                self.last_action_at = now
                self.bot.last_wb_action = now
                self.bot.world_boss_status = f"{active_pokemon}: {action_name} ({reason})"
                await self.bot.log()

                self._log_check(
                    "action_execute",
                    boss=self.last_enemy_name,
                    active=active_pokemon,
                    action=action_name,
                    reason=reason,
                )

                if not self.config.wb_dry_run:
                    try:
                        delay = randint(200, max(300, int(getattr(self.config, "suspicion_avoidance", 250) or 250))) / 1000.0
                        await asyncio.sleep(delay)
                        await button.click()
                    except InvalidData:
                        self._log_check("action_execute", status="invalid_data_retrying")
                        try:
                            # Re-fetch the message to refresh component tokens and retry click
                            fresh_message = await actionable_message.channel.fetch_message(actionable_message.id)
                            fresh_state = parse_battle_state(fresh_message, all_known_names)
                            fresh_moves = list(fresh_state.move_buttons.values()) if isinstance(fresh_state.move_buttons, dict) else list(fresh_state.move_buttons or [])
                            fresh_switches = list(fresh_state.switch_buttons.values()) if isinstance(fresh_state.switch_buttons, dict) else list(fresh_state.switch_buttons or [])
                            retry_btn, _, _ = self.decider.decide_action(fresh_moves, fresh_switches, fresh_state.ally_hp_percent)
                            if retry_btn:
                                await asyncio.sleep(0.3)
                                await retry_btn.click()
                                self._log_check("action_execute", status="retry_success")
                        except Exception as retry_exc:
                            self._log_check("action_execute", status="retry_failed", error=str(retry_exc))
                    except Exception as exc:
                        self._log_check("action_execute", status="failed", error=str(exc))

    @commands.Cog.listener()
    async def on_message(self, message: Message) -> None:
        await self._handle_candidate_message(message)

    @commands.Cog.listener()
    async def on_message_edit(self, _before: Message, after: Message) -> None:
        await self._handle_candidate_message(after)
