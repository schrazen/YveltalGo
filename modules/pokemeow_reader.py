from __future__ import annotations

import json
import re
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from discord import Message

from modules.file_utils import read_tail_jsonl

POKEMEOW_APP_ID = 664508672713424926

BASE_DIR = Path(__file__).resolve().parents[1]
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = LOG_DIR / "pokemeow_events.jsonl"

_MAX_EVENTS = 8000
_events: deque[dict[str, Any]] = deque(maxlen=_MAX_EVENTS)
_lock = threading.Lock()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(val: Any) -> str:
    try:
        return str(val or "")
    except Exception:
        return ""


def _sanitize_text(text: str) -> str:
    val = re.sub(r"<a?:[a-z0-9_]+:\d+>", " ", str(text or ""), flags=re.IGNORECASE)
    val = re.sub(r":[a-z0-9_]+:", " ", val, flags=re.IGNORECASE)
    val = re.sub(r"[*_`~]+", "", val)
    val = re.sub(r"\s+", " ", val)
    return val.strip()


def collect_message_text(message: Message) -> str:
    parts = [str(getattr(message, "content", "") or "")]
    for embed in getattr(message, "embeds", []) or []:
        parts.extend([
            str(getattr(embed, "title", "") or ""),
            str(getattr(embed, "description", "") or ""),
            str(getattr(getattr(embed, "author", None), "name", "") or ""),
            str(getattr(getattr(embed, "footer", None), "text", "") or ""),
        ])
        for field in getattr(embed, "fields", []) or []:
            parts.append(str(getattr(field, "name", "") or ""))
            parts.append(str(getattr(field, "value", "") or ""))
    return "\n".join(part for part in parts if part.strip())


def _extract_pokemon_name_from_haystack(haystack: str) -> str:
    patterns = [
        r"wild\s+(?:[:a-z0-9_]+\s+)?\*\*([^*]+)\*\*",
        r"wild\s+([A-Za-z0-9\-\. '\u2019]{1,40}?)\s+(?:appeared|ran away|got away|broke free|fled)",
        r"(?:the\s+)?wild\s+([A-Za-z0-9\-\. '\u2019]{1,40}?)\s+ran\s+away",
        r"(?:the\s+)?wild\s+([A-Za-z0-9\-\. '\u2019]{1,40}?)\s+got\s+away",
        r"(?:the\s+)?wild\s+([A-Za-z0-9\-\. '\u2019]{1,40}?)\s+broke\s+free",
        r"caught\s+(?:an?\s*)?(?:(?:<a?:[a-z0-9_]+:\d+>|:[a-z0-9_]+:)\s*)*\*\*([^*]+)\*\*",
        r"caught\s+(?:an?\s*)?(?:(?:<a?:[a-z0-9_]+:\d+>|:[a-z0-9_]+:)\s*)*([A-Za-z0-9\-\. '\u2019]{1,40}?)\s+with",
        r"fished\s+(?:an?\s*)?(?:(?:<a?:[a-z0-9_]+:\d+>|:[a-z0-9_]+:)\s*)*\*\*([^*]+)\*\*",
    ]
    for pat in patterns:
        m = re.search(pat, haystack, flags=re.IGNORECASE)
        if m:
            candidate = _sanitize_text(m.group(1))
            candidate = re.sub(r"^shiny\s+", "", candidate, flags=re.IGNORECASE)
            candidate = re.sub(r"^golden\s+", "", candidate, flags=re.IGNORECASE)
            if candidate and candidate.lower() not in {"you", "the", "a", "an"}:
                return candidate
    return "Unknown"


def _extract_rarity_from_haystack(haystack: str) -> str:
    lowered = haystack.lower()
    for rarity in [
        "golden",
        "shiny",
        "legendary",
        "mythical",
        "ultra beast",
        "event",
        "super rare",
        "rare",
        "uncommon",
        "common",
    ]:
        if rarity in lowered:
            return rarity.title()
    return "Unknown"


