import React, { useState } from "react";
import {
  SwordsIcon,
  PulseIcon,
  ClockIcon,
  CopyIcon,
  CheckIcon,
  SparkleIcon,
  ShieldCheckIcon,
  ZapIcon,
  InfoIcon,
  SpinnerIcon,
  RibbonIcon,
} from "../Icons.jsx";

export default function WorldBossView({
  bots = [],
  runtimeAvailable,
  busyAction,
  runAction,
  selectedBoss,
  setSelectedBoss,
  wbPresetsData,
  wbPresetsLoading,
  onCheckVotesNow,
}) {
  const [copiedIndex, setCopiedIndex] = useState(null);
  const [copiedAll, setCopiedAll] = useState(false);

  const primaryWbBot = bots.find((b) => b?.world_boss) || bots[0];
  const wbInfo = primaryWbBot?.world_boss || {};
  const estimator = wbInfo?.estimator || {};

  const currentVotes = Number(estimator.current_votes || 0);
  const targetVotes = Number(estimator.target_votes || 250);
  const votePercent = Math.min(100, Math.max(0, targetVotes > 0 ? (currentVotes / targetVotes) * 100 : 0));
  const voteVelocity = Number(estimator.vote_velocity || 0);
  const etaMins = Number(estimator.eta_minutes || 0);
  const stage = String(estimator.stage || "Discovering");
  const lastDefeatedSecs = estimator.last_defeated_seconds_ago;
  const lastDefeatedMins = lastDefeatedSecs != null ? Math.round(lastDefeatedSecs / 60) : null;
  const eternamaxVotes = estimator.eternamax_votes || [0, 10000];
  const eternamaxPercent = Math.min(100, Math.max(0, ((eternamaxVotes[0] || 0) / (eternamaxVotes[1] || 10000)) * 100));
  const wbEnabled = Boolean(primaryWbBot?.automations?.world_boss_enabled ?? wbInfo?.enabled);
  const inCombat = Boolean(wbInfo?.active);

  const knownBosses = wbPresetsData?.known_bosses || [
    "Gigantamax-Pikachu",
    "Gigantamax-Charizard",
    "Gigantamax-Kingler",
    "Gigantamax-Gengar",
    "Gigantamax-Lapras",
    "Gigantamax-Machamp",
    "Gigantamax-Snorlax",
    "Gigantamax-Venusaur",
    "Gigantamax-Blastoise",
    "Eternamax-Eternatus",
  ];

  const recommendedPreset = wbPresetsData?.recommended || null;
  const recommendationReason = wbPresetsData?.recommendation_reason || "Optimal Cheese Strategy";
  const allPresets = wbPresetsData?.all_presets || [];

  const copyToClipboard = (text, idx = null) => {
    if (!text) return;
    navigator.clipboard?.writeText(text);
    if (idx !== null) {
      setCopiedIndex(idx);
      setTimeout(() => setCopiedIndex(null), 2000);
    } else {
      setCopiedAll(true);
      setTimeout(() => setCopiedAll(false), 2000);
    }
  };

  return (
    <div className="space-y-4">
      {/* Top Header Card */}
      <div className="glass-panel p-5 rounded-2xl border border-rose-950/40 shadow-xl">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-rose-500/25 to-red-950/40 border border-rose-500/40 flex items-center justify-center text-rose-400 shadow-[0_0_20px_rgba(244,63,94,0.25)]">
              <SwordsIcon className="w-6 h-6" />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-lg font-black text-white tracking-tight">World Boss Intelligence & Cheese Center</h2>
                <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider border ${
                  wbEnabled
                    ? "bg-rose-500/15 text-rose-300 border-rose-500/40 shadow-sm"
                    : "bg-slate-800 text-slate-400 border-slate-700"
                }`}>
                  Auto-Boss: {wbEnabled ? "ON" : "OFF"}
                </span>
                {inCombat && (
                  <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider bg-amber-500/20 text-amber-300 border border-amber-500/40 animate-pulse flex items-center gap-1.5">
                    <SwordsIcon className="w-3 h-3 text-amber-400" />
                    <span>IN ACTIVE COMBAT</span>
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Real-time vote progress, automated spawn prediction radar, and meta cheese comps for maximum PokéMeow damage.
              </p>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-wrap items-center gap-2.5">
            <button
              onClick={() => runAction("toggle_world_boss", { target: primaryWbBot?.id, enabled: !wbEnabled })}
              disabled={!runtimeAvailable || busyAction !== ""}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition-all border shadow-sm ${
                wbEnabled
                  ? "bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-700 hover:text-white"
                  : "bg-gradient-to-r from-rose-600 to-red-700 text-white border-rose-500/50 hover:shadow-[0_0_15px_rgba(244,63,94,0.35)]"
              } disabled:opacity-40`}
            >
              {wbEnabled ? "Turn Auto WB OFF" : "Turn Auto WB ON"}
            </button>

            <button
              onClick={onCheckVotesNow}
              disabled={!runtimeAvailable || busyAction !== ""}
              className="bg-gradient-to-r from-rose-600 via-rose-500 to-red-600 hover:from-rose-500 hover:to-red-500 text-white font-bold px-4 py-2 rounded-xl text-xs flex items-center gap-2 border border-rose-400/40 shadow-md transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <PulseIcon className={`w-3.5 h-3.5 ${busyAction ? "animate-spin" : ""}`} />
              <span>Check Votes Now (;wb)</span>
            </button>
          </div>
        </div>
      </div>

      {/* 4 Radar Telemetry Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
        {/* Metric 1: Vote Threshold */}
        <div className="glass-card p-4 rounded-2xl flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-xs text-slate-400 mb-1.5">
              <span className="font-bold uppercase tracking-wider text-[10px]">Vote Threshold</span>
              <span className="text-rose-400 font-mono text-[10px] font-bold">Stage: {stage}</span>
            </div>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-3xl font-black text-white font-mono">{currentVotes}</span>
              <span className="text-xs text-slate-400 font-semibold">/ {targetVotes} votes</span>
              <span className="ml-auto text-xs font-mono font-bold text-emerald-400">
                {voteVelocity > 0 ? `+${voteVelocity.toFixed(1)} v/m` : "pacing..."}
              </span>
            </div>
            {/* Visual Progress Bar */}
            <div className="w-full bg-slate-900/90 rounded-full h-3 mt-3 overflow-hidden p-0.5 border border-rose-950/60">
              <div
                className="bg-gradient-to-r from-rose-600 via-red-500 to-amber-400 h-full rounded-full transition-all duration-700 shadow-[0_0_10px_rgba(244,63,94,0.5)]"
                style={{ width: `${votePercent}%` }}
              />
            </div>
          </div>
          <div className="mt-3 pt-2.5 border-t border-rose-950/40 flex items-center justify-between text-xs">
            <span className="text-slate-400">Votes Needed:</span>
            <span className="font-mono font-bold text-rose-300">{Math.max(0, targetVotes - currentVotes)}</span>
          </div>
        </div>

        {/* Metric 2: Estimated Time to Spawn */}
        <div className="glass-card p-4 rounded-2xl flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-xs text-slate-400 mb-1.5">
              <span className="font-bold uppercase tracking-wider text-[10px]">Spawn Forecast</span>
              <ClockIcon className="w-3.5 h-3.5 text-rose-400" />
            </div>
            <div className="mt-1">
              <div className="flex items-baseline gap-1.5">
                <span className="text-3xl font-black text-white font-mono">
                  {etaMins > 0 ? `~${etaMins.toFixed(0)}m` : "Standby"}
                </span>
                <span className="text-xs text-slate-400">estimated</span>
              </div>
              <p className="text-[11px] text-slate-400 mt-2">
                {etaMins > 0 && etaMins <= 5
                  ? "Spawn imminent: Bot is on high-frequency alert probe."
                  : etaMins > 0
                  ? `Adaptive probe tightening as threshold nears.`
                  : "Waiting for vote velocity calibration."}
              </p>
            </div>
          </div>
          <div className="mt-3 pt-2.5 border-t border-rose-950/40 flex items-center justify-between text-xs">
            <span className="text-slate-400">Estimated Spawn Window:</span>
            <span className="font-mono text-emerald-400 font-semibold">
              {etaMins > 0 ? `${etaMins.toFixed(0)} mins` : "Awaiting data"}
            </span>
          </div>
        </div>

        {/* Metric 3: Eternamax-Eternatus Progress */}
        <div className="glass-card p-4 rounded-2xl flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-xs text-slate-400 mb-1.5">
              <span className="font-bold uppercase tracking-wider text-[10px]">Eternamax Spawn</span>
              <span className="text-purple-400 font-mono font-bold">{eternamaxPercent.toFixed(1)}%</span>
            </div>
            <div className="mt-1">
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-black text-white font-mono">{(eternamaxVotes[0] || 0).toLocaleString()}</span>
                <span className="text-xs text-slate-400 font-semibold">/ 10,000</span>
              </div>
              <div className="w-full bg-slate-900/90 rounded-full h-2 mt-2.5 overflow-hidden p-0.5 border border-purple-950/60">
                <div
                  className="bg-gradient-to-r from-purple-600 to-indigo-400 h-full rounded-full transition-all duration-700 shadow-[0_0_8px_rgba(168,85,247,0.4)]"
                  style={{ width: `${eternamaxPercent}%` }}
                />
              </div>
            </div>
          </div>
          <div className="mt-3 pt-2.5 border-t border-rose-950/40 flex items-center justify-between text-xs">
            <span className="text-slate-400">Eternamax Needed:</span>
            <span className="font-mono font-bold text-purple-300">
              {Math.max(0, 10000 - (eternamaxVotes[0] || 0)).toLocaleString()}
            </span>
          </div>
        </div>

        {/* Metric 4: Last Defeated Timer */}
        <div className="glass-card p-4 rounded-2xl flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-xs text-slate-400 mb-1.5">
              <span className="font-bold uppercase tracking-wider text-[10px]">Previous World Boss</span>
              <SparkleIcon className="w-3.5 h-3.5 text-amber-400" />
            </div>
            <div className="mt-1">
              <span className="text-2xl font-black text-white font-mono">
                {lastDefeatedMins != null ? `${lastDefeatedMins}m ago` : "unknown"}
              </span>
              <p className="text-[11px] text-slate-400 mt-2">
                World Boss cooldown interval cycle is approximately ~120m.
              </p>
            </div>
          </div>
          <div className="mt-3 pt-2.5 border-t border-rose-950/40 flex items-center justify-between text-xs">
            <span className="text-slate-400">Active Boss Status:</span>
            <span className="font-bold text-rose-400">
              {wbInfo?.current_boss && wbInfo?.current_boss !== "None" ? wbInfo.current_boss : "No Active Boss"}
            </span>
          </div>
        </div>
      </div>

      {/* Boss Selection & Meta Cheese Recommender */}
      <div className="glass-panel p-5 rounded-2xl border border-rose-950/40 shadow-xl space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-rose-950/40">
          <div>
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <ZapIcon className="w-4 h-4 text-rose-500" />
              <span>Target Boss Meta Strategy & Cheese Compositions</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Choose a World Boss to inspect optimal Baton Pass setups, Stored Power sweepers, and one-click team commands.
            </p>
          </div>

          {/* Boss Dropdown Selector */}
          <div className="flex items-center gap-2">
            <label className="text-xs font-bold text-slate-300 whitespace-nowrap">Target Boss:</label>
            <select
              value={selectedBoss}
              onChange={(e) => setSelectedBoss(e.target.value)}
              className="bg-slate-900 border border-rose-900/40 text-xs font-bold text-rose-200 rounded-xl px-3 py-1.5 focus:outline-none focus:border-rose-500 cursor-pointer"
            >
              {knownBosses.map((boss) => (
                <option key={boss} value={boss}>{boss}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Recommended Preset Details */}
        {wbPresetsLoading ? (
          <div className="p-12 text-center text-sm text-slate-400 flex items-center justify-center gap-2">
            <SpinnerIcon className="w-4 h-4 text-rose-400" />
            <span>Loading Meta Preset Strategy...</span>
          </div>
        ) : recommendedPreset ? (
          <div className="space-y-4">
            {/* Recommendation Header */}
            <div className="p-4 rounded-xl bg-gradient-to-r from-rose-950/30 to-black/40 border border-rose-900/40 flex flex-col md:flex-row md:items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-black px-2 py-0.5 rounded bg-rose-500 text-white font-mono uppercase tracking-wider">
                    {recommendedPreset.tier || "S+"} TIER
                  </span>
                  <h4 className="text-sm font-black text-white">{recommendedPreset.name}</h4>
                  <span className="text-[10px] font-mono font-bold text-slate-400 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
                    archetype: {recommendedPreset.archetype}
                  </span>
                </div>
                <p className="text-xs text-slate-300 mt-1.5 leading-relaxed">
                  {recommendedPreset.description}
                </p>
                <p className="text-[11px] text-emerald-400 font-semibold mt-1 flex items-center gap-1.5">
                  <InfoIcon className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                  <span>Strategy Analysis: {recommendationReason}</span>
                </p>
              </div>

              {/* Copy All Commands Button */}
              <button
                onClick={() => copyToClipboard(recommendedPreset.commands?.join("\n"))}
                className="shrink-0 flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold bg-rose-600 hover:bg-rose-500 text-white shadow-md transition-all"
              >
                {copiedAll ? <CheckIcon className="w-3.5 h-3.5 text-white" /> : <CopyIcon className="w-3.5 h-3.5" />}
                <span>{copiedAll ? "Copied All!" : "Copy Setup Commands"}</span>
              </button>
            </div>

            {/* Team Slots Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {recommendedPreset.slots?.map((slot, sIdx) => {
                const isSweeper = sIdx === recommendedPreset.slots.length - 1;
                return (
                  <div
                    key={sIdx}
                    className={`p-3.5 rounded-xl border flex flex-col justify-between space-y-2.5 ${
                      isSweeper
                        ? "bg-rose-950/20 border-rose-800/40 shadow-sm"
                        : "bg-slate-900/60 border-slate-800/80"
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-black uppercase tracking-wider text-rose-400 font-mono">
                          Slot {slot.slot_number} {isSweeper ? "• Main Sweeper" : "• Setup / Passer"}
                        </span>
                        {slot.recommended_item && (
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30 flex items-center gap-1">
                            <RibbonIcon className="w-3 h-3 text-amber-400" />
                            <span>{slot.recommended_item}</span>
                          </span>
                        )}
                      </div>

                      <h5 className="text-base font-black text-white mt-1">
                        {slot.pokemon}
                      </h5>

                      {/* Recommended Moves */}
                      {slot.moves && slot.moves.length > 0 && (
                        <div className="mt-2">
                          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                            Key Battle Moves:
                          </span>
                          <div className="flex flex-wrap gap-1">
                            {slot.moves.map((m, mIdx) => (
                              <span
                                key={mIdx}
                                className="text-[10px] font-mono font-medium px-1.5 py-0.5 rounded bg-black/50 text-slate-200 border border-slate-800"
                              >
                                {m}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Copyable PokéMeow Commands Box */}
            <div className="p-4 rounded-xl bg-black/60 border border-rose-950/60 space-y-2">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span className="font-bold uppercase tracking-wider text-[10px] text-rose-400">
                  PokéMeow Configuration Commands (Valid Syntax)
                </span>
                <span className="text-[10px] text-slate-500">Click any command to copy individually</span>
              </div>

              <div className="space-y-1.5 font-mono text-xs">
                {recommendedPreset.commands?.map((cmd, cIdx) => (
                  <div
                    key={cIdx}
                    onClick={() => copyToClipboard(cmd, cIdx)}
                    className="flex items-center justify-between p-2 rounded-lg bg-slate-900/80 border border-slate-800 hover:border-rose-800/60 cursor-pointer group transition-colors"
                  >
                    <span className="text-rose-200">{cmd}</span>
                    <span className="text-[10px] text-slate-500 group-hover:text-rose-300 flex items-center gap-1">
                      {copiedIndex === cIdx ? (
                        <>
                          <CheckIcon className="w-3 h-3 text-emerald-400" />
                          <span className="text-emerald-400">Copied</span>
                        </>
                      ) : (
                        <>
                          <CopyIcon className="w-3 h-3" />
                          <span>Copy</span>
                        </>
                      )}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="p-8 text-center text-sm text-slate-500">
            No preset data available for this boss.
          </div>
        )}

        {/* All Cheese Compositions Library */}
        {allPresets.length > 1 && (
          <div className="pt-3 border-t border-rose-950/40 space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Alternative Meta Cheese Combos ({allPresets.length})
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
              {allPresets.map((preset, pIdx) => (
                <div
                  key={pIdx}
                  className="p-3 rounded-xl bg-slate-900/40 border border-slate-800/80 hover:border-rose-900/40 transition-colors flex items-center justify-between gap-2"
                >
                  <div>
                    <div className="flex items-center gap-1.5">
                      <span className="text-[9px] font-bold px-1.5 py-0.2 rounded bg-rose-500/20 text-rose-300 font-mono">
                        {preset.tier || "S"}
                      </span>
                      <span className="text-xs font-bold text-white">{preset.name}</span>
                    </div>
                    <p className="text-[10px] text-slate-400 mt-1 line-clamp-1">{preset.description}</p>
                  </div>
                  <button
                    onClick={() => copyToClipboard(preset.commands?.join("\n"))}
                    className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white shrink-0"
                    title="Copy commands"
                  >
                    <CopyIcon className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
