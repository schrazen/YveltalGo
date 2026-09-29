import json
import asyncio
import re
from time import time
from random import randint, choice
from pathlib import Path

from discord import Message, InvalidData
from discord.ext import commands

from cogs.hunting import auto_buy
from cogs.startup import Config
from modules.stats_store import persist_bot_stats, ensure_day_mode_window
from modules.anti_detect_log import record_anti_detect_event
from modules.cloudflare_indicator import is_cloudflare_1015_error, notify_cloudflare_in_channel
from modules.pokemeow_reader import inspect_and_record_pokemeow_message

BASE_DIR = Path(__file__).resolve().parents[1]
_fishes_file = BASE_DIR / "data" / "fishes.json"
if not _fishes_file.exists():
    _fishes_file = BASE_DIR / "fishes.json"
fishes = json.loads(_fishes_file.read_text(encoding="utf-8"))


def resolve_fishing_rarity(embed_description: str) -> str:
    lowered = embed_description.lower()
    if "shiny" in lowered:
        return "Shiny"

    if "golden" in lowered:
        return "Golden"

    try:
        fish_name = embed_description.split("**")[3]
        return fishes.get(fish_name, "Unknown")
    except Exception:
        return "Unknown"


class Fishing(commands.Cog):
    def __init__(self, bot: commands.Bot, break_coordinator=None) -> None:
        self.bot = bot
        self.config: Config = bot.config
        self.break_coordinator = break_coordinator
        self._last_fish_ball: str = "pb"
        self._last_fish_rarity: str = ""

    def _max_speed(self) -> bool:
        return bool(getattr(self.config, "max_speed_mode_enabled", False))

    async def _maybe_take_human_break(self) -> None:
        if self._max_speed():
            return
        if not self.config.human_breaks_enabled:
            return

        if self.break_coordinator:
            # If another cog is already taking a break, wait for it
            while self.break_coordinator.is_break_in_progress():
                await asyncio.sleep(1.0)

            break_seconds = self.break_coordinator.get_break_duration()
            if break_seconds > 0:
                print(f"[Fishing] Silent human break for {break_seconds}s")
                if hasattr(self.bot, "humanizer") and self.bot.humanizer:
                    self.bot.humanizer.last_break_time = time() + break_seconds

                record_anti_detect_event(
                    str(self.bot.user) if self.bot.user else "unknown",
                    "human_break",
                    module="fishing",
                    channel_id=self.config.fishing_channel_id,
                    details={"seconds": break_seconds, "stealth": True},
                )
                self.break_coordinator.start_break()
                try:
                    await asyncio.sleep(break_seconds)
                finally:
                    self.break_coordinator.end_break()
        elif hasattr(self.bot, "humanizer") and self.bot.humanizer:
            await self.bot.humanizer.maybe_take_human_break("fishing", self.config.fishing_channel_id)

    async def _maybe_add_idle_randomness(self) -> None:
        """
        Occasionally add unscheduled idle time to break the rhythm naturally.
        """
        if self._max_speed():
            return
        if not self.config.human_breaks_enabled:
            return

        if hasattr(self.bot, "humanizer") and self.bot.humanizer:
            await self.bot.humanizer.maybe_add_idle_randomness("fishing", self.config.fishing_channel_id)
        elif randint(0, 100) > 92:
            idle_seconds = randint(5, 20)
            print(f"[Fishing] Idle randomness: {idle_seconds}s")
            record_anti_detect_event(
                str(self.bot.user) if self.bot.user else "unknown",
                "idle_randomness",
                module="fishing",
                channel_id=self.config.fishing_channel_id,
                details={"seconds": idle_seconds, "reason": "human_like_pause"},
            )
            await asyncio.sleep(idle_seconds)

    def _get_behavioral_delay(self, min_sec: float, max_sec: float) -> float:
        """
        Return a natural log-normal delay clustering around human cognitive reaction times.
        """
        if hasattr(self.bot, "humanizer") and self.bot.humanizer:
            mid = (float(min_sec) + float(max_sec)) / 2.0
            return self.bot.humanizer.get_natural_jitter(mid, variance=0.25, min_floor=min_sec)

        roll = randint(0, 100)
        if roll < 70:
            return randint(int(min_sec * 1000), int(max_sec * 1000)) / 1000
        elif roll < 90:
            mid = (min_sec + max_sec) / 2
            return randint(int(mid * 1000), int(max_sec * 1000)) / 1000
        else:
            mid = (min_sec + max_sec) / 2
            return randint(int(min_sec * 1000), int(mid * 1000)) / 1000

    async def _get_pre_action_hesitation(self, rarity: str = "Common") -> float:
        """
        Cognitive hesitation before action, weighted by rarity and fatigue.
        """
        if self._max_speed():
            return 0.0
        if hasattr(self.bot, "humanizer") and self.bot.humanizer:
            return await self.bot.humanizer.get_cognitive_hesitation(
                "fishing", rarity=rarity, channel_id=self.config.fishing_channel_id
            )

        if randint(0, 100) > 70:
            hesitation = randint(500, 3000) / 1000
            record_anti_detect_event(
                str(self.bot.user) if self.bot.user else "unknown",
                "pre_action_hesitation",
                module="fishing",
                channel_id=self.config.fishing_channel_id,
                details={"seconds": hesitation},
            )
            return hesitation
        return 0.0

    def _should_skip_cycle(self) -> bool:
        """
        Simulate human distraction / delayed reaction skipping an action cycle.
        """
        if self._max_speed():
            return False
        if hasattr(self.bot, "humanizer") and self.bot.humanizer:
            return self.bot.humanizer.should_skip_cycle("fishing", self.config.fishing_channel_id)
        return randint(0, 100) > 95

    @staticmethod
    def _is_high_rarity(rarity: str) -> bool:
        lowered = (rarity or "").lower()
        return any(
            token in lowered
            for token in ("legendary", "shiny", "mythical", "ultra", "event", "golden")
        )

    @staticmethod
    def _select_best_ball_button(children: list, preferred_ball: str):
        # Choose the strongest available ball within the allowed downgrade range.
        priority = ["mb", "db", "prb", "ub", "gb", "pb"]
        safe_preferred = preferred_ball if preferred_ball in priority else "pb"
        allowed = priority[priority.index(safe_preferred) :]
        
        buttons_by_ball: dict[str, object] = {}
        for button in children:
            cid = str(getattr(button, "custom_id", "") or "").strip()
            if not cid:
                continue
            buttons_by_ball[cid] = button
            suffix = cid.split(":")[-1]
            buttons_by_ball[suffix] = button
            if suffix.endswith("_fish"):
                buttons_by_ball[suffix[:-5]] = button

        for ball_id in allowed:
            custom_id = f"{ball_id}_fish"
            if custom_id in buttons_by_ball:
                return buttons_by_ball[custom_id]
            if ball_id in buttons_by_ball:
                return buttons_by_ball[ball_id]
        return None

    @staticmethod
    def _parse_wait_seconds(message_content: str) -> float:
        lowered = message_content.lower()

        # Examples handled:
        # - "Please wait :stopwatch: 21 seconds before fishing again!"
        # - "Please wait a few more seconds before fishing again!"
        match = re.search(r"(\d+)\s*seconds?", lowered)
        if match:
            return max(float(match.group(1)), 1.0)

        if "few more seconds" in lowered or "few seconds" in lowered:
            return 4.0

        return 3.0

    @staticmethod
    def _contains_no_rod_signal(raw_text: str) -> bool:
        lowered = str(raw_text or "").lower()
        if "rod" not in lowered:
            return False

        no_rod_markers = (
            "don't have",
            "do not have",
            "dont have",
            "need a",
            "need to buy",
            "buy a",
            "missing",
            "without",
            "no fishing rod",
        )
        return any(marker in lowered for marker in no_rod_markers)

    async def _pause_fishing_for_missing_rod(self, raw_text: str) -> None:
        self.bot.pause_fishing = True
        self.bot.fishing_status = "Paused (No Fishing Rod)"
        record_anti_detect_event(
            str(self.bot.user) if self.bot.user else "unknown",
            "fishing_no_rod",
            module="fishing",
            channel_id=self.config.fishing_channel_id,
            details={"raw": str(raw_text or "")[:180]},
        )
        await self.bot.log()
        print("[Fishing] Auto-paused fishing: account appears to have no fishing rod.")

    async def _safe_fish_spawn(self) -> None:
        command_map = getattr(self.bot, "fishing_channel_commands", None)
        if not command_map:
            return

        fish_spawn = command_map.get("fish spawn")
        if fish_spawn is None:
            print("[Fishing] Warning: command 'fish spawn' not found.")
            return

        try:
            channel = self.bot.get_channel(self.config.fishing_channel_id)
            if channel is not None and hasattr(self.bot, "humanizer") and self.bot.humanizer:
                await self.bot.humanizer.simulate_human_typing(channel, chars_count=2)
            await fish_spawn()
        except InvalidData:
            # Discord timed out; startup loop will retry.
            print("[Fishing] Discord timed out invoking 'fish spawn'.")
        except Exception as exc:
            if is_cloudflare_1015_error(str(exc)):
                await notify_cloudflare_in_channel(
                    self.bot,
                    channel_id=int(self.config.fishing_channel_id or 0),
                    module_name="Fishing",
                    error_text=str(exc),
                    cooldown_seconds=60.0,
                )
            print(f"[Fishing] Failed invoking 'fish spawn' ({exc}).")

    async def _safe_fish_spawn_with_captcha_check(self) -> None:
        """
        Dispatch fish spawn only if no captcha is currently active.
        This prevents dispatch during captcha windows even if the flag changes during sleep phases.
        """
        if getattr(self.bot, "fishing_captcha_active", False) or self.bot.pause_fishing:
            return
        await self._safe_fish_spawn()

    @commands.Cog.listener()
    async def on_message(self, message: Message) -> None:
        if getattr(self.bot, "fishing_captcha_active", False) or self.bot.pause_fishing:
            return

        if not message.interaction:
            return

        if (
            message.interaction.name != "fish spawn"
            or message.interaction.user != self.bot.user
            or message.channel.id != self.config.fishing_channel_id
        ):
            return

        if self._contains_no_rod_signal(message.content):
            inspect_and_record_pokemeow_message(self.bot, message, context_module="fishing")
            await self._pause_fishing_for_missing_rod(message.content)
            return

        if "Please wait" not in message.content:
            inspect_and_record_pokemeow_message(self.bot, message, context_module="fishing")
            return

        inspect_and_record_pokemeow_message(self.bot, message, context_module="fishing")
        record_anti_detect_event(
            str(self.bot.user) if self.bot.user else "unknown",
            "please_wait",
            module="fishing",
            channel_id=self.config.fishing_channel_id,
            details={"raw": message.content[:120]},
        )

        self.bot.fishing_status = "Grinding..."
        await self.bot.log()

        # Respect fishing cooldown returned by PokéMeow to avoid spam loops.
        wait_seconds = self._parse_wait_seconds(message.content)
        self.bot.last_fish = time()
        base_wait = max(wait_seconds, 1.0)
        if hasattr(self.bot, "humanizer") and self.bot.humanizer:
            await asyncio.sleep(self.bot.humanizer.get_natural_jitter(base_wait, variance=0.15, min_floor=base_wait))
        else:
            await asyncio.sleep(base_wait)
            await asyncio.sleep(randint(0, self.config.suspicion_avoidance) / 1000)
            if self.config.enable_anti_detection:
                await asyncio.sleep(self.config.min_action_delay_seconds)
            else:
                await asyncio.sleep(self._get_behavioral_delay(self.config.fishing_delay_min, self.config.fishing_delay_max))
        await self._maybe_take_human_break()
        # Pre-action hesitation before dispatch
        hesitation = await self._get_pre_action_hesitation()
        if hesitation > 0:
            await asyncio.sleep(hesitation)
        record_anti_detect_event(
            str(self.bot.user) if self.bot.user else "unknown",
            "dispatch_fish_spawn",
            module="fishing",
            channel_id=self.config.fishing_channel_id,
            details={"source": "please_wait_retry", "wait_seconds": wait_seconds},
        )
        await self._safe_fish_spawn_with_captcha_check()

    @commands.Cog.listener()
    async def on_message_edit(self, before: Message, after: Message) -> None:
        if getattr(self.bot, "fishing_captcha_active", False) or self.bot.pause_fishing:
            return

        if not after.interaction:
            return

        if (
            after.interaction.user != self.bot.user
            or after.interaction.name != "fish spawn"
            or after.channel.id != self.config.fishing_channel_id
        ):
            return

        if not after.embeds:
            return

        before_description = ""
        if before.embeds and before.embeds[0].description:
            before_description = before.embeds[0].description

        after_description = after.embeds[0].description or ""
        combined_after_text = f"{after.content or ''}\n{after_description}"

        if after.content == before.content and after_description == before_description:
            return

        if self._contains_no_rod_signal(combined_after_text):
            await self._pause_fishing_for_missing_rod(combined_after_text)
            return

        lowered_after_description = after_description.lower()
        if (
            "not even a nibble" in lowered_after_description
            or "got away" in lowered_after_description
        ):
            previous_rarity = resolve_fishing_rarity(before_description)
            high_priority_escape = self._is_high_rarity(previous_rarity)
            record_anti_detect_event(
                str(self.bot.user) if self.bot.user else "unknown",
                "miss_or_escape",
                module="fishing",
                channel_id=self.config.fishing_channel_id,
                details={
                    "desc": lowered_after_description[:120],
                    "rarity": previous_rarity,
                    "high_priority": high_priority_escape,
                },
            )
            inspect_and_record_pokemeow_message(
                self.bot,
                after,
                before_message=before,
                context_module="fishing",
                ball_used=getattr(self, "_last_fish_ball", ""),
            )
            if high_priority_escape:
                record_anti_detect_event(
                    str(self.bot.user) if self.bot.user else "unknown",
                    "high_rarity_escape",
                    module="fishing",
                    channel_id=self.config.fishing_channel_id,
                    details={"rarity": previous_rarity},
                )
            self.bot.fishing_status = "Grinding..."
            await self.bot.log()

            self.bot.last_fish = time()
            fishing_cooldown = float(self.config.fishing_cooldown)
            if hasattr(self.bot, "humanizer") and self.bot.humanizer:
                cooldown_sleep = self.bot.humanizer.get_natural_jitter(
                    fishing_cooldown, variance=0.15, min_floor=fishing_cooldown * 0.95
                )
                await asyncio.sleep(cooldown_sleep)

                post_catch_mid = (
                    float(self.config.post_catch_delay_min)
                    + float(self.config.post_catch_delay_max)
                ) / 2.0
                post_catch_sleep = self.bot.humanizer.get_natural_jitter(
                    post_catch_mid, variance=0.25, min_floor=float(self.config.post_catch_delay_min)
                )
                await asyncio.sleep(post_catch_sleep)
            else:
                await asyncio.sleep(fishing_cooldown)
                await asyncio.sleep(randint(0, self.config.suspicion_avoidance) / 1000)
                await asyncio.sleep(
                    randint(
                        int(self.config.post_catch_delay_min * 1000),
                        int(self.config.post_catch_delay_max * 1000),
                    )
                    / 1000
                )
            # Occasional idle before retrying
            await self._maybe_add_idle_randomness()
            if self._should_skip_cycle():
                await asyncio.sleep(randint(2, 4))

            if self.config.enable_anti_detection:
                if hasattr(self.bot, "humanizer") and self.bot.humanizer:
                    action_delay = self.bot.humanizer.get_natural_jitter(
                        self.config.min_action_delay_seconds, variance=0.2
                    )
                else:
                    action_delay = self.config.min_action_delay_seconds
                await asyncio.sleep(action_delay)
            else:
                await asyncio.sleep(self._get_behavioral_delay(self.config.fishing_delay_min, self.config.fishing_delay_max))
            await self._maybe_take_human_break()
            # Pre-action hesitation before dispatch
            hesitation = await self._get_pre_action_hesitation()
            if hesitation > 0:
                await asyncio.sleep(hesitation)
            record_anti_detect_event(
                str(self.bot.user) if self.bot.user else "unknown",
                "dispatch_fish_spawn",
                module="fishing",
                channel_id=self.config.fishing_channel_id,
                details={"source": "miss_or_escape_loop"},
            )
            await self._safe_fish_spawn_with_captcha_check()
            return

        elif (
            "cast" in after_description
            and "click the" in after_description
        ):
            record_anti_detect_event(
                str(self.bot.user) if self.bot.user else "unknown",
                "cast_prompt",
                module="fishing",
                channel_id=self.config.fishing_channel_id,
                details={},
            )
            self.bot.fishing_status = "Grinding..."
            self.bot.last_fish = time()
            await self.bot.log()
            try:
                if not self._max_speed():
                    cast_reaction = (
                        self.bot.humanizer.get_natural_jitter(0.18, variance=0.15, min_floor=0.10)
                        if hasattr(self.bot, "humanizer") and self.bot.humanizer
                        else 0.15
                    )
                    await asyncio.sleep(cast_reaction)
                await after.components[0].children[0].click()

            except InvalidData:
                pass
            except Exception as exc:
                if is_cloudflare_1015_error(str(exc)):
                    await notify_cloudflare_in_channel(
                        self.bot,
                        channel_id=int(self.config.fishing_channel_id or 0),
                        module_name="Fishing",
                        error_text=str(exc),
                        cooldown_seconds=60.0,
                    )
                print(f"[Fishing] Failed clicking cast prompt: {exc}")

            return

        elif "fished" in after_description:
            ensure_day_mode_window(self.bot)
            self.bot.fish_encounters += 1
            self.bot.lifetime_fish_encounters += 1
            rarity = resolve_fishing_rarity(after_description)
            ball = self.config.fish_balls.get(rarity, self.config.fish_balls.get("Common", "pb"))
            high_rarity = self._is_high_rarity(rarity) or ball in {"mb", "db", "prb"}
            self._last_fish_ball = ball
            self._last_fish_rarity = rarity
            record_anti_detect_event(
                str(self.bot.user) if self.bot.user else "unknown",
                "fish_encounter",
                module="fishing",
                channel_id=self.config.fishing_channel_id,
                details={
                    "session_fish_encounters": self.bot.fish_encounters + 1,
                    "rarity": rarity,
                    "high_priority": high_rarity,
                },
            )
            inspect_and_record_pokemeow_message(
                self.bot,
                after,
                context_module="fishing",
                ball_used=ball,
            )
            persist_bot_stats(self.bot)
            await self.bot.log()

            if high_rarity:
                record_anti_detect_event(
                    str(self.bot.user) if self.bot.user else "unknown",
                    "high_rarity_priority",
                    module="fishing",
                    channel_id=self.config.fishing_channel_id,
                    details={"rarity": rarity, "ball": ball},
                )

            children = [
                child for component in after.components for child in component.children
            ]

            chosen_button = self._select_best_ball_button(children, ball)
            if not chosen_button:
                return

            # Fast human reflex for button click: never let the fish escape/timeout.
            # Humans tap buttons on screen in 120-350ms.
            hesitation = await self._get_pre_action_hesitation(rarity=rarity)
            if hesitation > 0:
                await asyncio.sleep(hesitation)
            elif not self._max_speed():
                await asyncio.sleep(randint(100, 250) / 1000)

            try:
                await chosen_button.click()
            except InvalidData:
                pass
            except Exception as exc:
                if is_cloudflare_1015_error(str(exc)):
                    await notify_cloudflare_in_channel(
                        self.bot,
                        channel_id=int(self.config.fishing_channel_id or 0),
                        module_name="Fishing",
                        error_text=str(exc),
                        cooldown_seconds=60.0,
                    )
                print(f"[Fishing] Failed clicking fish ball button: {exc}")
            return

        elif "fished" in before_description:
            tasks = []

            if "caught" in after_description or "caught" in lowered_combined:
                ensure_day_mode_window(self.bot)
                self.bot.fish_catches += 1
                self.bot.lifetime_fish_catches += 1
                self.bot.duplicates += 1
                try:
                    footer_text = str(getattr(getattr(after.embeds[0], "footer", None), "text", "") or "")
                    if "You earned " in footer_text:
                        coins_str = footer_text.split("You earned ")[1].split(" ")[0].replace(",", "")
                        coins = int(coins_str)
                        self.bot.coins_earned += coins
                        self.bot.lifetime_coins_earned += coins
                except Exception:
                    pass
                rarity = resolve_fishing_rarity(before_description)
                self.bot.fish_rarity_catches[rarity] = (
                    self.bot.fish_rarity_catches.get(rarity, 0) + 1
                )
                self.bot.lifetime_fish_rarity_catches[rarity] = (
                    self.bot.lifetime_fish_rarity_catches.get(rarity, 0) + 1
                )
                persist_bot_stats(self.bot, force=True)
                record_anti_detect_event(
                    str(self.bot.user) if self.bot.user else "unknown",
                    "fish_catch",
                    module="fishing",
                    channel_id=self.config.fishing_channel_id,
                    details={
                        "rarity": rarity,
                        "session_fish_catches": self.bot.fish_catches,
                    },
                )
                await self.bot.log()

                inspect_and_record_pokemeow_message(
                    self.bot,
                    after,
                    before_message=before,
                    context_module="fishing",
                    ball_used=getattr(self, "_last_fish_ball", ""),
                )

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
                            self.bot.fishing_channel_commands["release duplicates"]()
                        )
                    )

            elif any(marker in after_description.lower() for marker in ("got away", "ran away", "broke free", "fled")):
                rarity = resolve_fishing_rarity(before_description)
                ball_used = getattr(self, "_last_fish_ball", "")
                record_anti_detect_event(
                    str(self.bot.user) if self.bot.user else "unknown",
                    "fish_flee",
                    module="fishing",
                    channel_id=self.config.fishing_channel_id,
                    details={
                        "rarity": rarity,
                        "ball_used": ball_used,
                        "desc": after_description[:120],
                    },
                )
                inspect_and_record_pokemeow_message(
                    self.bot,
                    after,
                    before_message=before,
                    context_module="fishing",
                    ball_used=ball_used,
                )
                await self.bot.log()
            else:
                inspect_and_record_pokemeow_message(
                    self.bot,
                    after,
                    before_message=before,
                    context_module="fishing",
                    ball_used=getattr(self, "_last_fish_ball", ""),
                )

            if "Your next Quest is now ready!" in before.content:
                if not self._max_speed():
                    await asyncio.sleep(
                        1 + randint(0, self.config.suspicion_avoidance) / 1000
                    )

                tasks.append(
                    asyncio.create_task(
                        self.bot.fishing_channel_commands["quest info"]()
                    )
                )

            tasks.append(
                asyncio.create_task(
                    auto_buy(
                        self.bot, self.config, self.bot.fishing_channel_commands, after
                    )
                )
            )

            fishing_cooldown = float(self.config.fishing_cooldown)
            if hasattr(self.bot, "humanizer") and self.bot.humanizer:
                cooldown_sleep = self.bot.humanizer.get_natural_jitter(
                    fishing_cooldown, variance=0.15, min_floor=fishing_cooldown * 0.95
                )
                await asyncio.sleep(cooldown_sleep)

                post_catch_mid = (
                    float(self.config.post_catch_delay_min)
                    + float(self.config.post_catch_delay_max)
                ) / 2.0
                post_catch_sleep = self.bot.humanizer.get_natural_jitter(
                    post_catch_mid, variance=0.25, min_floor=float(self.config.post_catch_delay_min)
                )
                await asyncio.sleep(post_catch_sleep)
            else:
                await asyncio.sleep(fishing_cooldown)
                await asyncio.sleep(randint(0, self.config.suspicion_avoidance) / 1000)
                await asyncio.sleep(
                    randint(
                        int(self.config.post_catch_delay_min * 1000),
                        int(self.config.post_catch_delay_max * 1000),
                    )
                    / 1000
                )
            # Occasional idle before retrying (looks like human distraction)
            await self._maybe_add_idle_randomness()
            if self._should_skip_cycle():
                await asyncio.sleep(randint(2, 4))

            if self.config.enable_anti_detection:
                if hasattr(self.bot, "humanizer") and self.bot.humanizer:
                    action_delay = self.bot.humanizer.get_natural_jitter(
                        self.config.min_action_delay_seconds, variance=0.2
                    )
                else:
                    action_delay = self.config.min_action_delay_seconds
                await asyncio.sleep(action_delay)
            else:
                await asyncio.sleep(self._get_behavioral_delay(self.config.fishing_delay_min, self.config.fishing_delay_max))
            await self._maybe_take_human_break()
            # Pre-action hesitation before dispatch
            hesitation = await self._get_pre_action_hesitation()
            if hesitation > 0:
                await asyncio.sleep(hesitation)
            record_anti_detect_event(
                str(self.bot.user) if self.bot.user else "unknown",
                "dispatch_fish_spawn",
                module="fishing",
                channel_id=self.config.fishing_channel_id,
                details={
                    "source": "post_catch_loop",
                    "fishing_cooldown": self.config.fishing_cooldown,
                    "post_catch_delay_min": self.config.post_catch_delay_min,
                    "post_catch_delay_max": self.config.post_catch_delay_max,
                },
            )
            await self._safe_fish_spawn_with_captcha_check()
            [await task for task in tasks]
            return
