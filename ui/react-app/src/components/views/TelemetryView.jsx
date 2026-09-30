import React, { useState } from "react";
import { TerminalIcon, RefreshIcon, SearchIcon } from "../Icons.jsx";
import { formatRelativeTime } from "../../utils/helpers.js";

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

  const events = antiDetect.events || [];
  const filteredEvents = events.filter((ev) => {
    if (filterType !== "all") {
      const type = String(ev.event_type || ev.action || "").toLowerCase();
      if (!type.includes(filterType.toLowerCase())) return false;
    }
    if (telemetrySearch) {
      const q = telemetrySearch.toLowerCase();
      const txt = JSON.stringify(ev).toLowerCase();
      return txt.includes(q);
    }
    return true;
  });

  return (
    <div className="space-y-4">
      {/* Header & Search Bar */}
      <div className="glass-panel p-5 rounded-2xl border border-rose-950/40 shadow-xl space-y-3.5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-rose-950/40 pb-3">
          <div>
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <TerminalIcon className="w-4 h-4 text-rose-500" />
              <span>Anti-Detection & System Event Telemetry</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Live audit stream of pacing delays, humanizer breaks, and action cycles.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={onRefreshTelemetry}
              className="px-3 py-1.5 rounded-xl text-xs font-bold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1.5"
            >
              <RefreshIcon className="w-3.5 h-3.5" />
              <span>Refresh Logs</span>
            </button>

            <button
              onClick={onClearTelemetry}
              disabled={busyAction !== ""}
              className="px-3 py-1.5 rounded-xl text-xs font-bold bg-rose-950/40 text-rose-300 border border-rose-900/50 hover:bg-rose-900/60"
            >
              Clear Logs
            </button>
          </div>
        </div>

        {/* Filter and Search Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
          <div className="flex items-center gap-1.5 overflow-x-auto">
            {["all", "hunt", "fish", "fight", "captcha", "break"].map((chip) => (
              <button
                key={chip}
                onClick={() => setFilterType(chip)}
                className={`px-3 py-1 rounded-lg text-xs font-bold uppercase tracking-wider transition-all ${
                  filterType === chip
                    ? "bg-rose-600 text-white shadow-sm"
                    : "bg-slate-900 text-slate-400 hover:text-white border border-slate-800"
                }`}
              >
                {chip}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2">
            <div className="relative">
              <input
                type="text"
                value={telemetrySearch}
                onChange={(e) => setTelemetrySearch(e.target.value)}
                placeholder="Search telemetry..."
                className="bg-slate-900 border border-slate-700 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-rose-500 w-52"
              />
            </div>

            <select
              value={antiDetectLimit}
              onChange={(e) => setAntiDetectLimit(Number(e.target.value))}
              className="bg-slate-900 border border-slate-700 text-xs text-slate-300 rounded-xl px-2.5 py-1.5 focus:outline-none focus:border-rose-500"
            >
              <option value={100}>100 logs</option>
              <option value={200}>200 logs</option>
              <option value={500}>500 logs</option>
            </select>
          </div>
        </div>
      </div>

      {/* Log Feed */}
      <div className="glass-panel p-5 rounded-2xl border border-rose-950/40 shadow-xl space-y-2">
        <div className="flex items-center justify-between text-xs text-slate-400 pb-2 border-b border-rose-950/40">
          <span className="font-bold uppercase tracking-wider text-[10px]">
            Stream Events ({filteredEvents.length})
          </span>
          <span className="font-mono text-[10px] text-slate-500 truncate max-w-sm">
            {antiDetect.log_path || "logs/anti_detect.jsonl"}
          </span>
        </div>

        <div className="overflow-y-auto max-h-[62vh] space-y-1.5 font-mono text-xs pr-1">
          {filteredEvents.length === 0 && (
            <div className="p-10 text-center text-slate-500 text-sm">
              No telemetry events found matching the filter.
            </div>
          )}

          {filteredEvents.map((ev, idx) => {
            const evType = String(ev.event_type || ev.action || "log").toUpperCase();
            const isError = evType.includes("ERR") || evType.includes("FAIL");
            const isCaptcha = evType.includes("CAPTCHA");
            const isBreak = evType.includes("BREAK");

            return (
              <div
                key={idx}
                className="p-2.5 rounded-xl bg-slate-950/50 border border-slate-900 hover:border-slate-800 transition-colors flex items-center justify-between gap-3"
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <span className={`px-2 py-0.5 rounded text-[9px] font-black uppercase tracking-wider shrink-0 ${
                    isError
                      ? "bg-rose-500/20 text-rose-300 border border-rose-500/40"
                      : isCaptcha
                      ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                      : isBreak
                      ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/40"
                      : "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
                  }`}>
                    {evType}
                  </span>

                  <span className="text-slate-300 truncate">
                    {ev.message || ev.details || JSON.stringify(ev.payload || ev)}
                  </span>
                </div>

                <span className="text-[10px] text-slate-500 shrink-0 whitespace-nowrap">
                  {formatRelativeTime(ev.timestamp || ev.ts)}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
