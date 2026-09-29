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
    parts: list[str] = [str(getattr(message, "content", "") or "")]

    # Embeds
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

    # Interactive component buttons
    for row in getattr(message, "components", []) or []:
        for child in getattr(row, "children", []) or []:
            label = str(getattr(child, "label", "") or "").strip()
            custom_id = str(getattr(child, "custom_id", "") or "").strip()
            if label:
                parts.append(label)
            if custom_id:
                parts.append(custom_id)

    # Attachments
    for att in getattr(message, "attachments", []) or []:
        fn = str(getattr(att, "filename", "") or "").strip()
        desc = str(getattr(att, "description", "") or "").strip()
        if fn:
            parts.append(fn)
        if desc:
            parts.append(desc)

    return "\n".join(part for part in parts if part.strip())


def _extract_pokemon_name_from_haystack(haystack: str) -> str:
    patterns = [
        # Explicit catch patterns
        r"you\s+caught\s+(?:an?\s*)?(?:wild\s+)?(?:(?:<a?:[a-z0-9_]+:\d+>|:[a-z0-9_]+:)\s*)*(?:\*\*)?([A-Za-z][A-Za-z0-9\-\. '\u2019]{1,50}?)(?:\*\*)?(?:[!.]|\s+with\b|\s+has\b)",
        r"caught\s+(?:an?\s*)?(?:wild\s+)?(?:(?:<a?:[a-z0-9_]+:\d+>|:[a-z0-9_]+:)\s*)*(?:\*\*)?([A-Za-z][A-Za-z0-9\-\. '\u2019]{1,50}?)(?:\*\*)?(?:[!.]|\s+with\b|\s+has\b)",
        r"caught\s+(?:an?\s*)?(?:(?:<a?:[a-z0-9_]+:\d+>|:[a-z0-9_]+:)\s*)*\*\*([^*]+)\*\*",
        r"fished\s+(?:an?\s*)?(?:(?:<a?:[a-z0-9_]+:\d+>|:[a-z0-9_]+:)\s*)*\*\*([^*]+)\*\*",
        # Wild found / fished patterns
        r"(?:found|fished)\s+(?:an?\s*)?(?:wild\s+)(?:(?:<a?:[a-z0-9_]+:\d+>|:[a-z0-9_]+:)\s*)*(?:\*\*)?([A-Za-z][A-Za-z0-9\-\. '\u2019]{1,50}?)(?:\*\*)?[!.]",
        r"wild\s+(?:[:a-z0-9_]+\s+)?\*\*([^*]+)\*\*",
        r"wild\s+([A-Za-z0-9\-\. '\u2019]{1,40}?)\s+(?:appeared|ran away|got away|broke free|fled)",
        r"(?:the\s+)?wild\s+([A-Za-z0-9\-\. '\u2019]{1,40}?)\s+(?:ran\s+away|got\s+away|broke\s+free)",
    ]
    ignored = {"you", "the", "a", "an", "pokemon", "pokémon", "bot", "wild", "another", "schrazen", "yashi"}
    for pat in patterns:
        m = re.search(pat, haystack, flags=re.IGNORECASE)
        if m:
            candidate = _sanitize_text(m.group(1))
            candidate = re.sub(r"^(?:shiny|golden|wild)\s+", "", candidate, flags=re.IGNORECASE)
            candidate = candidate.strip(" .!,:;*-_\n\t")
            if candidate and candidate.lower() not in ignored and len(candidate) > 1:
                return candidate
    return "Unknown"


def _extract_rarity_from_haystack(haystack: str) -> str:
    lowered = haystack.lower()
    # Check for explicit rarity with rate first: e.g. "super rare (2% encounter rate)"
    for explicit_rarity in [
        "ultra beast",
        "super rare",
        "legendary",
        "mythical",
        "golden",
        "shiny",
        "uncommon",
        "common",
        "rare",
        "event",
    ]:
        if re.search(rf"\b{re.escape(explicit_rarity)}\s*(?:\(\d+(?:\.\d+)?%\s*encounter|\s*streak:)", lowered):
            return explicit_rarity.title()

    # Next check standalone rarity keywords
    for rarity in [
        "ultra beast",
        "super rare",
        "legendary",
        "mythical",
        "golden",
        "shiny",
        "uncommon",
        "common",
        "rare",
        "event",
    ]:
        if re.search(rf"\b{re.escape(rarity)}\b", lowered):
            if rarity == "rare" and "rare candy" in lowered and "rare streak" not in lowered and "rare (" not in lowered:
                continue
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


