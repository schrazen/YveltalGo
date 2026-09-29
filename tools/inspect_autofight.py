import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

af_log = Path("logs/autofight_log.jsonl")
if af_log.exists():
    with af_log.open("r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    print(f"Total autofight log entries: {len(lines)}")
    for line in lines:
        if line.strip():
            d = json.loads(line)
            ts = d.get("ts", "")
            if ts >= "2026-09-29T17:30":
                ev = d.get("event", "")
                details = d.get("details", {})
                print(f"[{ts}] {ev}: {details}")
