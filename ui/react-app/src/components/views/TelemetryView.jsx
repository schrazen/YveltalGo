import React, { useState, useMemo } from "react";
import {
  TerminalIcon,
  RefreshIcon,
  SearchIcon,
  CopyIcon,
  CheckIcon,
  ShieldIcon,
  ActivityIcon,
  DownloadIcon,
  ClockIcon,
} from "../Icons.jsx";
import { formatRelativeTime } from "../../utils/helpers.js";

function formatHumaneSummary(ev) {
  if (!ev) return "Empty event";
  if (typeof ev === "string") return ev;
  if (ev.message && typeof ev.message === "string") return ev.message;

  const d = ev.details;
  const evt = String(ev.event || ev.action || ev.event_type || "").toLowerCase();

  if (evt === "catch") {
    const name = d?.pokemon_name || "Pokemon";
    const rarity = d?.rarity ? ` (${d.rarity})` : "";
    const coins = d?.coins_total ? ` • Coins: ${Number(d.coins_total).toLocaleString()}` : "";
    const item = d?.retrieved_item ? ` • Found: ${d.retrieved_item}` : "";
    return `Captured ${name}${rarity}${coins}${item}`;
  }

  if (evt === "encounter") {
    const name = d?.pokemon_name || "Pokemon";
    const rarity = d?.rarity ? ` (${d.rarity})` : "";
    return `Encountered wild ${name}${rarity}`;
  }

  if (evt === "typing_simulated") {
    return `Human typing simulated: ${d?.simulated_chars ?? 0} chars (${d?.duration_seconds ?? 0}s duration)`;
  }

  if (evt.includes("hesitation")) {
    return `Natural hesitation delay: ${d?.seconds ?? 0}s on ${d?.rarity || "action"}`;
  }

  if (evt === "dispatch_pokemon") {
    return `Action loop dispatched (${d?.source || "cycle"}) • Cooldown: ${d?.hunting_cooldown ?? 0}s`;
  }

  if (evt.includes("captcha")) {
    return `Verification security event: ${d?.reason || d?.message || "Detection alert"}`;
  }

  if (evt.includes("break")) {
    return `Pacing break: ${d?.duration_minutes ?? d?.duration_seconds ?? 0}s cooldown`;
  }

  if (typeof d === "string") return d;
  if (d && typeof d === "object" && Object.keys(d).length > 0) {
    return Object.entries(d)
      .map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`)
      .join(" • ");
  }

  return ev.event || ev.action || ev.event_type || "System operation";
}

function getEventStyle(ev) {
  const mod = String(ev?.module || "").toLowerCase();
  const evt = String(ev?.event || ev?.action || ev?.event_type || "").toLowerCase();

  if (evt.includes("err") || evt.includes("fail") || mod.includes("err")) {
    return {
      badgeBg: "bg-rose-500/10 text-rose-300 border-rose-500/30",
      dotBg: "bg-rose-400",
      pill: "Error",
    };
  }
  if (evt.includes("captcha") || mod.includes("captcha")) {
    return {
      badgeBg: "bg-amber-500/10 text-amber-300 border-amber-500/30",
      dotBg: "bg-amber-400",
      pill: "Captcha",
    };
  }
  if (evt.includes("break") || mod.includes("break")) {
    return {
      badgeBg: "bg-indigo-500/10 text-indigo-300 border-indigo-500/30",
      dotBg: "bg-indigo-400",
      pill: "Pacing",
    };
  }
  if (mod.includes("human")) {
    return {
      badgeBg: "bg-sky-500/10 text-sky-300 border-sky-500/30",
      dotBg: "bg-sky-400",
      pill: "Humanizer",
    };
  }
  if (evt === "catch") {
    return {
      badgeBg: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
      dotBg: "bg-emerald-400",
      pill: "Catch",
    };
  }
  if (mod.includes("hunt")) {
    return {
      badgeBg: "bg-teal-500/10 text-teal-300 border-teal-500/30",
      dotBg: "bg-teal-400",
      pill: "Hunting",
    };
  }
  if (mod.includes("fish")) {
    return {
      badgeBg: "bg-cyan-500/10 text-cyan-300 border-cyan-500/30",
      dotBg: "bg-cyan-400",
      pill: "Fishing",
    };
  }
  if (mod.includes("fight") || mod.includes("battle")) {
    return {
      badgeBg: "bg-orange-500/10 text-orange-300 border-orange-500/30",
      dotBg: "bg-orange-400",
      pill: "Combat",
    };
  }
  return {
    badgeBg: "bg-slate-800 text-slate-300 border-slate-700/60",
    dotBg: "bg-slate-400",
    pill: mod || "Telemetry",
  };
}

export default function TelemetryView({
  antiDetect = { events: [], count: 0, log_path: "" },
  telemetrySearch,
  setTelemetrySearch,
  onRefreshTelemetry,
  onClearTelemetry,
  busyAction,
  antiDetectLimit,
  setAntiDetectLimit,
}) {
  const [filterType, setFilterType] = useState("all");
  const [expandedIndex, setExpandedIndex] = useState(null);
  const [copiedIndex, setCopiedIndex] = useState(null);

  const rawEvents = Array.isArray(antiDetect?.events) ? antiDetect.events : [];

  // Summary Metrics
  const summaryMetrics = useMemo(() => {
    let humanizerCount = 0;
    let catchesCount = 0;
    let securityCount = 0;

    rawEvents.forEach((ev) => {
      const mod = String(ev?.module || "").toLowerCase();
      const evt = String(ev?.event || ev?.action || "").toLowerCase();
      if (mod.includes("human") || evt.includes("typing") || evt.includes("hesitation")) {
        humanizerCount++;
      } else if (evt === "catch") {
        catchesCount++;
      } else if (evt.includes("captcha") || evt.includes("break") || mod.includes("guard")) {
        securityCount++;
      }
    });

    return {
      total: rawEvents.length,
      humanizerCount,
      catchesCount,
      securityCount,
    };
  }, [rawEvents]);

  // Filtered Events
  const filteredEvents = useMemo(() => {
    return rawEvents.filter((ev) => {
      if (!ev) return false;

      // Type filter
      if (filterType !== "all") {
        const mod = String(ev.module || "").toLowerCase();
        const action = String(ev.event || ev.action || ev.event_type || "").toLowerCase();
        const combined = `${mod} ${action}`;
        if (!combined.includes(filterType.toLowerCase())) return false;
      }

      // Search query filter
      if (telemetrySearch) {
        const q = telemetrySearch.toLowerCase();
        const text = `${ev.account || ""} ${ev.module || ""} ${ev.event || ""} ${JSON.stringify(ev.details || "")}`.toLowerCase();
        return text.includes(q);
      }

      return true;
    });
  }, [rawEvents, filterType, telemetrySearch]);

  const handleCopyJson = (ev, idx) => {
    try {
      navigator.clipboard.writeText(JSON.stringify(ev, null, 2));
      setCopiedIndex(idx);
      setTimeout(() => setCopiedIndex(null), 1800);
    } catch {
      // ignore
    }
  };

  const handleExportJson = () => {
    try {
      const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(filteredEvents, null, 2));
      const downloadAnchor = document.createElement("a");
      downloadAnchor.setAttribute("href", dataStr);
      downloadAnchor.setAttribute("download", `telemetry_export_${Date.now()}.json`);
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();
      downloadAnchor.remove();
    } catch {
      // ignore
    }
  };

  return (
    <div className="space-y-4">
      {/* Header & Quick Stats */}
      <div className="glass-panel p-5 rounded-2xl border border-rose-950/40 shadow-xl space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-rose-950/40 pb-3">
          <div>
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <TerminalIcon className="w-4 h-4 text-rose-500" />
              <span>Anti-Detection & System Telemetry</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Live audit stream of pacing delays, keystroke humanizers, and security compliance.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleExportJson}
              disabled={filteredEvents.length === 0}
              className="px-3 py-1.5 rounded-xl text-xs font-medium bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-700/80 flex items-center gap-1.5 transition-colors disabled:opacity-50"
              title="Export filtered events as JSON"
            >
              <DownloadIcon className="w-3.5 h-3.5" />
              <span>Export</span>
            </button>

            <button
              onClick={onRefreshTelemetry}
              className="px-3 py-1.5 rounded-xl text-xs font-medium bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-700/80 flex items-center gap-1.5 transition-colors"
            >
              <RefreshIcon className="w-3.5 h-3.5" />
              <span>Refresh</span>
            </button>

            <button
              onClick={onClearTelemetry}
              disabled={busyAction !== ""}
              className="px-3 py-1.5 rounded-xl text-xs font-medium bg-rose-950/30 text-rose-300 border border-rose-900/40 hover:bg-rose-900/50 transition-colors"
            >
              Clear Logs
            </button>
          </div>
        </div>

        {/* Micro Telemetry Metric Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80">
            <span className="text-[11px] font-medium text-slate-400 block">Loaded Logs</span>
            <span className="text-lg font-bold text-white font-mono mt-0.5 block">
              {summaryMetrics.total.toLocaleString()}
            </span>
          </div>

          <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80">
            <span className="text-[11px] font-medium text-slate-400 block">Humanizer Delays</span>
            <span className="text-lg font-bold text-sky-400 font-mono mt-0.5 block">
              {summaryMetrics.humanizerCount.toLocaleString()}
            </span>
          </div>

          <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80">
            <span className="text-[11px] font-medium text-slate-400 block">Confirmed Catches</span>
            <span className="text-lg font-bold text-emerald-400 font-mono mt-0.5 block">
              {summaryMetrics.catchesCount.toLocaleString()}
            </span>
          </div>

          <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80">
            <span className="text-[11px] font-medium text-slate-400 block">Safety Breaks & Guards</span>
            <span className="text-lg font-bold text-indigo-400 font-mono mt-0.5 block">
              {summaryMetrics.securityCount.toLocaleString()}
            </span>
          </div>
        </div>

        {/* Filter and Search Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 pt-1">
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
            {[
              { id: "all", label: "All" },
              { id: "hunt", label: "Hunting" },
              { id: "fish", label: "Fishing" },
              { id: "fight", label: "Combat" },
              { id: "human", label: "Humanizer" },
              { id: "break", label: "Pacing" },
              { id: "captcha", label: "Safety" },
            ].map((chip) => (
              <button
                key={chip.id}
                onClick={() => setFilterType(chip.id)}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                  filterType === chip.id
                    ? "bg-rose-600/90 text-white shadow-sm font-semibold"
                    : "bg-slate-900 text-slate-400 hover:text-white border border-slate-800"
                }`}
              >
                {chip.label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2">
            <div className="relative">
              <input
                type="text"
                value={telemetrySearch}
                onChange={(e) => setTelemetrySearch(e.target.value)}
                placeholder="Search audit trail..."
                className="bg-slate-900 border border-slate-700/80 rounded-xl px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-rose-500 w-52"
              />
            </div>

            <select
              value={antiDetectLimit}
              onChange={(e) => setAntiDetectLimit(Number(e.target.value))}
              className="bg-slate-900 border border-slate-700/80 text-xs text-slate-300 rounded-xl px-2.5 py-1.5 focus:outline-none focus:border-rose-500"
            >
              <option value={100}>100 logs</option>
              <option value={200}>200 logs</option>
              <option value={500}>500 logs</option>
              <option value={1000}>1,000 logs</option>
            </select>
          </div>
        </div>
      </div>

      {/* Log Feed */}
      <div className="glass-panel p-5 rounded-2xl border border-rose-950/40 shadow-xl space-y-2">
        <div className="flex items-center justify-between text-xs text-slate-400 pb-2 border-b border-rose-950/40">
          <span className="font-semibold text-slate-300 text-xs flex items-center gap-2">
            <span>Audit Trail</span>
            <span className="px-2 py-0.2 rounded-full bg-slate-800 text-[10px] text-slate-400 font-mono">
              {filteredEvents.length} events
            </span>
          </span>
          <span className="font-mono text-[10px] text-slate-500 truncate max-w-sm">
            {antiDetect?.log_path || "logs/anti_detect_log.jsonl"}
          </span>
        </div>

        <div className="overflow-y-auto max-h-[62vh] space-y-1.5 font-mono text-xs pr-1">
          {filteredEvents.length === 0 && (
            <div className="py-14 text-center text-slate-500 text-xs">
              No telemetry events match your criteria.
            </div>
          )}

          {filteredEvents.map((ev, idx) => {
            const style = getEventStyle(ev);
            const summary = formatHumaneSummary(ev);
            const isExpanded = expandedIndex === idx;
            const isCopied = copiedIndex === idx;
            const account = ev?.account || "system";
            const timeStr = formatRelativeTime(ev?.ts || ev?.timestamp);
            const exactTime = ev?.ts ? new Date(ev.ts).toLocaleTimeString() : "";

            return (
              <div
                key={idx}
                className="rounded-xl bg-slate-950/60 border border-slate-900/90 hover:border-slate-800 transition-colors overflow-hidden"
              >
                <div
                  onClick={() => setExpandedIndex(isExpanded ? null : idx)}
                  className="p-2.5 flex items-center justify-between gap-3 cursor-pointer select-none"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span className="flex items-center gap-1.5 shrink-0">
                      <span className={`w-1.5 h-1.5 rounded-full ${style.dotBg}`} />
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${style.badgeBg}`}
                      >
                        {style.pill}
                      </span>
                    </span>

                    {account && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-900 text-slate-400 border border-slate-800 shrink-0">
                        @{account}
                      </span>
                    )}

                    <span className="text-slate-300 truncate text-[11px]">
                      {summary}
                    </span>
                  </div>

                  <div className="flex items-center gap-2.5 shrink-0">
                    <span
                      title={exactTime}
                      className="text-[10px] text-slate-500 whitespace-nowrap font-sans"
                    >
                      {timeStr}
                    </span>
                  </div>
                </div>

                {/* Collapsible JSON payload detail */}
                {isExpanded && (
                  <div className="border-t border-slate-900 bg-slate-950/90 p-3.5 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-sans text-slate-400 font-medium">
                        Raw Event Payload
                      </span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleCopyJson(ev, idx);
                        }}
                        className="px-2 py-1 rounded text-[10px] font-sans bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 flex items-center gap-1 transition-colors"
                      >
                        {isCopied ? (
                          <>
                            <CheckIcon className="w-3 h-3 text-emerald-400" />
                            <span className="text-emerald-400">Copied</span>
                          </>
                        ) : (
                          <>
                            <CopyIcon className="w-3 h-3 text-slate-400" />
                            <span>Copy Payload</span>
                          </>
                        )}
                      </button>
                    </div>
                    <pre className="text-[10px] text-slate-400 overflow-x-auto p-2.5 rounded-lg bg-black/60 border border-slate-900/80 leading-relaxed font-mono">
                      {JSON.stringify(ev, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
