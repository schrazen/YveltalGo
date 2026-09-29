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
            entry = {"name": name, "id": npc_id, "tier": current_section}

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
) -> tuple[bool, str, str]:
    """Determines whether a battle quest can be executed and returns (is_doable, mode, reason).

    Tiers:
    - Basic Challenger: always doable (Steven ID 210).
    - Master Challenger: only doable if an active master invitation exists.
    - Elite / Boss Challenger: only doable if an active boss/elite invitation exists.
    - General Challengers: doable using any available challenger (defaults to Steven 210).
    - General NPCs: doable using 'npc 1'.
    """
    raw = str(quest_title or "").lower().strip()
    data = challenge_data or {}
    invitations = data.get("invitations", [])
    master_list = data.get("master", [])
    basic_list = data.get("basic", [])

    # 1. Master Challenger Quests
    if "master challenger" in raw:
        # Check active invitations for a master tier challenger
        master_invites = [inv for inv in invitations if inv.get("tier") == "master"]
        if master_invites:
            target_id = master_invites[0]["id"]
            return True, f"npc {target_id}", f"master_invite:{master_invites[0]['name']}"

        # If master list has unlocked entries from ;challenges
        if master_list:
            target_id = master_list[0]["id"]
            return True, f"npc {target_id}", f"master_unlocked:{master_list[0]['name']}"

        # No invitation held for Master Challenger
        return False, "", "no_master_invite"

    # 2. Elite / Boss Challenger Quests
    if "elite challenger" in raw or "boss challenger" in raw:
        boss_invites = [inv for inv in invitations if inv.get("tier") in ("boss", "elite")]
        if boss_invites:
            target_id = boss_invites[0]["id"]
            return True, f"npc {target_id}", f"boss_invite:{boss_invites[0]['name']}"
        return False, "", "no_boss_invite"

    # 3. Basic Challenger Quests
    if "basic challenger" in raw:
        target_id = basic_list[0]["id"] if basic_list else 210
        return True, f"npc {target_id}", "basic_challenger"

    # 4. General Challenger Quests (e.g. "Defeat 2 Challengers in battle", "Win Challenger battles")
    if "challenger" in raw:
        # Prefer basic challenger (Steven 210) because basic challenges have no prerequisites
        target_id = basic_list[0]["id"] if basic_list else 210
        return True, f"npc {target_id}", "general_challenger"

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
