"""Append-only file log so desktop/Electron users can inspect failures without a usable console."""
from __future__ import annotations

import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
RUNTIME_LOG_DIR = BASE_DIR / "logs"
RUNTIME_LOG_PATH = RUNTIME_LOG_DIR / "pokegrinder_runtime.log"

_logger: logging.Logger | None = None


def setup_runtime_file_logging() -> Path:
    """Idempotent; returns absolute log file path."""
    global _logger
    RUNTIME_LOG_DIR.mkdir(parents=True, exist_ok=True)
    lg = logging.getLogger("pokegrinder.runtime")
    if not any(isinstance(h, logging.FileHandler) for h in lg.handlers):
        fh = logging.FileHandler(RUNTIME_LOG_PATH, mode="a", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        )
        lg.addHandler(fh)
        lg.setLevel(logging.DEBUG)
        lg.propagate = False
    _logger = lg
    return RUNTIME_LOG_PATH


def runtime_log() -> logging.Logger:
    if _logger is None:
        setup_runtime_file_logging()
    return logging.getLogger("pokegrinder.runtime")


def _flush_runtime_log() -> None:
    for h in runtime_log().handlers:
        try:
            h.flush()
        except OSError:
            pass


def log_line(level: int, msg: str, *args) -> None:
    runtime_log().log(level, msg, *args)
    _flush_runtime_log()


def info(msg: str, *args) -> None:
    runtime_log().info(msg, *args)
    _flush_runtime_log()


def log_exception(where: str, exc: BaseException) -> None:
    import traceback

    runtime_log().error("%s: %s", where, exc)
    runtime_log().error("%s", traceback.format_exc())
    _flush_runtime_log()


def tail_log_file(max_lines: int = 120, max_bytes: int = 64_000) -> list[str]:
    path = RUNTIME_LOG_PATH
    if not path.is_file():
        return []
    try:
        raw = path.read_bytes()
        if len(raw) > max_bytes:
            raw = raw[-max_bytes:]
        text = raw.decode("utf-8", errors="replace")
        lines = text.splitlines()
        return lines[-max_lines:] if len(lines) > max_lines else lines
    except OSError:
        return ["(could not read log file)"]
