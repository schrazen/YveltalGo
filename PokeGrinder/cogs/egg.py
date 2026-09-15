import asyncio
import re
from time import time
from random import randint

from discord import Message, InvalidData
from discord.ext import commands

from cogs.startup import Config
from modules.cloudflare_indicator import (
    is_cloudflare_1015_error,
    notify_cloudflare_in_channel,
)

POKEMEOW_APP_ID = 664508672713424926


class Egg(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.config: Config = bot.config
        self.last_egg_action_at = 0.0
        self.egg_action_inflight = False

    async def _notify_cloudflare(self, channel_id: int, error_text: str) -> None:
        if not is_cloudflare_1015_error(error_text):
            return
        await notify_cloudflare_in_channel(
            self.bot,
            channel_id=int(channel_id or 0),
            module_name="Egg",
            error_text=error_text,
            cooldown_seconds=90.0,
            wait_seconds=self._parse_egg_cooldown_seconds(error_text),
        )

    def _parse_egg_cooldown_seconds(self, text: str) -> float:
        match = re.search(r"please wait\s+(\d+)\s+seconds?\s+before\s+viewing\s+your\s+eggs\s+again", text)
        if not match:
            return 0.0
        try:
            return float(match.group(1))
        except Exception:
            return 0.0

    def in_grinding_channel(self, channel_id: int) -> bool:
        return (
            channel_id == self.config.hunting_channel_id
            or channel_id == self.config.fishing_channel_id
        )

    def get_channel_commands(self, channel_id: int):
        if channel_id == self.config.hunting_channel_id:
            return getattr(self.bot, "hunting_channel_commands", None)

        if channel_id == self.config.fishing_channel_id:
            return getattr(self.bot, "fishing_channel_commands", None)

        return None

    async def safe_run_command(self, channel_id: int, command_map, command_name: str) -> bool:
        command = command_map.get(command_name) if command_map else None
        if command is None:
            print(f"Egg warning: command '{command_name}' not found.")
            return False

        try:
            await command()
            return True
        except InvalidData:
            print(f"Egg warning: Discord timed out for '{command_name}'.")
            return False
        except Exception as exc:
            error_text = str(exc)
            print(f"Egg warning: failed to run '{command_name}' ({error_text}).")
            await self._notify_cloudflare(channel_id=channel_id, error_text=error_text)
            return False

    async def _send_text_fallback(self, channel_id: int, text_command: str) -> bool:
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except Exception:
                return False

        try:
            await channel.send(text_command)
            return True
        except Exception as exc:
            error_text = str(exc)
            print(f"Egg warning: failed fallback '{text_command}' ({error_text}).")
            await self._notify_cloudflare(channel_id=channel_id, error_text=error_text)
            return False

    async def run_command_with_retry(
        self,
        channel_id: int,
        command_name: str,
        *,
        attempts: int = 3,
        base_delay: float = 1.0,
    ) -> bool:
        attempts = max(1, int(attempts))
        fallback_text = f";{command_name}"

        for idx in range(attempts):
            command_map = self.get_channel_commands(channel_id)
            if not command_map:
                startup_cog = self.bot.get_cog("Startup")
                if startup_cog is not None:
                    try:
                        if channel_id == self.config.hunting_channel_id:
                            await startup_cog.ensure_hunting_commands()
                        elif channel_id == self.config.fishing_channel_id:
                            await startup_cog.ensure_fishing_commands()
                    except Exception as exc:
                        print(f"Egg warning: failed command refresh for '{command_name}' ({exc}).")
                command_map = self.get_channel_commands(channel_id)

            ok = await self.safe_run_command(channel_id, command_map, command_name)
            if not ok:
                ok = await self._send_text_fallback(channel_id, fallback_text)
            if ok:
                return True

            if idx + 1 < attempts:
                await asyncio.sleep(base_delay + randint(0, self.config.suspicion_avoidance) / 1000)

        return False

    def _message_text(self, message: Message) -> str:
        text_parts = [message.content or ""]
        for embed in message.embeds or []:
            text_parts.extend([
                embed.title or "",
                embed.description or "",
                embed.footer.text if embed.footer else "",
            ])
        return " ".join(text_parts).lower()

    async def _wait_for_pokemeow_reply(self, channel_id: int, timeout: float = 5.0) -> str:
        def check(msg: Message) -> bool:
            return msg.author.id == POKEMEOW_APP_ID and msg.channel.id == channel_id

        try:
            response = await self.bot.wait_for("message", timeout=timeout, check=check)
            return self._message_text(response)
        except asyncio.TimeoutError:
            return ""
        except Exception as exc:
            print(f"Egg warning: failed waiting for Pokemeow reply ({exc}).")
            return ""

    async def run_hold_with_retry(self, channel_id: int, attempts: int = 3) -> bool:
        attempts = max(1, int(attempts))
        for idx in range(attempts):
            ok = await self.run_command_with_retry(
                channel_id,
                "egg hold",
                attempts=1,
                base_delay=0.0,
            )
            if not ok:
                if idx + 1 < attempts:
                    await asyncio.sleep(1.0 + randint(0, self.config.suspicion_avoidance) / 1000)
                    continue
                return False

            reply_text = await self._wait_for_pokemeow_reply(channel_id, timeout=5.0)
            cooldown_seconds = self._parse_egg_cooldown_seconds(reply_text)
            if cooldown_seconds > 0:
                await self._notify_cloudflare(channel_id=channel_id, error_text=reply_text)
                if idx + 1 < attempts:
                    await asyncio.sleep(cooldown_seconds + 0.6)
                    continue
                return False

            if "you aren't holding any eggs" in reply_text:
                if idx + 1 < attempts:
                    await asyncio.sleep(1.2 + randint(0, self.config.suspicion_avoidance) / 1000)
                    continue
                return False

            return True

        return False

    @commands.Cog.listener()
    async def on_message(self, message: Message) -> None:
        if not self.config.egg_hatching:
            return

        if self.bot.captcha_active:
            return

        if not self.in_grinding_channel(message.channel.id):
            return

        if message.author.id != POKEMEOW_APP_ID:
            return

        text = self._message_text(message)
        if "egg" not in text or "ready to hatch" not in text:
            return

        # Prevent duplicate hatch/hold calls if Discord emits repeated events.
        now = time()
        if self.egg_action_inflight:
            return
        if now - self.last_egg_action_at < 2:
            return

        self.egg_action_inflight = True
        prev_pause_hunting = bool(getattr(self.bot, "pause_hunting", False))
        prev_pause_fishing = bool(getattr(self.bot, "pause_fishing", False))

        if message.channel.id == self.config.hunting_channel_id:
            self.bot.pause_hunting = True
        elif message.channel.id == self.config.fishing_channel_id:
            self.bot.pause_fishing = True

        try:
            if message.channel.id == self.config.hunting_channel_id:
                self.bot.hunting_status = "Hatching Egg..."
            else:
                self.bot.fishing_status = "Hatching Egg..."
            await self.bot.log()

            await asyncio.sleep(1 + randint(0, self.config.suspicion_avoidance) / 1000)
            hatched = await self.run_command_with_retry(
                message.channel.id,
                "egg hatch",
                attempts=3,
                base_delay=1.5,
            )

            if not hatched:
                return

            if self.config.auto_hold_egg:
                if message.channel.id == self.config.hunting_channel_id:
                    self.bot.hunting_status = "Holding Egg..."
                else:
                    self.bot.fishing_status = "Holding Egg..."
                await self.bot.log()

                # Pokemeow can reject immediate egg view/hold checks with a short cooldown.
                await asyncio.sleep(2.2 + randint(0, self.config.suspicion_avoidance) / 1000)
                await self.run_hold_with_retry(message.channel.id, attempts=3)

            self.last_egg_action_at = time()

            if message.channel.id == self.config.hunting_channel_id:
                self.bot.hunting_status = "Grinding..."
            else:
                self.bot.fishing_status = "Grinding..."
            await self.bot.log()
        finally:
            self.bot.pause_hunting = prev_pause_hunting
            self.bot.pause_fishing = prev_pause_fishing
            self.egg_action_inflight = False