def _extract_cooldown_seconds(text: str) -> float:
    lowered = text.lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*seconds?", lowered)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            return 3.0
    if "few more seconds" in lowered or "few seconds" in lowered:
        return 4.0
    return 3.0


def _load_recent_from_disk(max_lines: int = 3000) -> None:
    _events.extend(read_tail_jsonl(LOG_PATH, max_lines=max_lines))


_load_recent_from_disk()


def parse_pokemeow_response(
    message: Message,
    before_message: Optional[Message] = None,
    context_module: str = "",
    ball_used: str = "",
) -> dict[str, Any]:
    """Inspects a Discord message from PokéMeow and classifies the event.

    Returns a structured dictionary with category, is_complication, details, and raw text preview.
    """
    haystack = collect_message_text(message)
    before_haystack = collect_message_text(before_message) if before_message else ""
    full_haystack = f"{before_haystack}\n{haystack}" if before_haystack else haystack
    lowered = haystack.lower()
    lowered_full = full_haystack.lower()

    preview = _sanitize_text(haystack)[:250]
    rarity = _extract_rarity_from_haystack(full_haystack)
    pokemon_name = _extract_pokemon_name_from_haystack(full_haystack)

    # 1. Cooldown Blocks ("Please wait")
    if "please wait" in lowered:
        wait_sec = _extract_cooldown_seconds(lowered)
        return {
            "category": "cooldown_block",
            "is_complication": True,
            "headline": f"Cooldown rate limit: wait {wait_sec}s",
            "details": {
                "module": context_module or "general",
                "wait_seconds": wait_sec,
                "preview": preview,
            },
            "raw_text": preview,
        }

    # 2. Daily Limits
    if any(m in lowered for m in [
        "daily catch limit",
        "daily encounter limit",
        "reached your daily catch limit",
        "reached the daily catch limit",
    ]):
        return {
            "category": "daily_limit",
            "is_complication": True,
            "headline": "Daily catch/encounter limit reached",
            "details": {
                "module": context_module or "hunting",
                "preview": preview,
            },
            "raw_text": preview,
        }

    # 3. Ball Starvation (Out of Pokeballs)
    if any(m in lowered for m in [
        "don't have enough pokeballs",
        "do not have enough pokeballs",
        "you don't have enough",
        "not enough pokeballs",
        "ran out of",
        "don't have any pokeball",
        "you do not have any",
    ]) and any(w in lowered for w in ["ball", "pokeball", "greatball", "ultraball", "masterball"]):
        return {
            "category": "ball_starvation",
            "is_complication": True,
            "headline": "Inventory empty: out of balls for encounter",
            "details": {
                "module": context_module or "hunting",
                "pokemon_name": pokemon_name,
                "rarity": rarity,
                "ball_attempted": ball_used,
                "preview": preview,
            },
            "raw_text": preview,
        }

    # 4. Coin Starvation (Insufficient Pokécoins during Auto-Buy / Shop)
    if any(m in lowered for m in [
        "not enough pokécoin",
        "not enough pokecoin",
        "don't have enough pokécoin",
        "don't have enough pokecoin",
        "do not have enough pokécoin",
        "do not have enough pokecoin",
        "need :coin:",
        "need more pokécoins",
        "need more pokecoins",
        "transaction failed",
    ]):
        return {
            "category": "coin_starvation",
            "is_complication": True,
            "headline": "Insufficient Pokécoins: auto-buy or shop purchase failed",
            "details": {
                "module": context_module or "shop",
                "preview": preview,
            },
            "raw_text": preview,
        }

    # 5. Captcha Prompt
    if any(m in lowered for m in [
        "captcha",
        "a wild captcha appeared",
        "you must type your answer",
    ]):
        return {
            "category": "captcha_prompt",
            "is_complication": True,
            "headline": "PokéMeow Captcha Verification Triggered",
            "details": {
                "module": context_module or "captcha",
                "preview": preview,
            },
            "raw_text": preview,
        }

    # 6. Missing Fishing Rod
    if context_module == "fishing" and any(m in lowered for m in [
        "rod",
        "don't have a rod",
        "do not have a rod",
        "need a fishing rod",
        "no fishing rod",
    ]):
        return {
            "category": "missing_rod",
            "is_complication": True,
            "headline": "Fishing failed: account has no fishing rod",
            "details": {
                "module": "fishing",
                "preview": preview,
            },
            "raw_text": preview,
        }

    # 7. Hunt Flee / Escape (Crucial complication previously dropped!)
    if any(m in lowered for m in [
        "ran away",
        "got away",
        "broke free and ran away",
        "broke free and fled",
        "fled",
    ]):
        is_fishing = (context_module == "fishing") or ("fish" in lowered_full and "cast" in lowered_full)
        category = "fish_flee" if is_fishing else "hunt_flee"
        headline = (
            f"Fish escaped ({rarity})"
            if is_fishing
            else f"Wild {pokemon_name} ({rarity}) ran away!"
        )
        return {
            "category": category,
            "is_complication": True,
            "headline": headline,
            "details": {
                "module": "fishing" if is_fishing else "hunting",
                "pokemon_name": pokemon_name,
                "rarity": rarity,
                "ball_used": ball_used,
                "preview": preview,
            },
            "raw_text": preview,
        }

    # Fishing: "not even a nibble"
    if "not even a nibble" in lowered:
        return {
            "category": "fish_nibble_miss",
            "is_complication": True,
            "headline": "Fishing cast missed: not even a nibble",
            "details": {
                "module": "fishing",
                "preview": preview,
            },
            "raw_text": preview,
        }

    # 8. Hunt / Fish Catch Success
    if "caught" in lowered:
        is_fishing = (context_module == "fishing") or ("fished" in lowered_full)
        category = "fish_catch" if is_fishing else "hunt_catch"
        is_rare = any(r in rarity.lower() for r in ["shiny", "golden", "legendary", "mythical", "ultra", "event"])
        headline = f"Caught {pokemon_name} ({rarity})"
        return {
            "category": category,
            "is_complication": False,
            "headline": headline,
            "details": {
                "module": "fishing" if is_fishing else "hunting",
                "pokemon_name": pokemon_name,
                "rarity": rarity,
                "is_rare": is_rare,
                "ball_used": ball_used,
                "preview": preview,
            },
            "raw_text": preview,
        }

    # 9. Quest Events
    if "your next quest is now ready" in lowered:
        return {
            "category": "quest_ready",
            "is_complication": False,
            "headline": "Your next Quest is now ready!",
            "details": {
                "module": "quest",
                "preview": preview,
            },
            "raw_text": preview,
        }
    if any(m in lowered for m in ["quest complete", "completed a quest", "quest completed"]):
        return {
            "category": "quest_complete",
            "is_complication": False,
            "headline": "Quest Complete!",
            "details": {
                "module": "quest",
                "preview": preview,
            },
            "raw_text": preview,
        }

    # 10. Egg Hatch / Incubation Events
    if any(m in lowered for m in [
        "hatched from the egg",
        "your egg is ready to hatch",
        "egg hatched into",
        "an egg has been incubated",
    ]):
        return {
            "category": "egg_event",
            "is_complication": False,
            "headline": "Egg Hatch / Incubation Event",
            "details": {
                "module": "egg",
                "pokemon_name": pokemon_name,
                "preview": preview,
            },
            "raw_text": preview,
        }

    # 11. Retrieved Held Item
    if any(m in lowered for m in ["retrieved a held item", "you retrieved", "holding a"]):
        return {
            "category": "item_retrieved",
            "is_complication": False,
            "headline": "Retrieved held item from encounter",
            "details": {
                "module": context_module or "hunting",
                "pokemon_name": pokemon_name,
                "rarity": rarity,
                "preview": preview,
            },
            "raw_text": preview,
        }

    # 12. Shop Buy Success
    if any(m in lowered for m in ["you bought", "successful purchase"]):
        return {
            "category": "shop_success",
            "is_complication": False,
            "headline": "Auto-buy purchase succeeded",
            "details": {
                "module": "shop",
                "preview": preview,
            },
            "raw_text": preview,
        }

    # 13. Encounter appeared
    if "found a wild" in lowered or "wild" in lowered and "appeared" in lowered:
        is_rare = any(r in rarity.lower() for r in ["shiny", "golden", "legendary", "mythical", "ultra", "event"])
        return {
            "category": "hunt_encounter",
            "is_complication": False,
            "headline": f"Wild {pokemon_name} ({rarity}) appeared",
            "details": {
                "module": "hunting",
                "pokemon_name": pokemon_name,
                "rarity": rarity,
                "is_rare": is_rare,
                "preview": preview,
            },
            "raw_text": preview,
        }

    # 14. Unhandled Response (Flagged so we can diagnose new or unhandled PokéMeow behaviors)
    return {
        "category": "unhandled_response",
        "is_complication": False,  # Not necessarily an error, but worth tracking
        "headline": f"Unhandled PokéMeow response: {preview[:60]}...",
        "details": {
            "module": context_module or "general",
            "preview": preview,
        },
        "raw_text": preview,
    }


