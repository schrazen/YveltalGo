import asyncio
import re
from time import time
from typing import Dict, TypeAlias
from random import randint, choice

from discord import (
    Message,
    SlashCommand,
    UserCommand,
    MessageCommand,
    InvalidData,
)
try:
    from discord import SubCommand
    CommandType: TypeAlias = SlashCommand | UserCommand | MessageCommand | SubCommand
except ImportError:
    # Newer py-cord builds may not export SubCommand at top-level.
    CommandType: TypeAlias = SlashCommand | UserCommand | MessageCommand

from discord.ext import commands
from cogs.startup import Config
from modules.stats_store import persist_bot_stats, ensure_day_mode_window
from modules.anti_detect_log import record_anti_detect_event
from modules.cloudflare_indicator import is_cloudflare_1015_error, notify_cloudflare_in_channel
from modules.rare_catch_log import record_rare_catch_event
from modules.retrieved_item_log import record_retrieved_item_event

POKEMEOW_APP_ID = 664508672713424926

auto_buy_sub_strings = {
    "Pokeballs: 0": "pb",
    "Pokeballs : 0": "pb",
    "Greatballs: 0": "gb",
    "Ultraballs: 0": "ub",
    "Masterballs: 0": "mb",
}


def resolve_hunting_rarity(config: Config, message: Message) -> str:
    footer_text = message.embeds[0].footer.text if message.embeds and message.embeds[0].footer else ""
    rarity_candidates = sorted(config.balls.keys(), key=len, reverse=True)

    for rarity in rarity_candidates:
        if rarity in footer_text:
            return rarity

    return "Unknown"


def extract_pokemon_name(message: Message) -> str:
    haystack = _collect_message_text(message)

    # Prefer explicit encounter/catch patterns first.
    explicit_patterns = [
        r"wild\s+(?:[:a-z0-9_]+\s+)?\*\*([^*]+)\*\*\s+appeared",
        r"wild\s+([A-Za-z0-9\-\. '\u2019]+?)\s+appeared",
        r"caught\s+(?:an?\s*)?(?:(?:<a?:[a-z0-9_]+:\d+>|:[a-z0-9_]+:)\s*)*\*\*([^*]+)\*\*\s+with",
        r"caught\s+(?:an?\s*)?(?:(?:<a?:[a-z0-9_]+:\d+>|:[a-z0-9_]+:)\s*)*([A-Za-z0-9\-\. '\u2019]+?)\s+with",
    ]
    for pattern in explicit_patterns:
        matched = re.search(pattern, haystack, flags=re.IGNORECASE)
        if not matched:
            continue
        candidate = str(matched.group(1)).strip(" .!,:;*-_\n\t")
        if candidate and "_" not in candidate and candidate.lower() != "you":
            return candidate

    # Fallback: inspect bold tokens and skip username-like values.
    matches = re.findall(r"\*\*([^*]+)\*\*", haystack)
    if matches:
        for candidate in matches:
            name = str(candidate).strip(" .!,:;*-_\n\t")
            lowered = name.lower()
            if not name:
                continue
            if "you" in lowered or "well done" in lowered:
                continue
            # Usernames are commonly underscore-heavy; pokemon names are not.
            if "_" in name:
                continue
            return name

    return "Unknown"


def extract_caught_pokemon_name(message: Message) -> str:
    haystack = _collect_message_text(message)
    # Prefer explicit line-level matching to avoid EXP/level/evolution text pollution.
    for line in str(haystack or "").splitlines():
        if "you caught" not in line.lower():
            continue
        matched = re.search(
            r"you\s+caught\s+(?:an?\s*)?(?:(?:<a?:[a-z0-9_]+:\d+>|:[a-z0-9_]+:)\s*)*(?:\*\*)?([A-Za-z][A-Za-z0-9\-\. '\u2019]{1,80}?)(?:\*\*)?\s+with\b",
            line,
            flags=re.IGNORECASE,
        )
        if not matched:
            continue
        candidate = _sanitize_entity_name(str(matched.group(1)))
        candidate = re.sub(r"^shiny\s+", "", candidate, flags=re.IGNORECASE)
        if candidate and candidate.lower() != "you":
            return candidate

    patterns = [
        # Handles variants like "You caught a :639: Terrakion with ..." and "You caught a:held_item::81: Magnemite with ..."
        r"you\s+caught\s+(?:an?\s*)?(?:(?:<a?:[a-z0-9_]+:\d+>|:[a-z0-9_]+:)\s*)*([A-Za-z][A-Za-z0-9\-\. '\u2019]{1,60}?)\s+with\b",
        r"caught\s+(?:an?\s*)?(?:(?:<a?:[a-z0-9_]+:\d+>|:[a-z0-9_]+:)\s*)*([A-Za-z][A-Za-z0-9\-\. '\u2019]{1,60}?)\s+with\b",
    ]
    for pattern in patterns:
        matched = re.search(pattern, haystack, flags=re.IGNORECASE)
        if not matched:
            continue
        candidate = _sanitize_entity_name(str(matched.group(1)))
        candidate = re.sub(r"^shiny\s+", "", candidate, flags=re.IGNORECASE)
        if candidate and candidate.lower() != "you":
            return candidate
    return "Unknown"


