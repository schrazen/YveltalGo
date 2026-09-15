from __future__ import annotations

import json
import re
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
LOG_PATH = BASE_DIR / "retrieved_items.jsonl"
_MAX_EVENTS = 6000
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


def _load_recent_from_disk(max_lines: int = 2500) -> None:
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


def record_retrieved_item_event(
    account: str,
    *,
    pokemon_name: str,
    pokemon_slug: str,
    item_name: str,
    item_slug: str,
    rarity: str,
    channel_id: int | None = None,
) -> None:
    payload: dict[str, Any] = {
        "ts": _utc_now_iso(),
        "account": _safe_str(account),
        "channel_id": int(channel_id or 0),
        "pokemon_name": _safe_str(pokemon_name),
        "pokemon_slug": _safe_str(pokemon_slug),
        "item_name": _safe_str(item_name),
        "item_slug": _safe_str(item_slug),
        "rarity": _safe_str(rarity),
    }

    with _lock:
        _events.append(payload)

    try:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except Exception:
        pass


def get_recent_retrieved_item_events(limit: int = 200) -> list[dict[str, Any]]:
    with _lock:
        items = list(_events)

    limit = max(1, min(int(limit), 5000))
    recent = items[-limit:][::-1]
    sanitized: list[dict[str, Any]] = []
    for row in recent:
        payload = dict(row)
        payload["item_name"] = _sanitize_label(payload.get("item_name", ""))
        payload["pokemon_name"] = _sanitize_label(payload.get("pokemon_name", ""))
        sanitized.append(payload)
    return sanitized


def retrieved_item_log_path() -> str:
    return str(LOG_PATH)