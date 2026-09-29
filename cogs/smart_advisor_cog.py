from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from random import randint
from typing import Any, TYPE_CHECKING

import discord
from discord import Message, InvalidData
from discord.ext import commands, tasks

from modules.captcha_gate import is_captcha_active, is_in_battle
from modules.smart_advisor import smart_advisor

if TYPE_CHECKING:
    from main import PokeGrinder

logger = logging.getLogger("pokegrinder.smart_advisor_cog")
POKEMEOW_APP_ID = 664508672713424926


def _extract_clickable_buttons(message: Message) -> list[tuple[Any, dict[str, str]]]:
    """Extract interactive, non-disabled button components from a message."""
    extracted = []
    components = getattr(message, "components", []) or []
    for action_row in components:
        children = getattr(action_row, "children", []) or []
        for child in children:
            if getattr(child, "type", None) == discord.ComponentType.button or "button" in str(getattr(child, "type", "")).lower():
                if not bool(getattr(child, "disabled", False)):
                    meta = {
                        "label": str(getattr(child, "label", "") or "").strip(),
                        "custom_id": str(getattr(child, "custom_id", "") or "").strip(),
                    }
                    extracted.append((child, meta))
    return extracted


def _is_routine_encounter_or_ball_button(button_cids: list[str], text: str = "") -> bool:
    """Detect if a message or its buttons belong to routine wild Pokémon catching or fishing."""
    lowered_text = text.lower()
    routine_tokens = (
        "found a wild",
        "fished a wild",
        "a wild pokemon appeared",
        "cast a",
        "click any of",
        "balls left",
        "caught",
        "got away",
        "not even a nibble",
        "cast into the water",
        "the current is strong",
    )
    if any(token in lowered_text for token in routine_tokens):
        return True

    for cid in button_cids:
        c = str(cid or "").lower()
        if (
            c.startswith("pokemon:")
            or "ball" in c
            or c in (
                "pb", "gb", "ub", "mb", "prb", "db", "bb",
                "fish_pull", "pb_fish", "gb_fish", "ub_fish", "mb_fish", "prb_fish", "db_fish", "bb_fish"
            )
        ):
            return True
    return False


