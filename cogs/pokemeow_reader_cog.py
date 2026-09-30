from __future__ import annotations

import logging
from typing import Any

from discord import Message
from discord.ext import commands

from cogs.startup import Config
from modules.pokemeow_reader import POKEMEOW_APP_ID, inspect_and_record_pokemeow_message
from modules.server_guard import is_message_in_required_server

logger = logging.getLogger("pokegrinder.pokemeow_reader")


class PokeMeowReaderCog(commands.Cog):
    """Actively monitors all PokéMeow messages in configured channels to capture

    complications (flees, ball starvation, coin starvation, rate-limits) and special game events.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.config: Config = bot.config

    def _resolve_context_module(self, channel_id: int) -> str:
        if channel_id == getattr(self.config, "hunting_channel_id", 0):
            return "hunting"
        if channel_id == getattr(self.config, "fishing_channel_id", 0):
            return "fishing"
        if channel_id == getattr(self.config, "autofight_channel_id", 0):
            return "autofight"
        if channel_id == getattr(self.config, "berry_channel_id", 0):
            return "berry"
        if channel_id == getattr(self.config, "catchbot_channel_id", 0):
            return "catchbot"
        return "general"

    def _is_relevant_pokemeow_message(self, message: Message) -> bool:
        if not is_message_in_required_server(self.bot, message):
            return False

        if getattr(getattr(message, "author", None), "id", 0) != POKEMEOW_APP_ID:
            return False

        channel_id = int(getattr(getattr(message, "channel", None), "id", 0) or 0)
        configured_channels = {
            int(getattr(self.config, "hunting_channel_id", 0) or 0),
            int(getattr(self.config, "fishing_channel_id", 0) or 0),
            int(getattr(self.config, "autofight_channel_id", 0) or 0),
            int(getattr(self.config, "berry_channel_id", 0) or 0),
            int(getattr(self.config, "catchbot_channel_id", 0) or 0),
        }
        configured_channels.discard(0)

        # Check channel relevance
        if channel_id in configured_channels:
            return True

        # Check interaction target relevance
        interaction = getattr(message, "interaction", None)
        if interaction is not None:
            user = getattr(interaction, "user", None)
            if user is not None and user == self.bot.user:
                return True

        # Check mention relevance
        mentions = getattr(message, "mentions", []) or []
        bot_user = getattr(self.bot, "user", None)
        if bot_user and any(getattr(m, "id", 0) == bot_user.id for m in mentions):
            return True

        return False

    @commands.Cog.listener()
    async def on_message(self, message: Message) -> None:
        try:
            if not self._is_relevant_pokemeow_message(message):
                return

            channel_id = int(getattr(getattr(message, "channel", None), "id", 0) or 0)
            context_module = self._resolve_context_module(channel_id)
            inspect_and_record_pokemeow_message(
                self.bot,
                message,
                context_module=context_module,
            )
        except Exception as exc:
            logger.debug(f"[PokeMeowReaderCog] on_message error: {exc}")

    @commands.Cog.listener()
    async def on_message_edit(self, before: Message, after: Message) -> None:
        try:
            if not self._is_relevant_pokemeow_message(after):
                return

            channel_id = int(getattr(getattr(after, "channel", None), "id", 0) or 0)
            context_module = self._resolve_context_module(channel_id)
            inspect_and_record_pokemeow_message(
                self.bot,
                after,
                before_message=before,
                context_module=context_module,
            )
        except Exception as exc:
            logger.debug(f"[PokeMeowReaderCog] on_message_edit error: {exc}")
