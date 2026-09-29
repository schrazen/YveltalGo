from __future__ import annotations

import asyncio
import re
import time
from random import uniform
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks

if TYPE_CHECKING:
    from main import PokeGrinder

from modules.berry_parser import parse_berry_garden

POKEMEOW_APP_ID = 664508672713424926


class BerryGarden(commands.Cog):
    def __init__(self, bot: PokeGrinder):
        self.bot = bot
        self.action_slot_min: int = 1
        self.action_slot_max: int = 3
        self.pending_water_slots: list[int] = []  # Slots waiting to be watered
        self.pending_harvest_slots: list[int] = []  # Slots ready to harvest
        self.last_water_time: float = 0.0
        self.water_in_progress: bool = False
        self.harvest_in_progress: bool = False
        self.last_check_trigger_time: float = 0.0
        self.last_check_source: str = "none"
        self.slot_watering_history: dict[int, set[int]] = {}  # {slot_num: {stages_watered}}
        self.slot_last_stage: dict[int, int] = {}  # {slot_num: last_known_stage}
        self.slot_last_berry_name: dict[int, str] = {}  # {slot_num: normalized berry key}
        self.water_retry_task: asyncio.Task | None = None
        self.last_slot_states: list[dict[str, str | int]] = []
        self.last_berry_command_at: float = 0.0
        self.berry_command_min_interval_seconds: float = 2.6
        self.consecutive_empty_checks: int = 0
        self.empty_check_suppress_threshold: int = 3
        self.empty_auto_suppressed: bool = False
        self.empty_suppression_notified: bool = False

        if self.bot.config.berry_enabled and self.bot.config.berry_channel_id != 0:
            print(f"[BerryGarden] Enabled for channel {self.bot.config.berry_channel_id}; starting check loop.")
            self.berry_check_loop.start()

    def _sanitize_action_slots(self, slots: list[int], action_name: str) -> list[int]:
        valid: list[int] = []
        seen: set[int] = set()

        for raw in slots:
            slot_num = int(raw)
            if slot_num < self.action_slot_min or slot_num > self.action_slot_max:
                print(
                    f"[BerryGarden] Ignoring invalid {action_name} slot {slot_num} "
                    f"(allowed: {self.action_slot_min}-{self.action_slot_max})."
                )
                continue
            if slot_num in seen:
                continue
            seen.add(slot_num)
            valid.append(slot_num)

        return valid

    def _resolve_berry_command(self):
        command_map = getattr(self.bot, "berry_channel_commands", None)
        if not command_map:
            return None, None

        # Prefer leaf subcommands first. Group roots can raise "Cannot use a group".
        for key in ("berry garden", "berry info", "berry check", "berry status"):
            cmd = command_map.get(key)
            if cmd is not None:
                return key, cmd

        # Then allow plain 'berry' only when it is directly invokable.
        cmd = command_map.get("berry")
        if cmd is not None and not getattr(cmd, "children", None):
            return "berry", cmd

        # Final fallback: any key that starts with 'berry' and is a leaf command.
        for key, cmd in command_map.items():
            if str(key).lower().startswith("berry") and not getattr(cmd, "children", None):
                return key, cmd

        return None, None

    async def _ensure_berry_context(self) -> None:
        # Recover channel reference when startup ordering or reconnect races leave it unset.
        if getattr(self.bot, "berry_channel", None) is None and self.bot.config.berry_channel_id:
            channel = self.bot.get_channel(self.bot.config.berry_channel_id)
            if channel is not None:
                self.bot.berry_channel = channel

        # Try to recover command map when absent.
        command_map = getattr(self.bot, "berry_channel_commands", None)
        channel = getattr(self.bot, "berry_channel", None)
        if command_map or channel is None:
            return

        try:
            app_commands = await channel.application_commands()
            recovered = {
                command.name: command
                for command in app_commands
                if command.application_id == POKEMEOW_APP_ID
            }
            for command in list(recovered.values()):
                for sub_command in getattr(command, "children", []):
                    recovered[f"{command.name} {sub_command.name}"] = sub_command

            self.bot.berry_channel_commands = recovered
        except Exception as exc:
            print(f"[BerryGarden] Could not recover berry commands: {exc}")

    def _is_in_berry_context(self, message: discord.Message) -> bool:
        if not bool(getattr(self.bot, "server_scope_valid", True)):
            return False

        required_server_id = int(getattr(self.bot, "required_server_id", 0) or 0)
        if required_server_id:
            msg_server_id = int(
                getattr(getattr(message, "guild", None), "id", 0)
                or getattr(getattr(message, "channel", None), "guild_id", 0)
                or 0
            )
            if msg_server_id != required_server_id:
                return False

        configured = int(self.bot.config.berry_channel_id or 0)
        if configured == 0:
            return False

        channel_id = int(getattr(message.channel, "id", 0) or 0)
        if channel_id == configured:
            return True

        # Support thread/forum replies where parent channel is the configured berry channel.
        parent_id = int(getattr(message.channel, "parent_id", 0) or 0)
        return parent_id == configured

    @staticmethod
    def _fallback_slot_states(raw_text: str) -> list[dict[str, str | int]]:
        if not raw_text:
            return []

        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        rows: list[dict[str, str | int]] = []

        i = 0
        while i < len(lines):
            line = lines[i]
            m = re.search(r"[Ss]lot\s+(\d+)\s+[—-]\s+(.+)$", line)
            if not m:
                i += 1
                continue

            slot_num = int(m.group(1))
            slot_raw_name = m.group(2)
            slot_line_lower = line.lower()

            state = "Healthy"
            detail = "Unknown"

            next_line = lines[i + 1] if i + 1 < len(lines) else ""
            next_lower = next_line.lower()

            if "slot locked" in slot_line_lower or "requires" in slot_line_lower:
                state = "Locked"
                detail = "Not available"
            elif "needs watering" in next_lower:
                state = "Needs Water"
                detail = next_line
            elif "healthy" in next_lower:
                state = "Healthy"
                detail = next_line
            elif "drying" in next_lower:
                state = "Drying"
                detail = next_line
            elif "ready" in next_lower or "[stage 4" in next_lower:
                state = "Ready"
                detail = next_line
            elif "wilting" in next_lower:
                state = "Wilting"
                detail = next_line
            elif next_line:
                detail = next_line

            berry_display = BerryGarden._clean_berry_display(slot_raw_name)
            rows.append({"slot": slot_num, "state": state, "detail": detail, "berry": berry_display})
            i += 1

        return sorted(rows, key=lambda row: int(row.get("slot", 0)))

    async def trigger_berry_check(self, source: str = "loop") -> bool:
        """Trigger a berry status refresh using slash command when available, fallback to text command."""
        if not bool(getattr(self.bot, "server_scope_valid", True)):
            return False

        source_name = str(source or "").lower().strip()
        manual_trigger = source_name in {"runtime_action", "manual"}
        if manual_trigger and self.empty_auto_suppressed:
            self.empty_auto_suppressed = False
            self.empty_suppression_notified = False
            self.consecutive_empty_checks = 0
            print("[BerryGarden] Manual trigger detected; re-enabled berry auto checks.")

        if source_name == "loop" and self.empty_auto_suppressed:
            if not self.empty_suppression_notified:
                print(
                    "[BerryGarden] Auto-check suppressed: garden was repeatedly empty. "
                    "Use runtime action 'force_berry_check' to run again."
                )
                self.empty_suppression_notified = True
            return False

        await self._ensure_berry_context()
        command_key, command = self._resolve_berry_command()
        if command is not None:
            self.last_check_trigger_time = time.time()
            self.last_check_source = f"slash:{command_key}"
            print(f"[BerryGarden] Triggering garden check via slash command '{command_key}' ({source}).")
            try:
                await command()
                return True
            except Exception as exc:
                print(f"[BerryGarden] Slash command failed ({exc}); trying text fallback.")

        if getattr(self.bot, "berry_channel", None):
            self.last_check_trigger_time = time.time()
            self.last_check_source = "text:;berry"
            print(f"[BerryGarden] Slash berry command not found; falling back to ';berry' ({source}).")
            await self._send_berry_text_command(";berry", reason=f"check:{source}")
            return True

        print("[BerryGarden] No berry command and no berry channel available for fallback.")
        return False

    @staticmethod
    def _embed_text_chunks(embed: discord.Embed, message_content: str) -> tuple[str, str]:
        title = str(embed.title or "")
        author = str(getattr(getattr(embed, "author", None), "name", "") or "")
        description = str(embed.description or "")

        field_chunks: list[str] = []
        for field in getattr(embed, "fields", []) or []:
            if getattr(field, "name", None):
                field_chunks.append(str(field.name))
            if getattr(field, "value", None):
                field_chunks.append(str(field.value))

        footer = str(embed.footer.text if embed.footer else "")
        combined = "\n".join(
            [
                title,
                author,
                description,
                "\n".join(field_chunks),
                str(message_content or ""),
                footer,
            ]
        )
        return combined, description

    @staticmethod
    def _normalize_identity_token(value: str) -> str:
        # Keep only alphanumerics so variants like `name`, `name_123`, and spacing differences compare reliably.
        return re.sub(r"[^a-z0-9]", "", str(value or "").lower())

    def _extract_garden_owner_name(self, embed: discord.Embed, combined_text: str) -> str:
        # Expected patterns:
        # - "reddice_026's Berry Garden"
        # - "reddice_026s Berry Garden"
        title = str(getattr(embed, "title", "") or "")
        author_name = str(getattr(getattr(embed, "author", None), "name", "") or "")
        probe = "\n".join([title, author_name, str(combined_text or "")])
        m = re.search(r"([A-Za-z0-9_\-\.]{2,40})\s*'?s\s+berry\s+garden", probe, flags=re.IGNORECASE)
        if not m:
            return ""
        return str(m.group(1) or "").strip()

    def _is_message_for_this_bot(self, message: discord.Message, embed: discord.Embed, combined_text: str) -> bool:
        # Best signal: interaction user should be the account that requested ;berry / slash berry status.
        try:
            interaction_user = getattr(getattr(message, "interaction", None), "user", None)
            if interaction_user is not None and self.bot.user is not None:
                if int(getattr(interaction_user, "id", 0) or 0) == int(getattr(self.bot.user, "id", 0) or 0):
                    return True
        except Exception:
            pass

        # Fallback signal: owner name in embed title/author/text should match this bot username.
        owner_name = self._extract_garden_owner_name(embed, combined_text)
        if not owner_name:
            return False

        bot_name = str(getattr(self.bot, "user", None) or "")
        if bot_name:
            bot_name = bot_name.split("#", 1)[0].strip()

        owner_norm = self._normalize_identity_token(owner_name)
        bot_norm = self._normalize_identity_token(bot_name)
        return bool(owner_norm and bot_norm and owner_norm == bot_norm)

    @staticmethod
    def _normalize_berry_for_replant(raw_berry_name: str) -> str:
        # Convert labels like ':hb: Hondew Berry' or '<123...> Hondew Berry' -> 'hondew_berry'.
        cleaned = BerryGarden._clean_berry_display(raw_berry_name)
        name = cleaned.strip().lower()
        name = re.sub(r"\s+", "_", name)
        name = re.sub(r"[^a-z0-9_]", "", name)
        return name

    @staticmethod
    def _clean_berry_display(raw_berry_name: str) -> str:
        # Convert labels like ':hb: Hondew Berry • Next stage...' or '<123...> Hondew Berry' -> 'Hondew Berry'.
        value = re.sub(r"\s*•.*$", "", str(raw_berry_name or "")).strip()
        value = re.sub(r"<[^>]+>", "", value).strip()
        value = re.sub(r":[^:\s]+:", "", value).strip()
        value = re.sub(r"\s+", " ", value)
        if "slot locked" in value.lower():
            return ""
        return value

    async def _send_berry_text_command(self, command_text: str, reason: str) -> None:
        if not bool(getattr(self.bot, "server_scope_valid", True)):
            return

        if not getattr(self.bot, "berry_channel", None):
            return

        now = time.time()
        elapsed = now - self.last_berry_command_at
        if elapsed < self.berry_command_min_interval_seconds:
            await asyncio.sleep(self.berry_command_min_interval_seconds - elapsed)

        # Small jitter to avoid exact mechanical cadence and avoid edge-case cooldowns.
        await asyncio.sleep(uniform(0.2, 0.6))
        await self.bot.berry_channel.send(command_text)
        self.last_berry_command_at = time.time()

    def cog_unload(self):
        """Run when cog is unloaded."""
        if self.berry_check_loop.is_running():
            self.berry_check_loop.cancel()
        if self.water_retry_task and not self.water_retry_task.done():
            self.water_retry_task.cancel()

    def _schedule_water_retry(self, delay_seconds: float) -> None:
        if not self.pending_water_slots:
            return

        if self.water_retry_task and not self.water_retry_task.done():
            return

        async def _runner():
            try:
                await asyncio.sleep(max(1.0, delay_seconds))
                if self.pending_water_slots and not self.water_in_progress:
                    self.water_in_progress = True
                    self.last_water_time = time.time()
                    await self._execute_water_actions()
            except asyncio.CancelledError:
                return

        self.water_retry_task = asyncio.create_task(_runner())

    @tasks.loop(minutes=15)
    async def berry_check_loop(self):
        """Check garden status every 15 minutes."""
        try:
            if not bool(getattr(self.bot, "server_scope_valid", True)):
                return
            await self.trigger_berry_check(source="loop")
        except Exception as e:
            print(f"[BerryGarden] Error in check loop: {e}")

    @berry_check_loop.before_loop
    async def before_berry_loop(self):
        """Wait until bot is ready before starting loop."""
        await self.bot.wait_until_ready()
        print("[BerryGarden] Bot ready; berry check loop active.")

    async def _process_berry_response(self, message: discord.Message, source: str) -> None:
        if not self.bot.config.berry_enabled:
            return

        # Ignore bot's own messages
        if message.author.id == getattr(self.bot.user, "id", 0):
            return

        # Only process in configured berry context (channel or thread under that channel).
        if not self._is_in_berry_context(message):
            return

        # Check if this is a berry-related embed response
        if not message.embeds or len(message.embeds) == 0:
            return

        embed = message.embeds[0]
        combined_text, description = self._embed_text_chunks(embed, message.content or "")
        combined_lower = combined_text.lower()

        # In shared berry channels, ignore other accounts' garden responses.
        if not self._is_message_for_this_bot(message, embed, combined_text):
            return

        # Only process garden overview responses, but detect across title/author/fields/content.
        if "garden" not in combined_lower and "berry" not in combined_lower:
            return

        # Ignore harvest-result-only embeds; they are confirmations, not actionable state snapshots.
        if "berry harvest results" in combined_lower and "current berry states" not in combined_lower:
            return

        # Some Pokemeow responses place garden slot lines in embed fields instead of description.
        parse_candidates = [
            description,
            combined_text,
        ]

        # Parse garden state (description first, then field text fallback).
        slots = None
        for candidate in parse_candidates:
            parsed = parse_berry_garden(candidate)
            if parsed:
                slots = parsed
                break

        if not slots:
            fallback_rows = self._fallback_slot_states(combined_text)
            if fallback_rows:
                self.last_slot_states = fallback_rows
                print(f"[BerryGarden] Fallback parsed {len(fallback_rows)} slot state(s) from berry response.")
                return

            print("[BerryGarden] Berry response received but parser found no slot data (author/title/description/fields checked).")
            return

        print(f"[BerryGarden] Parsed {len(slots)} slot(s) from berry response.")

        slot_state_rows: list[dict[str, str | int]] = []

        # Separate slots by action needed
        slots_to_harvest = []
        slots_to_water = []
        slots_status = []

        for slot in slots:
            status = f"Slot {slot.slot_number}: {slot.berry_name} [{slot.stage_name} {slot.stage_current}/{slot.stage_max}]"

            berry_name_lower = (slot.berry_name or "").lower()
            stage_label = slot.stage_name or "Unknown"
            detail = f"{stage_label} {slot.stage_current}/{slot.stage_max}"
            state = "Healthy"

            if "lock" in berry_name_lower or "slot locked" in berry_name_lower:
                state = "Locked"
                detail = "Not available"
            elif "empty" in berry_name_lower:
                state = "Empty"
                detail = "No berry planted"
            elif slot.is_wilting:
                state = "Wilting"
                detail = f"{stage_label} {slot.stage_current}/{slot.stage_max} • Wilting"
            elif slot.is_ripe:
                state = "Ready"
                detail = f"{stage_label} {slot.stage_current}/{slot.stage_max} • Ready to harvest"
            elif slot.needs_water:
                state = "Needs Water"
                detail = f"{stage_label} {slot.stage_current}/{slot.stage_max} • Needs watering"
            else:
                moisture_label = "Healthy" if int(slot.moisture or 0) >= 90 else "Drying"
                if moisture_label == "Drying":
                    state = "Drying"
                detail = f"{stage_label} {slot.stage_current}/{slot.stage_max} • {moisture_label}"

            if state not in {"Locked", "Empty"}:
                normalized = self._normalize_berry_for_replant(slot.berry_name)
                if normalized:
                    self.slot_last_berry_name[int(slot.slot_number)] = normalized

            berry_display = self._clean_berry_display(slot.berry_name)

            slot_state_rows.append(
                {
                    "slot": int(slot.slot_number),
                    "state": state,
                    "detail": detail,
                    "berry": berry_display,
                }
            )
            
            # Priority 1: Harvest ripe berries
            if slot.is_ripe and not slot.is_wilting:
                slots_to_harvest.append(slot.slot_number)
                status += " -> HARVEST"
                print(f"[BerryGarden] {status}")
                slots_status.append(status)
                continue
            
            # Priority 2: Water if dry AND not already watered this stage
            if slot.needs_water and not slot.is_wilting:
                watered_stages = self.slot_watering_history.get(slot.slot_number, set())

                # If a slot is still dry, retry watering even when stage was previously marked watered.
                # This covers missed/failed command sends where growth remains paused.
                slots_to_water.append(slot.slot_number)
                if slot.stage_current not in watered_stages:
                    status += f" -> WATER (stage {slot.stage_current}/{slot.stage_max}, {len(watered_stages)} watered so far)"
                else:
                    status += f" -> WATER RETRY (still dry at stage {slot.stage_current})"
                print(f"[BerryGarden] {status}")
                slots_status.append(status)
            else:
                status += f" -> OK (moisture: {slot.moisture}%)"
                print(f"[BerryGarden] {status}")
                slots_status.append(status)
            
            # Track current stage for wilt detection
            old_stage = self.slot_last_stage.get(slot.slot_number, -1)
            self.slot_last_stage[slot.slot_number] = slot.stage_current
            
            # Reset watering history if new berry planted (stage goes to 0)
            if slot.stage_current == 0 and old_stage > 0:
                self.slot_watering_history[slot.slot_number] = set()
                print(f"[BerryGarden] Slot {slot.slot_number}: New berry planted, reset watering history")

        self.last_slot_states = sorted(slot_state_rows, key=lambda row: int(row.get("slot", 0)))

        non_locked_rows = [row for row in self.last_slot_states if str(row.get("state", "")) != "Locked"]
        all_non_locked_empty = bool(non_locked_rows) and all(
            str(row.get("state", "")) == "Empty" for row in non_locked_rows
        )

        if all_non_locked_empty:
            self.consecutive_empty_checks += 1
            if self.consecutive_empty_checks >= self.empty_check_suppress_threshold and not self.empty_auto_suppressed:
                self.empty_auto_suppressed = True
                self.empty_suppression_notified = False
                print(
                    "[BerryGarden] Suppressing automatic berry loop checks after repeated empty garden responses. "
                    "Run force_berry_check to resume."
                )
        else:
            if self.consecutive_empty_checks > 0:
                self.consecutive_empty_checks = 0
            if self.empty_auto_suppressed:
                self.empty_auto_suppressed = False
                self.empty_suppression_notified = False
                print("[BerryGarden] Garden is no longer empty-only; automatic berry checks resumed.")

        slots_to_harvest = self._sanitize_action_slots(slots_to_harvest, "harvest")
        slots_to_water = self._sanitize_action_slots(slots_to_water, "water")

        # Log summary
        if slots_to_harvest or slots_to_water:
            print(f"[BerryGarden] Summary: {len(slots_to_harvest)} to harvest, {len(slots_to_water)} to water")
        else:
            print(f"[BerryGarden] Garden check: no actions needed")

        # Execute harvests first (Priority 1)
        if slots_to_harvest and not self.harvest_in_progress:
            self.harvest_in_progress = True
            self.pending_harvest_slots = slots_to_harvest.copy()
            await asyncio.sleep(1)
            await self._execute_harvest_actions()

        # Then handle watering (Priority 2)
        now = time.time()
        if slots_to_water and not self.water_in_progress:
            self.pending_water_slots = slots_to_water.copy()
            # Debounce: don't issue water commands more than once per 3 minutes
            if now - self.last_water_time >= 180:
                self.water_in_progress = True
                self.last_water_time = now
                if self.water_retry_task and not self.water_retry_task.done():
                    self.water_retry_task.cancel()
                
                await asyncio.sleep(2)
                await self._execute_water_actions()
            else:
                elapsed = now - self.last_water_time
                remaining = max(1.0, 180 - elapsed)
                print(f"[BerryGarden] Deferring water action ({remaining:.0f}s remaining, debounce=180s) -> scheduled retry")
                self._schedule_water_retry(remaining + 1)

    @commands.Cog.listener("on_message")
    async def on_berry_response(self, message: discord.Message):
        """Listen for berry responses and handle harvesting + smart watering."""
        await self._process_berry_response(message, source="on_message")

    @commands.Cog.listener("on_message_edit")
    async def on_berry_response_edit(self, _before: discord.Message, after: discord.Message):
        """Some slash-response embeds are delivered as message edits; process those too."""
        await self._process_berry_response(after, source="on_message_edit")

    async def _execute_harvest_actions(self):
        """Execute pending harvest actions."""
        if not self.pending_harvest_slots:
            self.harvest_in_progress = False
            return

        try:
            if not getattr(self.bot, "berry_channel", None):
                print(f"[BerryGarden] No berry channel available for harvest")
                self.harvest_in_progress = False
                return

            harvested_slots_to_water: list[int] = []

            for slot_num in self._sanitize_action_slots(self.pending_harvest_slots, "harvest"):
                try:
                    print(f"[BerryGarden] Harvesting slot {slot_num}...")
                    await self._send_berry_text_command(f";berry harvest {slot_num}", reason=f"harvest:{slot_num}")

                    berry_key = self.slot_last_berry_name.get(int(slot_num), "")
                    if berry_key:
                        # Replant the same berry after harvest using normalized key.
                        await self._send_berry_text_command(
                            f";berry plant {berry_key} {slot_num}",
                            reason=f"replant:{slot_num}:{berry_key}",
                        )
                        print(f"[BerryGarden] Replanted slot {slot_num} with {berry_key}.")
                        harvested_slots_to_water.append(int(slot_num))

                    # Reset watering history after harvest
                    self.slot_watering_history[slot_num] = set()
                    self.slot_last_stage[slot_num] = 0
                    
                except Exception as e:
                    print(f"[BerryGarden] Error harvesting slot {slot_num}: {e}")

            harvested_slots_to_water = self._sanitize_action_slots(harvested_slots_to_water, "water")
            if harvested_slots_to_water and not self.water_in_progress:
                merged_slots = list(self.pending_water_slots) + harvested_slots_to_water
                self.pending_water_slots = self._sanitize_action_slots(merged_slots, "water")
                self.water_in_progress = True
                self.last_water_time = time.time()
                if self.water_retry_task and not self.water_retry_task.done():
                    self.water_retry_task.cancel()
                await asyncio.sleep(1)
                await self._execute_water_actions()

        finally:
            self.pending_harvest_slots = []
            self.harvest_in_progress = False

    async def _execute_water_actions(self):
        """Execute pending water actions with stage tracking."""
        self.pending_water_slots = self._sanitize_action_slots(self.pending_water_slots, "water")
        if not self.pending_water_slots:
            self.water_in_progress = False
            return

        try:
            if not getattr(self.bot, "berry_channel", None):
                print(f"[BerryGarden] No berry channel available")
                self.water_in_progress = False
                return

            for slot_num in self.pending_water_slots:
                try:
                    current_stage = self.slot_last_stage.get(slot_num, 0)
                    print(f"[BerryGarden] Watering slot {slot_num} (tracking stage {current_stage})...")
                    await self._send_berry_text_command(f";berry water {slot_num}", reason=f"water:{slot_num}")
                    
                    # Track which stage was watered (for yield optimization)
                    if slot_num not in self.slot_watering_history:
                        self.slot_watering_history[slot_num] = set()
                    self.slot_watering_history[slot_num].add(current_stage)
                    print(f"[BerryGarden] Slot {slot_num}: watered at stage {current_stage} (total: {len(self.slot_watering_history[slot_num])}/4 max)")
                    
                except Exception as e:
                    print(f"[BerryGarden] Error watering slot {slot_num}: {e}")

        finally:
            self.pending_water_slots = []
            self.water_in_progress = False


async def setup(bot: PokeGrinder):
    """Entry point for loading the cog."""
    await bot.add_cog(BerryGarden(bot))
