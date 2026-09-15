from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime, timezone
from typing import Any

from discord import Message
from discord.ext import commands, tasks

POKEMEOW_APP_ID = 664508672713424926


class LimitedEvents(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.config = bot.config
        self.poll_interval_seconds = 1800
        self.last_check_at = 0.0
        self.refresh_lock = asyncio.Lock()

        if not isinstance(getattr(self.bot, "limited_events", None), dict):
            self.bot.limited_events = self._empty_snapshot("Pending initial refresh")

        if self.config.hunting_channel_id != 0:
            self.poll_loop.start()

    def cog_unload(self) -> None:
        self.poll_loop.cancel()

    def _empty_snapshot(self, status: str) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        return {
            "status": status,
            "interval_seconds": int(self.poll_interval_seconds),
            "last_checked_utc": "",
            "next_check_utc": now.isoformat(),
            "source": "init",
            "bonus": {"ok": False, "headline": "", "event_end": "", "important_lines": [], "raw_preview": "", "error": "Not checked yet", "jump_url": ""},
            "events": {"ok": False, "headline": "", "event_end": "", "important_lines": [], "raw_preview": "", "error": "Not checked yet", "jump_url": ""},
            "unlocks": {"ok": False, "headline": "", "event_end": "", "important_lines": [], "raw_preview": "", "error": "Not checked yet", "jump_url": ""},
        }

    @staticmethod
    def _format_discord_timestamp(epoch_text: str) -> str:
        try:
            epoch = int(str(epoch_text or "").strip())
            dt = datetime.fromtimestamp(epoch, timezone.utc)
            return dt.strftime("%d %b %Y %H:%M UTC")
        except Exception:
            return str(epoch_text or "")

    def _normalize_discord_timestamps(self, text: str) -> str:
        def _replace(match: re.Match[str]) -> str:
            return self._format_discord_timestamp(str(match.group(1) or ""))

        return re.sub(r"<t:(\d{6,})(?::[tTdDfFR])?>", _replace, str(text or ""))

    @staticmethod
    def _extract_message_text(message: Message) -> str:
        parts: list[str] = [str(message.content or "")]
        for embed in list(getattr(message, "embeds", []) or []):
            parts.append(str(getattr(embed, "title", "") or ""))
            parts.append(str(getattr(embed, "description", "") or ""))
            for field in list(getattr(embed, "fields", []) or []):
                parts.append(str(getattr(field, "name", "") or ""))
                parts.append(str(getattr(field, "value", "") or ""))
            footer = getattr(embed, "footer", None)
            if footer is not None:
                parts.append(str(getattr(footer, "text", "") or ""))
        return "\n".join(part for part in parts if str(part).strip())

    def _clean_line(self, line: str) -> str:
        value = str(line or "").strip()
        if not value:
            return ""

        value = self._normalize_discord_timestamps(value)
        # Drop Discord custom emoji first (numeric-only names included) before token rewrites.
        value = re.sub(r"<a?:[^:>]+:\d+>", "", value)
        # Preserve Pokemon ID-style emoji tokens for requirement clarity (:638_: -> #638).
        value = re.sub(r":(\d{1,5})_+:", r"#\1", value)
        value = re.sub(r":(\d{1,5}):", r"#\1", value)
        value = re.sub(r":[A-Za-z0-9_]+:", "", value)
        value = re.sub(r"\*{1,2}", "", value)
        value = re.sub(r"`+", "", value)
        value = re.sub(r"\s+", " ", value).strip(" -•|\t")
        return value.strip()

    def _extract_event_end_line(self, lines: list[str]) -> str:
        for line in lines:
            lower = line.lower()
            if "event ends" in lower or "ends on" in lower or "until" in lower:
                return line
        return ""

    @staticmethod
    def _looks_like_name_line(line: str) -> bool:
        value = str(line or "").strip()
        if not value:
            return False

        lower = value.lower()
        if any(token in lower for token in ("/unlocks for", "events buy", "checked means", "spawn rate:")):
            return False

        return bool(re.search(r"[A-Z][a-z]+(?:-[A-Z][a-z]+)?", value))

    def _extract_important_lines(self, lines: list[str], command_name: str, limit: int = 12) -> list[str]:
        scored: list[tuple[int, int, str]] = []
        seen: set[str] = set()
        command_key = str(command_name or "").lower()

        hard_exclude_patterns = [
            r"^global bonuses$",
            r"^boosted spawn rates:?$",
            r"^recent player-activated bonuses$",
            r"activated a .* bonus",
            r"^player-activated global bonuses",
            r"^activate a specific, powerful",
            r"event vouchers using ;bo",
            r"event vouchers have been used by players",
            r"^id:\s*\d+",
            r"^events buy",
            r"^/unlocks for spawn information\.?$",
            r"^/unlocks for more information\.?$",
        ]

        for idx, line in enumerate(lines):
            if not line or line in seen:
                continue
            if len(line) > 280:
                continue
            if any(re.search(pattern, line, flags=re.IGNORECASE) for pattern in hard_exclude_patterns):
                continue

            seen.add(line)
            lower = line.lower()
            score = 0

            if any(token in lower for token in ("active", "inactive", "expired")):
                score += 6
            if any(token in lower for token in ("event ends", "ends on", "until")):
                score += 6
            if any(token in lower for token in ("can spawn", "spawning", "available", "back in", "rotation")):
                score += 4
            if any(token in lower for token in ("unlock", "locked", "checked means", "checklist", "vote bonuses", "player-activated")):
                score += 3
            if any(token in lower for token in ("activated", "hours ago", "day ago", "used by players")):
                score += 2
            if re.search(r"\b\d+\/\d+\b", line):
                score += 2

            if self._looks_like_name_line(line):
                score += 6

            if "unlocks" in command_key:
                if lower in {
                    "event exclusive",
                    "vote exclusive",
                    "catchable",
                    "hatch exclusive",
                    "research exclusive",
                }:
                    continue
                if any(token in lower for token in ("you need", "requires", "in your box", "ancient fossil")):
                    score += 7
                if self._looks_like_name_line(line):
                    score += 5
                if any(token in lower for token in ("on /pokemon spawn", "on legendary", "on any /fish spawn")):
                    score -= 1

            if "events" in command_key:
                if "/unlocks for" in lower:
                    score -= 6
                if "events buy" in lower:
                    score -= 4

            if "bonus" in command_key:
                if "activate a specific" in lower:
                    score -= 5
                if "event vouchers using" in lower:
                    score -= 4

            if lower in {
                "global bonuses",
                "recent player-activated bonuses",
                "pokemeow unlockable pokemon",
                "event exclusive",
                "vote exclusive",
                "catchable",
                "hatch exclusive",
                "research exclusive",
            }:
                score -= 2

            if score > 0:
                scored.append((score, idx, line))

        if not scored:
            return [line for line in lines[:limit] if line]

        scored.sort(key=lambda item: (-item[0], item[1]))
        top = scored[:limit]
        top.sort(key=lambda item: item[1])
        return [line for _, _, line in top]

    def _build_summary(
        self,
        command_name: str,
        text: str,
        ok: bool,
        error: str = "",
        jump_url: str = "",
    ) -> dict[str, Any]:
        cleaned_lines = [self._clean_line(line) for line in str(text or "").splitlines()]
        cleaned_lines = [line for line in cleaned_lines if line]

        headline = cleaned_lines[0] if cleaned_lines else ""
        event_end = self._extract_event_end_line(cleaned_lines)
        important = self._extract_important_lines(cleaned_lines, command_name=command_name, limit=12)

        raw_preview = "\n".join(cleaned_lines[:30])
        if len(raw_preview) > 2400:
            raw_preview = raw_preview[:2400] + "..."

        return {
            "ok": bool(ok),
            "command": command_name,
            "headline": headline,
            "event_end": event_end,
            "important_lines": important,
            "raw_preview": raw_preview,
            "error": str(error or ""),
            "jump_url": str(jump_url or ""),
        }

    async def _resolve_hunting_channel(self):
        channel_id = int(getattr(self.config, "hunting_channel_id", 0) or 0)
        if channel_id <= 0:
            return None

        channel = getattr(self.bot, "hunting_channel", None)
        if channel is not None:
            return channel

        channel = self.bot.get_channel(channel_id)
        if channel is not None:
            self.bot.hunting_channel = channel
            return channel

        try:
            channel = await self.bot.fetch_channel(channel_id)
            self.bot.hunting_channel = channel
            return channel
        except Exception:
            return None

    async def _request_command_response(
        self,
        channel,
        command_text: str,
        expected_keywords: list[str],
        timeout_seconds: float = 45.0,
    ) -> tuple[bool, str, str, str]:
        for attempt in range(2):
            sent_at = time.time()
            try:
                await channel.send(command_text)
            except Exception as exc:
                return False, "", "", f"Failed to dispatch {command_text}: {exc}"

            def _matches(msg: Message) -> bool:
                if int(getattr(getattr(msg, "author", None), "id", 0) or 0) != POKEMEOW_APP_ID:
                    return False
                if int(getattr(getattr(msg, "channel", None), "id", 0) or 0) != int(getattr(channel, "id", 0) or 0):
                    return False
                created_at = getattr(msg, "created_at", None)
                if created_at is not None and created_at.timestamp() < (sent_at - 0.25):
                    return False

                blob = self._extract_message_text(msg).lower()
                if not blob:
                    return False
                if any(keyword in blob for keyword in expected_keywords):
                    return True
                return command_text.replace(";", "").strip() in blob

            try:
                message: Message = await asyncio.wait_for(
                    self.bot.wait_for("message", check=_matches),
                    timeout=timeout_seconds,
                )
                payload = self._extract_message_text(message)
                return True, payload, str(getattr(message, "jump_url", "") or ""), ""
            except asyncio.TimeoutError:
                if attempt == 0:
                    await asyncio.sleep(1.0)
                    continue
                return False, "", "", f"Timed out waiting for response to {command_text}"
            except Exception as exc:
                return False, "", "", f"Error while waiting for {command_text}: {exc}"

        return False, "", "", f"Timed out waiting for response to {command_text}"

    async def refresh_limited_events(self, source: str = "scheduled") -> tuple[bool, str]:
        if self.refresh_lock.locked():
            return False, "Limited events refresh already in progress"

        async with self.refresh_lock:
            return await self._refresh_limited_events_inner(source=source)

    async def _refresh_limited_events_inner(self, source: str = "scheduled") -> tuple[bool, str]:
        if not self.bot.is_ready():
            self.bot.limited_events = self._empty_snapshot("Bot not ready")
            return False, "Bot not ready"

        if bool(getattr(self.bot, "hunting_captcha_active", False)):
            now = datetime.now(timezone.utc)
            self.bot.limited_events = {
                **self._empty_snapshot("Skipped: captcha active"),
                "last_checked_utc": now.isoformat(),
                "next_check_utc": datetime.fromtimestamp(time.time() + self.poll_interval_seconds, timezone.utc).isoformat(),
                "source": source,
            }
            return False, "Skipped: captcha active"

        channel = await self._resolve_hunting_channel()
        if channel is None:
            self.bot.limited_events = self._empty_snapshot("Hunting channel unavailable")
            return False, "Hunting channel unavailable"

        requests = [
            ("bonus", ";bonus", ["global bonuses", "vote bonuses", "player-activated global bonuses"]),
            ("events", ";events", ["event ends", "events buy", "event ticket"]),
            ("unlocks", ";unlocks", ["unlockable pokemon", "checked means unlocked", "catchable"]),
        ]

        was_hunt_paused = bool(getattr(self.bot, "pause_hunting", False))
        was_fish_paused = bool(getattr(self.bot, "pause_fishing", False))
        self.bot.pause_hunting = True
        self.bot.pause_fishing = True

        summaries: dict[str, Any] = {}
        ok_count = 0
        try:
            await asyncio.sleep(1.0)
            for key, command_text, keywords in requests:
                ok, text, jump_url, error = await self._request_command_response(channel, command_text, keywords)
                if ok:
                    ok_count += 1
                summaries[key] = self._build_summary(command_text, text, ok, error=error, jump_url=jump_url)
                await asyncio.sleep(1.2)
        finally:
            self.bot.pause_hunting = was_hunt_paused
            self.bot.pause_fishing = was_fish_paused

        now = datetime.now(timezone.utc)
        next_check = datetime.fromtimestamp(time.time() + self.poll_interval_seconds, timezone.utc)
        self.last_check_at = time.time()

        self.bot.limited_events = {
            "status": "ok" if ok_count == len(requests) else ("partial" if ok_count > 0 else "failed"),
            "interval_seconds": int(self.poll_interval_seconds),
            "last_checked_utc": now.isoformat(),
            "next_check_utc": next_check.isoformat(),
            "source": source,
            "bonus": summaries.get("bonus", self._build_summary(";bonus", "", False, "No data")),
            "events": summaries.get("events", self._build_summary(";events", "", False, "No data")),
            "unlocks": summaries.get("unlocks", self._build_summary(";unlocks", "", False, "No data")),
        }

        if ok_count == len(requests):
            return True, "Limited events updated"
        if ok_count > 0:
            return True, f"Limited events partially updated ({ok_count}/{len(requests)})"
        return False, "Failed to fetch limited events"

    async def trigger_manual_refresh(self, source: str = "manual") -> tuple[bool, str]:
        return await self.refresh_limited_events(source=source)

    @tasks.loop(seconds=30)
    async def poll_loop(self) -> None:
        if not self.bot.is_ready():
            return

        now = time.time()
        if self.last_check_at > 0 and now - self.last_check_at < self.poll_interval_seconds:
            return

        await self.refresh_limited_events(source="scheduled")

    @poll_loop.before_loop
    async def _before_poll_loop(self) -> None:
        await self.bot.wait_until_ready()
        await asyncio.sleep(10)
        await self.refresh_limited_events(source="startup")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LimitedEvents(bot))
