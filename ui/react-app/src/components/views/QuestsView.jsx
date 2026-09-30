import React, { useState } from "react";
import {
  QuestIcon,
  SparkleIcon,
  RefreshIcon,
  CheckIcon,
  TargetIcon,
  TrophyIcon,
  StarIcon,
  LeafIcon,
  SpinnerIcon,
} from "../Icons.jsx";
import { formatRelativeTime } from "../../utils/helpers.js";

export default function QuestsView({
  questCatalog = [],
  questCatalogLoading,
  questCatalogStats,
  questCategoriesMeta = {},
  questCatalogFilter,
  setQuestCatalogFilter,
  questCatalogSearch,
  setQuestCatalogSearch,
  onUpdateQuestRule,
  onResetQuestDefaults,
  onScanLogs,
  questCatalogScanning,
  questScanFeedback,
  onOpenCustomRuleModal,
  challengesData,
  onSyncChallenges,
  syncChallengesBusy,
  limitedEvents = [],
  berryState,
  runAction,
  busyAction,
  runtimeAvailable,
}) {
  const [activeTab, setActiveTab] = useState("quests");

  const filteredCatalog = questCatalog.filter((item) => {
    if (questCatalogFilter !== "all" && item.category !== questCatalogFilter) return false;
    if (questCatalogSearch) {
      const q = questCatalogSearch.toLowerCase();
      return (
        String(item.title || "").toLowerCase().includes(q) ||
        String(item.pattern || "").toLowerCase().includes(q) ||
        String(item.category || "").toLowerCase().includes(q)
      );
    }
    return true;
  });

  return (
    <div className="space-y-4">
      {/* Subtab Bar */}
      <div className="glass-panel p-3 rounded-2xl border border-rose-950/40 flex flex-wrap items-center justify-between gap-3 shadow-lg">
        <div className="flex items-center gap-2">
          {[
            { key: "quests", label: "Quest Automation & Catalog", Icon: TargetIcon },
            { key: "challenges", label: "Daily Challenges", Icon: TrophyIcon },
            { key: "bonuses", label: "Events & Multipliers", Icon: StarIcon },
            { key: "berry", label: "Berry Garden", Icon: LeafIcon },
          ].map((tab) => {
            const TabIcon = tab.Icon;
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`px-3.5 py-2 rounded-xl text-xs font-semibold transition-all flex items-center gap-2 ${
                  activeTab === tab.key
                    ? "bg-rose-600 text-white shadow-md shadow-rose-950/50"
                    : "bg-slate-900/60 text-slate-400 hover:text-white border border-slate-800"
                }`}
              >
                <TabIcon className="w-4 h-4" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {activeTab === "quests" && (
          <div className="flex items-center gap-2">
            <button
              onClick={onScanLogs}
              disabled={questCatalogScanning}
              className="px-3 py-1.5 rounded-xl text-xs font-bold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1"
            >
              <RefreshIcon className={`w-3 h-3 ${questCatalogScanning ? "animate-spin text-rose-400" : ""}`} />
              <span>{questCatalogScanning ? "Scanning..." : "Scan Session Logs"}</span>
            </button>

            <button
              onClick={onOpenCustomRuleModal}
              className="px-3 py-1.5 rounded-xl text-xs font-bold bg-rose-600 hover:bg-rose-500 text-white shadow-sm"
            >
              + Add Custom Rule
            </button>
          </div>
        )}
      </div>

      {questScanFeedback && (
        <div className="p-3 rounded-xl bg-rose-950/20 border border-rose-900/40 text-xs text-rose-300">
          {questScanFeedback}
        </div>
      )}

      {/* Tab 1: Quest Catalog */}
      {activeTab === "quests" && (
        <div className="glass-panel p-5 rounded-2xl border border-rose-950/40 shadow-xl space-y-4">
          {/* Header & Filter Controls */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-rose-950/40 pb-3">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <QuestIcon className="w-4 h-4 text-rose-500" />
                <span>Daily Quest Automation Catalog ({questCatalog.length})</span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Configure auto-complete, auto-reset scroll, or ignore directives for all known PokéMeow daily quests.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <input
                type="text"
                value={questCatalogSearch}
                onChange={(e) => setQuestCatalogSearch(e.target.value)}
                placeholder="Search quest catalog..."
                className="bg-slate-900 border border-slate-700 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-rose-500 w-44"
              />

              <button
                onClick={onResetQuestDefaults}
                className="px-2.5 py-1.5 rounded-xl text-xs font-bold bg-slate-900 text-slate-400 hover:text-rose-300 border border-slate-800"
              >
                Reset Defaults
              </button>
            </div>
          </div>

          {/* Catalog Cards Grid */}
          {questCatalogLoading ? (
            <div className="p-12 text-center text-sm text-slate-400 flex items-center justify-center gap-2">
              <SpinnerIcon className="w-4 h-4 text-rose-400" />
              <span>Loading Quest Catalog...</span>
            </div>
          ) : filteredCatalog.length === 0 ? (
            <div className="p-8 text-center text-sm text-slate-500">
              No quests found matching your filter criteria.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
              {filteredCatalog.map((item) => {
                const isComplete = item.action === "auto_complete";
                const isReset = item.action === "auto_reset";

                return (
                  <div
                    key={item.id}
                    className={`p-4 rounded-xl border flex flex-col justify-between space-y-3 transition-colors ${
                      isComplete
                        ? "bg-emerald-950/15 border-emerald-500/30"
                        : isReset
                        ? "bg-amber-950/15 border-amber-500/30"
                        : "bg-slate-900/60 border-slate-800"
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-slate-400">
                        <span>{item.category || "General"}</span>
                        {item.is_impossible && (
                          <span className="px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                            Impossible
                          </span>
                        )}
                      </div>

                      <h4 className="text-sm font-bold text-white mt-1.5">{item.title}</h4>
                      <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                        {item.description || "Daily quest requirement."}
                      </p>
                    </div>

                    {/* Action Selector 3-way toggle */}
                    <div className="pt-2 border-t border-slate-800/80">
                      <div className="grid grid-cols-3 gap-1 p-1 rounded-xl bg-black/50 border border-slate-800 text-[11px] font-bold">
                        <button
                          onClick={() => onUpdateQuestRule(item.id, "auto_complete")}
                          className={`py-1 rounded-lg text-center transition-all ${
                            isComplete ? "bg-emerald-600 text-white shadow-sm" : "text-slate-400 hover:text-white"
                          }`}
                        >
                          Complete
                        </button>
                        <button
                          onClick={() => onUpdateQuestRule(item.id, "auto_reset")}
                          className={`py-1 rounded-lg text-center transition-all ${
                            isReset ? "bg-amber-600 text-white shadow-sm" : "text-slate-400 hover:text-white"
                          }`}
                        >
                          Reset
                        </button>
                        <button
                          onClick={() => onUpdateQuestRule(item.id, "ignore")}
                          className={`py-1 rounded-lg text-center transition-all ${
                            !isComplete && !isReset ? "bg-slate-700 text-white shadow-sm" : "text-slate-400 hover:text-white"
                          }`}
                        >
                          Ignore
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Daily Challenges */}
      {activeTab === "challenges" && (
        <div className="glass-panel p-5 rounded-2xl border border-rose-950/40 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-rose-950/40 pb-3">
            <div>
              <h3 className="text-base font-bold text-white">Daily Challenges Synchronization</h3>
              <p className="text-xs text-slate-400 mt-0.5">Track daily challenges and auto-claim rewards.</p>
            </div>
            <button
              onClick={onSyncChallenges}
              disabled={syncChallengesBusy}
              className="px-3.5 py-1.5 rounded-xl text-xs font-bold bg-rose-600 hover:bg-rose-500 text-white"
            >
              {syncChallengesBusy ? "Syncing..." : "Sync Challenges (;daily / ;ch)"}
            </button>
          </div>

          <div className="p-8 text-center text-sm text-slate-500 rounded-xl border border-dashed border-slate-800">
            {challengesData?.challenges?.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-left">
                {challengesData.challenges.map((ch, i) => (
                  <div key={i} className="p-3.5 rounded-xl bg-slate-900 border border-slate-800">
                    <h5 className="font-bold text-white text-xs">{ch.name}</h5>
                    <p className="text-[11px] text-slate-400 mt-1">{ch.progress} / {ch.target}</p>
                  </div>
                ))}
              </div>
            ) : (
              "No active challenges synced. Click 'Sync Challenges' to poll PokéMeow."
            )}
          </div>
        </div>
      )}

      {/* Tab 3: Limited Events & Multipliers */}
      {activeTab === "bonuses" && (
        <div className="glass-panel p-5 rounded-2xl border border-rose-950/40 shadow-xl space-y-4">
          <div className="border-b border-rose-950/40 pb-3">
            <h3 className="text-base font-bold text-white">Active Server Events & Multiplier Bonuses</h3>
            <p className="text-xs text-slate-400 mt-0.5">Special event catch rates, shiny bonuses, and patron perks.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
              <span className="text-[10px] font-bold text-slate-400 uppercase">Catch Rate Boost</span>
              <p className="text-xl font-black text-rose-400 mt-1 font-mono">1.0x (Standard)</p>
              <p className="text-xs text-slate-500 mt-1">Normal spawn thresholds</p>
            </div>
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
              <span className="text-[10px] font-bold text-slate-400 uppercase">Shiny Rate Multiplier</span>
              <p className="text-xl font-black text-amber-300 mt-1 font-mono">1.0x</p>
              <p className="text-xs text-slate-500 mt-1">Base PokéMeow odds</p>
            </div>
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
              <span className="text-[10px] font-bold text-slate-400 uppercase">Patreon Boost</span>
              <p className="text-xl font-black text-purple-400 mt-1 font-mono">Active</p>
              <p className="text-xs text-slate-500 mt-1">Cooldown reductions applied</p>
            </div>
          </div>
        </div>
      )}

      {/* Tab 4: Berry Garden */}
      {activeTab === "berry" && (
        <div className="glass-panel p-5 rounded-2xl border border-rose-950/40 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-rose-950/40 pb-3">
            <div>
              <h3 className="text-base font-bold text-white">Berry Garden Automation</h3>
              <p className="text-xs text-slate-400 mt-0.5">Automated soil watering, harvest cycles, and replanting.</p>
            </div>
            <button
              onClick={() => runAction("force_berry_check")}
              disabled={!runtimeAvailable || busyAction !== ""}
              className="px-3.5 py-1.5 rounded-xl text-xs font-bold bg-rose-600 hover:bg-rose-500 text-white"
            >
              Water / Harvest Now (;berry)
            </button>
          </div>

          <div className="p-8 text-center text-sm text-slate-300 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center justify-center gap-2">
            <LeafIcon className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>Berry auto-watering loop is active. The bot checks soil moisture every 15 minutes.</span>
          </div>
        </div>
      )}
    </div>
  );
}
