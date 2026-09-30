from __future__ import annotations

import json
import logging
import math
import random
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("pokegrinder.worldboss_estimator")

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_FILE = DATA_DIR / "worldboss_history.json"

DEFAULT_INTERVAL_SECONDS = 7200.0  # 2 hours baseline
MIN_PROBE_COOLDOWN_SECONDS = 45.0  # 45s hard floor when votes are imminent
VIGILANCE_INTERVAL_SECONDS = 600.0  # 10 minutes between probes in vigilance stage
OVERDUE_INTERVAL_SECONDS = 900.0  # 15 minutes between probes when overdue
BASELINE_INTERVAL_SECONDS = 1800.0  # 30 minutes when no historical data is known

_history_lock = threading.RLock()

# Extended regexes for PokéMeow ;wb embed responses
_SPAWN_REQUIREMENT_PATTERN = re.compile(
    r"(?:spawn requirement|votes?)\s*:\s*(\d[\d,]*)\s*/\s*(\d[\d,]*)\s*;?votes?",
    re.IGNORECASE,
)
_ETERNA_MAX_PATTERN = re.compile(
    r"eternamax(?:-eternatus)?\s+spawn\s*:\s*(\d[\d,]*)\s*/\s*(\d[\d,]*)\s*;?votes?",
    re.IGNORECASE,
)
_LAST_DEFEATED_PATTERN = re.compile(
    r"last defeated\s+(?:approx\.?\s*)?(?:(\d+)\s*h(?:ours?|rs?)?)?\s*(?:(?:and\s*)?(\d+)\s*m(?:inutes?|ins?)?)?\s*(?:(?:and\s*)?(\d+)\s*(?:seconds?|secs?))?\s*ago",
    re.IGNORECASE,
)
_LAST_DEFEATED_SIMPLE_PATTERN = re.compile(
    r"last defeated\s+(\d+)\s*(minutes?|mins?|hours?|hrs?|seconds?|secs?)\s+ago",
    re.IGNORECASE,
)
_FUTURE_COUNTDOWN_PATTERN = re.compile(
    r"(?:next\s+)?(?:world\s*boss|battle)\s+(?:in|starts(?:\s+in)?|begins(?:\s+in)?|appears(?:\s+in)?)\s*:?\s*(?:approx\.?\s*)?(?:(\d+)\s*h(?:ours?)?)?\s*(?:(?:and\s*)?(\d+)\s*m(?:inutes?|ins?)?)?\s*(?:(?:and\s*)?(\d+)\s*s(?:econds?|ecs?)?)?",
    re.IGNORECASE,
)


def parse_vote_progress(message_blob: str) -> Optional[Tuple[int, int]]:
    """Extract current and target votes from 'Spawn requirement: 232 / 250 ;votes'."""
    match = _SPAWN_REQUIREMENT_PATTERN.search(message_blob)
    if not match:
        return None
    try:
        curr = int(match.group(1).replace(",", "").strip())
        target = int(match.group(2).replace(",", "").strip())
        return curr, target
    except Exception:
        return None


def parse_eternamax_progress(message_blob: str) -> Optional[Tuple[int, int]]:
    """Extract Eternamax-Eternatus votes from 'Eternamax-Eternatus spawn: 6,795 / 10,000 ;votes'."""
    match = _ETERNA_MAX_PATTERN.search(message_blob)
    if not match:
        return None
    try:
        curr = int(match.group(1).replace(",", "").strip())
        target = int(match.group(2).replace(",", "").strip())
        return curr, target
    except Exception:
        return None


def parse_last_defeated_seconds(message_blob: str) -> Optional[int]:
    """Extract elapsed seconds from 'A World Boss was last defeated 37 minutes ago'."""
    match = _LAST_DEFEATED_PATTERN.search(message_blob)
    if match and any(match.groups()):
        try:
            h = int(match.group(1)) if match.group(1) else 0
            m = int(match.group(2)) if match.group(2) else 0
            s = int(match.group(3)) if match.group(3) else 0
            total = h * 3600 + m * 60 + s
            if total > 0:
                return total
        except Exception:
            pass

    simple_match = _LAST_DEFEATED_SIMPLE_PATTERN.search(message_blob)
    if simple_match:
        try:
            val = int(simple_match.group(1).strip())
            unit = simple_match.group(2).lower()
            if "h" in unit:
                return val * 3600
            if "m" in unit:
                return val * 60
            return val
        except Exception:
            return None
    return None