def parse_quest_board_payload(text: str) -> dict[str, Any]:
    next_quest = ""
    nq_m = re.search(r"your next quest is\s*(?:[^\w\s]*\s*)*([^!]+!?)", text, re.IGNORECASE)
    if nq_m:
        raw_nq = nq_m.group(1).strip()
        next_quest = re.sub(r"^[^\w]+", "", raw_nq).strip()
        next_quest = re.split(r"complete your quests", next_quest, flags=re.IGNORECASE)[0].strip()

    active_quests = []
    q_parts = re.split(r"Quest\s*#(\d+):", text, flags=re.IGNORECASE)
    if len(q_parts) > 1:
        for i in range(1, len(q_parts), 2):
            q_num = int(q_parts[i])
            body = q_parts[i + 1]
            title_part = re.split(r">\s*.*Rewards:", body, flags=re.IGNORECASE)
            title = ""
            if title_part:
                title = re.sub(r"^[^\w]+", "", title_part[0]).strip()
            rew_m = re.search(r"Rewards:\s*([^>\n\r]+)", body, re.IGNORECASE)
            rewards = rew_m.group(1).strip() if rew_m else ""
            prog_m = re.search(r"Progress:\s*([^\n\r]+)", body, re.IGNORECASE)
            progress_str = prog_m.group(1).strip() if prog_m else ""

            cur_prog = 0
            tot_prog = 1
            num_m = re.search(r"(\d[\d,]*)\s*(?:out of|/)\s*(\d[\d,]*)", progress_str, re.IGNORECASE)
            if num_m:
                try:
                    cur_prog = int(num_m.group(1).replace(",", ""))
                    tot_prog = int(num_m.group(2).replace(",", ""))
                except Exception:
                    pass

            active_quests.append({
                "id": q_num,
                "title": title,
                "rewards": rewards,
                "progress_str": progress_str,
                "progress_current": cur_prog,
                "progress_total": tot_prog,
            })

    return {
        "next_quest": next_quest,
        "active_quests": active_quests,
    }


def parse_quest_complete_payload(text: str) -> dict[str, Any]:
    quest_name = ""
    rewards = ""
    exp = ""
    m = re.search(r"completed the quest\s+(.+?)\s+and received:\s*([^!]+!)(?:\s*(.+?\bgained\s+[^\n\r!]+!?))?", text, re.IGNORECASE)
    if m:
        quest_name = m.group(1).strip()
        rewards = m.group(2).strip()
        if m.group(3):
            exp = m.group(3).strip()
    return {
        "quest_name": quest_name,
        "rewards": rewards,
        "exp": exp,
    }


