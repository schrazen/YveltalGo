"""
Shared break coordinator for Hunting and Fishing cogs.
Ensures both pause simultaneously for human breaks since they operate in the same channel.
"""
import asyncio
from time import time
from random import randint


class BreakCoordinator:
    """
    Coordinates human breaks between Hunting and Fishing cogs.
    Both cogs reference the same coordinator so they pause together.
    """
    
    def __init__(self, config):
        self.config = config
        self.next_short_break_at = time() + randint(
            max(10, getattr(config, "short_break_every_min_seconds", 90) or 90),
            max(max(10, getattr(config, "short_break_every_min_seconds", 90) or 90),
                getattr(config, "short_break_every_max_seconds", 180) or 180),
        )
        self.next_long_break_at = time() + randint(
            max(30, getattr(config, "long_break_every_min_seconds", 300) or 300),
            max(max(30, getattr(config, "long_break_every_min_seconds", 300) or 300),
                getattr(config, "long_break_every_max_seconds", 600) or 600),
        )
        self.is_break_active = False
        self.break_start_time = None
        
    def get_break_duration(self) -> int:
        """
        Calculate if a break is needed and return the duration in seconds.
        Returns 0 if no break needed, otherwise returns break duration.
        """
        if getattr(self.config, "max_speed_mode_enabled", False):
            return 0
        if not getattr(self.config, "human_breaks_enabled", True):
            return 0
        
        now = time()
        break_seconds = 0
        
        # Long break takes priority
        if now >= self.next_long_break_at:
            min_d = max(10, getattr(self.config, "long_break_duration_min_seconds", 120) or 120)
            max_d = max(min_d, getattr(self.config, "long_break_duration_max_seconds", 300) or 300)
            break_seconds = randint(min_d, max_d)
            self.next_long_break_at = now + randint(
                max(60, getattr(self.config, "long_break_every_min_seconds", 300) or 300),
                max(max(60, getattr(self.config, "long_break_every_min_seconds", 300) or 300),
                    getattr(self.config, "long_break_every_max_seconds", 600) or 600),
            )
        elif now >= self.next_short_break_at:
            min_d = max(5, getattr(self.config, "short_break_duration_min_seconds", 30) or 30)
            max_d = max(min_d, getattr(self.config, "short_break_duration_max_seconds", 90) or 90)
            break_seconds = randint(min_d, max_d)
            self.next_short_break_at = now + randint(
                max(20, getattr(self.config, "short_break_every_min_seconds", 90) or 90),
                max(max(20, getattr(self.config, "short_break_every_min_seconds", 90) or 90),
                    getattr(self.config, "short_break_every_max_seconds", 180) or 180),
            )
        
        return break_seconds
    
    def is_break_in_progress(self) -> bool:
        """Check if a break is currently active."""
        if not self.is_break_active or self.break_start_time is None:
            return False
        # Break is over if enough time has passed
        return True
    
    def start_break(self):
        """Mark that a break is starting."""
        self.is_break_active = True
        self.break_start_time = time()
    
    def end_break(self):
        """Mark that the break is ending."""
        self.is_break_active = False
        self.break_start_time = None