def _collect_message_text(message: Message) -> str:
    parts = [str(message.content or "")]
    for embed in message.embeds or []:
        parts.extend([
            str(embed.title or ""),
            str(embed.description or ""),
            str(getattr(getattr(embed, "author", None), "name", "") or ""),
            str(embed.footer.text if embed.footer else ""),
        ])
        for field in getattr(embed, "fields", []) or []:
            parts.append(str(field.name or ""))
            parts.append(str(field.value or ""))
    return "\n".join(parts)


def normalize_pokemon_slug(name: str) -> str:
    value = str(name or "").strip().lower()
    value = re.sub(r"[^a-z0-9\s\-]", "", value)
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value


def normalize_item_slug(name: str) -> str:
    value = str(name or "").strip().lower()
    value = re.sub(r"[^a-z0-9\s\-]", "", value)
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value


def _sanitize_entity_name(raw_value: str) -> str:
    value = str(raw_value or "")
    # Remove custom emoji (<:name:id>) and standard emoji aliases (:name:).
    value = re.sub(r"<a?:[a-z0-9_]+:\d+>", " ", value, flags=re.IGNORECASE)
    value = re.sub(r":[a-z0-9_]+:", " ", value, flags=re.IGNORECASE)
    # Strip common markdown wrappers used in Pokemeow responses.
    value = re.sub(r"[*_`~]+", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" .!,:;*-_\n\t")


def extract_retrieved_item_name(message: Message) -> str:
    haystack = _collect_message_text(message)
    patterns = [
        r"you\s+retrieved\s+(?:an?\s+)?(?::[^:\s]+:\s*)?([^!\n\r]+?)\s+from\b",
        r"you\s+retrieved\s+(?:an?\s+)?(?::[^:\s]+:\s*)?([^!\n\r]+?)(?:[.!]|$)",
    ]
    for pattern in patterns:
        matched = re.search(pattern, haystack, flags=re.IGNORECASE)
        if not matched:
            continue
        candidate = _sanitize_entity_name(str(matched.group(1)))
        if candidate:
            return candidate
    return ""


def extract_retrieved_item_pokemon_name(message: Message) -> str:
    haystack = _collect_message_text(message)
    patterns = [
        r"you\s+retrieved\s+[^!\n\r]+?\s+from\s+(?:the\s+)?([^!\n\r]+?)(?:[.!]|$)",
        r"from\s+(?:the\s+)?([^!\n\r]+?)\s*(?:[.!]|$)",
    ]
    for pattern in patterns:
        matched = re.search(pattern, haystack, flags=re.IGNORECASE)
        if not matched:
            continue
        candidate = _sanitize_entity_name(str(matched.group(1)))
        if candidate and candidate.lower() not in {"the", "you"}:
            return candidate
    return ""


def is_high_rarity_label(value: str) -> bool:
    lowered = str(value or "").lower()
    return any(token in lowered for token in ("legendary", "shiny", "mythical", "ultra", "event", "golden"))


def _is_max_speed_enabled(config: Config) -> bool:
    return bool(getattr(config, "max_speed_mode_enabled", False))


async def auto_buy(
    bot: commands.Bot,
    config: Config,
    command_map: Dict[str, object],
    message: Message,
) -> None:
    to_buy = [
        auto_buy_sub_strings[string]
        for string in list(auto_buy_sub_strings.keys())
        if string in message.embeds[0].footer.text
    ]

    if to_buy and config.auto_buy[to_buy[0]] != 0 and not bot.auto_buy_queued:
        bot.auto_buy_queued = True
        if not _is_max_speed_enabled(config):
            await asyncio.sleep(2 + randint(0, config.suspicion_avoidance) / 1000)
        task = asyncio.create_task(
            command_map["shop buy"](item=to_buy[0], amount=config.auto_buy[to_buy[0]])
        )
        bot.auto_buy_queued = False
        await task


