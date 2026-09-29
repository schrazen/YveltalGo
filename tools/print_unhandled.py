import sys
import json
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

events_path = Path("logs/pokemeow_events.jsonl")
events = []
with events_path.open("r", encoding="utf-8", errors="ignore") as f:
    for line in f:
        if line.strip():
            try:
                events.append(json.loads(line))
            except Exception:
                pass

print(f"Total events: {len(events)}")
unhandled = [e for e in events if e.get("category") == "unhandled_response"]
print(f"Total unhandled: {len(unhandled)}\n")

for idx, e in enumerate(unhandled):
    raw = repr(e.get("raw_text", ""))
    hl = e.get("headline", "")
    mod = e.get("module", "")
    ts = e.get("ts", "")
    print(f"#{idx+1:02d} [{ts[:19]}] [{mod}] {raw[:110]}")