def record_pokemeow_event(
    account: str,
    category: str,
    headline: str,
    *,
    is_complication: bool,
    module: str = "general",
    channel_id: int = 0,
    details: Optional[dict[str, Any]] = None,
    raw_text: str = "",
) -> dict[str, Any]:
    """Records a classified PokéMeow interaction response to memory and logs/pokemeow_events.jsonl."""
    payload: dict[str, Any] = {
        "ts": _utc_now_iso(),
        "account": _safe_str(account),
        "module": _safe_str(module),
        "channel_id": int(channel_id or 0),
        "category": _safe_str(category),
        "is_complication": bool(is_complication),
        "headline": _safe_str(headline),
        "details": details or {},
        "raw_text": _safe_str(raw_text)[:300],
    }

    with _lock:
        _events.append(payload)

    try:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass

    return payload


def get_recent_pokemeow_events(
    limit: int = 200,
    category: Optional[str] = None,
    complications_only: bool = False,
) -> list[dict[str, Any]]:
    """Retrieves recent PokéMeow events in reverse chronological order."""
    with _lock:
        items = list(_events)

    filtered = items
    if complications_only:
        filtered = [x for x in filtered if x.get("is_complication")]
    if category:
        filtered = [x for x in filtered if str(x.get("category", "")).lower() == category.lower()]

    limit = max(1, min(int(limit), 5000))
    return filtered[-limit:][::-1]


