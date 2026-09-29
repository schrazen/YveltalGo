import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

af_log = Path("logs/autofight_log.jsonl")
if af_log.exists():
    with af_log.open("r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    print(f"Total autofight log entries: {len(lines)}")
    for line in lines[-10000:]:
        if line.strip():
            d = json.loads(line)
            ts = d.get("ts", "")
            if "1554550287866273834" in line or "Baton pass." in line:
                ev = d.get("event", "")
                det = d.get("details", {})
                print(f"[{ts}] {ev}: {det}")
