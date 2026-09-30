import React, { useState } from "react";
import {
  PulseIcon,
  PlayIcon,
  PauseIcon,
  StopIcon,
  RefreshIcon,
  ZapIcon,
  ShieldCheckIcon,
  WarningIcon,
} from "../Icons.jsx";

export default function OperationsView({
  bots = [],
  accounts = [],
  runtimeAvailable,
  busyAction,
  runAction,
  runAccountAction,
  diagnostics,
  onRefreshDiagnostics,
  newAccount,
  setNewAccount,
  onAddAccount,
  addAccountBusy,
  addAccountFeedback,
  complications = {},
  sessionAnalysis,
  runSessionAnalysis,
  sessionAnalysisLoading,
}) {
  const [activeSubTab, setActiveSubTab] = useState("fleet");
  const [showAddModal, setShowAddModal] = useState(false);

  return (
    <div className="space-y-4">
      {/* Subtab Navigation */}
      <div className="glass-panel p-3 rounded-2xl border border-rose-950/40 flex flex-wrap items-center justify-between gap-3 shadow-lg">
        <div className="flex items-center gap-2">
          {[
            { key: "fleet", label: "Fleet & Bot Control", icon: "🤖" },
            { key: "diagnostics", label: "Runtime Diagnostics", icon: "🩺" },
            { key: "complications", label: "Complications & Flees", icon: "⚠️" },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveSubTab(tab.key)}
              className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 ${
                activeSubTab === tab.key
                  ? "bg-rose-600 text-white shadow-md shadow-rose-950/50"
                  : "bg-slate-900/60 text-slate-400 hover:text-white border border-slate-800"
              }`}
            >
              <span>{tab.icon}</span>
              <span>{tab.label}</span>
            </button>
          ))}
        </div>

        <button
          onClick={() => setShowAddModal(true)}
          className="px-3.5 py-2 rounded-xl text-xs font-bold bg-gradient-to-r from-rose-600 to-red-700 text-white hover:from-rose-500 hover:to-red-600 shadow-sm transition-all"
        >
          + Add New Account
        </button>
      </div>

      {/* SubTab 1: Fleet & Bot Control */}
      {activeSubTab === "fleet" && (
        <div className="space-y-4">
          {/* Configured Accounts Grid */}
          <div className="glass-panel p-5 rounded-2xl border border-rose-950/40 shadow-xl space-y-3.5">
            <div className="flex items-center justify-between border-b border-rose-950/40 pb-3">
              <div>
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                  Configured Discord Accounts ({accounts.length})
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Start, stop, and inspect per-token runtime processes.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
              {accounts.length === 0 && (
                <div className="col-span-full p-8 text-center text-sm text-slate-500">
                  No accounts found in config.json. Click "+ Add New Account" above to get started.
                </div>
              )}

              {accounts.map((acc, idx) => {
                const displayName = acc.display_name || acc.username || acc.label || `Account #${idx + 1}`;
                const isRunning = Boolean(acc.running);
                const isConnecting = Boolean(acc.connecting);

                return (
                  <div
                    key={acc.id || idx}
                    className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-rose-900/40 transition-all space-y-3"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-rose-800 to-red-950 flex items-center justify-center font-bold text-xs text-white">
                          {displayName[0].toUpperCase()}
                        </div>
                        <div>
                          <h4 className="text-sm font-bold text-white">{displayName}</h4>
                          <span className="text-[10px] text-slate-500 font-mono">
                            {acc.mention_name || `...${acc.token_suffix || ""}`}
                          </span>
                        </div>
                      </div>

                      <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider border ${
                        isRunning
                          ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
                          : isConnecting
                          ? "bg-amber-500/15 text-amber-300 border-amber-500/30 animate-pulse"
                          : "bg-slate-800 text-slate-400 border-slate-700"
                      }`}>
                        {isRunning ? "RUNNING" : isConnecting ? "CONNECTING" : "STOPPED"}
                      </span>
                    </div>

                    <div className="p-2 rounded-lg bg-black/40 border border-slate-800 text-[11px] font-mono text-slate-300 space-y-0.5">
                      <div>Hunt: <span className="text-rose-300">{acc.hunting_channel_id || "default"}</span></div>
                      <div>Fish: <span className="text-cyan-300">{acc.fishing_channel_id || "default"}</span></div>
                    </div>

                    <div className="flex gap-2 pt-1">
                      <button
                        onClick={() => runAccountAction(acc.id, "start_bot")}
                        disabled={!runtimeAvailable || busyAction !== "" || isRunning || isConnecting}
                        className="flex-1 py-1.5 rounded-lg text-xs font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500 hover:text-white transition-all disabled:opacity-30 disabled:cursor-not-allowed"
                      >
                        Start
                      </button>
                      <button
                        onClick={() => runAccountAction(acc.id, "stop_bot")}
                        disabled={!runtimeAvailable || busyAction !== "" || (!isRunning && !isConnecting)}
                        className="flex-1 py-1.5 rounded-lg text-xs font-bold bg-rose-500/15 text-rose-300 border border-rose-500/30 hover:bg-rose-600 hover:text-white transition-all disabled:opacity-30 disabled:cursor-not-allowed"
                      >
                        Stop
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Connected Live Bots Cards */}
          <div className="glass-panel p-5 rounded-2xl border border-rose-950/40 shadow-xl space-y-3.5">
            <div className="flex items-center justify-between border-b border-rose-950/40 pb-3">
              <div>
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                  Active Bot Runtimes ({bots.length})
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Live state inspection, cooldowns, and action force overrides.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
              {bots.map((bot, idx) => (
                <div
                  key={bot?.id || idx}
                  className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="text-sm font-bold text-white">{bot?.username || `Bot #${idx + 1}`}</h4>
                      <p className="text-[11px] text-emerald-400 font-semibold">{bot?.hunting_status} • {bot?.fishing_status}</p>
                    </div>

                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={() => runAction("force_hunt", { target: bot?.id })}
                        disabled={!runtimeAvailable || busyAction !== ""}
                        className="px-2.5 py-1 rounded-lg text-[11px] font-bold bg-slate-800 hover:bg-slate-700 text-slate-200"
                        title="Force Hunting Command"
                      >
                        🏹 Force Hunt
                      </button>
                      <button
                        onClick={() => runAction("force_fish", { target: bot?.id })}
                        disabled={!runtimeAvailable || busyAction !== ""}
                        className="px-2.5 py-1 rounded-lg text-[11px] font-bold bg-slate-800 hover:bg-slate-700 text-slate-200"
                        title="Force Fishing Command"
                      >
                        🎣 Force Fish
                      </button>
                    </div>
                  </div>

                  {/* Cooldown Bars */}
                  <div className="space-y-1.5 text-xs text-slate-300">
                    <div className="flex justify-between text-[11px]">
                      <span>Hunt Cooldown:</span>
                      <span className="font-mono text-rose-300">{bot?.last_hunt ? "Pacing Active" : "Ready"}</span>
                    </div>
                    <div className="flex justify-between text-[11px]">
                      <span>Fish Cooldown:</span>
                      <span className="font-mono text-cyan-300">{bot?.last_fish ? "Pacing Active" : "Ready"}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* SubTab 2: Diagnostics */}
      {activeSubTab === "diagnostics" && (
        <div className="glass-panel p-5 rounded-2xl border border-rose-950/40 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-rose-950/40 pb-3">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <PulseIcon className="w-4 h-4 text-rose-500" />
                <span>Runtime Diagnostics & Gateway Health</span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Process telemetry, memory consumption, and Discord heartbeat status.
              </p>
            </div>
            <button
              onClick={onRefreshDiagnostics}
              className="px-3 py-1.5 rounded-lg text-xs font-bold bg-slate-800 hover:bg-slate-700 text-slate-200 flex items-center gap-1.5"
            >
              <RefreshIcon className="w-3.5 h-3.5" />
              <span>Refresh</span>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
              <span className="text-[10px] font-bold uppercase text-slate-400 tracking-wider">Discord Gateway</span>
              <p className="text-xl font-black text-emerald-400 mt-1 font-mono">
                {diagnostics?.gateway_status || "Connected"}
              </p>
              <p className="text-xs text-slate-500 mt-1">Websocket connection stable</p>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
              <span className="text-[10px] font-bold uppercase text-slate-400 tracking-wider">Process Uptime</span>
              <p className="text-xl font-black text-white mt-1 font-mono">
                {diagnostics?.uptime || "Running"}
              </p>
              <p className="text-xs text-slate-500 mt-1">Main asyncio loop active</p>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
              <span className="text-[10px] font-bold uppercase text-slate-400 tracking-wider">Memory Allocation</span>
              <p className="text-xl font-black text-amber-300 mt-1 font-mono">
                {diagnostics?.memory_mb ? `${diagnostics.memory_mb} MB` : "Normal"}
              </p>
              <p className="text-xs text-slate-500 mt-1">Python heap profile</p>
            </div>
          </div>
        </div>
      )}

      {/* SubTab 3: Complications */}
      {activeSubTab === "complications" && (
        <div className="glass-panel p-5 rounded-2xl border border-rose-950/40 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-rose-950/40 pb-3">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <WarningIcon className="w-4 h-4 text-amber-400" />
                <span>Session Complications & Telemetry</span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Track fleeing Pokémon, ball starvations, and cooldown blocks.
              </p>
            </div>
            <button
              onClick={runSessionAnalysis}
              disabled={sessionAnalysisLoading}
              className="px-3.5 py-1.5 rounded-lg text-xs font-bold bg-amber-600/20 text-amber-300 border border-amber-500/30 hover:bg-amber-600 hover:text-white transition-all disabled:opacity-40"
            >
              {sessionAnalysisLoading ? "Analyzing..." : "Run AI Session Analysis"}
            </button>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800">
              <span className="text-[10px] font-bold text-slate-400 uppercase">Total Flees</span>
              <p className="text-2xl font-black text-rose-400 mt-1 font-mono">{complications?.flee_count || 0}</p>
            </div>
            <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800">
              <span className="text-[10px] font-bold text-slate-400 uppercase">Ball Starvations</span>
              <p className="text-2xl font-black text-amber-400 mt-1 font-mono">{complications?.ball_starvation_count || 0}</p>
            </div>
            <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800">
              <span className="text-[10px] font-bold text-slate-400 uppercase">Coin Starvations</span>
              <p className="text-2xl font-black text-yellow-400 mt-1 font-mono">{complications?.coin_starvation_count || 0}</p>
            </div>
            <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800">
              <span className="text-[10px] font-bold text-slate-400 uppercase">Cooldown Blocks</span>
              <p className="text-2xl font-black text-slate-200 mt-1 font-mono">{complications?.cooldown_block_count || 0}</p>
            </div>
          </div>
        </div>
      )}

      {/* Add Account Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="glass-panel-elevated p-6 rounded-2xl max-w-md w-full border border-rose-950/60 space-y-4 shadow-2xl">
            <div className="flex justify-between items-center border-b border-rose-950/40 pb-3">
              <h3 className="text-base font-bold text-white">Add Discord Account</h3>
              <button onClick={() => setShowAddModal(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <form onSubmit={(e) => { onAddAccount(e); setShowAddModal(false); }} className="space-y-3">
              <div>
                <label className="text-xs font-bold text-slate-300 block mb-1">User Discord Token</label>
                <input
                  type="password"
                  required
                  value={newAccount.token}
                  onChange={(e) => setNewAccount({ ...newAccount, token: e.target.value })}
                  placeholder="mfa.xxxxxxxx..."
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white"
                />
              </div>

              <div className="grid grid-cols-2 gap-2.5">
                <div>
                  <label className="text-xs font-bold text-slate-300 block mb-1">Hunting Channel ID</label>
                  <input
                    type="text"
                    required
                    value={newAccount.huntingChannelId}
                    onChange={(e) => setNewAccount({ ...newAccount, huntingChannelId: e.target.value })}
                    placeholder="121313876137..."
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white"
                  />
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-300 block mb-1">Fishing Channel ID</label>
                  <input
                    type="text"
                    required
                    value={newAccount.fishingChannelId}
                    onChange={(e) => setNewAccount({ ...newAccount, fishingChannelId: e.target.value })}
                    placeholder="121313876137..."
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-rose-950/40">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-3.5 py-1.5 rounded-lg text-xs font-bold bg-slate-800 text-slate-300 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={addAccountBusy}
                  className="px-4 py-1.5 rounded-lg text-xs font-bold bg-rose-600 hover:bg-rose-500 text-white"
                >
                  {addAccountBusy ? "Adding..." : "Save Account"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