_dedup_cache: dict[tuple[int, str], float] = {}


def _should_record(message_id: int, category: str) -> bool:
    import time
    now = time.time()
    stale = [k for k, ts in _dedup_cache.items() if (now - ts) > 15.0]
    for k in stale:
        _dedup_cache.pop(k, None)

    key = (int(message_id or 0), str(category))
    if message_id > 0 and key in _dedup_cache:
        return False
    if message_id > 0:
        _dedup_cache[key] = now
    return True


def get_session_complications_summary(
    since_dt: Optional[datetime] = None,
    account: Optional[str] = None,
    max_lines: int = 4000,
) -> dict[str, Any]:
    """Compiles a structured summary of complications from recent PokéMeow events."""
    with _lock:
        events = list(_events)

    if not events and LOG_PATH.exists():
        events = read_tail_jsonl(LOG_PATH, max_lines=max_lines)

    flees: list[dict[str, Any]] = []
    ball_starvations: list[dict[str, Any]] = []
    coin_starvations: list[dict[str, Any]] = []
    cooldown_blocks: list[dict[str, Any]] = []
    daily_limits: list[dict[str, Any]] = []
    unhandled_responses: list[dict[str, Any]] = []
    special_events: list[dict[str, Any]] = []

    flee_by_pokemon: dict[str, int] = {}
    flee_by_rarity: dict[str, int] = {}
    flee_by_ball: dict[str, int] = {}

    for ev in events:
        ts_str = str(ev.get("ts", ""))
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if since_dt and ts < since_dt:
                continue
        except Exception:
            pass

        if account and account.lower() not in str(ev.get("account", "")).lower():
            continue

        cat = str(ev.get("category", ""))
        details = ev.get("details", {}) or {}

        if cat in {"hunt_flee", "fish_flee"}:
            flees.append(ev)
            p_name = str(details.get("pokemon_name", "Unknown"))
            p_rarity = str(details.get("rarity", "Unknown"))
            p_ball = str(details.get("ball_used", "unknown"))
            flee_by_pokemon[p_name] = flee_by_pokemon.get(p_name, 0) + 1
            flee_by_rarity[p_rarity] = flee_by_rarity.get(p_rarity, 0) + 1
            flee_by_ball[p_ball] = flee_by_ball.get(p_ball, 0) + 1
        elif cat == "ball_starvation":
            ball_starvations.append(ev)
        elif cat == "coin_starvation":
            coin_starvations.append(ev)
        elif cat == "cooldown_block":
            cooldown_blocks.append(ev)
        elif cat == "daily_limit":
            daily_limits.append(ev)
        elif cat == "unhandled_response":
            unhandled_responses.append(ev)
        elif cat in {"quest_ready", "quest_complete", "egg_event", "item_retrieved", "rare_encounter", "rare_catch"}:
            special_events.append(ev)

    return {
        "total_complications": len(flees) + len(ball_starvations) + len(coin_starvations) + len(cooldown_blocks) + len(daily_limits),
        "flee_count": len(flees),
        "flees": flees[-50:][::-1],
        "flee_breakdown_by_pokemon": flee_by_pokemon,
        "flee_breakdown_by_rarity": flee_by_rarity,
        "flee_breakdown_by_ball": flee_by_ball,
        "ball_starvation_count": len(ball_starvations),
        "ball_starvations": ball_starvations[-20:][::-1],
        "coin_starvation_count": len(coin_starvations),
        "coin_starvations": coin_starvations[-20:][::-1],
        "cooldown_block_count": len(cooldown_blocks),
        "daily_limit_count": len(daily_limits),
        "unhandled_response_count": len(unhandled_responses),
        "unhandled_responses": unhandled_responses[-20:][::-1],
        "special_events_count": len(special_events),
        "special_events": special_events[-50:][::-1],
    }


