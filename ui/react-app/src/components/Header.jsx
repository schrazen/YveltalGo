import React from "react";
import {
  PokeBallIcon,
  ShieldCheckIcon,
  PlayIcon,
  PauseIcon,
  StopIcon,
  RefreshIcon,
  MenuIcon,
  PulseIcon,
} from "./Icons.jsx";

export default function Header({
  runtimeAvailable,
  bots = [],
  accounts = [],
  status = { text: "Idle", kind: "idle" },
  busyAction = "",
  runAction,
  selectedUserScope,
  setSelectedUserScope,
  onToggleMobileMenu,
  requiredServerId = 873791689939107861,
}) {
  const activeBotsCount = bots.filter((b) => b && !b.paused && !b.stopped).length;
  const captchaCount = bots.filter((b) => b && b.captcha_active).length;

  return (
    <header className="glass-panel sticky top-0 z-30 px-4 py-3 rounded-2xl border border-rose-950/40 mb-4 shadow-xl">
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
        {/* Left: Brand, Mobile Menu & Server Guard Security */}
        <div className="flex items-center justify-between md:justify-start gap-3">
          <button
            onClick={onToggleMobileMenu}
            className="md:hidden p-2 rounded-xl bg-rose-950/40 border border-rose-900/40 text-rose-300 hover:text-white"
            title="Open Navigation"
          >
            <MenuIcon className="w-5 h-5" />
          </button>

          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-rose-500 via-rose-600 to-red-800 p-0.5 shadow-[0_0_15px_rgba(244,63,94,0.35)] flex items-center justify-center">
              <PokeBallIcon className="w-7 h-7" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-black tracking-tight text-white">YVELTAL<span className="text-rose-500">GO</span></span>
                <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-rose-500/15 text-rose-300 border border-rose-500/30 uppercase tracking-widest font-mono">v2.0</span>
              </div>
              <p className="text-[10px] text-slate-400 font-medium">PokéMeow Operations Core</p>
            </div>
          </div>

          {/* Server Lock Firewall Pill */}
          <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-950/30 border border-emerald-500/30 text-emerald-300 text-xs font-medium shadow-sm ml-2">
            <ShieldCheckIcon className="w-3.5 h-3.5 text-emerald-400" />
            <span>Server: <strong className="font-mono text-emerald-200">{requiredServerId || "Locked"}</strong></span>
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
          </div>
        </div>

        {/* Right: Fleet Status, Account Picker & Global Actions */}
        <div className="flex flex-wrap items-center justify-end gap-2.5">
          {/* Captcha Alert Badge if any active */}
          {captchaCount > 0 && (
            <div className="flex items-center gap-1.5 px-3 py-1 rounded-xl bg-rose-500/20 border border-rose-500/60 text-rose-200 text-xs font-bold animate-pulse shadow-[0_0_15px_rgba(244,63,94,0.4)]">
              <span className="w-2 h-2 rounded-full bg-rose-500"></span>
              <span>{captchaCount} CAPTCHA PENDING!</span>
            </div>
          )}

          {/* Account Scope Dropdown */}
          <div className="relative">
            <select
              value={selectedUserScope}
              onChange={(e) => setSelectedUserScope(e.target.value)}
              className="bg-slate-900/90 text-xs font-semibold text-slate-200 border border-rose-900/40 rounded-xl px-3 py-1.5 pr-7 focus:outline-none focus:border-rose-500 transition-all cursor-pointer"
            >
              <option value="all">All Accounts ({accounts.length || bots.length})</option>
              {accounts.map((acc, i) => {
                const name = acc?.username || acc?.name || `Account ${i + 1}`;
                return <option key={i} value={acc?.username || acc?.id || i}>{name}</option>;
              })}
            </select>
          </div>

          {/* Quick Fleet Control Buttons */}
          <div className="flex items-center gap-1 bg-black/40 p-1 rounded-xl border border-rose-950/50">
            <button
              onClick={() => runAction("start_all")}
              disabled={!runtimeAvailable || busyAction !== ""}
              title="Start All Accounts"
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500 hover:text-white transition-all disabled:opacity-30 disabled:cursor-not-allowed shadow-sm"
            >
              <PlayIcon className="w-3 h-3" />
              <span className="hidden lg:inline">Start All</span>
            </button>

            <button
              onClick={() => runAction("pause_all")}
              disabled={!runtimeAvailable || busyAction !== ""}
              title="Pause All Accounts"
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-bold bg-amber-500/15 text-amber-300 border border-amber-500/30 hover:bg-amber-500 hover:text-white transition-all disabled:opacity-30 disabled:cursor-not-allowed shadow-sm"
            >
              <PauseIcon className="w-3 h-3" />
              <span className="hidden lg:inline">Pause</span>
            </button>

            <button
              onClick={() => runAction("stop_all")}
              disabled={!runtimeAvailable || busyAction !== ""}
              title="Emergency Stop All Accounts"
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-bold bg-rose-500/15 text-rose-300 border border-rose-500/30 hover:bg-rose-600 hover:text-white transition-all disabled:opacity-30 disabled:cursor-not-allowed shadow-sm"
            >
              <StopIcon className="w-3 h-3" />
              <span className="hidden lg:inline">Stop</span>
            </button>

            <button
              onClick={() => runAction("refresh_runtime")}
              disabled={busyAction !== ""}
              title="Refresh State"
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-all disabled:opacity-30"
            >
              <RefreshIcon className={`w-3.5 h-3.5 ${busyAction ? "animate-spin text-rose-400" : ""}`} />
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
