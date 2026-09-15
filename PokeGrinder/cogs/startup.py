import asyncio
from time import time
from typing import Tuple, Dict, Any
from dataclasses import dataclass
from typing import TypeAlias

from discord.ext import commands, tasks
from discord import SlashCommand, UserCommand, MessageCommand, TextChannel, InvalidData

from modules.runtime_file_log import info as runtime_info_log

try:
    from discord import SubCommand
    CommandType: TypeAlias = SlashCommand | UserCommand | MessageCommand | SubCommand
except ImportError:
    CommandType: TypeAlias = SlashCommand | UserCommand | MessageCommand


@dataclass
class Config:
    hunting_channel_id: int
    fishing_channel_id: int
    world_boss_channel_id: int
    berry_channel_id: int
    exception_balls: Dict[str, str]
    balls: Dict[str, str]
    fish_balls: Dict[str, str]
    auto_buy: Dict[str, int]
    auto_release_duplicates: int
    retry_cooldown: float
    hunting_cooldown: float
    fishing_cooldown: float
    captcha_auto_answer_enabled: bool
    captcha_auto_max_attempts: int
    captcha_manual_allowed_user_ids: list[int]
    suspicion_avoidance: int
    captcha_alerts_enabled: bool
    captcha_alert_channel_id: int
    captcha_alert_webhook_url: str
    captcha_alert_ping: str
    captcha_alert_cooldown_seconds: int
    egg_hatching: bool
    auto_hold_egg: bool
    world_boss_enabled: bool
    wb_danger_hp_percent: int
    wb_max_idle_seconds: int
    wb_dry_run: bool
    berry_enabled: bool
    hunting_delay_min: float
    hunting_delay_max: float
    fishing_delay_min: float
    fishing_delay_max: float
    post_catch_delay_min: float
    post_catch_delay_max: float
    enable_anti_detection: bool
    min_action_delay_seconds: float
    human_breaks_enabled: bool
    short_break_every_min_seconds: int
    short_break_every_max_seconds: int
    short_break_duration_min_seconds: int
    short_break_duration_max_seconds: int
    long_break_every_min_seconds: int
    long_break_every_max_seconds: int
    long_break_duration_min_seconds: int
    long_break_duration_max_seconds: int
    max_speed_mode_enabled: bool
    super_low_risk_mode_enabled: bool
    catchbot_enabled: bool
    catchbot_channel_id: int
    catchbot_check_interval_seconds: int
    autofight_enabled: bool
    autofight_channel_id: int
    autofight_on_command: str
    autofight_off_command: str


async def get_commands(bot: commands.Bot, channel_id: int) -> (
    Tuple[
        TextChannel,
        Dict[str, Any],
    ]
    | Tuple[None, None]
):
    if channel_id == 0:
        return None, None

    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
            print(f"[Startup] INFO: Fetched channel {channel_id} (was not in cache)")
        except Exception:
            print(f"[Startup] WARNING: Channel {channel_id} not found (bot not in channel or invalid ID)")
            return None, None

    try:
        app_commands = await channel.application_commands()
    except Exception as exc:
        print(f"[Startup] WARNING: Could not fetch application commands for channel {channel_id}: {exc}")
        return channel, {}

    commands: Dict[str, Any] = {
        command.name: command
        for command in app_commands
        if command.application_id == 664508672713424926
    }

    for command in list(commands.values()):
        for sub_command in command.children:
            commands[f"{command.name} {sub_command.name}"] = sub_command

    # Fallback: if no Pokémon Meow commands found, try all commands
    if not commands:
        print(f"[Startup] INFO: No Pokémon Meow commands found on {channel_id}, trying all available commands...")
        commands: Dict[str, Any] = {
            command.name: command
            for command in app_commands
        }
        for command in list(commands.values()):
            for sub_command in command.children:
                commands[f"{command.name} {sub_command.name}"] = sub_command

    return channel, commands


