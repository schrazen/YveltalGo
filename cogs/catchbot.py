from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks
from modules.cloudflare_indicator import (
    is_cloudflare_1015_error,
    notify_cloudflare_in_channel,
)

if TYPE_CHECKING:
    from main import PokeGrinder

POKEMEOW_APP_ID = 664508672713424926


class CatchBot(commands.Cog):
    def __init__(self, bot: PokeGrinder):
        self.bot = bot
        self.last_check_at: float = 0.0
        self.last_run_attempt_at: float = 0.0
        self.last_check_command_at: float = 0.0
        self.next_expected_return_at: float = 0.0
        self.next_expected_return_text: str = ""
        self.catchbot_running: bool = False
        self.min_run_attempt_interval_seconds: float = 20.0
        self.min_post_check_to_run_seconds: float = 3.2
        self.run_retry_task: asyncio.Task | None = None
        self.status_probe_task: asyncio.Task | None = None
        self.eta_backfill_task: asyncio.Task | None = None
        self.last_eta_probe_at: float = 0.0
        self.eta_probe_cooldown_seconds: float = 120.0

        self.catchbot_check_loop.start()
        print(
            f"[CatchBot] Enabled (channel={self.bot.config.catchbot_channel_id}, "
            f"check_interval={self.bot.config.catchbot_check_interval_seconds}s)."
        )

    def cog_unload(self):
        if self.catchbot_check_loop.is_running():
            self.catchbot_check_loop.cancel()
        if self.run_retry_task and not self.run_retry_task.done():
            self.run_retry_task.cancel()
        if self.status_probe_task and not self.status_probe_task.done():
            self.status_probe_task.cancel()
        if self.eta_backfill_task and not self.eta_backfill_task.done():
            self.eta_backfill_task.cancel()

    def _get_channel(self):
        channel = getattr(self.bot, "catchbot_channel", None)
        if channel is not None:
            return channel

        channel_id = int(getattr(self.bot.config, "catchbot_channel_id", 0) or 0)
        if channel_id <= 0:
            return None

        channel = self.bot.get_channel(channel_id)
        if channel is not None:
            self.bot.catchbot_channel = channel
        return channel

    async def _get_channel_async(self):
        channel = self._get_channel()
        if channel is not None:
            return channel

        channel_id = int(getattr(self.bot.config, "catchbot_channel_id", 0) or 0)
        if channel_id <= 0:
            return None

        try:
            fetched = await self.bot.fetch_channel(channel_id)
        except Exception:
            return None

        self.bot.catchbot_channel = fetched
        return fetched

    @staticmethod
    def _strip_discord_emojis(raw_text: str) -> str:
        # Remove Discord emoji codes like :alarm_clock:, :empty:, etc.
        return re.sub(r":[a-z_]+:", "", str(raw_text or ""), flags=re.IGNORECASE)

    @staticmethod
    def _parse_return_timestamp(raw_text: str) -> float:
        # Example: "It will be back on ... 01 April 2026 16:20 with 152 Pokemon."
        # First strip Discord emoji codes that might interfere with regex
        cleaned = CatchBot._strip_discord_emojis(raw_text)
        m = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\s+(\d{2}):(\d{2})", str(cleaned or ""))
        if not m:
            return 0.0

        try:
            day = int(m.group(1))
            month_name = str(m.group(2) or "").strip().lower()
            year = int(m.group(3))
            hour = int(m.group(4))
            minute = int(m.group(5))
            months = {
                "january": 1,
                "february": 2,
                "march": 3,
                "april": 4,
                "may": 5,
                "june": 6,
                "july": 7,
                "august": 8,
                "september": 9,
                "october": 10,
                "november": 11,
                "december": 12,
            }
            month = months.get(month_name)
            if month is None:
                return 0.0

            dt = datetime(year, month, day, hour, minute)
            return dt.timestamp()
        except Exception:
            return 0.0

    @staticmethod
    def _parse_return_text(raw_text: str) -> str:
        cleaned = CatchBot._strip_discord_emojis(raw_text)
        m = re.search(r"(\d{1,2}\s+[A-Za-z]+\s+\d{4}\s+\d{2}:\d{2})", str(cleaned or ""))
        if not m:
            return ""
        return str(m.group(1) or "").strip()

    @staticmethod
    def _parse_duration_hours(raw_text: str) -> int:
        # Only parse duration when it appears in CatchBot return context.
        # Avoid matching upgrade lines like "Duration - 10H" or "catch ... in 10H".
        m = re.search(
            r"it\s+will\s+be\s+back[^\n\r]{0,80}?\bin\s+(\d+)\s*h\b",
            str(raw_text or ""),
            flags=re.IGNORECASE,
        )
        if not m:
            return 0
        try:
            return max(0, int(m.group(1)))
        except Exception:
            return 0

    @staticmethod
    def _parse_hourly_rate(raw_text: str) -> int:
        m = re.search(r"pokemon\s*-\s*(\d+)\s*/\s*h\b", str(raw_text or ""), flags=re.IGNORECASE)
        if not m:
            return 0
        try:
            return max(0, int(m.group(1)))
        except Exception:
            return 0

    @staticmethod
    def _parse_remaining_pokemon(raw_text: str) -> int:
        text = str(raw_text or "")
        patterns = [
            r"it\s+will\s+be\s+back[^\n\r]{0,180}?with\s*(\d+)\s*pokemon\b",
            r"with\s*(\d+)\s*pokemon\b",
        ]
        for pattern in patterns:
            m = re.search(pattern, text, flags=re.IGNORECASE)
            if not m:
                continue
            try:
                return max(0, int(m.group(1)))
            except Exception:
                continue
        return 0

    @classmethod
    def _estimate_return_timestamp(cls, raw_text: str) -> float:
        rate = cls._parse_hourly_rate(raw_text)
        remaining = cls._parse_remaining_pokemon(raw_text)
        if rate <= 0 or remaining <= 0:
            return 0.0
        return time.time() + ((remaining / float(rate)) * 3600.0)

    @staticmethod
    def _is_running_signal(raw_text: str) -> bool:
        lowered = str(raw_text or "").lower()
        return (
            "currently catching pokemon" in lowered
            or "it will be back with" in lowered
            or "it will be back on" in lowered
            or "already running" in lowered
        )

    @staticmethod
    def _is_ready_signal(raw_text: str) -> bool:
        lowered = str(raw_text or "").lower()
        return (
            "ready to start catching" in lowered
            or ";catchbot run to run your catchbot" in lowered
            or ";cb run" in lowered
        )

    @staticmethod
    def _is_returned_signal(raw_text: str) -> bool:
        lowered = str(raw_text or "").lower()
        return (
            "catchbot returned" in lowered
            or "i have returned with some pokemon" in lowered
        )

    @staticmethod
    def _parse_wait_seconds(raw_text: str) -> float:
        lowered = str(raw_text or "").lower()
        m = re.search(r"please\s+wait\s+[^\n\r]*?(\d+)\s*seconds?", lowered)
        if m:
            try:
                return max(1.0, float(int(m.group(1))))
            except Exception:
                return 2.0
        if "please wait" in lowered:
            return 2.0
        return 0.0

    @staticmethod
    def _normalize_identity_token(value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", str(value or "").lower())

    @staticmethod
    def _extract_owner_name(raw_text: str) -> str:
        # Example: "schrazen's CatchBot"
        m = re.search(r"([A-Za-z0-9_\-\.]{2,40})\s*[\'\u2019]s\s+catchbot", str(raw_text or ""), flags=re.IGNORECASE)
        if not m:
            return ""
        return str(m.group(1) or "").strip()

    def _is_message_for_this_bot(self, message: discord.Message, combined_text: str) -> bool:
        # Strongest signal: interaction user id must match this account.
        try:
            interaction_user = getattr(getattr(message, "interaction", None), "user", None)
            if interaction_user is not None and self.bot.user is not None:
                if int(getattr(interaction_user, "id", 0) or 0) == int(getattr(self.bot.user, "id", 0) or 0):
                    return True
        except Exception:
            pass

        # Fallback to owner name in embed text.
        owner_name = self._extract_owner_name(combined_text)
        bot_name = str(getattr(self.bot, "user", None) or "")
        if bot_name:
            bot_name = bot_name.split("#", 1)[0].strip()

        owner_norm = self._normalize_identity_token(owner_name)
        bot_norm = self._normalize_identity_token(bot_name)
        if bool(owner_norm and bot_norm and owner_norm == bot_norm):
            return True

        # Final fallback: accept catchbot replies shortly after this account issued
        # a catchbot command, useful when owner text is omitted/altered in embeds.
        if self._is_catchbot_related_message(combined_text):
            last_command_ts = max(float(self.last_check_command_at or 0.0), float(self.last_run_attempt_at or 0.0))
            if last_command_ts > 0 and (time.time() - last_command_ts) <= 25.0:
                return True

        return False

    def _schedule_run_retry(self, delay_seconds: float, reason: str) -> None:
        delay = max(1.0, float(delay_seconds))
        if self.run_retry_task and not self.run_retry_task.done():
            return

        async def _runner():
            try:
                await asyncio.sleep(delay)
                await self._try_run_now(reason=reason)
            except asyncio.CancelledError:
                return

        self.run_retry_task = asyncio.create_task(_runner())

    def _schedule_status_probe(self, delay_seconds: float, source: str) -> None:
        delay = max(1.0, float(delay_seconds))
        if self.status_probe_task and not self.status_probe_task.done():
            return

        async def _runner():
            try:
                await asyncio.sleep(delay)
                await self.trigger_catchbot_check(source=source)
            except asyncio.CancelledError:
                return

        self.status_probe_task = asyncio.create_task(_runner())

    def _schedule_eta_backfill(self, delay_seconds: float) -> None:
        delay = max(1.0, float(delay_seconds))
        if self.eta_backfill_task and not self.eta_backfill_task.done():
            return

        async def _runner():
            try:
                await asyncio.sleep(delay)
                await self._backfill_eta_from_recent_messages()
            except asyncio.CancelledError:
                return
            except Exception:
                return

        self.eta_backfill_task = asyncio.create_task(_runner())

    async def _backfill_eta_from_recent_messages(self) -> None:
        channel = await self._get_channel_async()
        if channel is None:
            return

        try:
            async for msg in channel.history(limit=12):
                if int(getattr(msg.author, "id", 0) or 0) != POKEMEOW_APP_ID:
                    continue

                parts: list[str] = [str(msg.content or "")]
                for em in msg.embeds or []:
                    parts.append(str(em.title or ""))
                    parts.append(str(em.description or ""))
                    parts.append(str(getattr(getattr(em, "author", None), "name", "") or ""))
                    if getattr(em, "footer", None):
                        parts.append(str(em.footer.text or ""))
                    for field in getattr(em, "fields", []) or []:
                        parts.append(str(field.name or ""))
                        parts.append(str(field.value or ""))

                combined = "\n".join(parts)
                if not self._is_catchbot_related_message(combined):
                    continue

                parsed_return = self._parse_return_timestamp(combined)
                if parsed_return <= 0:
                    parsed_return = self._estimate_return_timestamp(combined)
                    if parsed_return <= 0:
                        continue

                if not self._is_message_for_this_bot(msg, combined):
                    continue

                parsed_text = self._parse_return_text(combined)
                self.catchbot_running = True
                self.next_expected_return_at = parsed_return
                if parsed_text:
                    self.next_expected_return_text = parsed_text
                self.bot.catchbot_status = "CatchBot running"
                return
        except Exception:
            return

    @staticmethod
    def _is_catchbot_related_message(raw_text: str) -> bool:
        lowered = str(raw_text or "").lower()
        if not lowered:
            return False

        return any(
            signal in lowered
            for signal in (
                "catch bot",
                "catchbot",
                ";cb",
                ";catchbot",
                "currently catching pokemon",
                "ready to start catching",
                "it will be back on",
                "it will be back with",
                "already running",
            )
        )

    async def _try_run_now(self, reason: str) -> bool:
        if self.bot.pause_hunting or self.bot.pause_fishing:
            return False

        if self.catchbot_running:
            return False

        now = time.time()

        if self.last_check_command_at > 0:
            elapsed_after_check = now - self.last_check_command_at
            if elapsed_after_check < self.min_post_check_to_run_seconds:
                await asyncio.sleep(self.min_post_check_to_run_seconds - elapsed_after_check)
                now = time.time()

        if now - self.last_run_attempt_at < self.min_run_attempt_interval_seconds:
            return False

        channel = await self._get_channel_async()
        if channel is None:
            self.bot.catchbot_status = "No catchbot channel"
            return False

        try:
            await channel.send(";cb run")
            self.last_run_attempt_at = now
            self.catchbot_running = True
            self.bot.catchbot_status = "CatchBot run dispatched"
            self._schedule_status_probe(4.0, source="post_run_probe")
            print(f"[CatchBot] Dispatched ';cb run' ({reason}).")
            return True
        except Exception as exc:
            error_text = str(exc)
            self.bot.catchbot_status = "CatchBot run failed"
            print(f"[CatchBot] Failed sending ';cb run' ({reason}): {error_text}")
            if is_cloudflare_1015_error(error_text):
                await notify_cloudflare_in_channel(
                    self.bot,
                    channel_id=int(getattr(self.bot.config, "catchbot_channel_id", 0) or 0),
                    module_name="CatchBot",
                    error_text=error_text,
                    cooldown_seconds=90.0,
                    wait_seconds=self._parse_wait_seconds(error_text),
                )
            return False

    async def trigger_catchbot_check(self, source: str = "loop") -> bool:
        channel = await self._get_channel_async()
        if channel is None:
            return False

        try:
            await channel.send(";cb")
            self.last_check_at = time.time()
            self.last_check_command_at = self.last_check_at
            self.bot.catchbot_status = f"Checking ({source})"
            self._schedule_eta_backfill(2.4)
            return True
        except Exception as exc:
            error_text = str(exc)
            print(f"[CatchBot] Failed sending ';cb' ({source}): {error_text}")
            self.bot.catchbot_status = "CatchBot check failed"
            if is_cloudflare_1015_error(error_text):
                await notify_cloudflare_in_channel(
                    self.bot,
                    channel_id=int(getattr(self.bot.config, "catchbot_channel_id", 0) or 0),
                    module_name="CatchBot",
                    error_text=error_text,
                    cooldown_seconds=90.0,
                    wait_seconds=self._parse_wait_seconds(error_text),
                )
            return False

    @tasks.loop(seconds=60)
    async def catchbot_check_loop(self):
        if not bool(getattr(self.bot.config, "catchbot_enabled", False)):
            return

        if not bool(getattr(self.bot, "server_scope_valid", True)):
            return

        now = time.time()
        interval = max(120, int(getattr(self.bot.config, "catchbot_check_interval_seconds", 900) or 900))

        # If we know return ETA and it's still far away, avoid unnecessary polling.
        if self.catchbot_running and self.next_expected_return_at > 0 and now < (self.next_expected_return_at - 120):
            self.bot.catchbot_status = "CatchBot running"
            return

        if now - self.last_check_at < interval:
            return

        await self.trigger_catchbot_check(source="loop")

    @catchbot_check_loop.before_loop
    async def before_catchbot_loop(self):
        await self.bot.wait_until_ready()

    async def _process_catchbot_message(self, message: discord.Message) -> None:
        if not bool(getattr(self.bot.config, "catchbot_enabled", False)):
            return

        if int(getattr(message.author, "id", 0) or 0) != POKEMEOW_APP_ID:
            return

        channel_id = int(getattr(self.bot.config, "catchbot_channel_id", 0) or 0)
        msg_channel_id = int(getattr(message.channel, "id", 0) or 0)
        msg_parent_id = int(getattr(message.channel, "parent_id", 0) or 0)
        if msg_channel_id != channel_id and msg_parent_id != channel_id:
            return

        parts: list[str] = [str(message.content or "")]
        for em in message.embeds or []:
            parts.append(str(em.title or ""))
            parts.append(str(em.description or ""))
            parts.append(str(getattr(getattr(em, "author", None), "name", "") or ""))
            if getattr(em, "footer", None):
                parts.append(str(em.footer.text or ""))
            for field in getattr(em, "fields", []) or []:
                parts.append(str(field.name or ""))
                parts.append(str(field.value or ""))
            try:
                embed_payload = em.to_dict() if hasattr(em, "to_dict") else {}
                if isinstance(embed_payload, dict):
                    for key in ("title", "description"):
                        if key in embed_payload:
                            parts.append(str(embed_payload.get(key) or ""))
                    author_payload = embed_payload.get("author")
                    if isinstance(author_payload, dict):
                        parts.append(str(author_payload.get("name") or ""))
                    footer_payload = embed_payload.get("footer")
                    if isinstance(footer_payload, dict):
                        parts.append(str(footer_payload.get("text") or ""))
                    for field_payload in embed_payload.get("fields", []) or []:
                        if isinstance(field_payload, dict):
                            parts.append(str(field_payload.get("name") or ""))
                            parts.append(str(field_payload.get("value") or ""))
            except Exception:
                pass

        combined = "\n".join(parts)

        parsed_return = self._parse_return_timestamp(combined)
        parsed_text = self._parse_return_text(combined)

        is_for_this_bot = self._is_message_for_this_bot(message, combined)
        if not is_for_this_bot:
            # Fallback for embed variants where owner text is omitted from parsed
            # message fields but an explicit return ETA line is still present.
            last_activity_at = max(
                float(self.last_check_at or 0.0),
                float(self.last_check_command_at or 0.0),
                float(self.last_run_attempt_at or 0.0),
            )
            recent_activity = last_activity_at > 0 and (time.time() - last_activity_at) <= 180.0
            if parsed_return > 0 and (self.catchbot_running or recent_activity):
                is_for_this_bot = True

        if not is_for_this_bot:
            return

        if not self._is_catchbot_related_message(combined):
            return

        if parsed_return > 0:
            self.catchbot_running = True
            self.next_expected_return_at = parsed_return
            self.next_expected_return_text = parsed_text
            self.bot.catchbot_status = "CatchBot running"
            return

        wait_seconds = self._parse_wait_seconds(combined)
        if wait_seconds > 0:
            self.bot.catchbot_status = f"CatchBot cooldown ({int(wait_seconds)}s)"
            self._schedule_run_retry(wait_seconds + 0.8, reason="cb_wait_retry")
            return

        if self._is_running_signal(combined):
            self.catchbot_running = True
            if parsed_text:
                self.next_expected_return_text = parsed_text
            hrs = self._parse_duration_hours(combined)
            if hrs > 0:
                self.next_expected_return_at = time.time() + (hrs * 3600)
            else:
                estimated = self._estimate_return_timestamp(combined)
                if estimated > 0:
                    self.next_expected_return_at = estimated
                elif time.time() - self.last_eta_probe_at >= self.eta_probe_cooldown_seconds:
                    self.last_eta_probe_at = time.time()
                    self._schedule_status_probe(3.0, source="running_eta_probe")
            self.bot.catchbot_status = "CatchBot running"
            return

        if self._is_returned_signal(combined):
            self.catchbot_running = False
            self.next_expected_return_at = 0.0
            self.next_expected_return_text = ""
            self.bot.catchbot_status = "CatchBot returned"
            await asyncio.sleep(1.2)
            await self._try_run_now(reason="returned")
            return

        if self._is_ready_signal(combined):
            self.catchbot_running = False
            self.next_expected_return_at = 0.0
            self.next_expected_return_text = ""
            self.bot.catchbot_status = "CatchBot ready"
            await asyncio.sleep(2.2)
            await self._try_run_now(reason="ready")
            return

    @commands.Cog.listener("on_message")
    async def on_catchbot_response(self, message: discord.Message):
        await self._process_catchbot_message(message)

    @commands.Cog.listener("on_message_edit")
    async def on_catchbot_response_edit(self, _before: discord.Message, after: discord.Message):
        await self._process_catchbot_message(after)


async def setup(bot: PokeGrinder):
    await bot.add_cog(CatchBot(bot))
