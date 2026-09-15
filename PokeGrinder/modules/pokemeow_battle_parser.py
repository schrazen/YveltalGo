from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from discord import Message

from modules.battle_state import normalize, parse_battle_state

_TITLE_PATTERN = re.compile(r"challenge$", re.IGNORECASE)
_WORLD_BOSS_HP_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9'\- ]+):\s*([\d,]+)\s*/\s*([\d,]+)\s*HP(?:\s+:fnt:)?$", re.IGNORECASE)
_TEAM_ROW_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9'\- ]+)\s+([\d,]+)\s*/\s*([\d,]+)(?:.*?DMG:\s*([\d,]+))?$", re.IGNORECASE)
_BOSS_STARE_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9'\- ]+) stares intensely at ([A-Za-z][A-Za-z0-9'\- ]+)(?:\.{3})?$", re.IGNORECASE)
_REWARD_PROGRESS_PATTERN = re.compile(r"^Reward potential:\s*\[([0-5])/5\]$", re.IGNORECASE)
_DMG_THRESHOLD_PATTERN = re.compile(r"^([\d,]+) DMG until next threshold$", re.IGNORECASE)
_PLAYERS_PATTERN = re.compile(r"^Players in battle:\s*(\d+)\s*•\s*Your total DMG dealt:\s*([\d,]+)$", re.IGNORECASE)
_MOVE_DAMAGE_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9'\- ]+) dealt ([\d,]+) DMG", re.IGNORECASE)
_RECOIL_DAMAGE_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9'\- ]+) took ([\d,]+) recoil damage!?$", re.IGNORECASE)
_HEALED_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9'\- ]+) healed ([\d,]+) HP!?$", re.IGNORECASE)
_STATUS_APPLIED_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9'\- ]+) is (?:now )?([A-Za-z\- ]+)!", re.IGNORECASE)
_CANT_MOVE_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9'\- ]+) is paralyzed! It can't move!?$", re.IGNORECASE)
_STAT_ROSE_FELL_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9'\- ]+)'s ([A-Za-z\- ]+) (rose|fell|harshly fell|won't go any higher|won't go any lower)!?(?:\s*\[([+-]?\d+)\])?$", re.IGNORECASE)
_SENT_OUT_LINE_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9'\- ]+) sent out ([A-Za-z][A-Za-z0-9'\- ]+)\.$", re.IGNORECASE)
_PIVOT_LINE_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9'\- ]+) passed the baton and sent out ([A-Za-z][A-Za-z0-9'\- ]+)\.$", re.IGNORECASE)

_USED_MOVE_PATTERN = re.compile(r"used\s+([^!]+)!", re.IGNORECASE)
_WHO_USED_CLEAN_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9'\- ]+)\s+used\s+([^!]+)!$", re.IGNORECASE)
_WHO_USED_PATTERN = re.compile(r":\d+_?:\s*([A-Za-z][A-Za-z0-9'\- ]+)\s+used", re.IGNORECASE)
_SENT_OUT_PATTERN = re.compile(r"sent out\s+[^\n!]*?([A-Za-z][A-Za-z0-9'\- ]+)!", re.IGNORECASE)
_HP_STATUS_PATTERN = re.compile(
    r"(?:<:\w+:\d+>|:\d+_?:)\s*([A-Za-z][A-Za-z0-9'\- ]+)\s+(?:(?:<:\w+:\d+>|:\w+:)\s+)*HP\s+(\d+)/(\d+)(\s+:fnt:)?",
    re.IGNORECASE,
)
_HP_FALLBACK_PATTERN = re.compile(r"\b([A-Za-z][A-Za-z0-9'\- ]{1,40}?)\s+HP\s+(\d+)/(\d+)", re.IGNORECASE)
_STAT_DELTA_PATTERN = re.compile(r"\[([+-])(\d+)\]")


