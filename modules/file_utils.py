"""Fast file seeking and tailing utilities for large telemetry and log files."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_tail_bytes(file_path: str | Path, max_bytes: int = 65536) -> bytes:
    """Reads up to max_bytes from the end of a file without reading the entire file into memory."""
    path = Path(file_path)
    if not path.is_file():
        return b""

    try:
        file_size = path.stat().st_size
    except OSError:
        return b""

    if file_size == 0:
        return b""

    bytes_to_read = min(file_size, max_bytes)
    try:
        with open(path, "rb") as f:
            if bytes_to_read < file_size:
                f.seek(file_size - bytes_to_read)
            return f.read(bytes_to_read)
    except OSError:
        return b""


def read_tail_lines(
    file_path: str | Path,
    max_lines: int = 500,
    chunk_size: int = 65536,
) -> list[str]:
    """Reads the last `max_lines` from a text file efficiently by seeking backwards in chunks.

    Returns the lines in chronological order (top to bottom).
    """
    path = Path(file_path)
    if not path.is_file() or max_lines <= 0:
        return []

    try:
        file_size = path.stat().st_size
    except OSError:
        return []

    if file_size == 0:
        return []

    try:
        with open(path, "rb") as f:
            # If the file is small, read it directly
            if file_size <= chunk_size:
                data = f.read()
                return data.decode("utf-8", errors="replace").splitlines()[-max_lines:]

            # Otherwise, read backwards in binary chunks from the end
            remaining = file_size
            buffer = bytearray()
            newline_count = 0

            while remaining > 0 and newline_count <= max_lines:
                read_size = min(chunk_size, remaining)
                remaining -= read_size
                f.seek(remaining)
                chunk = f.read(read_size)
                buffer = chunk + buffer
                newline_count += chunk.count(b"\n")

            text = buffer.decode("utf-8", errors="replace")
            return text.splitlines()[-max_lines:]
    except OSError:
        return []


def read_tail_jsonl(
    file_path: str | Path,
    max_lines: int = 500,
    chunk_size: int = 65536,
) -> list[dict[str, Any]]:
    """Reads the last `max_lines` valid JSON objects from a .jsonl file in chronological order."""
    raw_lines = read_tail_lines(file_path, max_lines=max_lines * 2, chunk_size=chunk_size)
    events: list[dict[str, Any]] = []

    for line in raw_lines:
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except Exception:
            continue
        if isinstance(payload, dict):
            events.append(payload)

    return events[-max_lines:]
