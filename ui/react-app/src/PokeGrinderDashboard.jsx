import React, { useCallback, useEffect, useMemo, useState } from "react";
import "./sakura-theme.css";

// Shared Icons and Utilities
import {
  fetchJson,
  fetchJsonWithFallback,
  formatRelativeTime,
  toPokeApiSlug,
  toDisplayName,
  readPokemonSlugOverrides,
  writePokemonSlugOverrides,
  getFlavorText,
  getBotKey,
} from "./utils/helpers.js";

// Layout & View Components
import Header from "./components/Header.jsx";
import Sidebar from "./components/Sidebar.jsx";
import DashboardView from "./components/views/DashboardView.jsx";
import WorldBossView from "./components/views/WorldBossView.jsx";
import OperationsView from "./components/views/OperationsView.jsx";
import QuestsView from "./components/views/QuestsView.jsx";
import CaptchaView from "./components/views/CaptchaView.jsx";
import TelemetryView from "./components/views/TelemetryView.jsx";
import ConfigView from "./components/views/ConfigView.jsx";
import PokemonModal from "./components/PokemonModal.jsx";

function resolveCaptchaPreviewSrc(channelState) {
  const localPath = String(channelState?.last_image_path || "").trim();
  if (localPath) {
    return `/api/captcha/image?path=${encodeURIComponent(localPath)}`;
  }
  const remoteUrl = String(channelState?.last_image_url || "").trim();
  return remoteUrl || "";
}

function rarityVisual(rarity) {
  const r = String(rarity || "").toLowerCase();
  if (r.includes("godly") || r.includes("mythic")) {
    return { border: "border-purple-500/50", bg: "bg-purple-950/20", badgeCls: "bg-purple-500/20 text-purple-300 border-purple-500/40" };
  }
  if (r.includes("legendary")) {
    return { border: "border-amber-500/50", bg: "bg-amber-950/20", badgeCls: "bg-amber-500/20 text-amber-300 border-amber-500/40" };
  }
  if (r.includes("shiny")) {
    return { border: "border-rose-500/50", bg: "bg-rose-950/20", badgeCls: "bg-rose-500/20 text-rose-300 border-rose-500/40" };
  }
  return { border: "border-slate-800", bg: "bg-slate-900/60", badgeCls: "bg-slate-800 text-slate-300 border-slate-700" };
}