def parse_future_boss_seconds(message_blob: str) -> Optional[int]:
    """Extract explicit future countdown (hours, minutes, seconds) until next World Boss."""
    lowered = message_blob.lower()
    if "registration is open" in lowered or "registered for this fight" in lowered:
        return None

    match = _FUTURE_COUNTDOWN_PATTERN.search(lowered)
    if not match:
        return None

    hours_str, mins_str, secs_str = match.groups()
    if not any((hours_str, mins_str, secs_str)):
        return None

    hours = int(hours_str) if hours_str else 0
    mins = int(mins_str) if mins_str else 0
    secs = int(secs_str) if secs_str else 0

    total = hours * 3600 + mins * 60 + secs
    return total if total > 300 else None


class WorldBossEstimator:
    """Intelligent adaptive estimator and probe scheduler for PokéMeow World Bosses.

    Analyzes community vote progress (e.g. 232/250 votes), vote accumulation velocity,
    time elapsed since last boss defeat, and historical intervals to dynamically
    pace ;wb maintenance probes with pinpoint accuracy.
    """

    def __init__(self, history_file: Path | None = None) -> None:
        self.history_file = history_file or HISTORY_FILE
        self.events: List[Dict[str, Any]] = []
        self.spawn_timestamps: List[float] = []
        self.learned_interval: float = DEFAULT_INTERVAL_SECONDS
        self.last_spawn_time: float = 0.0
        self.last_finish_time: float = 0.0
        self.explicit_target_time: float = 0.0
        self.last_probe_time: float = 0.0
        self.current_stage: str = "Discovering"
        self._jitter: float = random.uniform(-10.0, 10.0)

        # Vote tracking telemetry
        self.current_votes: int = 0
        self.target_votes: int = 250
        self.eternamax_votes: Tuple[int, int] = (0, 10000)
        self.last_vote_update_time: float = 0.0
        self.vote_samples: List[Tuple[float, int]] = []  # [(timestamp, current_votes)]
        self.vote_velocity_per_min: float = 4.0  # default assumption ~4 votes/min

        self._load_history()

    def _load_history(self) -> None:
        with _history_lock:
            if not self.history_file.exists():
                return
            try:
                data = json.loads(self.history_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self.events = data.get("events", [])[-50:]
                    self.spawn_timestamps = data.get("spawn_timestamps", [])[-30:]
                    self.last_spawn_time = float(data.get("last_spawn_time", 0.0) or 0.0)
                    self.last_finish_time = float(data.get("last_finish_time", 0.0) or 0.0)
                    self.explicit_target_time = float(data.get("explicit_target_time", 0.0) or 0.0)
                    self.last_probe_time = float(data.get("last_probe_time", 0.0) or 0.0)
                    self.current_votes = int(data.get("current_votes", 0) or 0)
                    self.target_votes = int(data.get("target_votes", 250) or 250)
                    raw_et = data.get("eternamax_votes", [0, 10000])
                    if isinstance(raw_et, (list, tuple)) and len(raw_et) == 2:
                        self.eternamax_votes = (int(raw_et[0] or 0), int(raw_et[1] or 10000))
                    self.vote_velocity_per_min = float(data.get("vote_velocity_per_min", 4.0) or 4.0)
                    self._recalculate_interval()
            except Exception as exc:
                logger.warning("Could not read WorldBoss history: %s", exc)

    def _save_history(self) -> None:
        with _history_lock:
            payload = {
                "events": self.events[-50:],
                "spawn_timestamps": self.spawn_timestamps[-30:],
                "learned_interval_seconds": self.learned_interval,
                "last_spawn_time": self.last_spawn_time,
                "last_finish_time": self.last_finish_time,
                "explicit_target_time": self.explicit_target_time,
                "last_probe_time": self.last_probe_time,
                "current_votes": self.current_votes,
                "target_votes": self.target_votes,
                "eternamax_votes": list(self.eternamax_votes),
                "vote_velocity_per_min": self.vote_velocity_per_min,
                "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            try:
                self.history_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            except Exception as exc:
                logger.warning("Could not save WorldBoss history: %s", exc)

    def _recalculate_interval(self) -> None:
        """Calculate weighted rolling average of observed time differences."""
        if len(self.spawn_timestamps) < 2:
            self.learned_interval = DEFAULT_INTERVAL_SECONDS
            return

        intervals = []
        for i in range(1, len(self.spawn_timestamps)):
            diff = self.spawn_timestamps[i] - self.spawn_timestamps[i - 1]
            if 1800.0 <= diff <= 43200.0:
                intervals.append(diff)

        if not intervals:
            self.learned_interval = DEFAULT_INTERVAL_SECONDS
            return

        weights = [1.0 + (i * 0.25) for i in range(len(intervals))]
        weighted_sum = sum(val * w for val, w in zip(intervals, weights))
        total_weight = sum(weights)
        self.learned_interval = round(weighted_sum / total_weight, 1)

    def record_vote_status(
        self,
        current_votes: int,
        target_votes: int,
        eternamax_data: Optional[Tuple[int, int]] = None,
    ) -> None:
        """Process updated vote count from PokéMeow ;wb response."""
        now = time.time()
        self.current_votes = current_votes
        self.target_votes = target_votes or 250
        if eternamax_data is not None:
            self.eternamax_votes = eternamax_data
        self.last_vote_update_time = now

        # Add sample and keep samples within last 20 minutes
        self.vote_samples.append((now, current_votes))
        cutoff = now - 1200.0
        self.vote_samples = [(ts, v) for ts, v in self.vote_samples if ts >= cutoff][-8:]

        # Calculate empirical vote velocity (votes/minute)
        if len(self.vote_samples) >= 2:
            first_ts, first_v = self.vote_samples[0]
            last_ts, last_v = self.vote_samples[-1]
            delta_mins = (last_ts - first_ts) / 60.0
            delta_votes = last_v - first_v

            # Handle counter reset when boss spawns
            if delta_votes >= 0 and delta_mins >= 0.5:
                rate = delta_votes / delta_mins
                if 0.2 <= rate <= 25.0:
                    self.vote_velocity_per_min = round(rate, 2)

        self._save_history()
        logger.info(
            "WorldBoss vote status: %d/%d (%d needed). Velocity: %.1f v/min. ETA: ~%.1f mins",
            current_votes,
            target_votes,
            max(0, target_votes - current_votes),
            self.vote_velocity_per_min,
            self.get_estimated_minutes_to_spawn(),
        )

    def record_last_defeated(self, seconds_ago: int) -> None:
        """Calibrate last boss defeat time directly from PokéMeow embed."""
        now = time.time()
        calculated_finish = now - float(seconds_ago)
        if not self.last_finish_time or abs(calculated_finish - self.last_finish_time) > 120.0:
            self.last_finish_time = calculated_finish
            self._save_history()

    def record_spawn(self, boss_name: str, countdown_seconds: Optional[int] = None) -> None:
        """Record a newly discovered World Boss spawn/registration event."""
        now = time.time()
        if self.last_spawn_time and (now - self.last_spawn_time) < 300.0:
            return

        spawn_time = now
        self.last_spawn_time = spawn_time
        self.explicit_target_time = 0.0
        self.current_votes = 0  # Counter resets upon spawn
        self.vote_samples.clear()
        self.spawn_timestamps.append(spawn_time)
        self._recalculate_interval()

        self.events.append({
            "timestamp": spawn_time,
            "type": "spawn",
            "boss_name": boss_name or "Unknown",
            "countdown_seconds": countdown_seconds,
            "iso": datetime.now(timezone.utc).isoformat(),
        })
        self._jitter = random.uniform(-10.0, 10.0)
        self._save_history()
        logger.info("Recorded WorldBoss spawn '%s'. Updated learned interval: %.1f mins", boss_name, self.learned_interval / 60.0)

    def record_completion(self, boss_name: str, outcome: str) -> None:
        """Record when a World Boss battle finishes (win or loss)."""
        now = time.time()
        self.last_finish_time = now
        self.events.append({
            "timestamp": now,
            "type": "completion",
            "boss_name": boss_name or "Unknown",
            "outcome": outcome,
            "iso": datetime.now(timezone.utc).isoformat(),
        })
        self._jitter = random.uniform(-10.0, 10.0)
        self._save_history()

    def record_explicit_countdown(self, seconds_until_next: int) -> None:
        """Record explicit future spawn timer announced by PokéMeow."""
        now = time.time()
        self.explicit_target_time = now + float(seconds_until_next)
        self.events.append({
            "timestamp": now,
            "type": "explicit_countdown",
            "seconds_until_next": seconds_until_next,
            "target_iso": datetime.fromtimestamp(self.explicit_target_time, tz=timezone.utc).isoformat(),
        })
        self._save_history()

    def record_probe(self, probe_time: float | None = None) -> None:
        """Record that a ;wb maintenance probe was executed."""
        self.last_probe_time = probe_time or time.time()
        self._jitter = random.uniform(-10.0, 10.0)
        self._save_history()

    def get_estimated_minutes_to_spawn(self) -> float:
        """Calculate estimated minutes until next World Boss spawn."""
        # 1. Based on explicit timer
        now = time.time()
        if self.explicit_target_time > now:
            return round((self.explicit_target_time - now) / 60.0, 1)

        # 2. Based on community vote progress
        if self.target_votes > 0 and self.current_votes > 0:
            remaining = max(0, self.target_votes - self.current_votes)
            if remaining == 0:
                return 0.0
            vel = max(0.5, self.vote_velocity_per_min)
            return round(remaining / vel, 1)

        # 3. Fallback to historical time difference
        if self.last_spawn_time > 0:
            elapsed = now - self.last_spawn_time
            rem_sec = max(0.0, self.learned_interval - elapsed)
            return round(rem_sec / 60.0, 1)

        return 30.0

    def should_probe(self, now: float | None = None) -> Tuple[bool, str]:
        """Determine whether the bot should send a ;wb maintenance probe right now."""
        now = now or time.time()

        # Threshold already met or exceeded: probe/sign in immediately!
        if self.target_votes > 0 and self.current_votes >= self.target_votes:
            self.current_stage = f"Threshold Met ({self.current_votes}/{self.target_votes})"
            if not self.last_probe_time or (now - self.last_probe_time) >= 20.0:
                return True, f"Vote threshold reached ({self.current_votes}/{self.target_votes}) - sign in now!"
            return False, "Awaiting threshold spawn cycle"

        votes_needed = max(0, self.target_votes - self.current_votes) if self.current_votes > 0 else 999

        # Hard rate-limit floor
        min_cooldown = MIN_PROBE_COOLDOWN_SECONDS
        if self.current_votes == 0 and self.last_spawn_time == 0.0:
            min_cooldown = 35.0
        elif votes_needed <= 12:
            min_cooldown = 25.0
        elif votes_needed > 25:
            min_cooldown = 90.0

        if self.last_probe_time and (now - self.last_probe_time) < min_cooldown:
            rem = int(min_cooldown - (now - self.last_probe_time))
            return False, f"Rate-limit cooldown ({rem}s remaining)"

        # Priority 1: Explicit target countdown set by PokéMeow
        if self.explicit_target_time > 0:
            if now >= (self.explicit_target_time - 45.0):
                self.current_stage = "Explicit Target Reached"
                return True, "Explicit target timer reached"
            rem = int(self.explicit_target_time - now)
            self.current_stage = f"Awaiting Target ({rem // 60}m {rem % 60}s)"
            return False, f"Awaiting explicit target ({rem}s remaining)"

        # Priority 2: Community Vote Pacing (Most Accurate Metric)
        if self.current_votes > 0 and self.target_votes > 0:
            # Imminent: within 12 votes of spawning (spawn in ~1-2 mins)
            if votes_needed <= 12:
                self.current_stage = f"Imminent ({self.current_votes}/{self.target_votes})"
                effective_interval = 30.0 + self._jitter
                if (now - self.last_probe_time) >= effective_interval:
                    return True, f"Imminent spawn probe ({votes_needed} votes left)"
                return False, f"Imminent pacing ({int(effective_interval - (now - self.last_probe_time))}s left)"

            # Approaching: within 35 votes of spawning (spawn in ~3-5 mins)
            if votes_needed <= 35:
                self.current_stage = f"Approaching ({self.current_votes}/{self.target_votes})"
                effective_interval = 75.0 + self._jitter  # ~1.2 mins
                if (now - self.last_probe_time) >= effective_interval:
                    return True, f"Approaching spawn probe ({votes_needed} votes left)"
                return False, f"Approaching pacing ({int(effective_interval - (now - self.last_probe_time))}s left)"

            # Mid-Progress: within 75 votes of spawning (spawn in ~10-15 mins)
            if votes_needed <= 75:
                self.current_stage = f"Mid-Progress ({self.current_votes}/{self.target_votes})"
                effective_interval = 180.0 + self._jitter  # ~3 mins
                if (now - self.last_probe_time) >= effective_interval:
                    return True, f"Mid-progress probe ({votes_needed} votes left)"
                return False, f"Mid-progress pacing ({int(effective_interval - (now - self.last_probe_time))}s left)"

            # Early Stage: more than 75 votes needed
            self.current_stage = f"Early Accumulation ({self.current_votes}/{self.target_votes})"
            effective_interval = 360.0 + self._jitter  # ~6 mins
            if (now - self.last_probe_time) >= effective_interval:
                return True, f"Early accumulation check ({votes_needed} votes left)"
            return False, f"Early pacing ({int(effective_interval - (now - self.last_probe_time))}s left)"

        # Priority 3: Historical Spawn Interval Calculation
        if self.last_spawn_time > 0:
            elapsed = now - self.last_spawn_time
            interval = self.learned_interval
            cooldown_period = interval * 0.50

            # Post-Fight Cooldown
            if elapsed < cooldown_period:
                rem_cooldown = int(cooldown_period - elapsed)
                self.current_stage = f"Cooldown ({rem_cooldown // 60}m)"
                return False, f"Post-boss cooldown ({rem_cooldown // 60}m remaining)"

            # Vigilance Window
            self.current_stage = "Approaching Vigilance"
            effective_interval = VIGILANCE_INTERVAL_SECONDS + self._jitter
            if (now - self.last_probe_time) >= effective_interval:
                return True, "Vigilance window probe"
            rem_vig = int(effective_interval - (now - self.last_probe_time))
            return False, f"Vigilance pacing ({rem_vig}s remaining)"

        # Priority 4: No history yet — rapid initial discovery probe (every 45s until calibrated)
        self.current_stage = "Initial Discovery"
        effective_interval = 45.0 + self._jitter
        if not self.last_probe_time or (now - self.last_probe_time) >= effective_interval:
            return True, "Initial discovery probe"
        rem_base = int(effective_interval - (now - self.last_probe_time))
        return False, f"Discovery pacing ({rem_base}s remaining)"

    def get_status_summary(self, now: float | None = None) -> str:
        """Generate human-readable status text for Discord commands and logging."""
        now = now or time.time()
        eta_mins = self.get_estimated_minutes_to_spawn()

        if self.current_votes > 0:
            votes_needed = max(0, self.target_votes - self.current_votes)
            votes_part = f"Votes: {self.current_votes}/{self.target_votes} ({votes_needed} left, {self.vote_velocity_per_min} v/m)"
        else:
            votes_part = "Votes: checking..."

        if self.last_finish_time > 0:
            elapsed_m = int((now - self.last_finish_time) // 60)
            last_boss_part = f"Last Defeated: {elapsed_m}m ago"
        else:
            last_boss_part = "Last Defeated: unknown"

        if self.learned_interval > 0:
            interval_part = f"Interval: ~{self.learned_interval / 60.0:.0f}m"
        else:
            interval_part = "Interval: default"

        if getattr(self, "eternamax_votes", None) and self.eternamax_votes[0] > 0:
            et_part = f" | Eternamax: {self.eternamax_votes[0]}/{self.eternamax_votes[1]}"
        else:
            et_part = ""

        return f"Stage: {self.current_stage} | ETA: ~{eta_mins:.1f}m | {votes_part}{et_part} | {last_boss_part} | {interval_part}"

