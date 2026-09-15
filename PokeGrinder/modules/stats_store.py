import json
import hashlib
from time import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

BASE_DIR = Path(__file__).resolve().parents[1]
STATS_PATH = BASE_DIR / "stats.json"
DAY_MODE_RESET_HOUR = 12


def get_stats_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:32]


def current_day_mode_anchor(now: datetime | None = None) -> datetime:
    local_now = now or datetime.now()
    anchor = local_now.replace(hour=DAY_MODE_RESET_HOUR, minute=0, second=0, microsecond=0)
    if local_now < anchor:
        anchor = anchor - timedelta(days=1)
    return anchor


def current_day_mode_anchor_str(now: datetime | None = None) -> str:
    return current_day_mode_anchor(now).isoformat(timespec="seconds")


def _reset_day_stats(payload: Dict[str, Any], anchor: str | None = None) -> None:
    payload["day_mode_anchor_local"] = str(anchor or current_day_mode_anchor_str())
    payload["day_encounters"] = 0
    payload["day_catches"] = 0
    payload["day_fish_encounters"] = 0
    payload["day_fish_catches"] = 0
    payload["day_coins_earned"] = 0
    payload["day_hunt_rarity_catches"] = {}
    payload["day_fish_rarity_catches"] = {}


def default_stats() -> Dict[str, Any]:
    return {
        "day_mode_anchor_local": current_day_mode_anchor_str(),
        "day_encounters": 0,
        "day_catches": 0,
        "day_fish_encounters": 0,
        "day_fish_catches": 0,
        "day_coins_earned": 0,
        "day_hunt_rarity_catches": {},
        "day_fish_rarity_catches": {},
        "lifetime_encounters": 0,
        "lifetime_catches": 0,
        "lifetime_fish_encounters": 0,
        "lifetime_fish_catches": 0,
        "lifetime_coins_earned": 0,
        "lifetime_hunt_rarity_catches": {},
        "lifetime_fish_rarity_catches": {},
    }