export default function PokeGrinderDashboard() {
  // Navigation State
  const [activeTab, setActiveTab] = useState("overview");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Status & Telemetry
  const [status, setStatus] = useState({ text: "Idle", kind: "idle" });
  const [busyAction, setBusyAction] = useState("");
  const [selectedUserScope, setSelectedUserScope] = useState("all");

  // Core Data Stores
  const [stats, setStats] = useState({});
  const [statsPath, setStatsPath] = useState("");
  const [runtime, setRuntime] = useState({ available: false, data: { bots: [] }, message: "Runtime not attached" });
  const [configJson, setConfigJson] = useState("{}");
  const [configPath, setConfigPath] = useState("");
  const [configDirty, setConfigDirty] = useState(false);
  const [diagnostics, setDiagnostics] = useState(null);

  // Telemetry & Logs
  const [antiDetect, setAntiDetect] = useState({ events: [], count: 0, log_path: "" });
  const [antiDetectLimit, setAntiDetectLimit] = useState(200);
  const [telemetrySearch, setTelemetrySearch] = useState("");

  // Captcha State
  const [captchaTelemetry, setCaptchaTelemetry] = useState({
    counts: { attempts: 0, outcomes: 0, resolved_outcomes: 0, failed_candidates: 0 },
    attempts: [],
    outcomes: [],
  });
  const [captchaTimers, setCaptchaTimers] = useState({});
  const [captchaManualAnswers, setCaptchaManualAnswers] = useState({});
  const [selectedCaptchaPreview, setSelectedCaptchaPreview] = useState(null);

  // Rare Catches & Trophy Showcase
  const [recentRareCatches, setRecentRareCatches] = useState([]);
  const [selectedCatch, setSelectedCatch] = useState(null);
  const [selectedPokemonInfo, setSelectedPokemonInfo] = useState(null);
  const [selectedPokemonLoading, setSelectedPokemonLoading] = useState(false);
  const [selectedPokemonError, setSelectedPokemonError] = useState("");
  const [pokemonFallbackPrompt, setPokemonFallbackPrompt] = useState(null);
  const [pokemonFallbackBusy, setPokemonFallbackBusy] = useState(false);
  const [pokemonSlugOverrides, setPokemonSlugOverrides] = useState(() => readPokemonSlugOverrides());

  // World Boss State
  const [selectedWbBoss, setSelectedWbBoss] = useState("Gigantamax-Pikachu");
  const [wbPresetsData, setWbPresetsData] = useState(null);
  const [wbPresetsLoading, setWbPresetsLoading] = useState(false);

  // Quests & Catalog
  const [questCatalog, setQuestCatalog] = useState([]);
  const [questCatalogStats, setQuestCatalogStats] = useState(null);
  const [questCategoriesMeta, setQuestCategoriesMeta] = useState({});
  const [questCatalogLoading, setQuestCatalogLoading] = useState(false);
  const [questCatalogFilter, setQuestCatalogFilter] = useState("all");
  const [questCatalogSearch, setQuestCatalogSearch] = useState("");
  const [questCatalogScanning, setQuestCatalogScanning] = useState(false);
  const [questScanFeedback, setQuestScanFeedback] = useState("");
  const [challengesData, setChallengesData] = useState(null);
  const [syncChallengesBusy, setSyncChallengesBusy] = useState(false);

  // Complications & Analysis
  const [complications, setComplications] = useState({});
  const [sessionAnalysis, setSessionAnalysis] = useState(null);
  const [sessionAnalysisLoading, setSessionAnalysisLoading] = useState(false);

  // Add Account State
  const [newAccount, setNewAccount] = useState({
    token: "",
    huntingChannelId: "",
    fishingChannelId: "",
  });
  const [addAccountBusy, setAddAccountBusy] = useState(false);

  const runtimeAvailable = Boolean(runtime?.available);
  const bots = runtime?.data?.bots || [];
  const accounts = runtime?.data?.accounts || [];

  // Scoped bots based on account filter
  const scopedBots = useMemo(() => {
    if (selectedUserScope === "all") return bots;
    return bots.filter((b) => String(b?.id || "") === selectedUserScope || String(b?.username || "") === selectedUserScope);
  }, [bots, selectedUserScope]);

  // Aggregate Day Stats Totals
  const dayTotals = useMemo(() => {
    let encounters = 0;
    let catches = 0;
    let fishEncounters = 0;
    let fishCatches = 0;
    let coins = 0;

    scopedBots.forEach((bot) => {
      const s = bot?.day || bot?.session || {};
      encounters += Number(bot?.encounters || s?.encounters || 0);
      catches += Number(bot?.catches || s?.catches || 0);
      fishEncounters += Number(bot?.fish_encounters || s?.fish_encounters || 0);
      fishCatches += Number(bot?.fish_catches || s?.fish_catches || 0);
      coins += Number(bot?.coins_earned || s?.coins || 0);
    });

    return { encounters, catches, fishEncounters, fishCatches, coins };
  }, [scopedBots]);

  // Captcha Queue Rows
  const captchaQueueRows = useMemo(() => {
    const rows = [];
    scopedBots.forEach((bot, idx) => {
      const draftKey = String(bot?.id || `${bot?.username || "bot"}-${idx}`);
      const channels = [
        { hint: "hunting", channelType: "HUNTING", state: bot?.captcha?.hunting || {} },
        { hint: "fishing", channelType: "FISHING", state: bot?.captcha?.fishing || {} },
        { hint: "autofight", channelType: "AUTOFIGHT", state: bot?.captcha?.autofight || {} },
      ];

      channels.forEach((entry) => {
        if (!entry.state?.active) return;
        const image = resolveCaptchaPreviewSrc(entry.state);
        rows.push({
          key: `${draftKey}-${entry.hint}`,
          bot,
          draftKey,
          username: bot?.username,
          channelId: String(entry.state?.channel_id || "").trim(),
          candidate: String(entry.state?.last_prediction || "-").trim(),
          image,
          captcha_detected_utc: Number(entry.state?.last_detected_utc || entry.state?.ts_utc || Date.now() / 1000),
        });
      });
    });
    return rows;
  }, [scopedBots]);

  // Captcha countdown timers
  useEffect(() => {
    const interval = setInterval(() => {
      setCaptchaTimers((prev) => {
        const now = Date.now() / 1000;
        const updated = {};
        captchaQueueRows.forEach((row) => {
          const detected = row.captcha_detected_utc || now;
          const elapsed = Math.max(0, now - detected);
          updated[row.key] = Math.max(0, 90 - elapsed);
        });
        return updated;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [captchaQueueRows]);

  // Rare Catches cards
  const rareCatchCards = useMemo(() => {
    return (recentRareCatches || []).map((row, idx) => {
      const visual = rarityVisual(row.rarity);
      return {
        key: `${row.ts || "na"}-${idx}`,
        name: row.pokemon_name || "Unknown",
        rarity: row.rarity || "Rare",
        ball: row.ball_used || "",
        sprite: row.sprite || "",
        ...visual,
      };
    });
  }, [recentRareCatches]);

  // Data Fetching Handlers
  const fetchTelemetry = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      params.set("limit", String(antiDetectLimit));
      params.set("ts", String(Date.now()));
      if (telemetrySearch) params.set("q", telemetrySearch);
      const data = await fetchJsonWithFallback(`/api/telemetry/anti-detect?${params.toString()}`, { events: [], count: 0 });
      setAntiDetect(data);
    } catch {
      // ignore
    }
  }, [antiDetectLimit, telemetrySearch]);

  const fetchCaptcha = useCallback(async () => {
    try {
      const data = await fetchJsonWithFallback(`/api/telemetry/captcha?ts=${Date.now()}`, { counts: {}, attempts: [], outcomes: [] });
      setCaptchaTelemetry(data);
    } catch {
      // ignore
    }
  }, []);

  const fetchWbPresets = useCallback(async (boss = selectedWbBoss) => {
    setWbPresetsLoading(true);
    try {
      const data = await fetchJsonWithFallback(`/api/worldboss/presets?boss=${encodeURIComponent(boss)}`, { ok: false });
      if (data?.ok) {
        setWbPresetsData(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setWbPresetsLoading(false);
    }
  }, [selectedWbBoss]);

  const fetchQuestCatalog = useCallback(async () => {
    setQuestCatalogLoading(true);
    try {
      const data = await fetchJsonWithFallback("/api/quest-catalog", { ok: false });
      if (data?.ok) {
        setQuestCatalog(data.catalog || []);
        setQuestCatalogStats(data.stats || null);
        setQuestCategoriesMeta(data.categories || {});
      }
    } catch (err) {
      console.error(err);
    } finally {
      setQuestCatalogLoading(false);
    }
  }, []);

  const refreshAll = useCallback(async () => {
    try {
      const [cfg, st, rt] = await Promise.all([
        fetchJsonWithFallback(`/api/config?ts=${Date.now()}`, { config: {}, path: "" }),
        fetchJsonWithFallback(`/api/stats?ts=${Date.now()}`, { stats: {}, path: "" }),
        fetchJsonWithFallback(`/api/runtime/status?ts=${Date.now()}`, { available: false, data: { bots: [], accounts: [] } }),
      ]);

      setConfigPath(cfg?.path || "");
      if (!configDirty) {
        setConfigJson(String(cfg?.config_text || JSON.stringify(cfg?.config || {}, null, 2)));
      }
      setStats(st?.stats || {});
      setStatsPath(st?.path || "");
      setRuntime(rt || { available: false, data: { bots: [], accounts: [] } });

      try {
        const rare = await fetchJson(`/api/telemetry/recent-rare-catches?hours=24&limit=12&ts=${Date.now()}`);
        setRecentRareCatches(Array.isArray(rare?.rows) ? rare.rows : []);
      } catch {
        setRecentRareCatches([]);
      }

      setStatus({ text: rt?.available ? "All Systems Connected" : "Standing By", kind: rt?.available ? "ok" : "idle" });
    } catch (err) {
      setStatus({ text: `Sync Error: ${err.message}`, kind: "bad" });
    }
  }, [configDirty]);

  // Initial and recurring poll
  useEffect(() => {
    refreshAll();
    const interval = setInterval(refreshAll, 6000);
    return () => clearInterval(interval);
  }, [refreshAll]);

  // Lazy tab data loaders
  useEffect(() => {
    if (activeTab === "worldboss") fetchWbPresets(selectedWbBoss);
    if (activeTab === "quests") fetchQuestCatalog();
    if (activeTab === "anti_detect") fetchTelemetry();
    if (activeTab === "captcha") fetchCaptcha();
  }, [activeTab, fetchWbPresets, fetchQuestCatalog, fetchTelemetry, fetchCaptcha, selectedWbBoss]);

  // Action Dispatcher
  const runAction = async (action, payload = {}) => {
    setBusyAction(action);
    setStatus({ text: `Dispatching ${action}...`, kind: "idle" });
    try {
      const res = await fetchJson("/api/runtime/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, ...payload }),
      });
      if (res?.ok === false) {
        setStatus({ text: res.error || "Action failed", kind: "bad" });
      } else {
        setStatus({ text: res.message || "Action successful", kind: "ok" });
      }
      await refreshAll();
    } catch (err) {
      setStatus({ text: err.message, kind: "bad" });
    } finally {
      setBusyAction("");
    }
  };

  const runAccountAction = async (accountId, action) => {
    await runAction(action, { target: accountId });
  };

  // Quest Catalog Actions
  const handleUpdateQuestRule = async (id, action) => {
    setQuestCatalog((prev) => prev.map((q) => (q.id === id ? { ...q, action } : q)));
    try {
      await fetchJson("/api/quest-catalog/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, action }),
      });
      setStatus({ text: "Quest directive updated", kind: "ok" });
    } catch (err) {
      setStatus({ text: `Failed: ${err.message}`, kind: "bad" });
      fetchQuestCatalog();
    }
  };

  const handleResetQuestDefaults = async () => {
    if (!window.confirm("Reset all quest rules to default?")) return;
    try {
      await fetchJson("/api/quest-catalog/reset-defaults", { method: "POST" });
      await fetchQuestCatalog();
      setStatus({ text: "Quest rules reset to defaults", kind: "ok" });
    } catch (err) {
      setStatus({ text: err.message, kind: "bad" });
    }
  };

  const handleScanLogs = async () => {
    setQuestCatalogScanning(true);
    setQuestScanFeedback("");
    try {
      const res = await fetchJson("/api/quest-catalog/scan-logs", { method: "POST" });
      if (res?.ok) {
        setQuestScanFeedback(`Discovered ${res.unique_harvested_count} unique quests from logs!`);
        await fetchQuestCatalog();
      }
    } catch (err) {
      setQuestScanFeedback(`Scan failed: ${err.message}`);
    } finally {
      setQuestCatalogScanning(false);
    }
  };

  // Captcha manual answer submission
  const handleSubmitManualAnswer = async (row, answer) => {
    if (!answer || !row?.bot?.id) return;
    await runAction("captcha_manual_answer", {
      target: row.bot.id,
      answer,
      channel_hint: row.hint || "auto",
    });
    setCaptchaManualAnswers((prev) => ({ ...prev, [row.draftKey]: "" }));
  };

  // Config save & format
  const handleSaveConfig = async () => {
    setBusyAction("save_config");
    try {
      const payload = JSON.parse(configJson);
      await fetchJson("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ config: payload }),
      });
      setConfigDirty(false);
      setStatus({ text: "Configuration saved successfully", kind: "ok" });
    } catch (err) {
      setStatus({ text: `Config save failed: ${err.message}`, kind: "bad" });
    } finally {
      setBusyAction("");
    }
  };

  const handleFormatConfig = () => {
    try {
      const parsed = JSON.parse(configJson);
      setConfigJson(JSON.stringify(parsed, null, 2));
      setStatus({ text: "JSON Formatted", kind: "ok" });
    } catch (err) {
      setStatus({ text: "Invalid JSON syntax", kind: "bad" });
    }
  };

  // Pokemon details modal
  const openPokemonDetails = async (pokemon) => {
    setSelectedCatch(pokemon);
    setSelectedPokemonInfo(null);
    setSelectedPokemonError("");
    setSelectedPokemonLoading(true);

    try {
      const baseSlug = toPokeApiSlug(pokemon.name);
      const res = await fetch(`https://pokeapi.co/api/v2/pokemon/${baseSlug}`);
      if (!res.ok) throw new Error("Pokémon not found on PokeAPI");
      const data = await res.json();

      let species = null;
      if (data?.species?.url) {
        const sRes = await fetch(data.species.url);
        if (sRes.ok) species = await sRes.json();
      }

      setSelectedPokemonInfo({ data, species });
    } catch (err) {
      setSelectedPokemonError("Could not resolve official PokeAPI artwork.");
    } finally {
      setSelectedPokemonLoading(false);
    }
  };

  return (
    <div className="sakura-theme text-slate-100 min-h-screen flex antialiased selection:bg-rose-500/30">
      {/* Responsive Collapsible Sidebar */}
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        mobileOpen={mobileMenuOpen}
        setMobileOpen={setMobileMenuOpen}
        status={status}
        bots={scopedBots}
      />

      {/* Main App Container */}
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto h-screen p-3 md:p-5 relative z-10">
        {/* Sticky Glass Command Header */}
        <Header
          runtimeAvailable={runtimeAvailable}
          bots={scopedBots}
          accounts={accounts}
          status={status}
          busyAction={busyAction}
          runAction={runAction}
          selectedUserScope={selectedUserScope}
          setSelectedUserScope={setSelectedUserScope}
          onToggleMobileMenu={() => setMobileMenuOpen(!mobileMenuOpen)}
        />

        {/* Tab 1: Dashboard Overview */}
        {activeTab === "overview" && (
          <DashboardView
            bots={scopedBots}
            runtimeAvailable={runtimeAvailable}
            busyAction={busyAction}
            runAction={runAction}
            dayTotals={dayTotals}
            rareCatchCards={rareCatchCards}
            openPokemonDetails={openPokemonDetails}
            onOpenWorldBossHub={() => setActiveTab("worldboss")}
          />
        )}

        {/* Tab 2: Dedicated World Boss Hub */}
        {activeTab === "worldboss" && (
          <WorldBossView
            bots={scopedBots}
            runtimeAvailable={runtimeAvailable}
            busyAction={busyAction}
            runAction={runAction}
            selectedBoss={selectedWbBoss}
            setSelectedBoss={setSelectedWbBoss}
            wbPresetsData={wbPresetsData}
            wbPresetsLoading={wbPresetsLoading}
            onCheckVotesNow={() => runAction("force_world_boss_probe")}
          />
        )}

        {/* Tab 3: Operations & Fleet Management */}
        {activeTab === "runtime" && (
          <OperationsView
            bots={scopedBots}
            accounts={accounts}
            runtimeAvailable={runtimeAvailable}
            busyAction={busyAction}
            runAction={runAction}
            runAccountAction={runAccountAction}
            diagnostics={diagnostics}
            onRefreshDiagnostics={() => fetchJson("/api/diagnostics").then(setDiagnostics)}
            newAccount={newAccount}
            setNewAccount={setNewAccount}
            onAddAccount={(e) => {
              e?.preventDefault();
              runAction("add_account", newAccount);
            }}
            addAccountBusy={addAccountBusy}
            complications={complications}
            sessionAnalysis={sessionAnalysis}
            runSessionAnalysis={async () => {
              setSessionAnalysisLoading(true);
              try {
                const res = await fetchJsonWithFallback("/api/session/analysis?hours=24", null);
                setSessionAnalysis(res);
              } finally {
                setSessionAnalysisLoading(false);
              }
            }}
            sessionAnalysisLoading={sessionAnalysisLoading}
          />
        )}

        {/* Tab 4: Quests, Challenges & Garden */}
        {activeTab === "quests" && (
          <QuestsView
            questCatalog={questCatalog}
            questCatalogLoading={questCatalogLoading}
            questCatalogStats={questCatalogStats}
            questCategoriesMeta={questCategoriesMeta}
            questCatalogFilter={questCatalogFilter}
            setQuestCatalogFilter={setQuestCatalogFilter}
            questCatalogSearch={questCatalogSearch}
            setQuestCatalogSearch={setQuestCatalogSearch}
            onUpdateQuestRule={handleUpdateQuestRule}
            onResetQuestDefaults={handleResetQuestDefaults}
            onScanLogs={handleScanLogs}
            questCatalogScanning={questCatalogScanning}
            questScanFeedback={questScanFeedback}
            challengesData={challengesData}
            onSyncChallenges={async () => {
              setSyncChallengesBusy(true);
              try {
                const data = await fetchJsonWithFallback("/api/challenges/sync", null);
                setChallengesData(data);
              } finally {
                setSyncChallengesBusy(false);
              }
            }}
            syncChallengesBusy={syncChallengesBusy}
            runAction={runAction}
            busyAction={busyAction}
            runtimeAvailable={runtimeAvailable}
          />
        )}

        {/* Tab 5: Captcha Safety Center */}
        {activeTab === "captcha" && (
          <CaptchaView
            captchaQueueRows={captchaQueueRows}
            captchaTelemetry={captchaTelemetry}
            captchaTimers={captchaTimers}
            captchaManualAnswers={captchaManualAnswers}
            setCaptchaManualAnswers={setCaptchaManualAnswers}
            onSubmitManualAnswer={handleSubmitManualAnswer}
            onMarkResolved={() => runAction("captcha_mark_resolved")}
            setSelectedCaptchaPreview={setSelectedCaptchaPreview}
            runtimeAvailable={runtimeAvailable}
            busyAction={busyAction}
            readCaptchaDraft={(map, key, fallback) => map?.[key] ?? fallback}
            updateCaptchaDraft={(setter, key, val) => setter((prev) => ({ ...prev, [key]: val }))}
          />
        )}

        {/* Tab 6: Telemetry & Logs */}
        {activeTab === "anti_detect" && (
          <TelemetryView
            antiDetect={antiDetect}
            telemetrySearch={telemetrySearch}
            setTelemetrySearch={setTelemetrySearch}
            onRefreshTelemetry={fetchTelemetry}
            onClearTelemetry={() => runAction("clear_anti_detect_logs")}
            busyAction={busyAction}
            antiDetectLimit={antiDetectLimit}
            setAntiDetectLimit={setAntiDetectLimit}
          />
        )}

        {/* Tab 7: Configuration & Settings */}
        {activeTab === "config" && (
          <ConfigView
            configJson={configJson}
            setConfigJson={setConfigJson}
            configDirty={configDirty}
            setConfigDirty={setConfigDirty}
            onSaveConfig={handleSaveConfig}
            onFormatConfig={handleFormatConfig}
            busyAction={busyAction}
            configPath={configPath}
          />
        )}

        {/* Pokemon Art & Pokédex Modal */}
        <PokemonModal
          selectedCatch={selectedCatch}
          selectedPokemonInfo={selectedPokemonInfo}
          selectedPokemonLoading={selectedPokemonLoading}
          selectedPokemonError={selectedPokemonError}
          onClose={() => setSelectedCatch(null)}
        />
      </div>
    </div>
  );
}
