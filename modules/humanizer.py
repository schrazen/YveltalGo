import asyncio
import math
import random
from time import time
from typing import Any

from modules.anti_detect_log import record_anti_detect_event


class Humanizer:
    """
    Enhanced Anti-Detection & Human Behavior Engine.

    Features:
    - Log-normal / Gaussian delay jitter (replaces static/uniform sleeps).
    - Realistic Discord channel typing simulation with human WPM speed.
    - Context & Rarity-aware cognitive hesitation (Legendaries/Shinies pause longer).
    - Fatigue & Session drift: reaction times slowly drift as grinding sessions extend.
    - Human micro-pauses (idle randomness) and occasional cycle skips.
    - Synchronized breaks shared across Hunting, Fishing, and Autofight without spamming chat.
    """

    def __init__(self, bot: Any) -> None:
        self.bot = bot
        self.config = bot.config
        self.session_start_time: float = time()
        self.last_break_time: float = time()
        self.actions_count: int = 0
        self._reschedule_breaks()

    def _reschedule_breaks(self) -> None:
        now = time()
        short_min = max(20, int(getattr(self.config, "short_break_every_min_seconds", 90) or 90))
        short_max = max(short_min, int(getattr(self.config, "short_break_every_max_seconds", 180) or 180))
        self.next_short_break_at = now + random.randint(short_min, short_max)

        long_min = max(60, int(getattr(self.config, "long_break_every_min_seconds", 300) or 300))
        long_max = max(long_min, int(getattr(self.config, "long_break_every_max_seconds", 600) or 600))
        self.next_long_break_at = now + random.randint(long_min, long_max)

    def is_anti_detection_enabled(self) -> bool:
        if self.max_speed():
            return False
        return bool(getattr(self.config, "enable_anti_detection", True))

    def max_speed(self) -> bool:
        return bool(getattr(self.config, "max_speed_mode_enabled", False))

    def is_super_low_risk(self) -> bool:
        return bool(getattr(self.config, "super_low_risk_mode_enabled", False))

    def get_fatigue_multiplier(self) -> float:
        """
        Simulates human fatigue: after hours of grinding, reaction time
        naturally increases slightly by 5% to 25% until a long break occurs.
        """
        if self.max_speed() or not self.is_anti_detection_enabled():
            return 1.0

        elapsed_since_break = max(0.0, time() - self.last_break_time)
        hours = elapsed_since_break / 3600.0
        fatigue = min(0.25, hours * 0.10)
        return 1.0 + fatigue

    def get_natural_jitter(self, base_delay: float, variance: float = 0.25, min_floor: float = 0.2) -> float:
        """
        Calculates realistic human reaction time using log-normal distribution.
        Humans don't react with uniform distributions: most reactions cluster around
        a median with an asymmetric long right tail (slower lapses).
        """
        if self.max_speed():
            return 0.0

        if base_delay <= 0:
            base_delay = float(getattr(self.config, "min_action_delay_seconds", 2.0) or 2.0)

        effective_base = base_delay * self.get_fatigue_multiplier()
        if self.is_super_low_risk():
            effective_base = max(effective_base, 3.5)

        mu = math.log(max(0.1, effective_base))
        sigma = variance
        sample = random.lognormvariate(mu, sigma)

        low_bound = max(min_floor, effective_base * 0.70)
        high_bound = max(low_bound + 0.5, effective_base * 2.20)
        final_delay = max(low_bound, min(high_bound, sample))
        return round(final_delay, 3)

    async def simulate_human_typing(self, channel: Any, duration: float | None = None, chars_count: int = 4) -> None:
        """
        Triggers Discord's real typing indicator in the target channel.
        This provides a strong anti-detection signal against Discord automated bot sweeps.
        """
        if self.max_speed() or not self.is_anti_detection_enabled():
            return

        if channel is None:
            return

        if duration is None:
            think_delay = random.uniform(0.18, 0.40)
            typing_speed = random.uniform(0.08, 0.16) * max(2, chars_count)
            duration = min(1.2, max(0.2, round(think_delay + typing_speed, 3)))

        try:
            async with channel.typing():
                record_anti_detect_event(
                    str(self.bot.user) if self.bot.user else "unknown",
                    "typing_simulated",
                    module="humanizer",
                    channel_id=int(getattr(channel, "id", 0) or 0),
                    details={"duration_seconds": duration, "simulated_chars": chars_count},
                )
                await asyncio.sleep(duration)
        except Exception:
            await asyncio.sleep(duration or 0.3)

    async def get_cognitive_hesitation(
        self,
        module_name: str,
        rarity: str = "Common",
        channel_id: int | None = None,
    ) -> float:
        """
        Humans pause significantly longer when encountering rare, shiny, or legendary spawns
        to double check balls, marvel at the sprite, or check IVs.
        """
        if self.max_speed() or not self.is_anti_detection_enabled():
            return 0.0

        lowered = str(rarity or "").lower()
        is_high = any(k in lowered for k in ["shiny", "legendary", "mythical", "super rare", "ultra beasts", "event"])

        if is_high:
            hesitation = round(random.uniform(1.2, 2.8), 3)
            event_type = "high_rarity_cognitive_pause"
        elif any(k in lowered for k in ["rare", "uncommon"]):
            hesitation = round(random.uniform(0.35, 0.9), 3)
            event_type = "medium_rarity_hesitation"
        else:
            if random.random() < 0.50:
                hesitation = round(random.uniform(0.15, 0.45), 3)
                event_type = "routine_hesitation"
            else:
                return 0.0

        record_anti_detect_event(
            str(self.bot.user) if self.bot.user else "unknown",
            event_type,
            module=module_name,
            channel_id=channel_id,
            details={"rarity": rarity, "seconds": hesitation},
        )
        return hesitation

    async def maybe_take_human_break(self, module_name: str, channel_id: int) -> None:
        """
        Coordinates realistic human breaks between modules without sending suspicious chat messages.
        """
        if self.max_speed():
            return
        if not getattr(self.config, "human_breaks_enabled", True):
            return

        now = time()
        break_seconds = 0
        break_type = "none"

        if now >= self.next_long_break_at:
            min_d = max(30, int(getattr(self.config, "long_break_duration_min_seconds", 120) or 120))
            max_d = max(min_d, int(getattr(self.config, "long_break_duration_max_seconds", 300) or 300))
            break_seconds = random.randint(min_d, max_d)
            break_type = "long_break"
            self.last_break_time = now + break_seconds
            self._reschedule_breaks()
        elif now >= self.next_short_break_at:
            min_d = max(10, int(getattr(self.config, "short_break_duration_min_seconds", 30) or 30))
            max_d = max(min_d, int(getattr(self.config, "short_break_duration_max_seconds", 90) or 90))
            break_seconds = random.randint(min_d, max_d)
            break_type = "short_break"
            short_min = max(20, int(getattr(self.config, "short_break_every_min_seconds", 90) or 90))
            short_max = max(short_min, int(getattr(self.config, "short_break_every_max_seconds", 180) or 180))
            self.next_short_break_at = now + break_seconds + random.randint(short_min, short_max)

        if break_seconds > 0:
            print(f"[{module_name.capitalize()}] Enhanced anti-detection break ({break_type}): {break_seconds}s")
            record_anti_detect_event(
                str(self.bot.user) if self.bot.user else "unknown",
                break_type,
                module=module_name,
                channel_id=channel_id,
                details={"seconds": break_seconds, "fatigue_reset": break_type == "long_break"},
            )
            await asyncio.sleep(break_seconds)

    async def maybe_add_idle_randomness(self, module_name: str, channel_id: int) -> None:
        """
        Simulates casual human distraction: glancing away from screen, phone notifications, etc.
        """
        if self.max_speed():
            return
        if not getattr(self.config, "human_breaks_enabled", True):
            return

        if random.randint(1, 100) > 93:
            idle_seconds = random.randint(4, 18)
            print(f"[{module_name.capitalize()}] Casual distraction pause: {idle_seconds}s")
            record_anti_detect_event(
                str(self.bot.user) if self.bot.user else "unknown",
                "idle_randomness",
                module=module_name,
                channel_id=channel_id,
                details={"seconds": idle_seconds, "reason": "casual_distraction"},
            )
            await asyncio.sleep(idle_seconds)

    def should_skip_cycle(self, module_name: str, channel_id: int | None = None) -> bool:
        """
        ~3% chance to skip an action cycle (human looked away or got a notification).
        """
        if self.max_speed():
            return False
        if not self.is_anti_detection_enabled():
            return False

        if random.randint(1, 100) > 97:
            skip_seconds = random.randint(3, 8)
            record_anti_detect_event(
                str(self.bot.user) if self.bot.user else "unknown",
                "cycle_skipped_distraction",
                module=module_name,
                channel_id=channel_id,
                details={"skip_seconds": skip_seconds},
            )
            return True
        return False