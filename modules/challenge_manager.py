from __future__ import annotations

import re
import time
from typing import Any


def parse_challenges_text(text: str) -> dict[str, Any]:
    """Parses text from PokéMeow ;challenges and ✉️ Battle invitations views."""
    clean_text = str(text or "")
    lines = clean_text.splitlines()

    basic_challenges: list[dict[str, Any]] = []
    boss_challenges: list[dict[str, Any]] = []
    master_challenges: list[dict[str, Any]] = []
    active_invitations: list[dict[str, Any]] = []

    current_section = "general"

    # Regex matches: [number.] [emoji] [name] • ID: [id]
    # Examples:
    # 1. <:trainer_steven:1372554426228674612> `trainer_steven` • `ID: 210`
    # 1. <:trainer_cynthia:1372554426228674612> trainer_cynthia • ID: 215
    entry_pattern = re.compile(
        r"(?:\d+\.\s+)?(?:<a?:[a-zA-Z0-9_]+:\d+>\s*)?(?:`?([a-zA-Z0-9_-]+)`?|\*\*([^*]+)\*\*)\s*•\s*`?ID:\s*(\d+)`?",
        re.IGNORECASE,
    )

    no_invitations = any(
        phrase in clean_text.lower()
        for phrase in (
            "no battle invitations",
            "no active invitations",
            "you do not have any battle invitations",
            "you do not have any active invitations",
            "you have not received an invite",
        )
    )

    for line in lines:
        lower = line.lower().strip()
        if "basic challenges" in lower:
            current_section = "basic"
            continue
        elif "boss challenges" in lower:
            current_section = "boss"
            continue
        elif "master challenges" in lower:
            current_section = "master"
            continue
        elif "battle invitations" in lower or "invitations" in lower:
            current_section = "invitations"
            continue

        m = entry_pattern.search(line)
        if m:
            name = (m.group(1) or m.group(2) or "").strip()
            npc_id = int(m.group(3))
            tier = current_section
            if current_section == "invitations":
                lower_line = line.lower()
                if "boss" in lower_line or "elite" in lower_line:
                    tier = "boss"
                elif "basic" in lower_line:
                    tier = "basic"
                else:
                    tier = "master"

            entry = {"name": name, "id": npc_id, "tier": tier}

            if current_section == "basic":
                basic_challenges.append(entry)
            elif current_section == "boss":
                boss_challenges.append(entry)
            elif current_section == "master":
                master_challenges.append(entry)
            elif current_section == "invitations":
                active_invitations.append(entry)

    # Basic challenges default: Steven is 210 (free for all players)
    if not basic_challenges:
        basic_challenges.append({"name": "trainer_steven", "id": 210, "tier": "basic"})

    return {
        "basic": basic_challenges,
        "boss": boss_challenges,
        "master": master_challenges,
        "invitations": active_invitations,
        "has_no_invites": no_invitations,
        "last_synced_utc": time.time(),
    }


def find_eligible_npc_for_quest(
    quest_title: str,
    challenge_data: dict[str, Any] | None = None,
    unbattleable_npc_ids: set[int] | None = None,
) -> tuple[bool, str, str]:
    """Determines whether a battle quest can be executed and returns (is_doable, mode, reason).

    Tiers:
    - Basic Challenger: doable via unlocked basic list or standard challenger.
    - Master Challenger: doable if an active master invitation exists OR unlocked in master_list.
    - Elite / Boss Challenger: doable if an active boss/elite invitation exists OR unlocked in boss_list.
    - General Challengers: doable using any available challenger (basic -> boss -> master).
    - General NPCs: doable using 'npc 1'.
    """
    raw = str(quest_title or "").lower().strip()
    data = challenge_data or {}
    invitations = data.get("invitations", [])
    master_list = data.get("master", [])
    boss_list = data.get("boss", [])
    basic_list = data.get("basic", [])
    unbattleable = set(unbattleable_npc_ids or [])

    # 1. Master Challenger Quests
    if "master challenger" in raw:
        master_invites = [
            inv for inv in invitations
            if (inv.get("tier") == "master" or "master" in str(inv.get("tier", "")).lower())
            and inv.get("id") not in unbattleable
        ]
        if master_invites:
            target_id = master_invites[0]["id"]
            return True, f"npc {target_id}", f"master_invite:{master_invites[0]['name']}"

        available_masters = [m for m in master_list if m.get("id") not in unbattleable]
        if available_masters:
            target_id = available_masters[0]["id"]
            return True, f"npc {target_id}", f"master_unlocked:{available_masters[0]['name']}"

        return False, "", "no_master_invite"

    # 2. Elite / Boss Challenger Quests
    if "elite challenger" in raw or "boss challenger" in raw:
        boss_invites = [
            inv for inv in invitations
            if inv.get("tier") in ("boss", "elite") and inv.get("id") not in unbattleable
        ]
        if boss_invites:
            target_id = boss_invites[0]["id"]
            return True, f"npc {target_id}", f"boss_invite:{boss_invites[0]['name']}"

        available_bosses = [b for b in boss_list if b.get("id") not in unbattleable]
        if available_bosses:
            target_id = available_bosses[0]["id"]
            return True, f"npc {target_id}", f"boss_unlocked:{available_bosses[0]['name']}"

        return False, "", "no_boss_invite"

    # 3. Basic Challenger Quests
    if "basic challenger" in raw:
        available_basic = [b for b in basic_list if b.get("id") not in unbattleable]
        if available_basic:
            target_id = available_basic[0]["id"]
            return True, f"npc {target_id}", f"basic_challenger:{available_basic[0]['name']}"
        fallback_id = 210 if 210 not in unbattleable else 209
        return True, f"npc {fallback_id}", "basic_challenger"

    # 4. General Challenger Quests (e.g. "Defeat 2 Challengers in battle", "Win Challenger battles")
    if "challenger" in raw:
        available_basic = [b for b in basic_list if b.get("id") not in unbattleable]
        if available_basic:
            target_id = available_basic[0]["id"]
            return True, f"npc {target_id}", f"general_challenger:{available_basic[0]['name']}"

        available_bosses = [b for b in boss_list if b.get("id") not in unbattleable]
        if available_bosses:
            target_id = available_bosses[0]["id"]
            return True, f"npc {target_id}", f"general_challenger:{available_bosses[0]['name']}"

        available_masters = [m for m in master_list if m.get("id") not in unbattleable]
        if available_masters:
            target_id = available_masters[0]["id"]
            return True, f"npc {target_id}", f"general_challenger:{available_masters[0]['name']}"

        fallback_id = 210 if 210 not in unbattleable else 209
        return True, f"npc {fallback_id}", "general_challenger"

    # 5. Standard NPC / Trainer Quests
    npc_patterns = [
        r"\bdefeats?\b.*\b(battle|npcs?|trainers?|pokemon)\b",
        r"\bwins?\b.*\b(battle|trainers?|npcs?)\b",
        r"\bbattles?\b",
        r"\bnpcs?\b",
        r"\btrainers?\b",
    ]
    for pat in npc_patterns:
        if re.search(pat, raw, re.IGNORECASE):
            return True, "npc 1", "standard_npc"

    return False, "", "not_a_battle_quest"
