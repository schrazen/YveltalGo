from __future__ import annotations

import asyncio
import logging
import re
import time
from random import randint
from typing import Any

from discord import Message, TextChannel
from discord.ext import commands, tasks

from modules.captcha_gate import is_captcha_active, is_in_battle
from modules.challenge_manager import find_eligible_npc_for_quest, parse_challenges_text
from modules.quest_catalog import quest_catalog
from modules.runtime_file_log import info as runtime_info_log

logger = logging.getLogger("pokegrinder.quest")
POKEMEOW_APP_ID = 664508672713424926


class QuestManager(commands.Cog):
    """Coordinates PokéMeow quest lifecycle:
    1. Monitors active daily quests and registers them into the Quest Catalog.
    2. Auto-resets quests configured for 'auto_reset' (e.g. Mega Chamber) using ';quest reset <id>' and auto-buys scrolls if needed.
    3. Auto-finishes doable battle quests configured for 'auto_complete' (e.g. Challengers, Trainer/NPC battles) via AutoFight.
    4. Enforces strict mutual exclusion between auto-battling and catching/fishing.
    5. Syncs ;challenges and 'Battle invitations' to battle invited NPCs or auto-reset impossible Master challenges.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.config = bot.config
        self._last_eval_at: float = 0.0
        self._last_reset_per_slot: dict[int, float] = {}
        self._last_battle_quest_dispatch_at: float = 0.0
        self._eval_lock = asyncio.Lock()
        self._pending_scroll_buy_for_slot: int | None = None
        self._last_scroll_buy_at: float = 0.0
        self._syncing_challenges: bool = False
        self._last_challenge_sync_at: float = 0.0

        if not hasattr(self.bot, "quest_data") or not isinstance(self.bot.quest_data, dict):
            self.bot.quest_data = {
                "next_quest": "",
                "active_quests": [],
                "last_completed": {},
                "last_updated_utc": "",
            }

        if not hasattr(self.bot, "challenge_data") or not isinstance(self.bot.challenge_data, dict):
            self.bot.challenge_data = {
                "basic": [{"name": "trainer_steven", "id": 210, "tier": "basic"}],
                "boss": [],
                "master": [],
                "invitations": [],
                "has_no_invites": False,
                "last_synced_utc": 0.0,
            }

        # Start background loop
        self.quest_supervisor_loop.start()

    def cog_unload(self) -> None:
        self.quest_supervisor_loop.cancel()

    async def sync_challenges(self, channel: TextChannel | None = None) -> bool:
        """Dispatches ;challenges to check available challenges and active invitations."""
        now = time.time()
        last_sync = float(getattr(self, "_last_challenge_sync_at", 0.0) or 0.0)
        if (now - last_sync) < 25.0:
            return False
        if is_captcha_active(self.bot) or is_in_battle(self.bot):
            return False

        target_channel = channel
        if target_channel is None:
            af_channel_id = int(getattr(self.config, "autofight_channel_id", 0) or 0)
            if af_channel_id:
                target_channel = getattr(self.bot, "autofight_channel", None) or self.bot.get_channel(af_channel_id)
        if target_channel is None:
            target_channel = getattr(self.bot, "hunting_channel", None)

        if target_channel is None:
            return False

        self._last_challenge_sync_at = now
        self._syncing_challenges = True
        runtime_info_log("[QuestManager] Querying ;challenges to verify battle invitations...")
        return await self._safe_send_text_or_slash(target_channel, ";challenges")

    def is_impossible_quest(self, title: str) -> bool:
        """Return True if the quest title matches impossible criteria or is configured for auto_reset."""
        raw = str(title or "").lower().strip()
        if not raw:
            return False

        # 1. Check user/catalog rule resolution
        decision = quest_catalog.resolve_quest_action(raw)
        if decision.get("action") == "auto_reset" or decision.get("is_impossible", False):
            return True

        # 2. Check challenge eligibility (e.g. Master/Boss challengers without active invitation)
        ch_data = getattr(self.bot, "challenge_data", None)
        is_doable, mode, reason = find_eligible_npc_for_quest(raw, ch_data)
        if not is_doable and reason in ("no_master_invite", "no_boss_invite"):
            return True

        if decision.get("action") in ("auto_complete", "ignore") and not decision.get("is_impossible", False):
            return False

        # 3. Check config keywords fallback
        keywords = getattr(self.config, "quest_impossible_keywords", None)
        if not keywords or not isinstance(keywords, list):
            keywords = ["mega chamber", "megachamber"]

        for kw in keywords:
            if str(kw).lower().strip() in raw:
                return True
        return False

    def classify_battle_quest(self, title: str) -> tuple[bool, str]:
        """Classify if a quest is a battle quest and return (is_battle, battle_mode).
        Uses challenge_manager to dynamically choose the correct NPC ID (e.g. Steven 210 for basic/general,
        or invited Master/Boss NPC ID).
        """
        raw = str(title or "").lower().strip()
        if not raw or self.is_impossible_quest(raw):
            return False, ""

        decision = quest_catalog.resolve_quest_action(raw)
        # If user explicitly configured this quest for ignore or auto_reset, do not auto-battle
        if decision.get("action") != "auto_complete":
            return False, ""

        # Determine via challenge_manager
        ch_data = getattr(self.bot, "challenge_data", None)
        is_doable, mode, reason = find_eligible_npc_for_quest(raw, ch_data)
        if is_doable and mode:
            return True, mode

        # Fallback to decision.get("battle_mode") if specified and valid
        bm = decision.get("battle_mode")
        if bm and str(bm) not in ("master_challenger", "elite_challenger", "champion_challenger"):
            return True, str(bm)

        return False, ""

    async def _safe_send_text_or_slash(
        self,
        channel: TextChannel,
        command_text: str,
        slash_command_name: str | None = None,
        slash_options: dict[str, Any] | None = None,
    ) -> bool:
        """Dispatches a command safely with jitter delay and captcha checks."""
        if channel is None:
            return False
        ch_id = getattr(channel, "id", None)
        if is_captcha_active(self.bot, ch_id):
            return False

        delay = 1.2 + (randint(100, 600) / 1000.0)
        await asyncio.sleep(delay)

        if is_captcha_active(self.bot, ch_id):
            return False

        # Try slash command first if available
        if slash_command_name:
            cmd_map = getattr(self.bot, "hunting_channel_commands", None) or {}
            candidate = cmd_map.get(slash_command_name)
            if candidate is not None:
                try:
                    if slash_options:
                        await candidate(**slash_options)
                    else:
                        await candidate()
                    return True
                except Exception as exc:
                    logger.debug(f"[QuestManager] Slash {slash_command_name} failed: {exc}, falling back to text")

        # Fallback to text command
        try:
            await channel.send(command_text)
            return True
        except Exception as exc:
            logger.warning(f"[QuestManager] Text dispatch '{command_text}' failed: {exc}")
            return False

    async def reset_quest_slot(self, slot_id: int, reason: str = "") -> bool:
        """Reset a specific quest slot using ';quest reset <id>'."""
        slot = int(slot_id)
        if slot not in (1, 2, 3):
            return False

        if is_captcha_active(self.bot):
            runtime_info_log(f"[QuestManager] Reset slot #{slot} aborted: captcha is active.")
            return False

        channel = getattr(self.bot, "hunting_channel", None) or getattr(self.bot, "fishing_channel", None)
        if channel is None:
            runtime_info_log(f"[QuestManager] No channel available to reset quest slot #{slot}.")
            return False

        now = time.time()
        last_reset = self._last_reset_per_slot.get(slot, 0.0)
        if (now - last_reset) < 45.0:
            return False
        self._last_reset_per_slot[slot] = now

        runtime_info_log(f"[QuestManager] Dispatching quest reset for slot #{slot} (reason: {reason or 'requested'}).")
        ok = await self._safe_send_text_or_slash(
            channel,
            f";quest reset {slot}",
            slash_command_name="quest reset",
            slash_options={"number": slot},
        )

        if ok:
            # Schedule sync after short delay
            asyncio.create_task(self._delayed_sync_quest_info(3.0))
        return ok

    async def auto_buy_reset_scroll(self, retry_slot: int | None = None) -> bool:
        """Auto-buys a Quest Reset Scroll (Shop item 6, 10,000 coins) and retries reset if requested."""
        if not bool(getattr(self.config, "quest_auto_buy_scroll", True)):
            return False

        now = time.time()
        if (now - self._last_scroll_buy_at) < 30.0:
            return False
        self._last_scroll_buy_at = now

        if is_captcha_active(self.bot):
            return False

        channel = getattr(self.bot, "hunting_channel", None) or getattr(self.bot, "fishing_channel", None)
        if channel is None:
            return False

        runtime_info_log("[QuestManager] Buying Quest Reset Scroll (Item 6, 10,000 coins)...")
        ok = await self._safe_send_text_or_slash(
            channel,
            ";shop buy 6",
            slash_command_name="shop buy",
            slash_options={"item": "6", "amount": 1},
        )

        if ok and retry_slot is not None:
            await asyncio.sleep(2.5)
            if not is_captcha_active(self.bot):
                runtime_info_log(f"[QuestManager] Retrying reset for slot #{retry_slot} with newly bought scroll...")
                await self.reset_quest_slot(retry_slot, reason="retry_after_scroll_purchase")
        return ok

    async def _delayed_sync_quest_info(self, delay_seconds: float) -> None:
        """Wait delay_seconds and trigger safe_request_quest_info."""
        await asyncio.sleep(delay_seconds)
        channel = getattr(self.bot, "hunting_channel", None) or getattr(self.bot, "fishing_channel", None)
        cmd_map = getattr(self.bot, "hunting_channel_commands", None)
        if channel is not None and not is_captcha_active(self.bot):
            from cogs.hunting import safe_request_quest_info
            await safe_request_quest_info(self.bot, channel, cmd_map, source="quest_manager_sync")

    async def evaluate_and_process_quests(self, source: str = "periodic") -> dict[str, Any]:
        """Core decision engine:
        1. Resets impossible quests (e.g. Mega Chamber) if auto-reset is enabled.
        2. Dispatches battle quests (Challengers, NPC/Trainer) to AutoFight if doable and enabled.
        """
        if self._eval_lock.locked():
            return {"ok": False, "reason": "already_evaluating"}

        async with self._eval_lock:
            if is_captcha_active(self.bot):
                return {"ok": False, "reason": "captcha_active"}

            if is_in_battle(self.bot):
                return {"ok": False, "reason": "bot_already_in_battle"}

            quests = list(self.bot.quest_data.get("active_quests", []) or [])
            if not quests:
                # No active quests recorded yet, request quest info
                channel = getattr(self.bot, "hunting_channel", None) or getattr(self.bot, "fishing_channel", None)
                if channel is not None:
                    asyncio.create_task(self._delayed_sync_quest_info(1.0))
                return {"ok": True, "action": "requested_sync"}

            now = time.time()
            auto_reset_enabled = bool(getattr(self.config, "quest_auto_reset_enabled", True))
            auto_battle_enabled = bool(getattr(self.config, "quest_auto_battle_enabled", True))

            # Auto-register all observed quests and next-quest queue into Quest Catalog
            for q in quests:
                t = str(q.get("title", "")).strip()
                if t:
                    try:
                        quest_catalog.register_observed_quest(t)
                    except Exception:
                        pass
            nq = str(self.bot.quest_data.get("next_quest", "")).strip()
            if nq:
                try:
                    quest_catalog.register_observed_quest(nq)
                except Exception:
                    pass

            # Sync challenges if active quests contain a challenger quest and data is stale
            has_challenger_quest = any(
                "challenger" in str(q.get("title", "")).lower() for q in quests
            )
            ch_data = getattr(self.bot, "challenge_data", None) or {}
            last_sync = float(ch_data.get("last_synced_utc", 0.0) or 0.0)
            if has_challenger_quest and (now - last_sync) > 600.0:
                af_channel_id = int(getattr(self.config, "autofight_channel_id", 0) or 0)
                af_channel = getattr(self.bot, "autofight_channel", None) or (self.bot.get_channel(af_channel_id) if af_channel_id else None)
                if af_channel and not is_captcha_active(self.bot) and not is_in_battle(self.bot):
                    await self.sync_challenges(af_channel)
                    await asyncio.sleep(2.0)

            # 1. Check for IMPOSSIBLE / AUTO-RESET quests first (Priority 1)
            if auto_reset_enabled:
                for q in quests:
                    title = str(q.get("title", ""))
                    slot_id = int(q.get("id", 0) or 0)
                    if slot_id <= 0:
                        continue

                    if self.is_impossible_quest(title):
                        last_reset = self._last_reset_per_slot.get(slot_id, 0.0)
                        if (now - last_reset) >= 45.0:
                            runtime_info_log(
                                f"[QuestManager] Impossible quest detected in slot #{slot_id}: '{title}'. Auto-resetting..."
                            )
                            await self.reset_quest_slot(slot_id, reason=f"impossible_quest:{title}")
                            return {"ok": True, "action": "reset_impossible_quest", "slot": slot_id, "title": title}

            # 2. Check for DOABLE BATTLE quests (Priority 2)
            if auto_battle_enabled:
                af_channel_id = int(getattr(self.config, "autofight_channel_id", 0) or 0)
                af_cog = self.bot.get_cog("AutoFight")

                if af_channel_id != 0 and af_cog is not None and not is_in_battle(self.bot):
                    af_channel = getattr(self.bot, "autofight_channel", None) or self.bot.get_channel(af_channel_id)

                    for q in quests:
                        title = str(q.get("title", ""))
                        cur = int(q.get("progress_current", 0) or 0)
                        total = int(q.get("progress_total", 0) or 0)
                        needed = max(0, total - cur)

                        if needed <= 0:
                            continue

                        is_battle, mode = self.classify_battle_quest(title)
                        if not is_battle:
                            continue

                        # Cooldown check for battle quest dispatch
                        if (now - self._last_battle_quest_dispatch_at) < 60.0:
                            continue

                        if af_channel is not None and not is_captcha_active(self.bot):
                            self._last_battle_quest_dispatch_at = now
                            target_battles = min(needed, 5)
                            runtime_info_log(
                                f"[QuestManager] Battle quest detected: '{title}' ({cur}/{total}). "
                                f"Initiating {target_battles} {mode} battle(s) in channel {af_channel_id}..."
                            )

                            # Ensure hunting is not in the middle of active encounter
                            # Small humanized pause so any in-flight encounter resolves cleanly
                            await asyncio.sleep(2.5)
                            if is_captcha_active(self.bot):
                                return {"ok": False, "reason": "captcha_active_pre_battle"}

                            started = await af_cog.start_battle_run(
                                af_channel,
                                count=target_battles,
                                mode=mode,
                                strategy="standard",
                            )

                            if started:
                                runtime_info_log(
                                    f"[QuestManager] AutoFight successfully launched for quest '{title}' ({target_battles} battles)."
                                )
                                return {
                                    "ok": True,
                                    "action": "started_autofight_quest",
                                    "title": title,
                                    "battles": target_battles,
                                    "mode": mode,
                                }
                            else:
                                runtime_info_log(f"[QuestManager] Failed to start AutoFight for quest '{title}'.")

            return {"ok": True, "action": "none_needed"}

    @tasks.loop(seconds=60)
    async def quest_supervisor_loop(self) -> None:
        """Periodic supervisor loop to evaluate quest state."""
        try:
            await self.evaluate_and_process_quests(source="loop")
        except Exception as exc:
            logger.debug(f"[QuestManager] Error in supervisor loop: {exc}")

    @quest_supervisor_loop.before_loop
    async def before_quest_supervisor_loop(self) -> None:
        await self.bot.wait_until_ready()
        # Initial jitter
        await asyncio.sleep(15.0)

    @commands.Cog.listener()
    async def on_message(self, message: Message) -> None:
        if getattr(getattr(message, "author", None), "id", 0) != POKEMEOW_APP_ID:
            return

        text = str(message.content or "").lower()
        embed_desc = ""
        for em in getattr(message, "embeds", []) or []:
            embed_desc += " " + str(getattr(em, "description", "") or "").lower()
        combined = (text + " " + embed_desc).lower()

        # 1. Missing Quest Reset Scroll detection
        if "you do not have a quest reset scroll" in combined or "buy a quest reset scroll" in combined:
            runtime_info_log("[QuestManager] PokéMeow reported missing Quest Reset Scroll.")
            if bool(getattr(self.config, "quest_auto_buy_scroll", True)):
                # Determine which slot was attempted or retry pending
                asyncio.create_task(self.auto_buy_reset_scroll(retry_slot=self._pending_scroll_buy_for_slot))

        # 2. Successful Quest Reset confirmation
        if "you have successfully reset quest" in combined or "reset your quest" in combined:
            runtime_info_log("[QuestManager] Quest successfully reset! Refreshing quest info...")
            asyncio.create_task(self._delayed_sync_quest_info(2.5))

        # 3. Next Quest Ready notification
        if "your next quest is now ready" in combined:
            runtime_info_log("[QuestManager] Next quest ready notification detected. Syncing quest info...")
            asyncio.create_task(self._delayed_sync_quest_info(1.5))

        # 4. Quest Completed notification
        if "completed the quest" in combined:
            m = re.search(r"completed the quest\s+(.+?)\s+and received:", (message.content or "") + " " + embed_desc, re.IGNORECASE)
            if m:
                q_name = m.group(1).strip()
                if q_name:
                    try:
                        quest_catalog.register_observed_quest(q_name)
                    except Exception:
                        pass

        # 5. Challenge menu & battle invitations button handler
        is_challenge_menu = any(
            t in combined
            for t in (
                "available battling challenges",
                "challenges in pokemeow",
                "basic challenges have no requirements",
            )
        )
        if is_challenge_menu:
            # Look for "Battle invitations" button
            for row in getattr(message, "components", []) or []:
                for btn in getattr(row, "children", []) or []:
                    lbl = str(getattr(btn, "label", "") or "").lower()
                    cid = str(getattr(btn, "custom_id", "") or "").lower()
                    emoji_str = str(getattr(btn, "emoji", "") or "").lower()
                    if (
                        "invitation" in lbl
                        or "invitation" in cid
                        or "✉" in emoji_str
                        or "📩" in emoji_str
                        or "mail" in emoji_str
                        or "envelope" in emoji_str
                    ):
                        if not bool(getattr(btn, "disabled", False)):
                            try:
                                runtime_info_log("[QuestManager] Clicking 'Battle invitations' button on challenges message...")
                                await btn.click()
                            except Exception as exc:
                                logger.debug(f"[QuestManager] Error clicking invitations button: {exc}")
                        break

        # 6. Parse challenge invitations or list
        if any(
            t in combined
            for t in (
                "battle invitations",
                "active invitations",
                "no battle invitations",
                "you do not have any battle invitations",
                "you have not received an invite",
            )
        ):
            full_text = str(message.content or "")
            for em in getattr(message, "embeds", []) or []:
                full_text += "\n" + str(getattr(em, "title", "") or "")
                full_text += "\n" + str(getattr(em, "description", "") or "")
                for fld in getattr(em, "fields", []) or []:
                    full_text += f"\n{getattr(fld, 'name', '')}: {getattr(fld, 'value', '')}"
            parsed = parse_challenges_text(full_text)
            existing = getattr(self.bot, "challenge_data", {}) or {}
            if not parsed.get("basic") and existing.get("basic"):
                parsed["basic"] = existing["basic"]
            if not parsed.get("master") and existing.get("master"):
                parsed["master"] = existing["master"]
            if not parsed.get("boss") and existing.get("boss"):
                parsed["boss"] = existing["boss"]

            self.bot.challenge_data = parsed
            if isinstance(getattr(self.bot, "quest_data", None), dict):
                self.bot.quest_data["challenges"] = parsed
            inv_count = len(parsed.get("invitations", []))
            has_no_inv = parsed.get("has_no_invites", False)
            runtime_info_log(
                f"[QuestManager] Synced challenge invitations: {inv_count} active invitation(s) (no_invites={has_no_inv})."
            )
            self._syncing_challenges = False

    @commands.Cog.listener()
    async def on_message_edit(self, before: Message, after: Message) -> None:
        """Handle edits on challenge messages or quest boards."""
        await self.on_message(after)