@dataclass
class ParsedBattleEvent:
    kind: str
    line_index: int
    line: str
    actor: str = ""
    target: str = ""
    move: str = ""
    stat: str = ""
    delta: int | None = None
    hp_current: int | None = None
    hp_total: int | None = None
    value: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def _collect_text(message: Message) -> str:
    parts: list[str] = []
    if getattr(message, "content", None):
        parts.append(str(message.content or ""))

    for embed in getattr(message, "embeds", []) or []:
        if getattr(embed, "title", None):
            parts.append(str(embed.title or ""))
        if getattr(embed, "description", None):
            parts.append(str(embed.description or ""))
        if getattr(getattr(embed, "footer", None), "text", None):
            parts.append(str(embed.footer.text or ""))
        for field in getattr(embed, "fields", []) or []:
            if getattr(field, "name", None):
                parts.append(str(field.name or ""))
            if getattr(field, "value", None):
                parts.append(str(field.value or ""))

    return "\n".join(parts)


def _clean_battle_line(line: str) -> str:
    cleaned = re.sub(r"<:[^>]+>", " ", str(line or ""))
    cleaned = re.sub(r":[A-Za-z0-9_]+:", " ", cleaned)
    cleaned = re.sub(r"\*\*|__|~~|`", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _classify_line(line: str, *, last_actor: str = "") -> tuple[str, dict[str, Any]]:
    lowered = line.lower()
    if not line:
        return "blank", {}

    if _TITLE_PATTERN.search(line):
        return "battle_title", {"title": line}
    if "reward potential" in lowered:
        reward_match = _REWARD_PROGRESS_PATTERN.search(line)
        stage = int(reward_match.group(1)) if reward_match else None
        return "reward_progress", {"reward_stage": stage}
    if _DMG_THRESHOLD_PATTERN.search(line):
        threshold_match = _DMG_THRESHOLD_PATTERN.search(line)
        return "damage_threshold", {"value": int(str(threshold_match.group(1) or "0").replace(",", ""))}
    if "players in battle" in lowered or "your total dmg dealt" in lowered:
        players_match = _PLAYERS_PATTERN.search(line)
        if players_match:
            return "battle_summary", {
                "players_in_battle": int(players_match.group(1)),
                "your_total_damage": int(players_match.group(2).replace(",", "")),
            }
        return "battle_summary", {}
    if "world boss has been defeated" in lowered or "won the battle" in lowered:
        return "terminal_win", {}
    if "lost the battle" in lowered:
        return "terminal_loss", {}
    if "re-join the battle" in lowered:
        return "rejoin_prompt", {}
    if "stares intensely" in lowered:
        stare_match = _BOSS_STARE_PATTERN.search(line)
        if stare_match:
            return "boss_targeting", {"actor": stare_match.group(1), "target": stare_match.group(2)}
    if "stares intensely" in lowered:
        actor_match = _WHO_USED_PATTERN.search(line)
        actor = str(actor_match.group(1) or "").strip() if actor_match else ""
        return "boss_targeting", {"actor": actor or last_actor}

    pivot_match = _PIVOT_LINE_PATTERN.search(line)
    if pivot_match:
        return "switch_in", {"actor": pivot_match.group(1), "target": pivot_match.group(2)}

    sent_out = _SENT_OUT_PATTERN.search(line)
    if sent_out:
        return "sent_out", {"actor": str(sent_out.group(1) or "").strip()}

    sent_out_line = _SENT_OUT_LINE_PATTERN.search(line)
    if sent_out_line:
        return "switch_in", {"actor": sent_out_line.group(1), "target": sent_out_line.group(2)}

    used = _USED_MOVE_PATTERN.search(line)
    if used:
        clean_used = _WHO_USED_CLEAN_PATTERN.search(line)
        if clean_used:
            actor = str(clean_used.group(1) or "").strip()
            move = str(clean_used.group(2) or "").strip()
            return "move_used", {"actor": actor, "move": move}

        who = _WHO_USED_PATTERN.search(line)
        actor = str(who.group(1) or "").strip() if who else last_actor
        return "move_used", {"actor": actor, "move": str(used.group(1) or "").strip()}

    hp_match = _WORLD_BOSS_HP_PATTERN.search(line) or _HP_STATUS_PATTERN.search(line) or _HP_FALLBACK_PATTERN.search(line)
    if hp_match:
        name = str(hp_match.group(1) or "").strip()
        current = int(str(hp_match.group(2) or "0").replace(",", ""))
        total = int(str(hp_match.group(3) or "0").replace(",", ""))
        fainted = bool(hp_match.group(4)) if len(hp_match.groups()) >= 4 else False
        kind = "boss_hp" if "health" not in lowered else "hp_update"
        return kind, {"actor": name, "hp_current": current, "hp_total": total, "fainted": fainted}

    row_match = _TEAM_ROW_PATTERN.search(line)
    if row_match and ("dmg:" in lowered or "/" in lowered):
        name = str(row_match.group(1) or "").strip()
        current = int(str(row_match.group(2) or "0").replace(",", ""))
        total = int(str(row_match.group(3) or "0").replace(",", ""))
        damage = row_match.group(4)
        return "team_row", {
            "actor": name,
            "hp_current": current,
            "hp_total": total,
            "value": int(str(damage).replace(",", "")) if damage else None,
            "fainted": ":fnt:" in lowered or current <= 0,
        }

    damage_match = _MOVE_DAMAGE_PATTERN.search(line)
    if damage_match:
        extra: dict[str, Any] = {
            "actor": damage_match.group(1),
            "value": int(str(damage_match.group(2)).replace(",", "")),
        }
        status_match = _STATUS_APPLIED_PATTERN.search(line)
        if status_match:
            extra["status"] = status_match.group(2).strip().lower()
        return "damage_dealt", extra

    recoil_match = _RECOIL_DAMAGE_PATTERN.search(line)
    if recoil_match:
        return "recoil_damage", {
            "actor": recoil_match.group(1),
            "value": int(str(recoil_match.group(2)).replace(",", "")),
        }

    heal_match = _HEALED_PATTERN.search(line)
    if heal_match:
        return "heal", {
            "actor": heal_match.group(1),
            "value": int(str(heal_match.group(2)).replace(",", "")),
        }

    status_match = _STATUS_APPLIED_PATTERN.search(line)
    if status_match:
        return "status_applied", {
            "actor": status_match.group(1),
            "status": status_match.group(2).strip().lower(),
        }

    cant_move_match = _CANT_MOVE_PATTERN.search(line)
    if cant_move_match:
        return "status_applied", {
            "actor": cant_move_match.group(1),
            "status": "paralyzed",
            "extra_text": "can't move",
        }

    stat_match = _STAT_ROSE_FELL_PATTERN.search(line)
    if stat_match:
        actor = stat_match.group(1)
        stat = stat_match.group(2).strip().lower()
        descriptor = stat_match.group(3).strip().lower()
        raw_delta = stat_match.group(4)
        delta: int | None = None
        if raw_delta and raw_delta.lstrip("+-").isdigit():
            delta = int(raw_delta)
        elif descriptor == "rose":
            delta = 1
        elif descriptor == "fell":
            delta = -1
        elif descriptor == "harshly fell":
            delta = -2
        elif descriptor == "won't go any higher":
            delta = 0
        elif descriptor == "won't go any lower":
            delta = 0
        return "stat_change", {"actor": actor, "stat": stat, "delta": delta, "stat_text": line}

    delta_match = _STAT_DELTA_PATTERN.search(line)
    if delta_match:
        delta = int(delta_match.group(2) or 0)
        if delta_match.group(1) == "-":
            delta *= -1
        actor_match = _WHO_USED_PATTERN.search(line)
        actor = str(actor_match.group(1) or "").strip() if actor_match else last_actor
        return "stat_change", {"actor": actor, "delta": delta, "stat_text": line}

    if "fainted" in lowered:
        actor_match = _WHO_USED_PATTERN.search(line)
        actor = str(actor_match.group(1) or "").strip() if actor_match else last_actor
        return "faint", {"actor": actor}

    if "used" in lowered or "rose" in lowered or "fell" in lowered or "healed" in lowered or "dealt" in lowered:
        actor_match = _WHO_USED_PATTERN.search(line)
        actor = str(actor_match.group(1) or "").strip() if actor_match else last_actor
        return "battle_line", {"actor": actor}

    return "battle_line", {}


def parse_pokemeow_battle_events(message: Message) -> tuple[list[ParsedBattleEvent], dict[str, Any]]:
    text = _collect_text(message)
    lines = [str(line or "").strip() for line in text.splitlines()]
    state = parse_battle_state(message, ["Mew", "Malamar", "Mega Mewtwo Y", "Mewtwo", "Boss", "World Boss"])

    events: list[ParsedBattleEvent] = []
    last_actor = str(state.active_pokemon or "")
    worldboss: dict[str, Any] = {
        "title": "",
        "boss_name": "",
        "boss_hp_current": None,
        "boss_hp_total": None,
        "reward_stage": None,
        "damage_threshold": None,
        "players_in_battle": None,
        "your_total_damage": None,
        "team_rows": [],
        "terminal": None,
    }

    for index, raw_line in enumerate(lines):
        cleaned = _clean_battle_line(raw_line)
        if not cleaned:
            continue

        kind, extra = _classify_line(cleaned, last_actor=last_actor)
        actor = str(extra.pop("actor", "") or "")
        move = str(extra.pop("move", "") or "")
        stat_text = str(extra.pop("stat_text", "") or "")
        delta = extra.pop("delta", None)
        hp_current = extra.pop("hp_current", None)
        hp_total = extra.pop("hp_total", None)
        value = extra.pop("value", None)

        if actor:
            last_actor = actor

        if kind == "battle_title":
            worldboss["title"] = str(extra.get("title", cleaned) or cleaned)
        elif kind in {"boss_hp", "hp_update"}:
            worldboss["boss_name"] = actor or worldboss.get("boss_name") or ""
            worldboss["boss_hp_current"] = hp_current
            worldboss["boss_hp_total"] = hp_total
        elif kind == "reward_progress":
            worldboss["reward_stage"] = extra.get("reward_stage")
        elif kind == "damage_threshold":
            worldboss["damage_threshold"] = value
        elif kind == "battle_summary":
            worldboss["players_in_battle"] = extra.get("players_in_battle")
            worldboss["your_total_damage"] = extra.get("your_total_damage")
        elif kind == "team_row":
            worldboss["team_rows"].append(
                {
                    "name": actor,
                    "hp_current": hp_current,
                    "hp_total": hp_total,
                    "damage": value,
                    "fainted": bool(extra.get("fainted", False)),
                }
            )
        elif kind in {"terminal_win", "terminal_loss"}:
            worldboss["terminal"] = kind
        elif kind == "switch_in" and actor:
            worldboss["last_switch_in"] = actor
            worldboss["active_pokemon"] = actor
        elif kind == "move_used" and actor:
            worldboss["last_move_actor"] = actor
            worldboss["last_move"] = move
            if actor:
                worldboss.setdefault("active_pokemon", actor)
        elif kind == "damage_dealt":
            worldboss["last_damage_actor"] = actor
            worldboss["last_damage_value"] = value
            if extra.get("status"):
                worldboss["last_damage_status"] = extra.get("status")
        elif kind == "status_applied":
            worldboss["last_status_actor"] = actor
            worldboss["last_status"] = extra.get("status")

        if kind == "move_used" and not move:
            move_match = _USED_MOVE_PATTERN.search(cleaned)
            move = str(move_match.group(1) or "").strip() if move_match else ""

        if kind == "stat_change" and delta is None:
            delta_match = _STAT_DELTA_PATTERN.search(cleaned)
            if delta_match:
                delta = int(delta_match.group(2) or 0) * (-1 if delta_match.group(1) == "-" else 1)

        events.append(
            ParsedBattleEvent(
                kind=kind,
                line_index=index,
                line=cleaned,
                actor=actor,
                move=move,
                stat=stat_text,
                delta=delta if isinstance(delta, int) else None,
                hp_current=hp_current if isinstance(hp_current, int) else None,
                hp_total=hp_total if isinstance(hp_total, int) else None,
                value=value if isinstance(value, int) else None,
                extra=extra,
            )
        )

    battle_state = asdict(state)
    if worldboss.get("active_pokemon"):
        battle_state["active_pokemon"] = worldboss.get("active_pokemon")

    summary = {
        "raw_text": text,
        "line_count": len(lines),
        "event_count": len(events),
        "battle_state": battle_state,
        "worldboss": worldboss,
    }
    return events, summary
