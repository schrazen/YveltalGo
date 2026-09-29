import sys
import json
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

events_path = Path("logs/pokemeow_events.jsonl")
if events_path.exists():
    events = []
    with events_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.strip():
                try:
                    events.append(json.loads(line))
                except Exception:
                    pass

    print(f"=== POKEMEOW EVENTS ({len(events)} total) ===")
    cats = Counter(e.get("category") for e in events)
    for cat, count in cats.most_common():
        print(f"  {cat}: {count}")

    print("\n--- DETAILED UNHANDLED RESPONSES ---")
    unhandled = [e for e in events if e.get("category") == "unhandled_response"]
    for idx, e in enumerate(unhandled):
        raw = e.get("raw_text", "")
        details = e.get("details", {})
        headline = e.get("headline", "")
        mod = e.get("module", "")
        print(f"\n[Unhandled #{idx + 1}] Module: {mod} | Headline: {headline}")
        print(f"  Raw: {raw}")
        print(f"  Details: {details}")

    print("\n--- ALL COMPLICATIONS ---")
    comps = [e for e in events if e.get("is_complication")]
    for idx, e in enumerate(comps):
        print(f"[{idx + 1}] Category: {e.get('category')} | Module: {e.get('module')} | Headline: {e.get('headline')} | Raw: {e.get('raw_text', '')[:120]}")

runtime_log_path = Path("logs/pokegrinder_runtime.log")
if runtime_log_path.exists():
    print(f"\n=== POKEGRINDER RUNTIME LOG (tail 50 lines) ===")
    lines = runtime_log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    for l in lines[-50:]:
        print(l)

electron_log_path = Path("logs/electron_backend.log")
if electron_log_path.exists():
    print(f"\n=== ELECTRON BACKEND LOG (tail 50 lines) ===")
    lines = electron_log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    for l in lines[-50:]:
        print(l)
