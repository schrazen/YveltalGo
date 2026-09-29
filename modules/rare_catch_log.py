from __future__ import annotations

import json
import re
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
LOG_PATH = BASE_DIR / "rare_catches.jsonl"
_MAX_EVENTS = 5000
_events: deque[dict[str, Any]] = deque(maxlen=_MAX_EVENTS)
_lock = threading.Lock()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(value: Any) -> str:
    try:
        return str(value)
    except Exception:
        return "<unprintable>"


def _sanitize_label(value: Any) -> str:
    text = _safe_str(value)
    text = re.sub(r"<a?:[a-z0-9_]+:\d+>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r":[a-z0-9_]+:", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"[*_`~]+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" .!,:;*-_\n\t")


def _coerce_name_from_slug(slug: str) -> str:
    clean_slug = _safe_str(slug).strip().strip("-")
    if not clean_slug:
        return "Unknown"
    return " ".join(part.capitalize() for part in clean_slug.split("-") if part)


def _dedupe_key(row: dict[str, Any]) -> tuple[Any, ...]:
    source_mid = int(row.get("source_message_id", 0) or 0)
    account = str(row.get("account", "") or "")
    channel_id = int(row.get("channel_id", 0) or 0)
    rarity = str(row.get("rarity", "") or "")
    slug = str(row.get("pokemon_slug", "") or "")
    if source_mid > 0:
        return ("mid", account, channel_id, source_mid)

    # Fallback for historical rows without message ids: collapse same mon/user/channel/rarity within same second.
    ts_value = str(row.get("ts", "") or "")
    ts_second = ts_value[:19]  # ISO yyyy-mm-ddTHH:MM:SS
    return ("legacy", account, channel_id, rarity, slug, ts_second)


def _load_recent_from_disk(max_lines: int = 2000) -> None:
    if not LOG_PATH.exists():
        return

    try:
        lines = LOG_PATH.read_text(encoding="utf-8").splitlines()
    except Exception:
        return

    for line in lines[-max_lines:]:
        try:
            payload = json.loads(line)
        except Exception:
            continue
        _events.append(payload)


_load_recent_from_disk()


def record_rare_catch_event(
    account: str,
    *,
    rarity: str,
    pokemon_name: str,
    pokemon_slug: str,
    channel_id: int | None = None,
    source_message_id: int | None = None,
) -> None:
    source_mid = int(source_message_id or 0)
    if source_mid > 0:
        with _lock:
            for existing in reversed(_events):
                if int(existing.get("source_message_id", 0) or 0) != source_mid:
                    continue
                if int(existing.get("channel_id", 0) or 0) != int(channel_id or 0):
                    continue
                if str(existing.get("account", "")) != _safe_str(account):
                    continue
                # Already recorded this catch event.
                return

    payload: dict[str, Any] = {
        "ts": _utc_now_iso(),
        "account": _safe_str(account),
        "channel_id": int(channel_id or 0),
        "rarity": _safe_str(rarity),
        "pokemon_name": _safe_str(pokemon_name),
        "pokemon_slug": _safe_str(pokemon_slug),
        "source_message_id": source_mid,
    }

    with _lock:
        _events.append(payload)

    try:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except Exception:
        pass


def get_recent_rare_catch_events(limit: int = 200) -> list[dict[str, Any]]:
    with _lock:
        items = list(_events)

    limit = max(1, min(int(limit), 5000))
    recent = items[-limit:][::-1]
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()

    for row in recent:
        key = _dedupe_key(row)
        if key in seen:
            continue
        seen.add(key)

        payload = dict(row)
        payload["pokemon_name"] = _sanitize_label(payload.get("pokemon_name", ""))
        payload["rarity"] = _sanitize_label(payload.get("rarity", ""))

        if not str(payload.get("pokemon_name", "") or ""):
            payload["pokemon_name"] = _coerce_name_from_slug(str(payload.get("pokemon_slug", "") or ""))

        deduped.append(payload)

    return deduped


def rare_catch_log_path() -> str:
    return str(LOG_PATH)