class Hunting(commands.Cog):
    def __init__(self, bot: commands.Bot, break_coordinator=None) -> None:
        self.bot = bot
        self.config: Config = bot.config
        self.break_coordinator = break_coordinator
        self._processed_catch_message_ids: dict[int, float] = {}

    def _max_speed(self) -> bool:
        return bool(getattr(self.config, "max_speed_mode_enabled", False))

    def _should_process_catch_message(self, message_id: int) -> bool:
        now = time()
        # Keep cache bounded: remove entries older than 30 minutes.
        stale_keys = [mid for mid, ts in self._processed_catch_message_ids.items() if (now - ts) > 1800]
        for mid in stale_keys:
            self._processed_catch_message_ids.pop(mid, None)

        mid = int(message_id or 0)
        if mid <= 0:
            return True
        if mid in self._processed_catch_message_ids:
            return False

        self._processed_catch_message_ids[mid] = now
        return True

    async def _maybe_take_human_break(self) -> None:
        if self._max_speed():
            return
        if not self.config.human_breaks_enabled:
            return
        if not self.break_coordinator:
            return

        # Use shared coordinator so hunting and fishing break together
        break_seconds = self.break_coordinator.get_break_duration()
        if break_seconds > 0:
            print(f"[Hunting] Human break for {break_seconds}s")
            channel = self.bot.get_channel(self.config.hunting_channel_id)
            if channel is not None:
                try:
                    await channel.send(choice(["brb", "brb getting water", "afk a bit", "brb phone call"]))
                except Exception:
                    pass
            record_anti_detect_event(
                str(self.bot.user) if self.bot.user else "unknown",
                "human_break",
                module="hunting",
                channel_id=self.config.hunting_channel_id,
                details={"seconds": break_seconds},
            )
            self.break_coordinator.start_break()
            await asyncio.sleep(break_seconds)
            self.break_coordinator.end_break()

    async def _maybe_add_idle_randomness(self) -> None:
        """
        Occasionally add unscheduled idle time (5-20s) to break the perfect rhythm.
        This makes behavior look less bot-like by introducing random "doing nothing" pauses.
        """
        if self._max_speed():
            return
        if not self.config.human_breaks_enabled:
            return

        # ~8% chance of random idle (roughly once per 12-15 actions)
        if randint(0, 100) > 92:
            idle_seconds = randint(5, 20)
            print(f"[Hunting] Idle randomness: {idle_seconds}s")
            record_anti_detect_event(
                str(self.bot.user) if self.bot.user else "unknown",
                "idle_randomness",
                module="hunting",
                channel_id=self.config.hunting_channel_id,
                details={"seconds": idle_seconds, "reason": "human_like_pause"},
            )
            await asyncio.sleep(idle_seconds)

    def _get_behavioral_delay(self, min_sec: float, max_sec: float) -> float:
        """
        Return a delay that's more human-like: sometimes upper range, sometimes lower,
        but NOT consistently in the middle. Occasionally biased to look like hesitation.
        """
        # 70% natural random, 20% weighted to upper (hesitation), 10% weighted to lower (rushing)
        roll = randint(0, 100)
        
        if roll < 70:
            # Natural uniform random
            return randint(int(min_sec * 1000), int(max_sec * 1000)) / 1000
        elif roll < 90:
            # Bias to upper (humans hesitate/think)
            mid = (min_sec + max_sec) / 2
            return randint(int(mid * 1000), int(max_sec * 1000)) / 1000
        else:
            # Bias to lower (humans sometimes rush)
            mid = (min_sec + max_sec) / 2
            return randint(int(min_sec * 1000), int(mid * 1000)) / 1000

    async def _get_pre_action_hesitation(self) -> float:
        """
        Random hesitation BEFORE a critical action (encounter, dispatch).
        Humans pause to think before acting; makes it look less instant.
        ~30% chance of 0.5-3s delay.
        """
        if self._max_speed():
            return 0
        if randint(0, 100) > 70:  # 30% chance
            hesitation = randint(500, 3000) / 1000
            record_anti_detect_event(
                str(self.bot.user) if self.bot.user else "unknown",
                "pre_action_hesitation",
                module="hunting",
                channel_id=self.config.hunting_channel_id,
                details={"seconds": hesitation},
            )
            return hesitation
        return 0

    def _should_skip_cycle(self) -> bool:
        """
        ~5% chance to skip a cycle (late reaction, distraction).
        Makes it look like human didn't react instantly to encounter.
        """
        if self._max_speed():
            return False
        return randint(0, 100) > 95

    @staticmethod
    def _is_high_rarity(rarity: str) -> bool:
        lowered = (rarity or "").lower()
        return any(
            token in lowered
            for token in ("legendary", "shiny", "mythical", "ultra", "event", "golden")
        )

    def _record_retrieved_item_from_message(self, message: Message, rarity: str, pokemon_name: str) -> None:
        item_name = extract_retrieved_item_name(message)
        if not item_name:
            return

        retrieved_pokemon_name = extract_retrieved_item_pokemon_name(message)
        chosen_pokemon_name = retrieved_pokemon_name or pokemon_name

        item_slug = normalize_item_slug(item_name)
        record_retrieved_item_event(
            str(self.bot.user) if self.bot.user else "unknown",
            pokemon_name=chosen_pokemon_name,
            pokemon_slug=normalize_pokemon_slug(chosen_pokemon_name),
            item_name=item_name,
            item_slug=item_slug,
            rarity=rarity,
            channel_id=self.config.hunting_channel_id,
        )

    @staticmethod
    def _parse_wait_seconds(message_content: str) -> float:
        lowered = str(message_content or "").lower()
        match = re.search(r"(\d+)\s*seconds?", lowered)
        if match:
            return max(float(match.group(1)), 1.0)
        if "few more seconds" in lowered or "few seconds" in lowered:
            return 3.0
        return 2.0

    @staticmethod
    def _select_best_ball_button(children: list, preferred_ball: str):
        # Choose the strongest available ball within the allowed downgrade range.
        priority = ["mb", "db", "prb", "ub", "gb", "pb"]
        safe_preferred = preferred_ball if preferred_ball in priority else "pb"
        allowed = priority[priority.index(safe_preferred) :]
        buttons_by_id = {getattr(button, "custom_id", ""): button for button in children}
        for ball_id in allowed:
            if ball_id in buttons_by_id:
                return buttons_by_id[ball_id]
        return None

    def _is_message_for_this_bot(self, message: Message) -> bool:
        # Prefer interaction ownership when available.
        if message.interaction and message.interaction.user == self.bot.user:
            return True

        # Fallback: only consider messages that mention this bot username.
        username = ""
        if self.bot.user is not None:
            username = str(getattr(self.bot.user, "name", "")).lower()

        if not username:
            return False

        text_parts = [message.content or ""]
        for embed in message.embeds:
            text_parts.extend(
                [
                    embed.title or "",
                    embed.description or "",
                    embed.footer.text if embed.footer else "",
                ]
            )

        haystack = " ".join(text_parts).lower()
        return username in haystack

    def _is_daily_limit_notice(self, message: Message) -> bool:
        if message.author.id != POKEMEOW_APP_ID:
            return False

        if message.channel.id != self.config.hunting_channel_id:
            return False

        is_owned_interaction = bool(
            message.interaction and message.interaction.user == self.bot.user
        )
        if not is_owned_interaction and not self._is_message_for_this_bot(message):
            return False

        text_parts = [message.content or ""]
        for embed in message.embeds:
            text_parts.extend(
                [
                    embed.title or "",
                    embed.description or "",
                    embed.footer.text if embed.footer else "",
                ]
            )

        haystack = " ".join(text_parts).lower()
        return (
            "you have reached your daily catch limit" in haystack
            or "you have reached your daily encounter limit" in haystack
            or "you have reached the daily catch limit" in haystack
            or "you have reached the daily encounter limit" in haystack
        )

    async def _handle_daily_limit(self) -> None:
        record_anti_detect_event(
            str(self.bot.user) if self.bot.user else "unknown",
            "daily_limit",
            module="hunting",
            channel_id=self.config.hunting_channel_id,
            details={"action": "pause_hunting_resume_fishing"},
        )
        self.bot.limit = True
        self.bot.pause_hunting = True
        self.bot.hunting_status = "Encounter limit reached!"

        if self.config.fishing_channel_id != 0:
            self.bot.pause_fishing = False
            self.bot.fishing_status = "Grinding..."

        await self.bot.log()

        if self.config.fishing_channel_id == 0:
            return

        if not getattr(self.bot, "fishing_channel_commands", None):
            return

        fish_spawn = self.bot.fishing_channel_commands.get("fish spawn")
        if fish_spawn is None:
            return

        try:
            await asyncio.sleep(randint(0, self.config.suspicion_avoidance) / 1000)
            await fish_spawn()
        except Exception:
            # Fishing loop will retry shortly if this kickoff fails.
            pass

    async def _safe_hunt_pokemon_with_captcha_check(self) -> None:
        """
        Dispatch pokemon hunt only if no captcha is currently active.
        This prevents dispatch during captcha windows even if the flag changes during sleep phases.
        """
        if getattr(self.bot, "hunting_captcha_active", False) or self.bot.pause_hunting or self.bot.limit:
            return
        try:
            await self.bot.hunting_channel_commands["pokemon"]()
        except Exception as exc:
            if is_cloudflare_1015_error(str(exc)):
                await notify_cloudflare_in_channel(
                    self.bot,
                    channel_id=int(self.config.hunting_channel_id or 0),
                    module_name="Hunting",
                    error_text=str(exc),
                    cooldown_seconds=60.0,
                )
            print(f"[Hunting] Failed dispatching pokemon command: {exc}")

    @commands.Cog.listener()
    async def on_message(self, message: Message) -> None:
        if self._is_daily_limit_notice(message):
            await self._handle_daily_limit()
            return

        if getattr(self.bot, "hunting_captcha_active", False) or self.bot.pause_hunting:
            return

        if not message.interaction:
            return

        if (
            message.interaction.name != "pokemon"
            or message.interaction.user != self.bot.user
            or message.channel.id != self.config.hunting_channel_id
        ):
            return

        if "Please wait" in message.content:
            record_anti_detect_event(
                str(self.bot.user) if self.bot.user else "unknown",
                "please_wait",
                module="hunting",
                channel_id=self.config.hunting_channel_id,
                details={"retry_cooldown": self.config.retry_cooldown},
            )
            wait_seconds = self._parse_wait_seconds(message.content)
            await asyncio.sleep(max(wait_seconds, float(self.config.retry_cooldown or 0.0)))
            await asyncio.sleep(randint(0, self.config.suspicion_avoidance) / 1000)
            if self.config.enable_anti_detection:
                await asyncio.sleep(self.config.min_action_delay_seconds)
            else:
                await asyncio.sleep(randint(int(self.config.hunting_delay_min * 1000), int(self.config.hunting_delay_max * 1000)) / 1000)
            await self._maybe_take_human_break()
            # Pre-action hesitation before dispatch
            hesitation = await self._get_pre_action_hesitation()
            if hesitation > 0:
                await asyncio.sleep(hesitation)
            record_anti_detect_event(
                str(self.bot.user) if self.bot.user else "unknown",
                "dispatch_pokemon",
                module="hunting",
                channel_id=self.config.hunting_channel_id,
                details={"source": "please_wait_retry"},
            )
            await self._safe_hunt_pokemon_with_captcha_check()
            return

        if not message.embeds:
            return

        embed_description = message.embeds[0].description or ""
        lowered_embed_description = embed_description.lower()
        if (
            "you have reached your daily catch limit" in lowered_embed_description
            or "you have reached your daily encounter limit" in lowered_embed_description
            or "you have reached the daily catch limit" in lowered_embed_description
            or "you have reached the daily encounter limit" in lowered_embed_description
        ):
            await self._handle_daily_limit()
            return

        # Some responses arrive as direct final catch messages instead of an
        # encounter message that is later edited, so capture retrieved-item
        # telemetry here as well.
        if "caught" in lowered_embed_description and "found a wild" not in message.content.lower():
            rarity = resolve_hunting_rarity(self.config, message)
            pokemon_name = extract_pokemon_name(message)
            self._record_retrieved_item_from_message(message, rarity, pokemon_name)
            return

        if "found a wild" not in message.content:
            return

        self.bot.hunting_status = "Grinding..."

        ensure_day_mode_window(self.bot)
        self.bot.encounters += 1
        self.bot.lifetime_encounters += 1
        self.bot.last_hunt = time()

        rarity = resolve_hunting_rarity(self.config, message)
        name = extract_pokemon_name(message)
        if name in self.config.exception_balls:
            ball = self.config.exception_balls[name]
        else:
            ball = self.config.balls.get(rarity, self.config.balls.get("Common", "pb"))
        high_rarity = self._is_high_rarity(rarity) or ball in {"mb", "db", "prb"}

        record_anti_detect_event(
            str(self.bot.user) if self.bot.user else "unknown",
            "encounter",
            module="hunting",
            channel_id=self.config.hunting_channel_id,
            details={
                "session_encounters": self.bot.encounters + 1,
                "rarity": rarity,
                "pokemon_name": name,
                "pokemon_slug": normalize_pokemon_slug(name),
                "high_priority": high_rarity,
            },
        )
        persist_bot_stats(self.bot)
        await self.bot.log()

        # Occasional skip - sometimes don't react immediately to encounter
        if not high_rarity and self._should_skip_cycle():
            skip_seconds = randint(2, 8)
            print(f"[Hunting] Skipping cycle (late reaction): {skip_seconds}s")
            record_anti_detect_event(
                str(self.bot.user) if self.bot.user else "unknown",
                "action_skip",
                module="hunting",
                channel_id=self.config.hunting_channel_id,
                details={"reason": "late_encounter_reaction", "seconds": skip_seconds},
            )
            await asyncio.sleep(skip_seconds)
            return

        if high_rarity:
            record_anti_detect_event(
                str(self.bot.user) if self.bot.user else "unknown",
                "high_rarity_priority",
                module="hunting",
                channel_id=self.config.hunting_channel_id,
                details={"rarity": rarity, "ball": ball},
            )
            if not self._max_speed():
                await asyncio.sleep(randint(120, 450) / 1000)
        elif self.config.enable_anti_detection:
            await asyncio.sleep(self.config.min_action_delay_seconds)
        else:
            await asyncio.sleep(self._get_behavioral_delay(self.config.hunting_delay_min, self.config.hunting_delay_max))
        if not high_rarity:
            await self._maybe_take_human_break()
        # Pre-action hesitation before throwing ball
        if not high_rarity:
            hesitation = await self._get_pre_action_hesitation()
            if hesitation > 0:
                await asyncio.sleep(hesitation)

        children = [
            child for component in message.components for child in component.children
        ]

        chosen_button = self._select_best_ball_button(children, ball)
        if not chosen_button:
            return

        try:
            if high_rarity:
                if not self._max_speed():
                    await asyncio.sleep(randint(80, 300) / 1000)
            else:
                await asyncio.sleep(randint(0, self.config.suspicion_avoidance) / 1000)
            await chosen_button.click()

        except InvalidData:
            pass
        except Exception as exc:
            if is_cloudflare_1015_error(str(exc)):
                await notify_cloudflare_in_channel(
                    self.bot,
                    channel_id=int(self.config.hunting_channel_id or 0),
                    module_name="Hunting",
                    error_text=str(exc),
                    cooldown_seconds=60.0,
                )
            print(f"[Hunting] Failed clicking hunt button: {exc}")

    @commands.Cog.listener()
    async def on_message_edit(self, before: Message, after: Message) -> None:
        if getattr(self.bot, "hunting_captcha_active", False) or self.bot.pause_hunting:
            return

        if not after.interaction:
            return

        if (
            after.interaction.name != "pokemon"
            or after.interaction.user != self.bot.user
            or after.channel.id != self.config.hunting_channel_id
            or "found a wild" not in before.content
        ):
            return

        if after.content == before.content:
            if after.embeds != []:
                if before.embeds != []:
                    if after.embeds[0].description == before.embeds[0].description:
                        return
            else:
                return

        tasks = []

        if "caught" in after.embeds[0].description:
            if not self._should_process_catch_message(int(getattr(after, "id", 0) or 0)):
                return

            ensure_day_mode_window(self.bot)
            self.bot.catches += 1
            self.bot.lifetime_catches += 1
            self.bot.coins_earned += int(
                after.embeds[0]
                .footer.text.split("You earned ")[1]
                .split(" ")[0]
                .replace(",", "")
            )
            self.bot.lifetime_coins_earned += int(
                after.embeds[0]
                .footer.text.split("You earned ")[1]
                .split(" ")[0]
                .replace(",", "")
            )

            rarity = resolve_hunting_rarity(self.config, before)
            pokemon_name = extract_caught_pokemon_name(after)
            if pokemon_name == "Unknown":
                pokemon_name = extract_pokemon_name(after)
            if pokemon_name == "Unknown":
                pokemon_name = extract_pokemon_name(before)
            self.bot.hunt_rarity_catches[rarity] = (
                self.bot.hunt_rarity_catches.get(rarity, 0) + 1
            )
            self.bot.lifetime_hunt_rarity_catches[rarity] = (
                self.bot.lifetime_hunt_rarity_catches.get(rarity, 0) + 1
            )
            persist_bot_stats(self.bot, force=True)
            item_name = extract_retrieved_item_name(after)
            item_slug = normalize_item_slug(item_name)

            record_anti_detect_event(
                str(self.bot.user) if self.bot.user else "unknown",
                "catch",
                module="hunting",
                channel_id=self.config.hunting_channel_id,
                details={
                    "rarity": rarity,
                    "pokemon_name": pokemon_name,
                    "pokemon_slug": normalize_pokemon_slug(pokemon_name),
                    "retrieved_item": item_name,
                    "retrieved_item_slug": item_slug,
                    "session_catches": self.bot.catches,
                    "coins_total": self.bot.coins_earned,
                },
            )

            if item_name:
                self._record_retrieved_item_from_message(after, rarity, pokemon_name)

            if is_high_rarity_label(rarity):
                record_rare_catch_event(
                    str(self.bot.user) if self.bot.user else "unknown",
                    rarity=rarity,
                    pokemon_name=pokemon_name,
                    pokemon_slug=normalize_pokemon_slug(pokemon_name),
                    channel_id=self.config.hunting_channel_id,
                    source_message_id=int(getattr(after, "id", 0) or 0),
                )

            await self.bot.log()

            if "has been added to your Pokedex" not in after.embeds[0].description:
                self.bot.duplicates += 1

            if (
                self.config.auto_release_duplicates != 0
                and self.bot.duplicates >= self.config.auto_release_duplicates
            ):
                self.bot.duplicates = 0
                if not self._max_speed():
                    await asyncio.sleep(
                        2 + randint(0, self.config.suspicion_avoidance) / 1000
                    )

                tasks.append(
                    asyncio.create_task(
                        self.bot.hunting_channel_commands["release duplicates"]()
                    )
                )

        if "Your next Quest is now ready!" in before.content:
            if not self._max_speed():
                await asyncio.sleep(1 + randint(0, self.config.suspicion_avoidance) / 1000)
            tasks.append(
                asyncio.create_task(self.bot.hunting_channel_commands["quest info"]())
            )

        tasks.append(
            asyncio.create_task(
                auto_buy(
                    self.bot, self.config, self.bot.hunting_channel_commands, after
                )
            )
        )

        await asyncio.sleep(self.config.hunting_cooldown)
        await asyncio.sleep(randint(0, self.config.suspicion_avoidance) / 1000)
        await asyncio.sleep(randint(int(self.config.post_catch_delay_min * 1000), int(self.config.post_catch_delay_max * 1000)) / 1000)
        if (
            not getattr(self.bot, "hunting_captcha_active", False)
            and not self.bot.pause_hunting
            and not self.bot.limit
        ):
            # Occasional idle before retrying (looks like human distraction)
            await self._maybe_add_idle_randomness()
            
            if self.config.enable_anti_detection:
                await asyncio.sleep(self.config.min_action_delay_seconds)
            else:
                await asyncio.sleep(self._get_behavioral_delay(self.config.hunting_delay_min, self.config.hunting_delay_max))
            await self._maybe_take_human_break()
            # Pre-action hesitation before dispatch
            hesitation = await self._get_pre_action_hesitation()
            if hesitation > 0:
                await asyncio.sleep(hesitation)
            record_anti_detect_event(
                str(self.bot.user) if self.bot.user else "unknown",
                "dispatch_pokemon",
                module="hunting",
                channel_id=self.config.hunting_channel_id,
                details={
                    "source": "post_catch_loop",
                    "hunting_cooldown": self.config.hunting_cooldown,
                    "post_catch_delay_min": self.config.post_catch_delay_min,
                    "post_catch_delay_max": self.config.post_catch_delay_max,
                },
            )
            await self._safe_hunt_pokemon_with_captcha_check()
        [await task for task in tasks]
