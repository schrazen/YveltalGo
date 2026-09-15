from __future__ import annotations

import json
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
LOG_PATH = BASE_DIR / "autofight_log.jsonl"
_MAX_EVENTS = 2500
_events: deque[dict[str, Any]] = deque(maxlen=_MAX_EVENTS)
_lock = threading.Lock()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(value: Any) -> str:
    try:
        return str(value)
    except Exception:
        return "<unprintable>"


def _load_recent_from_disk(max_lines: int = 1500) -> None:
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


def record_autofight_event(
    account: str,
    event: str,
    *,
    channel_id: int | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "ts": _utc_now_iso(),
        "account": _safe_str(account),
        "event": _safe_str(event),
        "channel_id": int(channel_id or 0),
        "details": details or {},
    }

    with _lock:
        _events.append(payload)

    try:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except Exception:
        pass


def get_autofight_events(limit: int = 250) -> list[dict[str, Any]]:
    with _lock:
        items = list(_events)

    limit = max(1, min(int(limit), 5000))
    return items[-limit:][::-1]


def clear_autofight_events(truncate_file: bool = False) -> None:
    with _lock:
        _events.clear()

    if truncate_file:
        try:
            LOG_PATH.write_text("", encoding="utf-8")
        except Exception:
            pass


def autofight_log_path() -> str:
    return str(LOG_PATH)
