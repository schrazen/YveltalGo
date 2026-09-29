import asyncio
import json
import re
import sqlite3
from pathlib import Path
from random import randint
from time import time
from typing import Any, Dict, List, Optional

from discord import InvalidData, Message
from discord.ext import commands

from cogs.startup import Config
from modules.battle_state import ParsedBattleState, normalize, parse_battle_state
from modules.pokemeow_battle_parser import parse_pokemeow_battle_events
from modules.worldboss_strategies import (
    WORLD_BOSS_STRATEGIES,
    WorldBossActionDecider,
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

    def _in_world_boss_channel(self, channel_id: int) -> bool:
        configured_id = int(getattr(self.config, "world_boss_channel_id", 0) or 0)
        return configured_id != 0 and channel_id == configured_id

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
        return ""

    @staticmethod
    def _log_check(step: str, **details) -> None:
        payload = {k: v for k, v in details.items() if v is not None}
        try:
            print(f"[WorldBoss] {step}: {payload}")
        except Exception:
            pass

    async def _resolve_actionable_message(self, message: Message) -> Message:
        """Return a message that actually carries action buttons for this WB event."""
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

        try:
            async for hist_message in message.channel.history(limit=15):
                if hist_message.id == message.id:
                    continue
                if not hist_message.author or hist_message.author.id != POKEMEOW_APP_ID:
                    continue
                if getattr(hist_message, "components", None):
                    return hist_message
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

            if not self.config.wb_dry_run:
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
            if "register" in label or "register" in custom_id or "world_boss" in label or "world_boss" in custom_id:
                return button

        return buttons[0] if buttons else None

    async def _try_start_fight(self, message: Message, message_blob: str) -> bool:
        trigger_texts = (
            "successfully registered your",
            "the battle starts automatically in 5 minutes",
            "type ;wb fight to start",
            "you are registered for this fight",
            "battle begins in 5 minutes",
            "start the battle using ;wb fight",
            "the battle is underway",
        )
        matched_trigger = next((token for token in trigger_texts if token in message_blob), "")
        if not matched_trigger:
            return False

        message_id = int(getattr(message, "id", 0) or 0)
        if message_id > 0 and message_id == int(self.last_fight_request_message_id or 0):
            return False

        countdown_seconds = self._extract_fight_delay_seconds(message_blob)
        delay_seconds = MIN_WB_FIGHT_START_BUFFER_SECONDS
        if countdown_seconds is not None:
            delay_seconds = max(delay_seconds, float(countdown_seconds) + MIN_WB_FIGHT_START_BUFFER_SECONDS)

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

    def _looks_like_world_boss(self, message: Message) -> bool:
        if self._in_world_boss_channel(getattr(message.channel, "id", 0)):
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

        lowered = normalize(message.content or "")
        if "world boss" in lowered or ";wb" in lowered or "boss challenge" in lowered:
            return True

        if "select a pokemon switch button to complete baton pass" in lowered:
            return True

        for embed in getattr(message, "embeds", []) or []:
            text = normalize(
                (embed.title or "")
                + " "
                + (embed.description or "")
                + " "
                + (getattr(getattr(embed, "footer", None), "text", "") or "")
            )
            if "world boss" in text or "boss" in text or "challenge" in text:
                return True
            if "select a pokemon switch button to complete baton pass" in text:
                return True

        return False

    async def _handle_candidate_message(self, message: Message) -> None:
        if not message or not message.channel:
            return

        if message.content:
            toggle = self._toggle_command(message.content)
            if toggle == "on":
                self.config.world_boss_enabled = True
                self.restart_requested = False
                self.bot.world_boss_status = "WorldBoss auto: ON"
                await self.bot.log()
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
                await message.channel.send(f"WorldBoss auto: {status} | Boss: {boss} | Active: {active}")
                return

        if not bool(getattr(self.config, "world_boss_enabled", False)):
            return

        if not self._is_pokemeow_message(message):
            return

        if not self._looks_like_world_boss(message):
            return

        self.bot.last_wb_action = time()
        actionable_message = await self._resolve_actionable_message(message)

        message_blob = normalize(
            (message.content or "")
            + " "
            + " ".join(str(embed.description or "") for embed in getattr(message, "embeds", []) or [])
            + " "
            + " ".join(str(embed.title or "") for embed in getattr(message, "embeds", []) or [])
        )

        enemy_name = self._extract_enemy_name({}, message_blob)
        if enemy_name:
            self.last_enemy_name = enemy_name

        # 1. Registration prompts
        if any(
            token in message_blob
            for token in (
                "register now",
                "you have not yet registered",
                "registration is open",
            )
        ):
            register_button = self._find_register_button(actionable_message)
            if register_button is not None and not self.config.wb_dry_run:
                try:
                    await asyncio.sleep(randint(0, self.config.suspicion_avoidance) / 1000)
                    await register_button.click()
                    self.bot.world_boss_status = "Registering for WorldBoss"
                    await self.bot.log()
                except (InvalidData, Exception):
                    pass

        # 2. Countdown parsing & Scheduling
        if self._schedule_fight_start(message, message_blob):
            self.bot.world_boss_status = "WorldBoss fight scheduled"
            await self.bot.log()
            return

        if await self._try_start_fight(message, message_blob):
            return

        # 3. Terminal detection without buttons
        if "your team has been defeated" in message_blob or "you lost the battle" in message_blob:
            self._log_check("terminal", matched=True, outcome="loss")
            self.bot.world_boss_status = "WorldBoss battle lost"
            self._reset_fight()
            await self.bot.log()
            return

        if "world boss has been defeated" in message_blob or "you won the battle" in message_blob:
            self._log_check("terminal", matched=True, outcome="win")
            self.bot.world_boss_status = "WorldBoss defeated!"
            self._reset_fight()
            await self.bot.log()
            return

        # 4. Check for active battle state
        all_known_names = [
            "Smeargle", "Shiny Smeargle", "Mega-Gardevoir", "Mega Gardevoir",
            "Swoobat", "Necrozma-Ultra", "Necrozma Ultra", "Mega-Mewtwo-Y", "Mega Mewtwo Y",
            "Poliwrath", "Mew", "Shuckle", "Vaporeon", "Gliscor",
            "Incineroar", "Umbreon", "Bellossom", "Gmax-Inteleon", "Gmax-Charizard",
        ]
        state = parse_battle_state(actionable_message, all_known_names)
        events, summary = parse_pokemeow_battle_events(actionable_message)
        worldboss = summary.get("worldboss", {}) if isinstance(summary, dict) else {}

        boss_name = self._extract_enemy_name(worldboss, message_blob)
        if boss_name:
            self.last_enemy_name = boss_name

        if state.terminal_win:
            self.bot.world_boss_status = "WorldBoss defeated!"
            self._reset_fight()
            await self.bot.log()
            return

        if state.terminal_loss:
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

            button, action_name, reason = self.decider.decide_action(
                move_buttons=state.move_buttons,
                switch_buttons=state.switch_buttons,
                ally_hp_percent=state.ally_hp_percent,
                is_baton_pass_prompt=is_baton_pass_prompt,
            )

            if button is None and (state.move_buttons or state.switch_buttons):
                move_names = [str(getattr(b, "label", "") or getattr(b, "custom_id", "")) for b in state.move_buttons]
                switch_names = [str(getattr(b, "label", "") or getattr(b, "custom_id", "")) for b in state.switch_buttons]
                ai_adv = await smart_advisor.advise_combat_action(
                    boss_name=self.last_enemy_name,
                    active_pokemon=active_pokemon,
                    ally_hp_percent=state.ally_hp_percent,
                    available_moves=move_names,
                    available_switches=switch_names,
                    recent_log=message_blob[-200:],
                )
                target = str(ai_adv.get("target", "")).lower()
                for b in (state.move_buttons + state.switch_buttons):
                    label = str(getattr(b, "label", "") or "").lower()
                    cid = str(getattr(b, "custom_id", "") or "").lower()
                    if (target and target in label) or (target and target in cid) or (label and label in target):
                        button = b
                        action_name = f"AI_{ai_adv.get('type', 'action')}:{getattr(b, 'label', '')}"
                        reason = ai_adv.get("reason", "AI tactical decision")
                        break

            if button is not None:
                action_signature = f"{actionable_message.id}:{action_name}"
                now = time()
                if action_signature == self.last_action_signature and now - self.last_action_at < 2.0:
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
                        delay = randint(0, self.config.suspicion_avoidance) / 1000
                        await asyncio.sleep(delay)
                        await button.click()
                    except InvalidData:
                        self._log_check("action_execute", status="invalid_data")
                    except Exception as exc:
                        self._log_check("action_execute", status="failed", error=str(exc))

    @commands.Cog.listener()
    async def on_message(self, message: Message) -> None:
        await self._handle_candidate_message(message)

    @commands.Cog.listener()
    async def on_message_edit(self, _before: Message, after: Message) -> None:
        await self._handle_candidate_message(after)