class Startup(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.config: Config = bot.config

    async def _send_text_fallback(self, channel: TextChannel | None, text_command: str) -> bool:
        if channel is None:
            return False

        try:
            await channel.send(text_command)
            print(f"[Startup] Fallback sent: {text_command}")
            return True
        except Exception as exc:
            print(f"Startup warning: failed fallback '{text_command}' ({exc}).")
            return False

    async def safe_invoke(
        self,
        command_map: Dict[str, Any] | None,
        command_name: str,
        fallback_channel: TextChannel | None = None,
        fallback_text: str | None = None,
    ) -> bool:
        command_map = command_map or {}
        command = command_map.get(command_name)
        if command is None:
            print(f"Startup warning: command '{command_name}' not found.")
            if fallback_text:
                return await self._send_text_fallback(fallback_channel, fallback_text)
            return False

        try:
            await command()
            return True
        except InvalidData:
            print(f"Startup warning: Discord timed out for '{command_name}', will retry via loop.")
            if fallback_text:
                return await self._send_text_fallback(fallback_channel, fallback_text)
        except Exception as exc:
            print(f"Startup warning: failed to run '{command_name}' ({exc}).")
            if fallback_text:
                return await self._send_text_fallback(fallback_channel, fallback_text)

        return False

    async def ensure_hunting_commands(self) -> bool:
        command_map = getattr(self.bot, "hunting_channel_commands", None)
        if command_map:
            return True

        self.bot.hunting_channel, self.bot.hunting_channel_commands = (
            await get_commands(self.bot, self.config.hunting_channel_id)
        )
        return bool(self.bot.hunting_channel_commands)

    async def ensure_fishing_commands(self) -> bool:
        command_map = getattr(self.bot, "fishing_channel_commands", None)
        if command_map:
            return True

        self.bot.fishing_channel, self.bot.fishing_channel_commands = (
            await get_commands(self.bot, self.config.fishing_channel_id)
        )
        return bool(self.bot.fishing_channel_commands)

    async def ensure_autofight_commands(self) -> bool:
        command_map = getattr(self.bot, "autofight_channel_commands", None)
        if command_map:
            return True

        self.bot.autofight_channel, self.bot.autofight_channel_commands = (
            await get_commands(self.bot, self.config.autofight_channel_id)
        )
        return bool(self.bot.autofight_channel_commands)

    async def _enforce_required_server(self) -> bool:
        required_server_id = int(getattr(self.bot, "required_server_id", 0) or 0)
        if required_server_id == 0:
            return True

        channels_to_validate = [
            ("hunting", self.config.hunting_channel_id, getattr(self.bot, "hunting_channel", None)),
            ("fishing", self.config.fishing_channel_id, getattr(self.bot, "fishing_channel", None)),
            ("berry", self.config.berry_channel_id, getattr(self.bot, "berry_channel", None)),
        ]

        for label, configured_channel_id, channel in channels_to_validate:
            if configured_channel_id == 0:
                continue

            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(configured_channel_id)
                    if label == "hunting":
                        self.bot.hunting_channel = channel
                    elif label == "fishing":
                        self.bot.fishing_channel = channel
                    elif label == "berry":
                        self.bot.berry_channel = channel
                    print(f"[Startup] INFO: Fetched {label} channel {configured_channel_id} for RequiredServerID validation")
                except Exception:
                    pass

            if channel is None:
                print(
                    f"[Startup] RequiredServerID check failed for {label}: "
                    f"channel {configured_channel_id} not found (required server {required_server_id}). "
                    "This bot will stay connected, but automation for this account will not start."
                )
                return False

            channel_server_id = int(
                getattr(getattr(channel, "guild", None), "id", 0)
                or getattr(channel, "guild_id", 0)
                or 0
            )
            if channel_server_id != required_server_id:
                print(
                    f"[Startup] RequiredServerID mismatch for {label}: "
                    f"channel {configured_channel_id} is in server {channel_server_id}, "
                    f"required server is {required_server_id}. "
                    "This bot will stay connected, but automation for this account will not start."
                )
                return False

        return True

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        print(f"Started grinding as {self.bot.user.name}!")
        runtime_info_log(
            "Discord on_ready: logged in as %s (id=%s) account_id=%s",
            str(self.bot.user),
            getattr(self.bot.user, "id", None),
            getattr(self.bot, "stats_key", ""),
        )
        self.bot.server_scope_valid = True

        if self.config.hunting_channel_id != 0:
            self.bot.hunting_status = "Loading slash commands…"
        if self.config.fishing_channel_id != 0:
            self.bot.fishing_status = "Loading slash commands…"
        # WorldBoss system is removed from runtime.
        self.config.world_boss_enabled = False

        (
            hunt_res,
            fish_res,
            berry_res,
            autofight_res,
        ) = await asyncio.gather(
            get_commands(self.bot, self.config.hunting_channel_id),
            get_commands(self.bot, self.config.fishing_channel_id),
            get_commands(self.bot, self.config.berry_channel_id),
            get_commands(self.bot, self.config.autofight_channel_id),
        )

        self.bot.hunting_channel, self.bot.hunting_channel_commands = hunt_res
        print(
            f"[Startup] Hunting channel {self.config.hunting_channel_id}: "
            f"{len(self.bot.hunting_channel_commands or {}) if self.bot.hunting_channel_commands else 0} commands found"
        )

        self.bot.fishing_channel, self.bot.fishing_channel_commands = fish_res
        print(
            f"[Startup] Fishing channel {self.config.fishing_channel_id}: "
            f"{len(self.bot.fishing_channel_commands or {}) if self.bot.fishing_channel_commands else 0} commands found"
        )

        self.bot.berry_channel, self.bot.berry_channel_commands = berry_res
        print(
            f"[Startup] Berry channel {self.config.berry_channel_id}: "
            f"{len(self.bot.berry_channel_commands or {}) if self.bot.berry_channel_commands else 0} commands found"
        )

        self.bot.autofight_channel, self.bot.autofight_channel_commands = autofight_res
        print(
            f"[Startup] AutoFight channel {self.config.autofight_channel_id}: "
            f"{len(self.bot.autofight_channel_commands or {}) if self.bot.autofight_channel_commands else 0} commands found"
        )

        self.bot.server_scope_valid = await self._enforce_required_server()
        if not self.bot.server_scope_valid:
            if self.config.hunting_channel_id != 0:
                self.bot.hunting_status = "Blocked: RequiredServerID mismatch"
            if self.config.fishing_channel_id != 0:
                self.bot.fishing_status = "Blocked: RequiredServerID mismatch"
            await self.bot.log()
            return

        if self.bot.hunting_channel_commands:
            self.hunting_check.start()
            print(f"[Startup] Hunting check loop started")
            await self.safe_invoke(
                self.bot.hunting_channel_commands,
                "pokemon",
                fallback_channel=getattr(self.bot, "hunting_channel", None),
                fallback_text=";p",
            )
            if self.bot.hunting_status == "Starting...":
                self.bot.hunting_status = "Running checks..."
        else:
            print(f"[Startup] WARNING: No hunting commands found on channel {self.config.hunting_channel_id}")
            sent = await self._send_text_fallback(getattr(self.bot, "hunting_channel", None), ";p")
            self.hunting_check.start()
            self.bot.hunting_status = "Running checks..." if sent else "No commands detected"

        if self.bot.fishing_channel_commands:
            self.fishing_check.start()
            print(f"[Startup] Fishing check loop started")
            await self.safe_invoke(
                self.bot.fishing_channel_commands,
                "fish spawn",
                fallback_channel=getattr(self.bot, "fishing_channel", None),
                fallback_text=";fish spawn",
            )
            if self.bot.fishing_status == "Starting...":
                self.bot.fishing_status = "Running checks..."
        else:
            print(f"[Startup] WARNING: No fishing commands found on channel {self.config.fishing_channel_id}")
            sent = await self._send_text_fallback(getattr(self.bot, "fishing_channel", None), ";fish spawn")
            self.fishing_check.start()
            self.bot.fishing_status = "Running checks..." if sent else "No commands detected"

        if self.config.berry_enabled and getattr(self.bot, "berry_channel", None):
            berry_cog = self.bot.get_cog("BerryGarden")
            if berry_cog is not None and hasattr(berry_cog, "trigger_berry_check"):
                try:
                    await berry_cog.trigger_berry_check(source="startup")
                except Exception as exc:
                    print(f"Startup warning: initial berry check failed ({exc}).")

        await self.bot.log()

    @tasks.loop(seconds=20)
    async def hunting_check(self) -> None:
        try:
            if self.bot.limit:
                return

            if bool(getattr(self.bot, "hunting_captcha_active", False)) or self.bot.pause_hunting:
                return

            if time() - self.bot.last_hunt < 20:
                return

            if not await self.ensure_hunting_commands():
                await self._send_text_fallback(getattr(self.bot, "hunting_channel", None), ";p")
                return

            await self.safe_invoke(
                self.bot.hunting_channel_commands,
                "pokemon",
                fallback_channel=getattr(self.bot, "hunting_channel", None),
                fallback_text=";p",
            )
        except Exception as exc:
            print(f"Startup warning: hunting_check failed ({exc}).")

    @tasks.loop(seconds=40)
    async def fishing_check(self) -> None:
        try:
            if bool(getattr(self.bot, "fishing_captcha_active", False)) or self.bot.pause_fishing:
                return

            if time() - self.bot.last_fish < 40:
                return

            if not await self.ensure_fishing_commands():
                await self._send_text_fallback(getattr(self.bot, "fishing_channel", None), ";fish spawn")
                return

            await self.safe_invoke(
                self.bot.fishing_channel_commands,
                "fish spawn",
                fallback_channel=getattr(self.bot, "fishing_channel", None),
                fallback_text=";fish spawn",
            )
        except Exception as exc:
            print(f"Startup warning: fishing_check failed ({exc}).")