def inspect_and_record_pokemeow_message(
    bot: Any,
    message: Message,
    before_message: Optional[Message] = None,
    context_module: str = "",
    ball_used: str = "",
) -> dict[str, Any] | None:
    """Helper that parses a message from PokéMeow and logs it if relevant."""
    author_id = getattr(getattr(message, "author", None), "id", 0)
    if author_id != POKEMEOW_APP_ID:
        return None

    parsed = parse_pokemeow_response(
        message,
        before_message=before_message,
        context_module=context_module,
        ball_used=ball_used,
    )
    if not parsed:
        return None

    msg_id = int(getattr(message, "id", 0) or 0)
    if not _should_record(msg_id, parsed["category"]):
        return None

    account_name = str(getattr(bot, "user", "unknown") or "unknown")
    channel_id = int(getattr(getattr(message, "channel", None), "id", 0) or 0)

    # Record to pokemeow_events.jsonl
    recorded = record_pokemeow_event(
        account=account_name,
        category=parsed["category"],
        headline=parsed["headline"],
        is_complication=parsed["is_complication"],
        module=context_module or parsed["details"].get("module", "general"),
        channel_id=channel_id,
        details=parsed["details"],
        raw_text=parsed.get("raw_text", ""),
    )
    return recorded


def pokemeow_events_log_path() -> str:
    return str(LOG_PATH)
