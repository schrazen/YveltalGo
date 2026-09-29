import asyncio
from time import time
from random import randint

from modules.anti_detect_log import record_anti_detect_event


class Humanizer:
    """
    A centralized class to manage human-like behavior, delays, and breaks.
    An instance of this should be attached to each bot account to share break timers
    across different activities like hunting and fishing.
    """

    def __init__(self, bot) -> None:
        self.bot = bot
        self.config = bot.config
        self.next_short_break_at = time() + randint(
            max(10, self.config.short_break_every_min_seconds),
            max(
                max(10, self.config.short_break_every_min_seconds),
                self.config.short_break_every_max_seconds,
            ),
        )
        self.next_long_break_at = time() + randint(
            max(30, self.config.long_break_every_min_seconds),
            max(
                max(30, self.config.long_break_every_min_seconds),
                self.config.long_break_every_max_seconds,
            ),
        )

    def max_speed(self) -> bool:
        return bool(getattr(self.config, "max_speed_mode_enabled", False))

    async def maybe_take_human_break(self, module_name: str, channel_id: int) -> None:
        if self.max_speed():
            return
        if not self.config.human_breaks_enabled:
            return

        now = time()
        break_seconds = 0

        if now >= self.next_long_break_at:
            min_d = max(10, self.config.long_break_duration_min_seconds)
            max_d = max(min_d, self.config.long_break_duration_max_seconds)
            break_seconds = randint(min_d, max_d)
            self.next_long_break_at = now + randint(
                max(60, self.config.long_break_every_min_seconds),
                max(
                    max(60, self.config.long_break_every_min_seconds),
                    self.config.long_break_every_max_seconds,
                ),
            )
        elif now >= self.next_short_break_at:
            min_d = max(5, self.config.short_break_duration_min_seconds)
            max_d = max(min_d, self.config.short_break_duration_max_seconds)
            break_seconds = randint(min_d, max_d)
            self.next_short_break_at = now + randint(
                max(20, self.config.short_break_every_min_seconds),
                max(
                    max(20, self.config.short_break_every_min_seconds),
                    self.config.short_break_every_max_seconds,
                ),
            )

        if break_seconds > 0:
            print(f"[{module_name.capitalize()}] Human break for {break_seconds}s")
            record_anti_detect_event(
                str(self.bot.user) if self.bot.user else "unknown",
                "human_break",
                module=module_name,
                channel_id=channel_id,
                details={"seconds": break_seconds},
            )
            await asyncio.sleep(break_seconds)

    async def maybe_add_idle_randomness(self, module_name: str, channel_id: int) -> None:
        if self.max_speed():
            return
        if not self.config.human_breaks_enabled:
            return

        if randint(0, 100) > 92:
            idle_seconds = randint(5, 20)
            print(f"[{module_name.capitalize()}] Idle randomness: {idle_seconds}s")
            record_anti_detect_event(
                str(self.bot.user) if self.bot.user else "unknown",
                "idle_randomness",
                module=module_name,
                channel_id=channel_id,
                details={"seconds": idle_seconds, "reason": "human_like_pause"},
            )
            await asyncio.sleep(idle_seconds)

    def get_behavioral_delay(self, min_sec: float, max_sec: float) -> float:
        roll = randint(0, 100)
        if roll < 70:
            return randint(int(min_sec * 1000), int(max_sec * 1000)) / 1000
        elif roll < 90:
            mid = (min_sec + max_sec) / 2
            return randint(int(mid * 1000), int(max_sec * 1000)) / 1000
        else:
            mid = (min_sec + max_sec) / 2
            return randint(int(min_sec * 1000), int(mid * 1000)) / 1000

    async def get_pre_action_hesitation(self, module_name: str, channel_id: int) -> float:
        if self.max_speed():
            return 0
        if randint(0, 100) > 70:
            hesitation = randint(500, 3000) / 1000
            record_anti_detect_event(
                str(self.bot.user) if self.bot.user else "unknown",
                "pre_action_hesitation",
                module=module_name,
                channel_id=channel_id,
                details={"seconds": hesitation},
            )
            return hesitation
        return 0

    def should_skip_cycle(self) -> bool:
        if self.max_speed():
            return False
        return randint(0, 100) > 95