class SmartAdvisorCog(commands.Cog):
    """Cog providing active surveillance, dead-man's switch inactivity watchdog,
    and Gemini-backed unhandled prompt resolution.
    """

    def __init__(self, bot: PokeGrinder) -> None:
        self.bot = bot
        self.config = bot.config
        self.last_active_timestamp: float = time.time()
        self.inactivity_timeout_seconds: float = float(
            getattr(self.config, "SmartAdvisor", {}).get("InactivityTimeoutSeconds", 40.0)
            if hasattr(self.config, "SmartAdvisor") else 40.0
        )
        self.consecutive_stalls: int = 0
        self._handled_message_ids: set[int] = set()
        self._watchdog_running_check: bool = False

        # Start background watchdog safely
        try:
            self.watchdog_loop.start()
            print(f"[SmartAdvisor] Inactivity watchdog started (timeout={self.inactivity_timeout_seconds}s).")
        except RuntimeError:
            pass

    def cog_unload(self) -> None:
        if self.watchdog_loop.is_running():
            self.watchdog_loop.cancel()

    def mark_active(self) -> None:
        """Call whenever an action, response, or command happens."""
        self.last_active_timestamp = time.time()
        self.consecutive_stalls = 0

    def _is_message_for_this_bot(self, message: Message) -> bool:
        """Verify whether this PokéMeow message was targeted at or triggered by our bot account."""
        if not self.bot or not getattr(self.bot, "user", None):
            return False

        # 1. Direct interaction ownership check
        if getattr(message, "interaction", None) and getattr(message.interaction, "user", None) == self.bot.user:
            return True

        # 2. Direct user mention
        if self.bot.user in getattr(message, "mentions", []):
            return True

        # 3. Match username or display name in message content and embeds
        username = str(getattr(self.bot.user, "name", "") or "").lower()
        display_name = str(getattr(self.bot.user, "display_name", "") or "").lower()
        valid_names = {n for n in (username, display_name) if n}
        if not valid_names:
            return False

        text_parts = [str(message.content or "")]
        for em in getattr(message, "embeds", []) or []:
            text_parts.append(str(getattr(em, "title", "") or ""))
            text_parts.append(str(getattr(em, "description", "") or ""))
            if getattr(em, "footer", None) and getattr(em.footer, "text", None):
                text_parts.append(str(em.footer.text or ""))

        haystack = " ".join(text_parts).lower()
        return any(n in haystack for n in valid_names)

    # =========================================================================
    # Dead-Man's Switch Inactivity Watchdog
    # =========================================================================

    @tasks.loop(seconds=10.0)
    async def watchdog_loop(self) -> None:
        await self.check_inactivity_and_recover()

    async def check_inactivity_and_recover(self) -> None:
        if self._watchdog_running_check:
            return

        try:
            self._watchdog_running_check = True

            # Only monitor if the bot is fully initialized and gateway connected
            if not getattr(self.bot, "server_scope_valid", False) or self.bot.is_closed():
                return

            # Check if bot is intentionally paused for captcha
            if is_captcha_active(self.bot):
                return

            now = time.time()
            elapsed = now - self.last_active_timestamp

            # Phase 1: Local Lock Audit (aggressive unsticking)
            # -------------------------------------------------------------
            # Auto-clear orphaned WorldBoss lock if idle for > 40s
            if bool(getattr(self.bot, "world_boss_active", False)):
                wb_elapsed = now - float(getattr(self.bot, "last_wb_action", 0.0) or 0.0)
                if wb_elapsed > 40.0:
                    logger.warning("SmartAdvisor: Releasing stuck world_boss_active lock (%0.1fs elapsed)", wb_elapsed)
                    self.bot.world_boss_active = False
                    self.bot.pause_hunting = False
                    self.bot.pause_fishing = False
                    self.mark_active()
                    await self.bot.log()

            # Auto-clear orphaned AutoFight lock if idle for > 40s
            af_cog = self.bot.get_cog("AutoFight")
            af_active = bool(getattr(self.bot, "autofight_active", False)) or (
                af_cog is not None and int(getattr(af_cog, "_run_target_battles", 0) or 0) > 0
            )
            if af_active:
                af_elapsed = now - float(getattr(self.bot, "last_autofight_action", 0.0) or 0.0)
                if af_elapsed > 40.0:
                    logger.warning("SmartAdvisor: Aborting stuck AutoFight battle run (%0.1fs elapsed)", af_elapsed)
                    if af_cog and hasattr(af_cog, "abort_battle_run"):
                        try:
                            await af_cog.abort_battle_run("watchdog_inactivity_timeout")
                        except Exception as exc:
                            logger.error("Error aborting stuck battle run: %s", exc)
                    self.bot.autofight_active = False
                    self.bot.pause_hunting = False
                    self.bot.pause_fishing = False
                    self.mark_active()
                    await self.bot.log()

            # Auto-clear orphaned pause_hunting / pause_fishing if not in battle
            if (bool(getattr(self.bot, "pause_hunting", False)) or bool(getattr(self.bot, "pause_fishing", False))) and not af_active and not bool(getattr(self.bot, "world_boss_active", False)):
                if elapsed > 40.0:
                    logger.warning("SmartAdvisor: Clearing stuck pause_hunting/pause_fishing flags (%0.1fs elapsed)", elapsed)
                    self.bot.pause_hunting = False
                    self.bot.pause_fishing = False
                    self.mark_active()
                    await self.bot.log()

            # If elapsed time has not reached the threshold, nothing more to do
            if elapsed < self.inactivity_timeout_seconds:
                return

            print(f"[SmartAdvisor] Inactivity warning: Bot has been silent for {int(elapsed)}s. Initiating recovery...")

            # Phase 2: Channel Snapshot & AI Diagnosis
            # -------------------------------------------------------------
            active_channel = getattr(self.bot, "hunting_channel", None) or getattr(self.bot, "fishing_channel", None)
            if not active_channel:
                return

            recent_messages = []
            unhandled_message = None
            try:
                async for msg in active_channel.history(limit=4):
                    author_id = getattr(getattr(msg, "author", None), "id", 0)
                    buttons = _extract_clickable_buttons(msg)
                    msg_dict = {
                        "id": msg.id,
                        "author": str(msg.author),
                        "is_pokemeow": (author_id == POKEMEOW_APP_ID),
                        "content": msg.content or "",
                        "embed_titles": [e.title for e in msg.embeds if getattr(e, "title", None)],
                        "embed_descriptions": [e.description for e in msg.embeds if getattr(e, "description", None)],
                        "has_clickable_buttons": [b[1]["label"] for b in buttons],
                    }
                    recent_messages.append(msg_dict)
                    if (
                        author_id == POKEMEOW_APP_ID
                        and buttons
                        and unhandled_message is None
                        and self._is_message_for_this_bot(msg)
                    ):
                        b_cids = [b[1]["custom_id"] for b in buttons]
                        txt = (msg.content or "") + " " + " ".join(
                            (e.title or "") + " " + (e.description or "") for e in getattr(msg, "embeds", []) or []
                        )
                        if not _is_routine_encounter_or_ball_button(b_cids, txt):
                            unhandled_message = (msg, buttons)
            except Exception as hist_err:
                logger.warning("Could not fetch channel history: %s", hist_err)

            # If an unhandled message with buttons is sitting in the channel, resolve it!
            if unhandled_message:
                msg_obj, btn_list = unhandled_message
                message_data = {
                    "content": msg_obj.content,
                    "embed_titles": [e.title for e in msg_obj.embeds if getattr(e, "title", None)],
                    "embed_descriptions": [e.description for e in msg_obj.embeds if getattr(e, "description", None)],
                }
                button_metas = [b[1] for b in btn_list]
                advice = await smart_advisor.advise_unhandled_interaction(message_data, button_metas)
                if advice.get("action") == "CLICK_BUTTON" and "validated_button" in advice:
                    matched_meta = advice["validated_button"]
                    for btn_component, bmeta in btn_list:
                        if bmeta.get("custom_id") == matched_meta.get("custom_id"):
                            print(f"[SmartAdvisor] AI clicking button '{bmeta.get('label')}' to unblock channel.")
                            try:
                                await btn_component.click()
                                self.mark_active()
                                return
                            except InvalidData:
                                pass
                            except Exception as click_err:
                                if "50035" in str(click_err) or "Component validation failed" in str(click_err):
                                    logger.info("Button component expired or unavailable: %s", click_err)
                                else:
                                    logger.error("AI click execution failed: %s", click_err)

            # Phase 3: AI Inactivity Diagnosis
            # -------------------------------------------------------------
            bot_locks = {
                "world_boss_active": bool(getattr(self.bot, "world_boss_active", False)),
                "autofight_active": bool(getattr(self.bot, "autofight_active", False)),
                "pause_hunting": bool(getattr(self.bot, "pause_hunting", False)),
                "pause_fishing": bool(getattr(self.bot, "pause_fishing", False)),
                "elapsed_inactive_seconds": elapsed,
            }

            diagnosis = await smart_advisor.diagnose_inactivity(recent_messages, bot_locks)
            action = diagnosis.get("action", "KICKSTART_COMMAND")

            if action == "RESET_LOCKS":
                self.bot.world_boss_active = False
                self.bot.autofight_active = False
                self.bot.pause_hunting = False
                self.bot.pause_fishing = False
                print("[SmartAdvisor] Executed RESET_LOCKS per AI diagnosis.")
                self.mark_active()
                return

            if action == "PAUSE_ALERT":
                self.consecutive_stalls += 1
                if self.consecutive_stalls >= 2:
                    print("[SmartAdvisor] Bot paused per AI diagnosis to prevent ban / error.")
                    self.bot.pause_hunting = True
                    self.bot.hunting_status = f"Paused ({diagnosis.get('reason', 'AI alert')})"
                    await self.bot.log()
                    return

            # Phase 4: Controlled Safe Kickstart Pulse
            # -------------------------------------------------------------
            self.consecutive_stalls += 1
            if self.consecutive_stalls > 2:
                print("[SmartAdvisor] Circuit Breaker: 2 recovery pulses failed. Pausing to prevent spam.")
                self.bot.pause_hunting = True
                self.bot.hunting_status = "Paused (Circuit Breaker: Inactive)"
                smart_advisor.record_incident(
                    trigger="CIRCUIT_BREAKER_TRIPPED",
                    context={"stalls": self.consecutive_stalls, "channel": active_channel.id},
                    ai_output=diagnosis,
                    suggested_patch="Check if PokéMeow is experiencing a network outage or if account was logged out.",
                    success=False,
                )
                await self.bot.log()
                return

            # Send safe pulse command to wake up the bot cycle
            pulse_cmd = ";p"
            if getattr(self.bot.config, "hunting_channel_id", 0) != 0:
                pulse_cmd = ";p"
            elif getattr(self.bot.config, "fishing_channel_id", 0) != 0:
                pulse_cmd = ";fish spawn"

            print(f"[SmartAdvisor] Dispatching recovery pulse '{pulse_cmd}' to kickstart bot...")
            await asyncio.sleep(randint(1000, 2500) / 1000.0)
            await active_channel.send(pulse_cmd)
            self.mark_active()

        except Exception as exc:
            logger.error("Watchdog loop error: %s", exc, exc_info=True)
        finally:
            self._watchdog_running_check = False

    # =========================================================================
    # Edge-Case Listener: Unhandled Interactive Components
    # =========================================================================

    @commands.Cog.listener()
    async def on_message(self, message: Message) -> None:
        await self._process_message_for_unhandled_components(message)

    @commands.Cog.listener()
    async def on_message_edit(self, _before: Message, after: Message) -> None:
        await self._process_message_for_unhandled_components(after)

    async def _process_message_for_unhandled_components(self, message: Message) -> None:
        if not message or not message.channel:
            return

        # Check if message is a user command to inspect AI status
        if message.content:
            text = message.content.strip().lower()
            if text in (";ai status", "!ai status"):
                quota = smart_advisor.get_quota_status()
                now = time.time()
                inactive = int(now - self.last_active_timestamp)
                rpd = quota.get("requests_today", 0)
                total = quota.get("total_all_time", 0)
                await message.channel.send(
                    f"🤖 **Smart Advisor Status**\n"
                    f"• **AI Model**: `{smart_advisor.model}` (Fallback: `{smart_advisor.fallback_model}`)\n"
                    f"• **Quota Today**: `{rpd} / {smart_advisor.max_rpd}` requests used\n"
                    f"• **Total AI Invocations**: `{total}`\n"
                    f"• **Watchdog**: Active (Last activity: `{inactive}s` ago)\n"
                    f"• **Stall Count**: `{self.consecutive_stalls}`"
                )
                return

            if text in (";ai unfreeze", "!ai unfreeze"):
                af_cog = self.bot.get_cog("AutoFight")
                if af_cog and hasattr(af_cog, "abort_battle_run"):
                    await af_cog.abort_battle_run("manual_ai_unfreeze")
                self.bot.world_boss_active = False
                self.bot.autofight_active = False
                self.bot.pause_hunting = False
                self.bot.pause_fishing = False
                self.consecutive_stalls = 0
                self.mark_active()
                await message.channel.send("✅ **Smart Advisor**: All locks cleared, bot unfreezed!")
                await message.channel.send(";p")
                return

        # Only evaluate PokéMeow messages
        author_id = getattr(getattr(message, "author", None), "id", 0)
        if author_id != POKEMEOW_APP_ID:
            return

        # Crucial guard: Only evaluate messages belonging to THIS bot account
        if not self._is_message_for_this_bot(message):
            return

        # Record activity because our bot received a targeted event
        self.mark_active()

        # Channel scope check: only inspect channels configured for this bot
        channel_id = int(getattr(message.channel, "id", 0) or 0)
        allowed_channels = {
            int(getattr(getattr(self.bot, "config", None), "hunting_channel_id", 0) or 0),
            int(getattr(getattr(self.bot, "config", None), "fishing_channel_id", 0) or 0),
            int(getattr(getattr(self.bot, "config", None), "autofight_channel_id", 0) or 0),
            int(getattr(getattr(self.bot, "config", None), "world_boss_channel_id", 0) or 0),
        }
        allowed_channels.discard(0)
        if allowed_channels and channel_id not in allowed_channels:
            return

        # Ignore if bot is actively fighting or in a WorldBoss encounter (handled by battle cogs)
        if (
            is_in_battle(self.bot)
            or bool(getattr(self.bot, "autofight_active", False))
            or bool(getattr(self.bot, "world_boss_active", False))
        ):
            return

        buttons = _extract_clickable_buttons(message)
        if not buttons:
            return

        # Fast exclusion of routine hunting and fishing spawns / catches / escapes
        initial_cids = [b[1]["custom_id"] for b in buttons]
        initial_text = (message.content or "") + " " + " ".join(
            (e.title or "") + " " + (e.description or "") for e in getattr(message, "embeds", []) or []
        )
        if _is_routine_encounter_or_ball_button(initial_cids, initial_text):
            return

        # Avoid processing same message repeatedly
        if message.id in self._handled_message_ids:
            return

        # Grace period: let normal cogs (Hunting, Fishing, WorldBoss, Captcha) claim it first
        await asyncio.sleep(2.0)

        # Refresh message to verify buttons are still active and unclicked
        try:
            current_message = await message.channel.fetch_message(message.id)
            current_buttons = _extract_clickable_buttons(current_message)
        except Exception:
            return

        if not current_buttons:
            return

        # Re-verify that refreshed message is not a routine encounter
        refreshed_cids = [b[1]["custom_id"] for b in current_buttons]
        refreshed_text = (current_message.content or "") + " " + " ".join(
            (e.title or "") + " " + (e.description or "") for e in getattr(current_message, "embeds", []) or []
        )
        if _is_routine_encounter_or_ball_button(refreshed_cids, refreshed_text):
            return

        # This is a TRUE unhandled interactive prompt!
        self._handled_message_ids.add(message.id)
        if len(self._handled_message_ids) > 100:
            self._handled_message_ids.pop()

        print(f"[SmartAdvisor] Unhandled interactive prompt detected on message {message.id}. Consulting Gemini...")
        message_data = {
            "content": current_message.content or "",
            "embed_titles": [e.title for e in current_message.embeds if getattr(e, "title", None)],
            "embed_descriptions": [e.description for e in current_message.embeds if getattr(e, "description", None)],
        }
        button_metas = [b[1] for b in current_buttons]

        advice = await smart_advisor.advise_unhandled_interaction(message_data, button_metas)
        if advice.get("action") == "CLICK_BUTTON" and "validated_button" in advice:
            matched_meta = advice["validated_button"]
            for btn_component, bmeta in current_buttons:
                if bmeta.get("custom_id") == matched_meta.get("custom_id"):
                    print(f"[SmartAdvisor] AI clicking '{bmeta.get('label')}' (Reason: {advice.get('reason')})")
                    try:
                        await btn_component.click()
                        self.mark_active()
                    except InvalidData:
                        pass
                    except Exception as exc:
                        if "50035" in str(exc) or "Component validation failed" in str(exc):
                            logger.info("Button component expired or unavailable: %s", exc)
                        else:
                            logger.error("Failed clicking AI validated button: %s", exc)
