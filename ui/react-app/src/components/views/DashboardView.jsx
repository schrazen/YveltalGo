import React, { useState } from "react";
import {
  PokeBallIcon,
  SwordsIcon,
  PulseIcon,
  ClockIcon,
  SparkleIcon,
  ShieldCheckIcon,
  PlayIcon,
  PauseIcon,
  FishIcon,
  CoinIcon,
  CrosshairIcon,
  CrownIcon,
  ChevronRightIcon,
} from "../Icons.jsx";
import { formatRelativeTime } from "../../utils/helpers.js";

export default function DashboardView({
  bots = [],
  runtimeAvailable,
  busyAction,
  runAction,
  dayTotals = { encounters: 0, catches: 0, fishEncounters: 0, fishCatches: 0, coins: 0 },
  rareCatchCards = [],
  openPokemonDetails,
  onOpenWorldBossHub,
  pokemeowEvents = [],
}) {
  const [rarityFilter, setRarityFilter] = useState("all");

  const primaryWbBot = bots.find((b) => b?.world_boss) || bots[0];
  const wbInfo = primaryWbBot?.world_boss || {};
  const estimator = wbInfo?.estimator || {};
  const currentVotes = Number(estimator.current_votes || 0);
  const targetVotes = Number(estimator.target_votes || 250);
  const votePercent = Math.min(100, Math.max(0, targetVotes > 0 ? (currentVotes / targetVotes) * 100 : 0));
  const etaMins = Number(estimator.eta_minutes || 0);
  const activeBots = bots.filter((b) => b && !b.paused && !b.stopped);
  const activeCaptchas = bots.filter((b) => b && b.captcha_active);

  const filteredRareCards = rareCatchCards.filter((p) => {
    if (rarityFilter === "all") return true;
    return String(p.rarity || "").toLowerCase().includes(rarityFilter.toLowerCase());
  });

  return (
    <div className="space-y-4">
      {/* 6 Hero KPI Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {/* KPI 1: Active Fleet */}
        <div className="glass-card p-3.5 rounded-2xl flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="font-bold uppercase tracking-wider text-[10px]">Active Fleet</span>
            <span className={`w-2 h-2 rounded-full ${activeBots.length > 0 ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)] animate-pulse" : "bg-slate-500"}`}></span>
          </div>
          <div className="mt-2">
            <div className="text-2xl font-black text-white font-mono">{activeBots.length} <span className="text-xs text-slate-400 font-normal">/ {bots.length || 1}</span></div>
            <p className="text-[10px] text-emerald-400 font-semibold mt-0.5">Online & Guarded</p>
          </div>
        </div>

        {/* KPI 2: World Boss Quick Radar */}
        <div
          onClick={onOpenWorldBossHub}
          className="glass-card p-3.5 rounded-2xl flex flex-col justify-between cursor-pointer hover:border-rose-500/50 group transition-all"
        >
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="font-bold uppercase tracking-wider text-[10px] group-hover:text-rose-300">WB Votes</span>
            <SwordsIcon className="w-3.5 h-3.5 text-rose-400" />
          </div>
          <div className="mt-2">
            <div className="text-2xl font-black text-rose-200 font-mono">
              {currentVotes} <span className="text-xs text-slate-400 font-normal">/ 250</span>
            </div>
            <div className="w-full bg-slate-900 rounded-full h-1.5 mt-1.5 overflow-hidden">
              <div className="bg-gradient-to-r from-rose-500 to-amber-400 h-full rounded-full" style={{ width: `${votePercent}%` }} />
            </div>
            <p className="text-[10px] text-rose-400 font-semibold mt-1 flex items-center gap-0.5">
              <span>{etaMins > 0 ? `ETA ~${etaMins.toFixed(0)}m` : "Open Hub"}</span>
              <ChevronRightIcon className="w-3 h-3 inline" />
            </p>
          </div>
        </div>

        {/* KPI 3: Catches Today */}
        <div className="glass-card p-3.5 rounded-2xl flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="font-bold uppercase tracking-wider text-[10px]">Catches Today</span>
            <PokeBallIcon className="w-3.5 h-3.5 text-rose-400" />
          </div>
          <div className="mt-2">
            <div className="text-2xl font-black text-white font-mono">{dayTotals.catches.toLocaleString()}</div>
            <p className="text-[10px] text-emerald-400 font-semibold mt-0.5">
              {dayTotals.encounters > 0 ? `${((dayTotals.catches / dayTotals.encounters) * 100).toFixed(1)}% success` : "100% ready"}
            </p>
          </div>
        </div>

        {/* KPI 4: Fish Catches */}
        <div className="glass-card p-3.5 rounded-2xl flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="font-bold uppercase tracking-wider text-[10px]">Fish Today</span>
            <FishIcon className="w-3.5 h-3.5 text-cyan-400" />
          </div>
          <div className="mt-2">
            <div className="text-2xl font-black text-white font-mono">{dayTotals.fishCatches.toLocaleString()}</div>
            <p className="text-[10px] text-cyan-400 font-semibold mt-0.5">
              {dayTotals.fishEncounters > 0 ? `${dayTotals.fishEncounters} cast cycles` : "Auto-fishing"}
            </p>
          </div>
        </div>

        {/* KPI 5: Coins Earned */}
        <div className="glass-card p-3.5 rounded-2xl flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="font-bold uppercase tracking-wider text-[10px]">Coins Earned</span>
            <CoinIcon className="w-3.5 h-3.5 text-amber-400" />
          </div>
          <div className="mt-2">
            <div className="text-2xl font-black text-amber-300 font-mono">+{dayTotals.coins.toLocaleString()}</div>
            <p className="text-[10px] text-amber-400 font-semibold mt-0.5">Since 12:00 Reset</p>
          </div>
        </div>

        {/* KPI 6: Captcha Safety */}
        <div className="glass-card p-3.5 rounded-2xl flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="font-bold uppercase tracking-wider text-[10px]">Captcha Safety</span>
            <ShieldCheckIcon className="w-3.5 h-3.5 text-emerald-400" />
          </div>
          <div className="mt-2">
            <div className={`text-2xl font-black font-mono ${activeCaptchas.length > 0 ? "text-rose-400 animate-pulse" : "text-emerald-400"}`}>
              {activeCaptchas.length > 0 ? `${activeCaptchas.length} Alert!` : "0 Pending"}
            </div>
            <p className="text-[10px] text-slate-400 mt-0.5">Auto-Solver Ready</p>
          </div>
        </div>
      </div>

      {/* Live Account Fleet Cards */}
      <div className="glass-panel p-5 rounded-2xl border border-rose-950/40 shadow-xl space-y-3.5">
        <div className="flex items-center justify-between border-b border-rose-950/40 pb-3">
          <div>
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <PulseIcon className="w-4 h-4 text-rose-500" />
              <span>Live Bot Operations & Account Toggles</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Direct live toggles for hunting, fishing, autofight, and world boss per connected account.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
          {bots.length === 0 && (
            <div className="col-span-full p-8 text-center text-sm text-slate-500">
              No active bots connected. Start accounts from the Operations tab.
            </div>
          )}

          {bots.map((bot, idx) => {
            const isPaused = Boolean(bot?.paused);
            const isStopped = Boolean(bot?.stopped);
            const huntActive = !Boolean(bot?.hunt_paused);
            const fishActive = !Boolean(bot?.fish_paused);
            const autofightActive = Boolean(bot?.autofight_active);
            const wbActive = Boolean(bot?.world_boss_active || bot?.world_boss?.enabled);
            const botKey = bot?.id || idx;

            return (
              <div
                key={botKey}
                className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 hover:border-rose-900/40 transition-all space-y-3"
              >
                {/* Account Header */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-rose-700 to-rose-900 flex items-center justify-center font-black text-xs text-white">
                      {(bot?.username || "B")[0].toUpperCase()}
                    </div>
                    <div>
                      <h4 className="text-sm font-bold text-white leading-tight">{bot?.username || `Account ${idx + 1}`}</h4>
                      <p className="text-[10px] text-slate-400 font-mono">ID: {bot?.id || "N/A"}</p>
                    </div>
                  </div>

                  <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider border ${
                    bot?.captcha_active
                      ? "bg-rose-500/20 text-rose-300 border-rose-500/40 animate-pulse"
                      : isPaused
                      ? "bg-amber-500/15 text-amber-300 border-amber-500/30"
                      : isStopped
                      ? "bg-slate-800 text-slate-400 border-slate-700"
                      : "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
                  }`}>
                    {bot?.captcha_active ? "CAPTCHA" : isPaused ? "PAUSED" : isStopped ? "STOPPED" : "ACTIVE"}
                  </span>
                </div>

                {/* 4 Quick Automation Toggles Grid */}
                <div className="grid grid-cols-2 gap-2 pt-2 border-t border-slate-800/60">
                  {/* Toggle: Hunting */}
                  <button
                    onClick={() => runAction(huntActive ? "pause_hunt" : "resume_hunt", { target: bot?.id })}
                    disabled={!runtimeAvailable || busyAction !== ""}
                    className={`p-2 rounded-lg text-xs font-bold flex items-center justify-between border transition-all ${
                      huntActive
                        ? "bg-emerald-950/20 border-emerald-500/30 text-emerald-300 hover:bg-emerald-950/40"
                        : "bg-slate-900 border-slate-800 text-slate-500 hover:text-slate-300"
                    }`}
                  >
                    <span className="flex items-center gap-1.5">
                      <CrosshairIcon className="w-3.5 h-3.5" />
                      <span>Hunt</span>
                    </span>
                    <span className="text-[10px] font-mono">{huntActive ? "ON" : "OFF"}</span>
                  </button>

                  {/* Toggle: Fishing */}
                  <button
                    onClick={() => runAction(fishActive ? "pause_fish" : "resume_fish", { target: bot?.id })}
                    disabled={!runtimeAvailable || busyAction !== ""}
                    className={`p-2 rounded-lg text-xs font-bold flex items-center justify-between border transition-all ${
                      fishActive
                        ? "bg-cyan-950/20 border-cyan-500/30 text-cyan-300 hover:bg-cyan-950/40"
                        : "bg-slate-900 border-slate-800 text-slate-500 hover:text-slate-300"
                    }`}
                  >
                    <span className="flex items-center gap-1.5">
                      <FishIcon className="w-3.5 h-3.5" />
                      <span>Fish</span>
                    </span>
                    <span className="text-[10px] font-mono">{fishActive ? "ON" : "OFF"}</span>
                  </button>

                  {/* Toggle: AutoFight */}
                  <button
                    onClick={() => runAction("toggle_autofight", { target: bot?.id, enabled: !autofightActive })}
                    disabled={!runtimeAvailable || busyAction !== ""}
                    className={`p-2 rounded-lg text-xs font-bold flex items-center justify-between border transition-all ${
                      autofightActive
                        ? "bg-amber-950/20 border-amber-500/30 text-amber-300 hover:bg-amber-950/40"
                        : "bg-slate-900 border-slate-800 text-slate-500 hover:text-slate-300"
                    }`}
                  >
                    <span className="flex items-center gap-1.5">
                      <SwordsIcon className="w-3.5 h-3.5" />
                      <span>AutoFight</span>
                    </span>
                    <span className="text-[10px] font-mono">{autofightActive ? "ON" : "OFF"}</span>
                  </button>

                  {/* Toggle: World Boss */}
                  <button
                    onClick={() => runAction("toggle_world_boss", { target: bot?.id, enabled: !wbActive })}
                    disabled={!runtimeAvailable || busyAction !== ""}
                    className={`p-2 rounded-lg text-xs font-bold flex items-center justify-between border transition-all ${
                      wbActive
                        ? "bg-rose-950/20 border-rose-500/30 text-rose-300 hover:bg-rose-950/40"
                        : "bg-slate-900 border-slate-800 text-slate-500 hover:text-slate-300"
                    }`}
                  >
                    <span className="flex items-center gap-1.5">
                      <CrownIcon className="w-3.5 h-3.5" />
                      <span>WorldBoss</span>
                    </span>
                    <span className="text-[10px] font-mono">{wbActive ? "ON" : "OFF"}</span>
                  </button>
                </div>

                {/* Account Day Stats Summary */}
                <div className="pt-2 border-t border-slate-800/60 flex items-center justify-between text-[11px] text-slate-400">
                  <span>Catches: <strong className="text-white font-mono">{bot?.catches || bot?.day?.catches || 0}</strong></span>
                  <span>Fish: <strong className="text-white font-mono">{bot?.fish_catches || bot?.day?.fish_catches || 0}</strong></span>
                  <span>Coins: <strong className="text-amber-400 font-mono">+{bot?.coins_earned || bot?.day?.coins || 0}</strong></span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Recent Rare Highlights Showcase */}
      <div className="glass-panel p-5 rounded-2xl border border-rose-950/40 shadow-xl space-y-3.5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-rose-950/40 pb-3">
          <div>
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <SparkleIcon className="w-4 h-4 text-amber-400" />
              <span>Recent Trophy Catches & Rare Highlights</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Click any Pokémon to inspect Pokédex artwork, elemental types, and base stats.
            </p>
          </div>

          {/* Rarity Filter Chips */}
          <div className="flex items-center gap-1.5 overflow-x-auto">
            {["all", "legendary", "shiny", "godly", "rare"].map((chip) => (
              <button
                key={chip}
                onClick={() => setRarityFilter(chip)}
                className={`px-2.5 py-1 rounded-lg text-xs font-bold uppercase tracking-wider transition-all ${
                  rarityFilter === chip
                    ? "bg-rose-600 text-white shadow-sm"
                    : "bg-slate-900 text-slate-400 hover:text-slate-200 border border-slate-800"
                }`}
              >
                {chip}
              </button>
            ))}
          </div>
        </div>

        {/* Pokemon Cards Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
          {filteredRareCards.length === 0 && (
            <div className="col-span-full p-8 text-center text-sm text-slate-500">
              No recent rare catches found matching this filter in the current session.
            </div>
          )}

          {filteredRareCards.map((p, idx) => (
            <div
              key={p.key || idx}
              onClick={() => openPokemonDetails(p)}
              className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-rose-500/50 hover:shadow-[0_4px_20px_rgba(244,63,94,0.15)] cursor-pointer transition-all group flex flex-col items-center text-center space-y-2"
            >
              <div className="w-16 h-16 rounded-xl bg-black/60 border border-rose-950/60 flex items-center justify-center p-1 overflow-hidden group-hover:scale-105 transition-transform">
                {p.sprite ? (
                  <img
                    src={p.sprite}
                    alt={p.name}
                    className="w-14 h-14 object-contain"
                    style={{ imageRendering: "pixelated" }}
                  />
                ) : (
                  <PokeBallIcon className="w-8 h-8 text-rose-500" />
                )}
              </div>

              <div>
                <h5 className="text-xs font-bold text-white truncate max-w-[110px] group-hover:text-rose-300">
                  {p.name}
                </h5>
                <span className="text-[9px] font-extrabold px-1.5 py-0.2 rounded bg-rose-500/20 text-rose-300 uppercase tracking-widest mt-1 inline-block">
                  {p.rarity}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
