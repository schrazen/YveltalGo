#!/usr/bin/env python3
"""
Session Log Analyzer for PokeGrinder.

Analyzes telemetry from logs/anti_detect_log.jsonl, assets/captcha_samples/, and stats.json
to evaluate bot performance over a specific duration (e.g., last 30m, 1h, 6h, or current session).

Usage:
    python tools/analyze_session.py [--minutes N] [--hours N] [--save] [--all]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from modules.file_utils import read_tail_jsonl
from modules.pokemeow_reader import get_session_complications_summary

ANTI_DETECT_LOG = BASE_DIR / "logs" / "anti_detect_log.jsonl"
CAPTCHA_OUTCOMES_LOG = BASE_DIR / "assets" / "captcha_samples" / "auto_solver_outcomes.jsonl"
OUTPUT_REPORT_PATH = BASE_DIR / "logs" / "session_analysis_latest.md"


def _parse_utc_iso(ts_str: str) -> datetime | None:
    if not ts_str:
        return None
    try:
        # Handle trailing Z or offsets
        cleaned = ts_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def collect_session_metrics(
    window_start: datetime | None = None,
    account_filter: str | None = None,
    max_lines: int = 15000,
) -> dict[str, Any]:
    """Scans telemetry logs within the given time window and compiles performance metrics."""
    events = read_tail_jsonl(ANTI_DETECT_LOG, max_lines=max_lines)
    captcha_events = read_tail_jsonl(CAPTCHA_OUTCOMES_LOG, max_lines=500) if CAPTCHA_OUTCOMES_LOG.exists() else []

    if not events:
        return {"error": "No telemetry logs found in anti_detect_log.jsonl"}

    filtered_events: list[dict[str, Any]] = []
    earliest_seen: datetime | None = None
    latest_seen: datetime | None = None

    for ev in events:
        ts = _parse_utc_iso(ev.get("ts", ""))
        if not ts:
            continue

        if account_filter and account_filter.lower() not in str(ev.get("account", "")).lower():
            continue

        if window_start and ts < window_start:
            continue

        filtered_events.append(ev)
        if earliest_seen is None or ts < earliest_seen:
            earliest_seen = ts
        if latest_seen is None or ts > latest_seen:
            latest_seen = ts

    # Hunting metrics
    encounters = 0
    catches = 0
    hunt_rarities: dict[str, int] = {}
    hunt_dispatches = 0

    # Fishing metrics
    fish_encounters = 0
    fish_catches = 0
    fish_escapes = 0
    cast_prompts = 0
    fish_dispatches = 0

    # Anti-detection metrics
    human_breaks = 0
    human_break_total_seconds = 0.0
    idle_pauses = 0
    idle_pause_total_seconds = 0.0
    action_skips = 0
    please_waits = 0
    typing_simulations = 0
    typing_total_seconds = 0.0
    hesitations = 0
    hesitation_total_seconds = 0.0

    # Captcha metrics from anti_detect_log
    captchas_detected = 0
    captchas_resolved = 0

    for ev in filtered_events:
        evt = str(ev.get("event", ""))
        details = ev.get("details", {}) or {}

        if evt == "encounter":
            encounters += 1
        elif evt == "catch":
            catches += 1
            rarity = str(details.get("rarity", "Unknown"))
            hunt_rarities[rarity] = hunt_rarities.get(rarity, 0) + 1
        elif evt == "dispatch_pokemon":
            hunt_dispatches += 1
        elif evt == "fish_encounter":
            fish_encounters += 1
        elif evt == "fish_catch":
            fish_catches += 1
        elif evt == "miss_or_escape":
            fish_escapes += 1
        elif evt == "cast_prompt":
            cast_prompts += 1
        elif evt == "dispatch_fish_spawn":
            fish_dispatches += 1
        elif evt == "human_break":
            human_breaks += 1
            human_break_total_seconds += float(details.get("seconds", 0) or 0)
        elif evt == "idle_randomness":
            idle_pauses += 1
            idle_pause_total_seconds += float(details.get("seconds", 0) or 0)
        elif evt == "action_skip" or evt == "cycle_skipped_distraction":
            action_skips += 1
        elif evt == "please_wait":
            please_waits += 1
        elif evt == "typing_simulated":
            typing_simulations += 1
            typing_total_seconds += float(details.get("duration_seconds", 0) or 0)
        elif "hesitation" in evt or "pause" in evt:
            hesitations += 1
            hesitation_total_seconds += float(details.get("seconds", 0) or 0)
        elif evt == "captcha_detected":
            captchas_detected += 1
        elif evt == "captcha_resolved":
            captchas_resolved += 1

    # Captcha solver file metrics
    solver_resolved = 0
    solver_failed = 0
    for c_ev in captcha_events:
        c_ts = _parse_utc_iso(c_ev.get("ts_utc", ""))
        if window_start and c_ts and c_ts < window_start:
            continue
        outcome = str(c_ev.get("outcome", "")).lower()
        if "resolved" in outcome:
            solver_resolved += 1
        elif "failed" in outcome:
            solver_failed += 1

    # Duration calculations
    elapsed_seconds = 0.0
    if earliest_seen and latest_seen:
        elapsed_seconds = max(1.0, (latest_seen - earliest_seen).total_seconds())
    elapsed_hours = elapsed_seconds / 3600.0

    hunt_catch_rate = round((catches / encounters * 100), 1) if encounters > 0 else 0.0
    fish_catch_rate = round((fish_catches / fish_encounters * 100), 1) if fish_encounters > 0 else 0.0
    encounters_per_hour = round(encounters / elapsed_hours, 1) if elapsed_hours > 0 else 0.0
    catches_per_hour = round(catches / elapsed_hours, 1) if elapsed_hours > 0 else 0.0

    avg_typing_ms = round((typing_total_seconds / typing_simulations * 1000), 1) if typing_simulations > 0 else 0.0
    avg_hesitation_ms = round((hesitation_total_seconds / hesitations * 1000), 1) if hesitations > 0 else 0.0

    # Automated Diagnosis & Recommendations
    insights: list[str] = []
    recommendations: list[str] = []

    if encounters > 0:
        if hunt_catch_rate >= 80.0:
            insights.append(f"Hunting catch conversion is excellent at {hunt_catch_rate}% ({catches}/{encounters}).")
        elif hunt_catch_rate >= 60.0:
            insights.append(f"Hunting catch conversion is normal at {hunt_catch_rate}%. Most misses are Pokeball RNG on Uncommons/Rares.")
        else:
            insights.append(f"Hunting catch conversion is low ({hunt_catch_rate}%).")
            recommendations.append("Check ball settings: consider upgrading Uncommon/Rare to Greatball or Ultraball, or inspect if balls ran out.")

    if fish_encounters > 0:
        if fish_catch_rate >= 70.0:
            insights.append(f"Fishing catch conversion is solid at {fish_catch_rate}% ({fish_catches}/{fish_encounters}).")
        else:
            insights.append(f"Fishing catch conversion is {fish_catch_rate}%. {fish_escapes} fish escaped.")

    if please_waits > 10:
        recommendations.append(f"Detected {please_waits} 'Please wait' cooldown hits. Pacing may be slightly fast; consider bumping HuntingDelayMin by 0.5s.")

    total_solver_attempts = solver_resolved + solver_failed
    if total_solver_attempts > 0:
        captcha_solve_rate = round((solver_resolved / total_solver_attempts * 100), 1)
        insights.append(f"Captcha auto-solver success rate: {captcha_solve_rate}% ({solver_resolved}/{total_solver_attempts}).")
        if captcha_solve_rate < 80.0:
            recommendations.append("Captcha solve rate is under 80%. Check assets/captcha_samples/solver_tuning.json or update sample labels.")
    elif captchas_detected > 0:
        insights.append(f"{captchas_detected} captchas detected; {captchas_resolved} resolved.")

    if human_breaks > 0:
        break_mins = round(human_break_total_seconds / 60.0, 1)
        insights.append(f"Anti-detection breaks taken: {human_breaks} breaks ({break_mins} mins total downtime).")

    # In-Game Complications & Event Journal
    complications = get_session_complications_summary(since_dt=window_start, account=account_filter)

    if complications["flee_count"] > 0:
        insights.append(f"{complications['flee_count']} encounters fled in this window (Breakdown by ball: {complications['flee_breakdown_by_ball']}).")
        # Check if Rares fled on standard pokeball
        rare_flees_on_pb = sum(
            1 for f in complications["flees"]
            if str(f.get("details", {}).get("rarity", "")).lower() in {"rare", "super rare", "legendary", "shiny", "golden"}
            and str(f.get("details", {}).get("ball_used", "")).lower() in {"pb", "pokeball"}
        )
        if rare_flees_on_pb > 0:
            recommendations.append(f"{rare_flees_on_pb} high-tier encounters fled using standard Pokéballs. Upgrade config.balls['Rare'] to Greatball (gb) or Ultraball (ub).")

    if complications["ball_starvation_count"] > 0:
        insights.append(f"CRITICAL: Encountered {complications['ball_starvation_count']} ball starvation alerts (account ran out of balls during encounter).")
        recommendations.append("Increase auto_buy amounts in config.json to maintain a larger reserve of Pokéballs.")

    if complications["coin_starvation_count"] > 0:
        insights.append(f"WARNING: Auto-buy purchase failed {complications['coin_starvation_count']} times due to insufficient Pokécoins.")
        recommendations.append("Account balance is low on Pokécoins. Grind battles or lower auto_buy target quantities.")

    if complications.get("active_encounter_block_count", 0) > 0:
        insights.append(f"WARNING: Encountered {complications['active_encounter_block_count']} active encounter overlap blocks ('Please catch the Pokemon you spawned first').")
        recommendations.append("Active encounter overlap detected. Bot auto-recovery waited and safely resumed; consider slightly increasing hunting delay.")

    if complications.get("casket_timeout_count", 0) > 0:
        insights.append(f"WARNING: {complications['casket_timeout_count']} Sunken Caskets timed out.")
        recommendations.append("Sunken Casket auto-salvage is now active to automatically click treasure boxes before they sink away.")

    if complications.get("shop_error_count", 0) > 0:
        insights.append(f"WARNING: {complications['shop_error_count']} shop item purchase errors ('item not in shop').")

    if complications["unhandled_response_count"] > 0:
        insights.append(f"Recorded {complications['unhandled_response_count']} unhandled PokéMeow responses (stored in logs/pokemeow_events.jsonl for diagnostics).")

    if complications["special_events_count"] > 0:
        insights.append(f"Tracked {complications['special_events_count']} special in-game events (quests, egg hatch/incubation, held items).")

    return {
        "start_utc": earliest_seen.isoformat() if earliest_seen else "N/A",
        "end_utc": latest_seen.isoformat() if latest_seen else "N/A",
        "duration_minutes": round(elapsed_seconds / 60.0, 1),
        "duration_hours": round(elapsed_hours, 2),
        "hunting": {
            "encounters": encounters,
            "catches": catches,
            "missed": max(0, encounters - catches),
            "catch_rate_percent": hunt_catch_rate,
            "encounters_per_hour": encounters_per_hour,
            "catches_per_hour": catches_per_hour,
            "rarity_breakdown": hunt_rarities,
            "dispatches": hunt_dispatches,
        },
        "fishing": {
            "casts": cast_prompts,
            "encounters": fish_encounters,
            "catches": fish_catches,
            "escapes": fish_escapes,
            "catch_rate_percent": fish_catch_rate,
            "dispatches": fish_dispatches,
        },
        "complications": complications,
        "anti_detection": {
            "human_breaks": human_breaks,
            "human_break_minutes": round(human_break_total_seconds / 60.0, 1),
            "idle_pauses": idle_pauses,
            "idle_pause_seconds": round(idle_pause_total_seconds, 1),
            "action_skips": action_skips,
            "typing_simulations": typing_simulations,
            "avg_typing_ms": avg_typing_ms,
            "avg_hesitation_ms": avg_hesitation_ms,
            "please_wait_cooldown_hits": please_waits,
        },
        "captcha": {
            "detected": captchas_detected,
            "resolved": captchas_resolved,
            "solver_resolved": solver_resolved,
            "solver_failed": solver_failed,
        },
        "insights": insights,
        "recommendations": recommendations,
    }


def format_markdown_report(metrics: dict[str, Any]) -> str:
    """Formats session metrics into a clean markdown document."""
    if "error" in metrics:
        return f"# Session Analysis\n\n**Error:** {metrics['error']}\n"

    h = metrics["hunting"]
    f = metrics["fishing"]
    ad = metrics["anti_detection"]
    c = metrics["captcha"]
    comp = metrics.get("complications", {})

    lines = [
        "# PokeGrinder Session Analysis Report",
        "",
        f"- **Time Window**: `{metrics['start_utc']}` to `{metrics['end_utc']}`",
        f"- **Duration**: **{metrics['duration_minutes']} minutes** ({metrics['duration_hours']} hours)",
        "",
        "---",
        "",
        "## 1. Hunting Performance",
        f"- **Encounters**: `{h['encounters']}` (~`{h['encounters_per_hour']}/hr`)",
        f"- **Catches**: `{h['catches']}` (~`{h['catches_per_hour']}/hr`)",
        f"- **Missed / Ran Away**: `{h['missed']}`",
        f"- **Catch Conversion Rate**: **{h['catch_rate_percent']}%**",
    ]

    if h["rarity_breakdown"]:
        lines.append("- **Catches by Rarity**:")
        for r, cnt in sorted(h["rarity_breakdown"].items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  - **{r}**: {cnt}")

    lines.extend([
        "",
        "## 2. In-Game Complications & Flee Diagnostics",
        f"- **Total Complications Logged**: `{comp.get('total_complications', 0)}`",
        f"- **Encounter Flees**: `{comp.get('flee_count', 0)}`",
        f"- **Ball Starvation Alerts**: `{comp.get('ball_starvation_count', 0)}`",
        f"- **Coin Starvation Alerts**: `{comp.get('coin_starvation_count', 0)}`",
        f"- **Cooldown Blocks**: `{comp.get('cooldown_block_count', 0)}`",
        f"- **Daily Limits**: `{comp.get('daily_limit_count', 0)}`",
    ])

    flee_balls = comp.get("flee_breakdown_by_ball", {})
    if flee_balls:
        lines.append("- **Flees by Ball Thrown**:")
        for b, cnt in sorted(flee_balls.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  - **{b}**: {cnt}")

    flee_rarities = comp.get("flee_breakdown_by_rarity", {})
    if flee_rarities:
        lines.append("- **Flees by Encounter Rarity**:")
        for r, cnt in sorted(flee_rarities.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  - **{r}**: {cnt}")

    flee_pokemon = comp.get("flee_breakdown_by_pokemon", {})
    if flee_pokemon:
        top_fled = sorted(flee_pokemon.items(), key=lambda x: x[1], reverse=True)[:5]
        lines.append("- **Most Frequent Flees**:")
        for p, cnt in top_fled:
            lines.append(f"  - **{p}**: {cnt}")

    unhandled = comp.get("unhandled_responses", [])
    if unhandled:
        lines.append(f"- **Unhandled PokéMeow Prompts ({len(unhandled)})**:")
        for u in unhandled[:3]:
            lines.append(f"  - `{u.get('headline', '')}`")

    lines.extend([
        "",
        "## 3. Special In-Game Events & Discoveries",
        f"- **Special Events Logged**: `{comp.get('special_events_count', 0)}`",
    ])
    events_list = comp.get("special_events", [])
    if events_list:
        for ev in events_list[:5]:
            lines.append(f"- `[{ev.get('category', '')}]` {ev.get('headline', '')}")

    lines.extend([
        "",
        "## 4. Fishing Performance",
        f"- **Cast Prompts**: `{f['casts']}`",
        f"- **Fish Encounters**: `{f['encounters']}`",
        f"- **Fish Caught**: `{f['catches']}`",
        f"- **Got Away**: `{f['escapes']}`",
        f"- **Fishing Catch Rate**: **{f['catch_rate_percent']}%**",
        "",
        "## 5. Anti-Detection & Timing Telemetry",
        f"- **Silent Human Breaks**: `{ad['human_breaks']}` ({ad['human_break_minutes']} mins total)",
        f"- **Casual Idle Distractions**: `{ad['idle_pauses']}` ({ad['idle_pause_seconds']}s total)",
        f"- **Simulated Typing Events**: `{ad['typing_simulations']}` (avg `{ad['avg_typing_ms']}ms`)",
        f"- **Cognitive Reflex Hesitations**: Avg `{ad['avg_hesitation_ms']}ms`",
        f"- **Please Wait / Cooldown Clashes**: `{ad['please_wait_cooldown_hits']}`",
        "",
        "## 6. Captcha Health",
        f"- **Captchas Detected**: `{c['detected']}`",
        f"- **Captchas Resolved**: `{c['resolved']}` (Solver: {c['solver_resolved']} solved, {c['solver_failed']} failed)",
        "",
        "---",
        "",
        "## 7. Insights & Observations",
    ])

    if metrics["insights"]:
        for ins in metrics["insights"]:
            lines.append(f"- {ins}")
    else:
        lines.append("- Session data recorded normally with no anomalous events.")

    lines.extend([
        "",
        "## 8. Recommended Next Actions",
    ])

    if metrics["recommendations"]:
        for rec in metrics["recommendations"]:
            lines.append(f"- {rec}")
    else:
        lines.append("- Bot is operating at optimal efficiency with no immediate adjustments required.")

    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Analyze PokeGrinder session telemetry logs.")
    parser.add_argument("--minutes", type=int, default=None, help="Analyze the last N minutes.")
    parser.add_argument("--hours", type=float, default=None, help="Analyze the last N hours.")
    parser.add_argument("--all", action="store_true", help="Analyze all available recent telemetry lines.")
    parser.add_argument("--account", type=str, default=None, help="Filter by specific username / account.")
    parser.add_argument("--save", action="store_true", default=True, help="Save markdown report to logs/session_analysis_latest.md")
    parser.add_argument("--json", action="store_true", help="Output raw JSON metrics instead of text.")

    args = parser.parse_args()

    window_start: datetime | None = None
    now = datetime.now(timezone.utc)

    if args.minutes:
        window_start = now - timedelta(minutes=args.minutes)
    elif args.hours:
        window_start = now - timedelta(hours=args.hours)
    elif not args.all:
        # Default: last 60 minutes
        window_start = now - timedelta(minutes=60)

    metrics = collect_session_metrics(window_start=window_start, account_filter=args.account)

    if args.json:
        print(json.dumps(metrics, indent=2))
        return

    report = format_markdown_report(metrics)
    print(report)

    if args.save:
        OUTPUT_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_REPORT_PATH.write_text(report, encoding="utf-8")
        print(f"\n[Report saved to {OUTPUT_REPORT_PATH}]")


if __name__ == "__main__":
    main()
