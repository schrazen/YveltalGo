import re
from dataclasses import dataclass, field
from typing import Any

from discord import Message


@dataclass
class ParsedBattleState:
    raw_text: str
    active_pokemon: str | None
    boss_hp_percent: int | None
    ally_hp_percent: int | None
    move_buttons: dict[str, Any] = field(default_factory=dict)
    switch_buttons: dict[str, Any] = field(default_factory=dict)
    has_baton_pass: bool = False
    has_recover: bool = False
    special_stats_reduced: bool = False
    terminal_win: bool = False
    terminal_loss: bool = False


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _collect_text(message: Message) -> str:
    parts: list[str] = []
    if message.content:
        parts.append(message.content)

    for embed in message.embeds:
        if embed.title:
            parts.append(embed.title)
        if embed.description:
            parts.append(embed.description)
        if embed.footer and embed.footer.text:
            parts.append(embed.footer.text)
        for field in embed.fields:
            if field.name:
                parts.append(field.name)
            if field.value:
                parts.append(field.value)

    return "\n".join(parts)


def _iter_component_buttons(message: Message):
    for component in getattr(message, "components", []) or []:
        nested = getattr(component, "children", None)
        if nested is None:
            nested = getattr(component, "items", None)
        for child in nested or []:
            yield child


def _extract_hp(raw_text: str) -> tuple[int | None, int | None]:
    lowered = normalize(raw_text)
    matches = list(re.finditer(r"(\d{1,3})\s*%", lowered))
    if not matches:
        return None, None

    boss_hp = None
    ally_hp = None

    for match in matches:
        percent = int(match.group(1))
        if percent > 100:
            continue

        window_start = max(0, match.start() - 24)
        window_end = min(len(lowered), match.end() + 24)
        context = lowered[window_start:window_end]
        if "boss" in context or "enemy" in context:
            boss_hp = percent
        elif "your" in context or "you" in context or "ally" in context:
            ally_hp = percent

    if boss_hp is None:
        boss_hp = int(matches[0].group(1))
    if ally_hp is None and len(matches) > 1:
        ally_hp = int(matches[1].group(1))

    return boss_hp, ally_hp


def _extract_action_buttons(message: Message, known_team_names: list[str] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    move_buttons: dict[str, Any] = {}
    switch_buttons: dict[str, Any] = {}
    known_switch_targets = {normalize(name) for name in (known_team_names or []) if str(name or "").strip()}

    for child in _iter_component_buttons(message):
        label = normalize(getattr(child, "label", "") or "")
        custom_id = normalize(getattr(child, "custom_id", "") or "")
        key = label or custom_id
        if not key:
            raw_custom_id = getattr(child, "custom_id", "") or ""
            if not raw_custom_id:
                continue
            key = f"button_{raw_custom_id}"

        is_known_switch_target = any(target and target in key for target in known_switch_targets)
        if "switch" in key or "send" in key or is_known_switch_target:
            switch_buttons[key] = child
            continue

        move_buttons[key] = child

    return move_buttons, switch_buttons


def _extract_active_pokemon(raw_text: str, known_names: list[str]) -> str | None:
    lowered = normalize(raw_text)
    for name in known_names:
        if normalize(name) in lowered:
            return name

    return None


def parse_battle_state(message: Message, known_team_names: list[str]) -> ParsedBattleState:
    raw_text = _collect_text(message)
    boss_hp, ally_hp = _extract_hp(raw_text)
    move_buttons, switch_buttons = _extract_action_buttons(message, known_team_names)
    lowered = normalize(raw_text)

    terminal_win = (
        "the world boss has been defeated" in lowered
        or "you won the battle" in lowered
        or "victory" in lowered
    )
    terminal_loss = (
        "your team has been defeated" in lowered
        or "you lost the battle" in lowered
    )

    return ParsedBattleState(
        raw_text=raw_text,
        active_pokemon=_extract_active_pokemon(raw_text, known_team_names),
        boss_hp_percent=boss_hp,
        ally_hp_percent=ally_hp,
        move_buttons=move_buttons,
        switch_buttons=switch_buttons,
        has_baton_pass=("baton-pass" in move_buttons) or ("baton pass" in move_buttons),
        has_recover=("recover" in move_buttons),
        special_stats_reduced=(
            "sp. atk fell" in lowered
            or "sp atk fell" in lowered
            or "special attack fell" in lowered
            or "sp. def fell" in lowered
            or "sp def fell" in lowered
            or "special defense fell" in lowered
        ),
        terminal_win=terminal_win,
        terminal_loss=terminal_loss,
    )
