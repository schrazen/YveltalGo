import React from "react";
import {
  LayoutIcon,
  SwordsIcon,
  PulseIcon,
  QuestIcon,
  PokeBallIcon,
  TerminalIcon,
  CogIcon,
  CloseIcon,
  ShieldCheckIcon,
} from "./Icons.jsx";

export const UI_TABS = [
  { key: "overview", label: "Dashboard", icon: LayoutIcon, badgeKey: null },
  { key: "worldboss", label: "World Boss", icon: SwordsIcon, badgeKey: "wb" },
  { key: "runtime", label: "Operations", icon: PulseIcon, badgeKey: "runtime" },
  { key: "quests", label: "Quests & Events", icon: QuestIcon, badgeKey: "quests" },
  { key: "captcha", label: "Captcha Center", icon: PokeBallIcon, badgeKey: "captcha" },
  { key: "anti_detect", label: "Telemetry & Logs", icon: TerminalIcon, badgeKey: null },
  { key: "config", label: "Settings", icon: CogIcon, badgeKey: null },
];

export default function Sidebar({
  activeTab,
  setActiveTab,
  mobileOpen,
  setMobileOpen,
  status = { text: "Idle", kind: "idle" },
  bots = [],
}) {
  const activeCaptcha = bots.some((b) => b?.captcha_active);
  const activeWbInCombat = bots.some((b) => b?.world_boss?.active);

  const getBadge = (badgeKey) => {
    if (badgeKey === "captcha" && activeCaptcha) {
      return <span className="w-2 h-2 rounded-full bg-rose-500 animate-ping"></span>;
    }
    if (badgeKey === "wb" && activeWbInCombat) {
      return <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40 animate-pulse">WAR</span>;
    }
    return null;
  };

  const navContent = (
    <div className="flex flex-col h-full justify-between p-3">
      {/* Brand Header */}
      <div>
        <div className="flex items-center justify-between px-2 py-3 mb-3 border-b border-rose-950/40">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-rose-600 to-red-900 flex items-center justify-center shadow-[0_0_12px_rgba(244,63,94,0.35)]">
              <span className="text-white text-xs font-black">YG</span>
            </div>
            <div>
              <h1 className="text-xs font-black tracking-wider text-white uppercase">YveltalGo</h1>
              <p className="text-[9px] uppercase tracking-widest text-rose-400 font-bold">Suite v2.0</p>
            </div>
          </div>

          {/* Close button on mobile */}
          <button
            onClick={() => setMobileOpen(false)}
            className="md:hidden p-1.5 rounded-lg text-slate-400 hover:text-white"
          >
            <CloseIcon className="w-4 h-4" />
          </button>
        </div>

        {/* Navigation Links */}
        <nav className="space-y-1.5">
          {UI_TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => {
                  setActiveTab(tab.key);
                  setMobileOpen(false);
                }}
                className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-xs font-bold transition-all group ${
                  isActive
                    ? "bg-gradient-to-r from-rose-600/25 to-rose-700/10 text-white border border-rose-500/35 shadow-[0_0_15px_rgba(244,63,94,0.15)]"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-900/60 border border-transparent"
                }`}
              >
                <div className="flex items-center gap-3">
                  <Icon
                    className={`w-4 h-4 transition-transform group-hover:scale-110 ${
                      isActive ? "text-rose-400" : "text-slate-400 group-hover:text-rose-300"
                    }`}
                  />
                  <span>{tab.label}</span>
                </div>
                {getBadge(tab.badgeKey)}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Footer System Status */}
      <div className="pt-3 border-t border-rose-950/40 px-2 space-y-2">
        <div className="flex items-center justify-between text-[11px] text-slate-400">
          <div className="flex items-center gap-1.5">
            <span
              className={`w-2 h-2 rounded-full ${
                status.kind === "ok"
                  ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)] animate-pulse"
                  : status.kind === "bad"
                  ? "bg-rose-500"
                  : "bg-slate-400"
              }`}
            />
            <span className="font-semibold text-slate-300 truncate max-w-[120px]">{status.text}</span>
          </div>
        </div>

        <div className="p-2 rounded-xl bg-black/40 border border-rose-950/40 text-[10px] text-slate-400 flex items-center justify-between">
          <span className="flex items-center gap-1">
            <ShieldCheckIcon className="w-3 h-3 text-emerald-400" />
            <span>Firewall Active</span>
          </span>
          <span className="font-mono text-emerald-300">100% Locked</span>
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Sidebar */}
      <aside className="hidden md:flex flex-col w-60 shrink-0 h-screen sticky top-0 bg-slate-950/85 backdrop-blur-2xl border-r border-rose-950/40 z-20">
        {navContent}
      </aside>

      {/* Mobile Drawer Overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden flex">
          <div
            className="fixed inset-0 bg-black/80 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="relative w-64 max-w-[80vw] h-full bg-slate-950 border-r border-rose-900/50 z-10 shadow-2xl">
            {navContent}
          </aside>
        </div>
      )}
    </>
  );
}