def parse_pokemeow_response(
    message: Message,
    before_message: Optional[Message] = None,
    context_module: str = "",
    ball_used: str = "",
) -> dict[str, Any] | None:
    """Inspects a Discord message from PokéMeow and classifies the event.

    Returns a structured dictionary with category, is_complication, details, and raw text preview.
    Returns None if the message contains no text/components (discarding intermediate gateway updates).
    """
    haystack = collect_message_text(message)
    if not haystack.strip():
        # Discard empty intermediate gateway/loading events
        return None

    before_haystack = collect_message_text(before_message) if before_message else ""
    full_haystack = f"{before_haystack}\n{haystack}" if before_haystack else haystack
    lowered = haystack.lower()
    lowered_full = full_haystack.lower()

    preview = _sanitize_text(haystack)[:300]
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

    # 3. Active Encounter Pending / Overlap
    if "please catch the pokemon you spawned first" in lowered or "catch the pokemon you spawned first" in lowered:
        return {
            "category": "active_encounter_pending",
            "is_complication": True,
            "headline": "Encounter blocked: active Pokémon already spawned",
            "details": {
                "module": context_module or "hunting",
                "preview": preview,
            },
            "raw_text": preview,
        }

    # 4. Ball Starvation (Out of Pokeballs)
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

    # 5. Coin Starvation (Insufficient Pokécoins during Auto-Buy / Shop)
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

    # 6. Captcha Prompt
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

    # 7. Missing Fishing Rod (Strict matching to avoid false positives on fish names)
    if context_module == "fishing" and any(m in lowered for m in [
        "don't have a rod",
        "do not have a rod",
        "need a fishing rod",
        "no fishing rod",
        "buy a fishing rod",
        "missing fishing rod",
        "need to buy a rod",
        "without a fishing rod",
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

    # 8. Casket Minigame Timeout
    if any(m in lowered for m in [
        "casket sank away",
        "sunken casket in time",
        "did not choose what to do with sunken casket",
    ]):
        return {
            "category": "casket_timeout",
            "is_complication": True,
            "headline": "Sunken Casket sank away: action timed out",
            "details": {
                "module": "fishing",
                "preview": preview,
            },
            "raw_text": preview,
        }

    # 9. Shop Error / Invalid Item
    if any(m in lowered for m in ["not in the shop", "item is not in the shop", "invalid item"]):
        return {
            "category": "shop_invalid_item",
            "is_complication": True,
            "headline": "Shop error: item not found in shop",
            "details": {
                "module": "shop",
                "preview": preview,
            },
            "raw_text": preview,
        }

    # 10. Flees / Escapes
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

    # 11. Fishing: "not even a nibble"
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

    # 12. CatchBot Status Summary (Must be checked before generic catch)
    if any(m in lowered for m in [
        "lifetime caught by cb",
        "on total upgrades to run your catchbot",
        ";catchbot run",
        ";catchbot upgrade",
    ]):
        return {
            "category": "catchbot_status",
            "is_complication": False,
            "headline": "CatchBot status / stats summary",
            "details": {
                "module": "catchbot",
                "preview": preview,
            },
            "raw_text": preview,
        }

    # 13. Event Announcements & Global Bonuses
    if any(m in lowered for m in [
        "event ticket is active",
        "event exclusive",
        "event ends:",
        "global bonuses",
        "vote coin bonus:",
    ]):
        return {
            "category": "event_status",
            "is_complication": False,
            "headline": "Event ticket / global bonuses status",
            "details": {
                "module": context_module or "general",
                "preview": preview,
            },
            "raw_text": preview,
        }

    # 14. Inventory / Bag View
    if any(m in lowered for m in [
        "item inventory page",
        "to view your pokemon box, type ;box",
        ";item info",
    ]):
        return {
            "category": "inventory_view",
            "is_complication": False,
            "headline": "Item inventory and currency overview",
            "details": {
                "module": context_module or "inventory",
                "preview": preview,
            },
            "raw_text": preview,
        }

    # 15. Shop Menu & Balances
    if ("pokecoins:" in lowered or "votecoins:" in lowered) and any(m in lowered for m in [
        "═ balls ═",
        "═ items ═",
        "1 pokeball 200",
    ]):
        return {
            "category": "shop_menu",
            "is_complication": False,
            "headline": "Shop catalog and coin balances",
            "details": {
                "module": "shop",
                "preview": preview,
            },
            "raw_text": preview,
        }

    # 16. Berry Garden Overview
    if "garden overview" in lowered or ("slot 1 —" in lowered and "planted [stage" in lowered):
        return {
            "category": "berry_garden_status",
            "is_complication": False,
            "headline": "Berry garden status overview",
            "details": {
                "module": "berry",
                "preview": preview,
            },
            "raw_text": preview,
        }

    # 17. Consumables & Buffs Activated
    if any(m in lowered for m in [
        "you used 1x",
        "you used 2x",
        "you ate",
        "gained the following bonuses",
        "increased timer for pull",
        "encounter rate has been significantly increased",
    ]):
        return {
            "category": "item_buff_activated",
            "is_complication": False,
            "headline": "Item buff activated (encounter/fishing bonus)",
            "details": {
                "module": context_module or "items",
                "preview": preview,
            },
            "raw_text": preview,
        }

    # 18. Lootbox Opened
    if "opened" in lowered and "lootbox" in lowered and "received:" in lowered:
        return {
            "category": "lootbox_opened",
            "is_complication": False,
            "headline": "Lootbox opened: items received",
            "details": {
                "module": context_module or "items",
                "preview": preview,
            },
            "raw_text": preview,
        }

    # 19. Quest Board / List
    if "your next quest is" in lowered and ("quest #1:" in lowered or "complete your quests for rewards" in lowered):
        parsed_board = parse_quest_board_payload(preview)
        return {
            "category": "quest_board",
            "is_complication": False,
            "headline": "Quest board: active quests overview",
            "details": {
                "module": "quest",
                "preview": preview,
                "next_quest": parsed_board.get("next_quest", ""),
                "active_quests": parsed_board.get("active_quests", []),
            },
            "raw_text": preview,
        }

    # 20. Quest Ready / Complete
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
    if any(m in lowered for m in ["completed the quest", "quest complete", "completed a quest"]):
        parsed_comp = parse_quest_complete_payload(preview)
        return {
            "category": "quest_complete",
            "is_complication": False,
            "headline": "Quest Complete!",
            "details": {
                "module": "quest",
                "preview": preview,
                "quest_name": parsed_comp.get("quest_name", ""),
                "rewards": parsed_comp.get("rewards", ""),
                "exp": parsed_comp.get("exp", ""),
            },
            "raw_text": preview,
        }

    # 21. Egg Hatch / Incubation Events
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

    # 22. Retrieved Held Item
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

    # 23. Shop Buy Success
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

    # 24. System Notices & Promo Announcements
    if any(m in lowered for m in [
        "support the development of pokemeow",
        "type ;patreon to support",
        "trade with other train",
        "be active in the support server",
    ]):
        return {
            "category": "system_notice",
            "is_complication": False,
            "headline": "PokéMeow announcement / support notice",
            "details": {
                "module": context_module or "general",
                "preview": preview,
            },
            "raw_text": preview,
        }

    # 25. Hunt / Fish Catch Success
    if "you caught" in lowered or ("caught" in lowered and any(k in lowered for k in ["wild", "pokedex", "with a", "earned"])):
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

    # 26. Wild Encounter Spawns
    if "found a wild" in lowered or ("wild" in lowered and "appeared" in lowered) or "fished a wild" in lowered:
        is_rare = any(r in rarity.lower() for r in ["shiny", "golden", "legendary", "mythical", "ultra", "event"])
        is_fishing = (context_module == "fishing")
        category = "fish_encounter" if is_fishing else "hunt_encounter"
        headline = f"Wild {pokemon_name} ({rarity}) appeared"
        return {
            "category": category,
            "is_complication": False,
            "headline": headline,
            "details": {
                "module": "fishing" if is_fishing else "hunting",
                "pokemon_name": pokemon_name,
                "rarity": rarity,
                "is_rare": is_rare,
                "preview": preview,
            },
            "raw_text": preview,
        }

    # 27. Truly Unhandled Response (Non-empty text only)
    return {
        "category": "unhandled_response",
        "is_complication": False,
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
    active_encounter_blocks: list[dict[str, Any]] = []
    casket_timeouts: list[dict[str, Any]] = []
    shop_errors: list[dict[str, Any]] = []
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
        elif cat == "active_encounter_pending":
            active_encounter_blocks.append(ev)
        elif cat == "casket_timeout":
            casket_timeouts.append(ev)
        elif cat == "shop_invalid_item":
            shop_errors.append(ev)
        elif cat == "unhandled_response":
            unhandled_responses.append(ev)
        elif cat in {
            "quest_ready",
            "quest_complete",
            "egg_event",
            "item_retrieved",
            "rare_encounter",
            "rare_catch",
            "item_buff_activated",
            "lootbox_opened",
            "catchbot_status",
            "berry_garden_status",
        }:
            special_events.append(ev)

    total_complications = (
        len(flees)
        + len(ball_starvations)
        + len(coin_starvations)
        + len(cooldown_blocks)
        + len(daily_limits)
        + len(active_encounter_blocks)
        + len(casket_timeouts)
        + len(shop_errors)
    )

    return {
        "total_complications": total_complications,
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
        "active_encounter_block_count": len(active_encounter_blocks),
        "active_encounter_blocks": active_encounter_blocks[-20:][::-1],
        "casket_timeout_count": len(casket_timeouts),
        "casket_timeouts": casket_timeouts[-20:][::-1],
        "shop_error_count": len(shop_errors),
        "shop_errors": shop_errors[-20:][::-1],
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

    if bot is not None:
        if parsed["category"] == "quest_board":
            if not hasattr(bot, "quest_data") or not isinstance(bot.quest_data, dict):
                bot.quest_data = {}
            bot.quest_data["next_quest"] = str(parsed["details"].get("next_quest", "") or "")
            bot.quest_data["active_quests"] = list(parsed["details"].get("active_quests", []) or [])
            bot.quest_data["last_updated_utc"] = _utc_now_iso()
        elif parsed["category"] == "quest_complete":
            if not hasattr(bot, "quest_data") or not isinstance(bot.quest_data, dict):
                bot.quest_data = {}
            bot.quest_data["last_completed"] = {
                "quest": str(parsed["details"].get("quest_name", "") or ""),
                "rewards": str(parsed["details"].get("rewards", "") or ""),
                "exp": str(parsed["details"].get("exp", "") or ""),
                "completed_at": _utc_now_iso(),
            }
            bot.quest_data["last_updated_utc"] = _utc_now_iso()

    return recorded


def pokemeow_events_log_path() -> str:
    return str(LOG_PATH)