def read_all_stats() -> Dict[str, Any]:
    if not STATS_PATH.exists():
        return {}

    try:
        return json.loads(STATS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_all_stats(payload: Dict[str, Any]) -> bool:
    serialized = json.dumps(payload, indent=2)
    temp_path = STATS_PATH.with_suffix(STATS_PATH.suffix + ".tmp")
    try:
        temp_path.write_text(serialized, encoding="utf-8")
        temp_path.replace(STATS_PATH)
        return True
    except Exception:
        # Fallback to direct write if atomic replace is unavailable.
        try:
            STATS_PATH.write_text(serialized, encoding="utf-8")
            return True
        except Exception:
            return False


def load_stats_for_key(stats_key: str) -> Dict[str, Any]:
    saved = read_all_stats().get(stats_key, {})
    merged = default_stats()

    # Backward compatibility with previous schema where totals were saved as session keys.
    if "lifetime_encounters" not in saved:
        saved["lifetime_encounters"] = int(saved.get("encounters", 0))

    if "lifetime_catches" not in saved:
        saved["lifetime_catches"] = int(saved.get("catches", 0))

    if "lifetime_fish_encounters" not in saved:
        saved["lifetime_fish_encounters"] = int(saved.get("fish_encounters", 0))

    if "lifetime_fish_catches" not in saved:
        saved["lifetime_fish_catches"] = int(saved.get("fish_catches", 0))

    if "lifetime_coins_earned" not in saved:
        saved["lifetime_coins_earned"] = int(saved.get("coins_earned", 0))

    if "lifetime_hunt_rarity_catches" not in saved:
        saved["lifetime_hunt_rarity_catches"] = dict(saved.get("hunt_rarity_catches", {}))

    if "lifetime_fish_rarity_catches" not in saved:
        saved["lifetime_fish_rarity_catches"] = dict(saved.get("fish_rarity_catches", {}))

    # Day-mode migration and compatibility for old schema.
    if "day_encounters" not in saved:
        saved["day_encounters"] = int(saved.get("encounters", 0))

    if "day_catches" not in saved:
        saved["day_catches"] = int(saved.get("catches", 0))

    if "day_fish_encounters" not in saved:
        saved["day_fish_encounters"] = int(saved.get("fish_encounters", 0))

    if "day_fish_catches" not in saved:
        saved["day_fish_catches"] = int(saved.get("fish_catches", 0))

    if "day_coins_earned" not in saved:
        saved["day_coins_earned"] = int(saved.get("coins_earned", 0))

    if "day_hunt_rarity_catches" not in saved:
        saved["day_hunt_rarity_catches"] = dict(saved.get("hunt_rarity_catches", {}))

    if "day_fish_rarity_catches" not in saved:
        saved["day_fish_rarity_catches"] = dict(saved.get("fish_rarity_catches", {}))

    if "day_mode_anchor_local" not in saved:
        saved["day_mode_anchor_local"] = current_day_mode_anchor_str()

    for key, value in saved.items():
        if key in merged:
            merged[key] = value

    if not isinstance(merged.get("lifetime_hunt_rarity_catches"), dict):
        merged["lifetime_hunt_rarity_catches"] = {}

    if not isinstance(merged.get("lifetime_fish_rarity_catches"), dict):
        merged["lifetime_fish_rarity_catches"] = {}

    if not isinstance(merged.get("day_hunt_rarity_catches"), dict):
        merged["day_hunt_rarity_catches"] = {}

    if not isinstance(merged.get("day_fish_rarity_catches"), dict):
        merged["day_fish_rarity_catches"] = {}

    if str(merged.get("day_mode_anchor_local", "")) != current_day_mode_anchor_str():
        _reset_day_stats(merged)

    return merged


def ensure_day_mode_window(bot: Any, persist_on_reset: bool = True) -> bool:
    desired_anchor = current_day_mode_anchor_str()
    current_anchor = str(getattr(bot, "day_mode_anchor_local", "") or "").strip()
    if current_anchor == desired_anchor:
        return False

    bot.day_mode_anchor_local = desired_anchor
    bot.encounters = 0
    bot.catches = 0
    bot.fish_encounters = 0
    bot.fish_catches = 0
    bot.coins_earned = 0
    bot.hunt_rarity_catches = {}
    bot.fish_rarity_catches = {}

    if persist_on_reset:
        persist_bot_stats(bot, force=True, min_interval_seconds=0.0)

    return True


def persist_bot_stats(bot: Any, force: bool = False, min_interval_seconds: float = 2.0) -> None:
    ensure_day_mode_window(bot, persist_on_reset=False)
    now = time()
    last_saved = getattr(bot, "last_stats_save", 0.0)

    if not force and now - last_saved < min_interval_seconds:
        return

    stats_key = getattr(bot, "stats_key", "")
    if not stats_key:
        return

    payload = read_all_stats()
    payload[stats_key] = {
        "day_mode_anchor_local": str(getattr(bot, "day_mode_anchor_local", current_day_mode_anchor_str())),
        "day_encounters": int(getattr(bot, "encounters", 0)),
        "day_catches": int(getattr(bot, "catches", 0)),
        "day_fish_encounters": int(getattr(bot, "fish_encounters", 0)),
        "day_fish_catches": int(getattr(bot, "fish_catches", 0)),
        "day_coins_earned": int(getattr(bot, "coins_earned", 0)),
        "day_hunt_rarity_catches": dict(getattr(bot, "hunt_rarity_catches", {})),
        "day_fish_rarity_catches": dict(getattr(bot, "fish_rarity_catches", {})),
        "lifetime_encounters": int(getattr(bot, "lifetime_encounters", 0)),
        "lifetime_catches": int(getattr(bot, "lifetime_catches", 0)),
        "lifetime_fish_encounters": int(getattr(bot, "lifetime_fish_encounters", 0)),
        "lifetime_fish_catches": int(getattr(bot, "lifetime_fish_catches", 0)),
        "lifetime_coins_earned": int(getattr(bot, "lifetime_coins_earned", 0)),
        "lifetime_hunt_rarity_catches": dict(getattr(bot, "lifetime_hunt_rarity_catches", {})),
        "lifetime_fish_rarity_catches": dict(getattr(bot, "lifetime_fish_rarity_catches", {})),
    }

    if write_all_stats(payload):
        bot.last_stats_save = now
