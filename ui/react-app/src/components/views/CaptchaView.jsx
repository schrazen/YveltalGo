import React, { useState } from "react";
import {
  PokeBallIcon,
  ShieldCheckIcon,
  WarningIcon,
  SparkleIcon,
  ClockIcon,
  CheckIcon,
} from "../Icons.jsx";
import { formatRelativeTime } from "../../utils/helpers.js";

export default function CaptchaView({
  captchaQueueRows = [],
  captchaTelemetry = { counts: {}, attempts: [], outcomes: [] },
  captchaTimers = {},
  captchaManualAnswers = {},
  setCaptchaManualAnswers,
  onSubmitManualAnswer,
  onMarkResolved,
  setSelectedCaptchaPreview,
  runtimeAvailable,
  busyAction,
  readCaptchaDraft,
  updateCaptchaDraft,
}) {
  const counts = captchaTelemetry?.counts || {};
  const activeCount = captchaQueueRows.length;

  return (
    <div className="space-y-4">
      {/* 4 Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3.5">
        <div className="glass-card p-4 rounded-2xl">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="font-bold uppercase tracking-wider text-[10px]">Active Queue</span>
            <span className={`w-2 h-2 rounded-full ${activeCount > 0 ? "bg-rose-500 animate-pulse" : "bg-emerald-400"}`}></span>
          </div>
          <div className="flex items-baseline gap-2 mt-2">
            <span className="text-3xl font-black text-white font-mono">{activeCount}</span>
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
              activeCount > 0 ? "bg-rose-500/20 text-rose-300 border-rose-500/40 animate-pulse" : "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
            }`}>
              {activeCount > 0 ? "ACTION REQ" : "CLEAR"}
            </span>
          </div>
        </div>

        <div className="glass-card p-4 rounded-2xl">
          <span className="font-bold uppercase tracking-wider text-[10px] text-slate-400">Total Attempts</span>
          <p className="text-3xl font-black text-amber-300 mt-2 font-mono">
            {Number(counts.attempts || 0).toLocaleString()}
          </p>
        </div>

        <div className="glass-card p-4 rounded-2xl">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="font-bold uppercase tracking-wider text-[10px]">Auto Solved</span>
            <span className="text-emerald-400 font-mono text-xs font-bold">{counts.solve_rate || 0}% rate</span>
          </div>
          <p className="text-3xl font-black text-emerald-300 mt-2 font-mono">
            {Number(counts.resolved_outcomes || 0).toLocaleString()}
          </p>
        </div>

        <div className="glass-card p-4 rounded-2xl">
          <span className="font-bold uppercase tracking-wider text-[10px] text-slate-400">Manual Interventions</span>
          <p className="text-3xl font-black text-rose-400 mt-2 font-mono">
            {Number(counts.failed_candidates || 0).toLocaleString()}
          </p>
        </div>
      </div>

      {/* Active Resolution Queue */}
      <div className="glass-panel p-5 rounded-2xl border border-rose-950/40 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-rose-950/40 pb-3">
          <div>
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <span className={`w-2.5 h-2.5 rounded-full ${activeCount > 0 ? "bg-rose-500 animate-ping" : "bg-emerald-400"}`}></span>
              <span>Active Captcha Resolution Queue</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Live AI OCR predictions, candidate confidence scores, and manual overrides.
            </p>
          </div>

          <button
            onClick={onMarkResolved}
            disabled={!runtimeAvailable || busyAction !== ""}
            className="px-3.5 py-1.5 rounded-xl text-xs font-bold bg-emerald-600/20 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-600 hover:text-white transition-all disabled:opacity-40"
          >
            Mark Latest Resolved
          </button>
        </div>

        {activeCount === 0 ? (
          <div className="p-10 text-center rounded-xl bg-slate-900/40 border border-dashed border-slate-800 flex flex-col items-center justify-center space-y-2">
            <SparkleIcon className="w-8 h-8 text-emerald-400 opacity-80" />
            <p className="text-sm font-bold text-emerald-300">All nodes safe and clear. No captchas pending.</p>
            <p className="text-xs text-slate-500">The automated solver is standing by on all accounts.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {captchaQueueRows.map((row) => {
              const timer = Math.ceil(captchaTimers[row.key] || 0);
              const manualVal = readCaptchaDraft ? readCaptchaDraft(captchaManualAnswers, row.draftKey, "") : "";

              return (
                <div
                  key={row.key}
                  className="p-4 rounded-xl bg-gradient-to-br from-rose-950/30 to-black/60 border border-rose-500/50 shadow-lg flex flex-col sm:flex-row gap-4 relative overflow-hidden"
                >
                  {/* Captcha Image Container */}
                  <div className="w-full sm:w-48 shrink-0 flex flex-col gap-2">
                    <div
                      onClick={() => setSelectedCaptchaPreview(row)}
                      className="bg-black/80 rounded-xl border border-rose-950 p-2 h-28 flex items-center justify-center cursor-pointer hover:border-rose-500/60 transition-colors overflow-hidden group"
                    >
                      {row.image ? (
                        <img
                          src={row.image}
                          alt="captcha"
                          className="w-full h-full object-contain rounded-lg group-hover:scale-105 transition-transform"
                        />
                      ) : (
                        <WarningIcon className="w-8 h-8 text-rose-500" />
                      )}
                    </div>
                    <div className="flex justify-between items-center bg-black/60 px-2.5 py-1 rounded-lg border border-slate-800 text-[11px]">
                      <span className="text-slate-400 font-bold uppercase text-[9px]">Timer</span>
                      <span className={`font-mono font-bold ${timer > 30 ? "text-emerald-400" : "text-rose-400 animate-pulse"}`}>
                        {timer}s
                      </span>
                    </div>
                  </div>

                  {/* Manual Answer Input & Info */}
                  <div className="flex-1 flex flex-col justify-between space-y-3">
                    <div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-white">{row.username || "Account"}</span>
                        <span className="text-[10px] text-slate-400 font-mono">Ch: {row.channelId}</span>
                      </div>
                      <p className="text-[11px] text-slate-400 mt-1">
                        AI Candidate: <strong className="text-rose-300 font-mono">{row.candidate || "Analyzing..."}</strong>
                      </p>
                    </div>

                    <div className="space-y-2">
                      <div className="flex gap-2">
                        <input
                          type="text"
                          value={manualVal}
                          onChange={(e) => updateCaptchaDraft && updateCaptchaDraft(setCaptchaManualAnswers, row.draftKey, e.target.value)}
                          placeholder="Type manual answer..."
                          className="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white flex-1 focus:outline-none focus:border-rose-500"
                        />
                        <button
                          onClick={() => onSubmitManualAnswer(row, manualVal)}
                          disabled={!manualVal || !runtimeAvailable || busyAction !== ""}
                          className="px-3.5 py-1.5 rounded-lg text-xs font-bold bg-rose-600 hover:bg-rose-500 text-white disabled:opacity-40"
                        >
                          Submit
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Historical Captcha Telemetry */}
      {captchaTelemetry?.outcomes?.length > 0 && (
        <div className="glass-panel p-5 rounded-2xl border border-rose-950/40 shadow-xl space-y-3.5">
          <h3 className="text-sm font-bold text-white uppercase tracking-wider">
            Recent Resolved Captchas ({captchaTelemetry.outcomes.length})
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-900/80 text-[10px] uppercase font-bold text-slate-400">
                <tr>
                  <th className="p-2.5">Time</th>
                  <th className="p-2.5">Account</th>
                  <th className="p-2.5">Outcome</th>
                  <th className="p-2.5">Answer</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {captchaTelemetry.outcomes.slice(0, 10).map((out, idx) => (
                  <tr key={idx} className="hover:bg-slate-800/30">
                    <td className="p-2.5 font-mono text-[11px] text-slate-400">{formatRelativeTime(out.timestamp)}</td>
                    <td className="p-2.5 text-white">{out.username || out.account_id || "Bot"}</td>
                    <td className="p-2.5">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        out.success ? "bg-emerald-500/15 text-emerald-300" : "bg-rose-500/15 text-rose-300"
                      }`}>
                        {out.success ? "SOLVED" : "FAILED"}
                      </span>
                    </td>
                    <td className="p-2.5 font-mono text-white">{out.answer || "N/A"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
