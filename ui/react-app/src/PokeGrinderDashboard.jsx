import React, { useCallback, useEffect, useMemo, useState } from "react";
import "./sakura-theme.css";

const runtimeActions = [
  { key: "start_all", label: "Start All", cls: "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500 hover:text-white" },
  { key: "pause_all", label: "Pause All", cls: "bg-orange-500/10 text-orange-400 border border-orange-500/30 hover:bg-orange-500 hover:text-white" },
  { key: "resume_all", label: "Resume All", cls: "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500 hover:text-white" },
  { key: "pause_hunt", label: "Pause Hunt", cls: "bg-slate-700 hover:bg-slate-600 text-slate-200" },
  { key: "resume_hunt", label: "Resume Hunt", cls: "bg-slate-700 hover:bg-slate-600 text-slate-200" },
  { key: "pause_fish", label: "Pause Fish", cls: "bg-slate-700 hover:bg-slate-600 text-slate-200" },
  { key: "resume_fish", label: "Resume Fish", cls: "bg-slate-700 hover:bg-slate-600 text-slate-200" },
  { key: "clear_limit", label: "Clear Limit", cls: "bg-slate-700 hover:bg-slate-600 text-slate-200" },
  { key: "stop_all", label: "Stop All", cls: "bg-red-500/10 text-red-400 border border-red-500/30 hover:bg-red-500 hover:text-white" },
  { key: "force_hunt", label: "Force Hunt", cls: "bg-slate-700 hover:bg-slate-600 text-slate-200" },
  { key: "force_fight", label: "Force Fight", cls: "bg-slate-700 hover:bg-slate-600 text-slate-200" },
  { key: "force_fish", label: "Force Fish", cls: "bg-slate-700 hover:bg-slate-600 text-slate-200" },
  { key: "force_berry_check", label: "Force Berry", cls: "bg-slate-700 hover:bg-slate-600 text-slate-200" },
];

function PokeBallIcon({ className = "" }) {
  return (
    <svg viewBox="0 0 100 100" aria-hidden="true" className={className}>
      <circle cx="50" cy="50" r="46" fill="#f4f1f2" stroke="#2f1b26" strokeWidth="6" />
      <path d="M4,50 A46,46 0 0 1 96,50" fill="#c74f7c" />
      <line x1="6" y1="50" x2="94" y2="50" stroke="#2f1b26" strokeWidth="6" />
      <circle cx="50" cy="50" r="14" fill="#f8f3f5" stroke="#2f1b26" strokeWidth="6" />
      <circle cx="50" cy="50" r="6" fill="#f8d2e0" stroke="#2f1b26" strokeWidth="2" />
    </svg>
  );
}

function LayoutIcon({ className = "" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
      <line x1="3" y1="9" x2="21" y2="9"></line>
      <line x1="9" y1="21" x2="9" y2="9"></line>
    </svg>
  );
}

function PulseIcon({ className = "" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
    </svg>
  );
}

function TerminalIcon({ className = "" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <polyline points="4 17 10 11 4 5"></polyline>
      <line x1="12" y1="19" x2="20" y2="19"></line>
    </svg>
  );
}

function CogIcon({ className = "" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <circle cx="12" cy="12" r="3"></circle>
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
    </svg>
  );
}

function SparkleIcon({ className = "" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M12 3v18M3 12h18M5.3 5.3l13.4 13.4M18.7 5.3L5.3 18.7" />
    </svg>
  );
}

function ClockIcon({ className = "" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

function TicketIcon({ className = "" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <rect x="2" y="7" width="20" height="10" rx="2" ry="2" />
      <path d="M12 11h.01" />
      <path d="M12 13h.01" />
      <path d="M7 7v10" />
      <path d="M17 7v10" />
    </svg>
  );
}

function UnlockIcon({ className = "" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0 1 9.9-1" />
    </svg>
  );
}

function WarningIcon({ className = "" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

function StatusBadge({ status, text }) {
  if (status === "ACTIVE" || status === true) {
    return <span className="bg-[#E11D48]/20 text-[#F43F5E] border border-[#E11D48]/40 px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-widest">{text || "ACTIVE"}</span>;
  }
  if (status === "INACTIVE" || status === false) {
    return <span className="bg-[#180508] text-[#9F1239] border border-[#380D16] px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-widest">{text || "INACTIVE"}</span>;
  }
  return <span className="bg-orange-950/30 text-orange-400 border border-orange-900/50 px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-widest">{text || String(status || "UNKNOWN")}</span>;
}

async function fetchJson(url, options) {
  const res = await fetch(url, { cache: "no-store", ...(options || {}) });
  const text = await res.text();
  const contentType = (res.headers.get("content-type") || "").toLowerCase();

  if (!contentType.includes("application/json")) {
    throw new Error(`Expected JSON from ${url}, got ${res.status}`);
  }

  const data = JSON.parse(text);
  if (!res.ok) {
    throw new Error(data?.error || data?.message || `HTTP ${res.status}`);
  }

  return data;
}

async function fetchJsonWithFallback(url, fallbackValue, options) {
  try {
    return await fetchJson(url, options);
  } catch {
    return fallbackValue;
  }
}

function buildFallbackConfigPayload() {
  return {
    config: {},
    config_text: "{}",
    accounts: [],
    path: "",
  };
}

function buildFallbackStatsPayload() {
  return {
    stats: {},
    path: "",
    updated: new Date().toISOString(),
  };
}

function buildFallbackRuntimePayload() {
  return {
    available: false,
    message: "Runtime endpoint unavailable",
    data: {
      bots: [],
      accounts: [],
    },
  };
}

function formatRelativeTime(ts) {
  if (!ts) return "unknown";
  const when = new Date(ts).getTime();
  if (Number.isNaN(when)) return "unknown";
  const deltaSec = Math.max(0, Math.floor((Date.now() - when) / 1000));
  if (deltaSec < 60) return `${deltaSec}s ago`;
  if (deltaSec < 3600) return `${Math.floor(deltaSec / 60)}m ago`;
  if (deltaSec < 86400) return `${Math.floor(deltaSec / 3600)}h ago`;
  return `${Math.floor(deltaSec / 86400)}d ago`;
}

function toPokeApiSlug(name) {
  return String(name || "")
    .toLowerCase()
    .replace(/[.'`:]/g, "")
    .replace(/\s+/g, "-")
    .replace(/♀/g, "-f")
    .replace(/♂/g, "-m")
    .replace(/[^a-z0-9-]/g, "")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
}

function toDisplayName(value) {
  const raw = String(value || "").replace(/-/g, " ").trim();
  if (!raw) return "Unknown";
  return raw.replace(/\b\w/g, (c) => c.toUpperCase());
}

const POKEMON_SLUG_OVERRIDES_KEY = "pg_pokemon_slug_overrides_v1";

function readPokemonSlugOverrides() {
  try {
    const raw = window.localStorage.getItem(POKEMON_SLUG_OVERRIDES_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function writePokemonSlugOverrides(map) {
  try {
    window.localStorage.setItem(POKEMON_SLUG_OVERRIDES_KEY, JSON.stringify(map || {}));
  } catch {
    // Ignore persistence failures.
  }
}

function getFlavorText(speciesData) {
  const entries = Array.isArray(speciesData?.flavor_text_entries) ? speciesData.flavor_text_entries : [];
  const english = entries.find((entry) => entry?.language?.name === "en");
  return String(english?.flavor_text || "").replace(/\f|\n|\r/g, " ").trim();
}

function formatCatchBotReturnLabel(epochSeconds) {
  const ts = Number(epochSeconds || 0);
  if (!Number.isFinite(ts) || ts <= 0) return "";

  const target = new Date(ts * 1000);
  if (Number.isNaN(target.getTime())) return "";

  const now = new Date();
  const diffMs = target.getTime() - now.getTime();
  if (diffMs <= 0) {
    return `back ${target.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
  }

  const totalMin = Math.round(diffMs / 60000);
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  const rel = h > 0 ? `${h}h ${m}m` : `${m}m`;
  const clock = target.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return `in ${rel} (${clock})`;
}

function parseCatchBotReturnTextToEpoch(returnText) {
  const raw = String(returnText || "").trim();
  if (!raw) return 0;
  const m = raw.match(/(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\s+(\d{2}):(\d{2})/);
  if (!m) return 0;

  const day = Number(m[1]);
  const monthName = String(m[2] || "").toLowerCase();
  const year = Number(m[3]);
  const hour = Number(m[4]);
  const minute = Number(m[5]);
  const months = {
    january: 0, february: 1, march: 2, april: 3, may: 4, june: 5,
    july: 6, august: 7, september: 8, october: 9, november: 10, december: 11,
  };
  if (!(monthName in months)) return 0;

  const dt = new Date(year, months[monthName], day, hour, minute, 0, 0);
  const ms = dt.getTime();
  if (!Number.isFinite(ms) || Number.isNaN(ms)) return 0;
  return Math.floor(ms / 1000);
}

function rarityVisual(rarity) {
  const lowered = String(rarity || "").toLowerCase();
  if (lowered.includes("legendary")) {
    return {
      accent: "text-amber-300",
      border: "border-amber-500/30",
      bg: "bg-amber-500/10",
    };
  }
  if (lowered.includes("mythical")) {
    return {
      accent: "text-fuchsia-300",
      border: "border-fuchsia-500/30",
      bg: "bg-fuchsia-500/10",
    };
  }
  if (lowered.includes("shiny")) {
    return {
      accent: "text-rose-300",
      border: "border-rose-500/30",
      bg: "bg-rose-500/10",
    };
  }
  return {
    accent: "text-emerald-300",
    border: "border-emerald-500/30",
    bg: "bg-emerald-500/10",
  };
}

function sanitizeEventDisplayLine(line, preserveIds = false) {
  let value = String(line || "").trim();
  if (!value) return "";

  if (!preserveIds) {
    value = value.replace(/#\d+\s*/g, "");
  }

  value = value.replace(/\s+/g, " ").trim();
  return value;
}

function resolveCaptchaPreviewSrc(channelState) {
  const localPath = String(channelState?.last_image_path || "").trim();
  if (localPath) {
    return `/api/captcha/image?path=${encodeURIComponent(localPath)}`;
  }

  const remoteUrl = String(channelState?.last_image_url || "").trim();
  return remoteUrl || "";
}

export default function PokeGrinderDashboard() {
  const [activeTab, setActiveTab] = useState("overview");
  const [status, setStatus] = useState({ text: "Idle", kind: "idle" });
  const [statsPath, setStatsPath] = useState("");
  const [configPath, setConfigPath] = useState("");
  const [stats, setStats] = useState({});
  const [runtime, setRuntime] = useState({ available: false, data: { bots: [] }, message: "Runtime not attached" });
  const [configJson, setConfigJson] = useState("{}");
  const [busyAction, setBusyAction] = useState("");
  const [statsRefreshMs, setStatsRefreshMs] = useState(8000);
  const [runtimeRefreshMs, setRuntimeRefreshMs] = useState(3000);
  const [actionHistory, setActionHistory] = useState([]);
  const [diagnostics, setDiagnostics] = useState(null);
  const [diagnosticsError, setDiagnosticsError] = useState("");
  const [configDirty, setConfigDirty] = useState(false);
  const [configSyncedAt, setConfigSyncedAt] = useState(null);
  const [antiDetect, setAntiDetect] = useState({ events: [], count: 0, log_path: "" });
  const [antiDetectLimit, setAntiDetectLimit] = useState(200);
  const [telemetrySearch, setTelemetrySearch] = useState("");
  const [captchaTelemetry, setCaptchaTelemetry] = useState({
    counts: { attempts: 0, outcomes: 0, resolved_outcomes: 0, failed_candidates: 0, labels: 0 },
    paths: {},
    attempts: [],
    outcomes: [],
    failed_candidates: [],
    labels: [],
  });
  const [captchaTelemetryLimit, setCaptchaTelemetryLimit] = useState(60);
  const [captchaTelemetrySearch, setCaptchaTelemetrySearch] = useState("");
  const [captchaManualAnswers, setCaptchaManualAnswers] = useState({});
  const [captchaChannelHints, setCaptchaChannelHints] = useState({});
  const [captchaMaxAttemptsDraft, setCaptchaMaxAttemptsDraft] = useState({});
  const [captchaManualUsersDraft, setCaptchaManualUsersDraft] = useState({});
  const [captchaAlertPingDraft, setCaptchaAlertPingDraft] = useState({});
  const [expandedCaptchaConfig, setExpandedCaptchaConfig] = useState("");
  const [selectedCaptchaPreview, setSelectedCaptchaPreview] = useState(null);
  const [captchaTimers, setCaptchaTimers] = useState({});
  const [recentRareCatches, setRecentRareCatches] = useState([]);
  const [recentItemRetrieves, setRecentItemRetrieves] = useState([]);
  const [selectedUserScope, setSelectedUserScope] = useState("all");
  const [selectedCatch, setSelectedCatch] = useState(null);
  const [selectedPokemonInfo, setSelectedPokemonInfo] = useState(null);
  const [selectedPokemonError, setSelectedPokemonError] = useState("");
  const [selectedPokemonLoading, setSelectedPokemonLoading] = useState(false);
  const [pokemonSlugOverrides, setPokemonSlugOverrides] = useState(() => readPokemonSlugOverrides());
  const [pokemonFallbackPrompt, setPokemonFallbackPrompt] = useState(null);
  const [pokemonFallbackBusy, setPokemonFallbackBusy] = useState(false);
  const [overviewSection, setOverviewSection] = useState("highlights");
  const [eventsFocusUser, setEventsFocusUser] = useState("");
  const [newAccount, setNewAccount] = useState({
    token: "",
    huntingChannelId: "",
    fishingChannelId: "",
    berryChannelId: "",
    requiredServerId: "",
    captchaAutoAnswerEnabled: true,
    captchaMaxAutoAttempts: "3",
    captchaManualAllowedUserIds: "",
    captchaAlertsEnabled: false,
    captchaAlertChannelId: "",
    captchaAlertPing: "",
    captchaAlertWebhookUrl: "",
    captchaAlertCooldownSeconds: "",
    startAfterAdd: true,
  });

  const runtimeAvailable = Boolean(runtime?.available);
  const telemetrySearchTrimmed = String(telemetrySearch || "").trim();
  const captchaTelemetrySearchTrimmed = String(captchaTelemetrySearch || "").trim();
  const bots = runtime?.data?.bots || [];
  const accounts = runtime?.data?.accounts || [];

  const fetchAntiDetectTelemetry = async (searchValue = telemetrySearchTrimmed) => {
    const params = new URLSearchParams();
    params.set("limit", String(antiDetectLimit));
    params.set("ts", String(Date.now()));
    if (searchValue) {
      params.set("q", searchValue);
    }

    const ad = await fetchJson(`/api/telemetry/anti-detect?${params.toString()}`);
    setAntiDetect(ad || { events: [], count: 0, log_path: "" });
  };

  const fetchCaptchaTelemetry = async (searchValue = captchaTelemetrySearchTrimmed) => {
    const params = new URLSearchParams();
    params.set("limit", String(captchaTelemetryLimit));
    params.set("ts", String(Date.now()));
    if (searchValue) {
      params.set("q", searchValue);
    }

    const data = await fetchJson(`/api/telemetry/captcha?${params.toString()}`);
    setCaptchaTelemetry(
      data || {
        counts: { attempts: 0, outcomes: 0, resolved_outcomes: 0, failed_candidates: 0, labels: 0 },
        paths: {},
        attempts: [],
        outcomes: [],
        failed_candidates: [],
        labels: [],
      },
    );
  };

  const accountLabelById = useMemo(
    () => Object.fromEntries(
      (accounts || []).map((account, idx) => [
        String(account?.id || `account-${idx}`),
        String(account?.display_name || account?.username || account?.label || `account#${idx + 1}`),
      ]),
    ),
    [accounts],
  );

  const userScopeOptions = useMemo(() => {
    const options = [{ id: "all", label: "All Users" }];
    const seen = new Set();

    (bots || []).forEach((bot, idx) => {
      const id = String(bot?.id || "").trim();
      if (!id || seen.has(id)) {
        return;
      }
      seen.add(id);

      const username = String(bot?.username || "").trim();
      const fallback = accountLabelById[id] || `account#${idx + 1}`;
      options.push({ id, label: username && username !== "Not ready" ? username : fallback });
    });

    return options;
  }, [bots, accountLabelById]);

  useEffect(() => {
    if (selectedUserScope === "all") {
      return;
    }
    if (!userScopeOptions.some((option) => option.id === selectedUserScope)) {
      setSelectedUserScope("all");
    }
  }, [selectedUserScope, userScopeOptions]);

  const scopedBots = useMemo(
    () => selectedUserScope === "all"
      ? bots
      : bots.filter((bot) => String(bot?.id || "") === selectedUserScope),
    [bots, selectedUserScope],
  );

  const runtimeDisplayBots = useMemo(
    () => selectedUserScope === "all"
      ? bots
      : bots.filter((bot) => String(bot?.id || "") === selectedUserScope),
    [bots, selectedUserScope],
  );

  const runtimeDisplayAccounts = useMemo(
    () => selectedUserScope === "all"
      ? accounts
      : accounts.filter((account) => String(account?.id || "") === selectedUserScope),
    [accounts, selectedUserScope],
  );

  const accountsById = useMemo(() => {
    const m = {};
    (accounts || []).forEach((a) => {
      if (a?.id != null && String(a.id) !== "") m[String(a.id)] = a;
    });
    return m;
  }, [accounts]);

  const isBotDiscordReady = (bot) =>
    bot && typeof bot.ready === "boolean"
      ? bot.ready
      : Boolean(bot?.username && bot.username !== "Not ready");

  const dayTotals = useMemo(
    () => scopedBots.reduce(
      (acc, bot) => {
        const v = bot?.day || bot?.session || {};
        acc.encounters += Number(v.encounters || 0);
        acc.catches += Number(v.catches || 0);
        acc.fishEncounters += Number(v.fish_encounters || 0);
        acc.fishCatches += Number(v.fish_catches || 0);
        acc.coins += Number(v.coins || 0);
        return acc;
      },
      { encounters: 0, catches: 0, fishEncounters: 0, fishCatches: 0, coins: 0 },
    ),
    [scopedBots],
  );

  const lifetimeTotals = useMemo(
    () => scopedBots.reduce(
      (acc, bot) => {
        const v = bot?.lifetime || {};
        acc.encounters += Number(v.encounters || 0);
        acc.catches += Number(v.catches || 0);
        acc.fishEncounters += Number(v.fish_encounters || 0);
        acc.fishCatches += Number(v.fish_catches || 0);
        acc.coins += Number(v.coins || 0);
        return acc;
      },
      { encounters: 0, catches: 0, fishEncounters: 0, fishCatches: 0, coins: 0 },
    ),
    [scopedBots],
  );

  const aggregateRarity = (sourceBots, scope, key) => sourceBots.reduce((acc, bot) => {
    const bucket = bot?.[scope]?.[key] || {};
    Object.entries(bucket).forEach(([name, count]) => {
      acc[name] = (acc[name] || 0) + Number(count || 0);
    });
    return acc;
  }, {});

  const huntSessionRarity = useMemo(() => aggregateRarity(scopedBots, "day", "hunt_rarity_catches"), [scopedBots]);
  const huntLifetimeRarity = useMemo(() => aggregateRarity(scopedBots, "lifetime", "hunt_rarity_catches"), [scopedBots]);
  const fishSessionRarity = useMemo(() => aggregateRarity(scopedBots, "day", "fish_rarity_catches"), [scopedBots]);
  const fishLifetimeRarity = useMemo(() => aggregateRarity(scopedBots, "lifetime", "fish_rarity_catches"), [scopedBots]);

  const berryRows = useMemo(
    () => bots
      .filter((bot) => bot?.berry?.enabled)
      .map((bot) => {
        const berry = bot.berry || {};
        const pendingSlots = berry.pending_water_slots || [];
        const isWorking = Boolean(berry.water_in_progress);
        const hasPending = pendingSlots.length > 0;
        const rawSlotStates = Array.isArray(berry.slot_states) ? berry.slot_states : [];
        const visibleSlotStates = rawSlotStates.filter((slotState) => {
          const s = String(slotState?.state || "").toLowerCase();
          return s !== "locked" && s !== "empty";
        });
        const plantedSummary = Array.from(new Set(
          visibleSlotStates
            .map((slotState) => String(slotState?.berry || "").trim())
            .filter(Boolean),
        )).join(", ") || "None";
        const hasNeedsWater = visibleSlotStates.some((slotState) => String(slotState?.state || "") === "Needs Water");
        const hasReady = visibleSlotStates.some((slotState) => String(slotState?.state || "") === "Ready");
        const hasHealthy = visibleSlotStates.some((slotState) => {
          const s = String(slotState?.state || "");
          return s === "Healthy" || s === "Drying";
        });
        const lastCheckTs = Number(berry.last_check_trigger_time || 0);
        const ageSeconds = lastCheckTs > 0 ? Math.max(0, Math.floor(Date.now() / 1000 - lastCheckTs)) : null;

        let ageLabel = "Never";
        if (ageSeconds !== null) {
          if (ageSeconds < 60) ageLabel = `${ageSeconds}s ago`;
          else if (ageSeconds < 3600) ageLabel = `${Math.floor(ageSeconds / 60)}m ago`;
          else ageLabel = `${Math.floor(ageSeconds / 3600)}h ago`;
        }

        let state = "Idle";
        let stateKind = "idle";
        if (isWorking) {
          state = "Watering";
          stateKind = "working";
        } else if (hasNeedsWater || hasPending) {
          state = "Needs Water";
          stateKind = "attention";
        } else if (hasReady) {
          state = "Ready";
          stateKind = "ok";
        } else if (hasHealthy) {
          state = "Healthy";
          stateKind = "ok";
        }

        return {
          id: bot.id || "",
          username: bot.username,
          source: berry.last_check_source || "none",
          slotStates: visibleSlotStates,
          plantedSummary,
          pendingSlotsText: pendingSlots.join(", ") || "None",
          pendingCount: pendingSlots.length,
          state,
          stateKind,
          activity: isWorking ? "Sending ;berry water commands" : (hasNeedsWater || hasPending) ? "Waiting for watering cycle" : hasReady ? "Ready to harvest" : "No pending tasks",
          ageLabel,
        };
      }),
    [bots],
  );

  const runtimeSummary = useMemo(
    () => bots.reduce(
      (acc, bot) => {
        if (!isBotDiscordReady(bot)) {
          return acc;
        }
        if (!bot.hunt_paused) acc.huntRunning += 1;
        if (!bot.fish_paused) acc.fishRunning += 1;
        if (bot.captcha_active) acc.captcha += 1;
        if (bot.limit) acc.limit += 1;
        return acc;
      },
      { huntRunning: 0, fishRunning: 0, captcha: 0, limit: 0 },
    ),
    [bots],
  );

  const limitedEventRows = useMemo(
    () => scopedBots.map((bot, idx) => {
      const limited = bot?.limited_events || {};
      const bonus = limited?.bonus || {};
      const events = limited?.events || {};
      const unlocks = limited?.unlocks || {};
      return {
        key: bot?.id || `${bot?.username || "bot"}-${idx}`,
        target: bot?.id || bot?.username || "",
        username: bot?.username || "Unknown",
        status: String(limited?.status || "pending"),
        lastChecked: String(limited?.last_checked_utc || ""),
        nextCheck: String(limited?.next_check_utc || ""),
        intervalSeconds: Number(limited?.interval_seconds || 0),
        bonus,
        events,
        unlocks,
      };
    }),
    [scopedBots],
  );

  useEffect(() => {
    if (limitedEventRows.length === 0) {
      if (eventsFocusUser) {
        setEventsFocusUser("");
      }
      return;
    }

    const exists = limitedEventRows.some((row) => row.key === eventsFocusUser);
    if (!eventsFocusUser || !exists) {
      setEventsFocusUser(limitedEventRows[0].key);
    }
  }, [limitedEventRows, eventsFocusUser]);

  const focusedEventsRow = useMemo(
    () => limitedEventRows.find((row) => row.key === eventsFocusUser) || limitedEventRows[0] || null,
    [limitedEventRows, eventsFocusUser],
  );

  const globalDirectives = useMemo(() => {
    const directives = [];
    const seen = new Set();

    for (const row of limitedEventRows) {
      const eventEnd = String(row?.events?.event_end || row?.bonus?.event_end || "").trim();
      if (eventEnd && !seen.has(`end:${eventEnd}`)) {
        directives.push({
          title: "Event End",
          detail: eventEnd,
          tone: "warn",
        });
        seen.add(`end:${eventEnd}`);
      }

      const eventLines = Array.isArray(row?.events?.important_lines) ? row.events.important_lines : [];
      for (const line of eventLines) {
        const value = sanitizeEventDisplayLine(line);
        if (!value || seen.has(`event:${value}`)) {
          continue;
        }
        if (/^id:\s*\d+|events\s+buy|\b50,?000\b|\b10,?000\b/i.test(value)) {
          continue;
        }
        if (/available|spawning|back in|rotation|event\s+ends/i.test(value)) {
          directives.push({
            title: "Directive",
            detail: value,
            tone: "ok",
          });
          seen.add(`event:${value}`);
        }
        if (directives.length >= 6) {
          break;
        }
      }

      if (directives.length >= 6) {
        break;
      }
    }

    return directives.slice(0, 6);
  }, [limitedEventRows]);

  const focusedEventDetails = useMemo(() => {
    if (!focusedEventsRow) {
      return null;
    }

    const splitLines = (payload) => {
      const important = Array.isArray(payload?.important_lines) ? payload.important_lines : [];
      const preview = String(payload?.raw_preview || "")
        .split("\n")
        .map((line) => String(line || "").trim())
        .filter(Boolean);
      const seen = new Set();
      return [...important, ...preview].filter((line) => {
        if (!line || seen.has(line)) return false;
        seen.add(line);
        return true;
      });
    };

    const bonusLines = splitLines(focusedEventsRow.bonus);
    const eventLines = splitLines(focusedEventsRow.events);
    const unlockLines = splitLines(focusedEventsRow.unlocks);
    const bonusBlob = bonusLines.join("\n");
    const eventBlob = eventLines.join("\n");

    const findState = (lines, regex) => {
      for (const line of lines) {
        const m = line.match(regex);
        if (m) {
          return String(m[1] || "").toUpperCase();
        }
      }
      return "UNKNOWN";
    };

    const status = {
      ticket: (() => {
        const direct = findState(eventLines, /event\s+ticket[^\n]*\b(active|inactive)\b/i);
        if (direct !== "UNKNOWN") return direct;
        const m = eventBlob.match(/your\s+event\s+ticket[^\n]*\b(active|inactive)\b/i);
        return m ? String(m[1] || "").toUpperCase() : "UNKNOWN";
      })(),
      vote: (() => {
        const direct = findState(bonusLines, /vote\s+bonuses?.*\b(active|inactive)\b/i);
        if (direct !== "UNKNOWN") return direct;
        const m = bonusBlob.match(/your\s+vote\s+bonuses[^\n]*\b(active|inactive)\b/i);
        return m ? String(m[1] || "").toUpperCase() : "UNKNOWN";
      })(),
      eggRate: findState(bonusLines, /2x\s+egg\s+hatch\s+rate:\s*(active|inactive)/i),
      doubleExp: findState(bonusLines, /double\s+exp\s+bonus:\s*(active|inactive)/i),
    };

    const checklist = eventLines
      .filter((line) => /checklist\s+reward|special\s+checklist\s+reward/i.test(line))
      .slice(0, 4)
      .map((line) => ({
        text: sanitizeEventDisplayLine(line),
        special: /special/i.test(line),
      }));

    const unlocks = [];
    for (let i = 0; i < unlockLines.length; i += 1) {
      const line = unlockLines[i];
      if (!line) continue;
      if (/^_+|event exclusive|vote exclusive|catchable|hatch exclusive|research exclusive|checked\s+means|spawn\s+rate:|\/pokemon\s+spawn|on\s+legendary|on\s+any\s+\/fish\s+spawn/i.test(line)) {
        continue;
      }
      if (!/[A-Z][a-z]+/.test(line)) {
        continue;
      }
      const next = unlockLines[i + 1] || "";
      const reqCandidate = /you\s+need|requires|required|in\s+your\s+box|fossil/i.test(next) ? sanitizeEventDisplayLine(next, true) : "";
      const req = /you\s+need\s+and\s+in\s+your\s+box\.?$/i.test(reqCandidate) ? "" : reqCandidate;
      unlocks.push({ text: sanitizeEventDisplayLine(line), req });
      if (unlocks.length >= 6) break;
    }

    const modifiers = bonusLines
      .filter((line) => /\+\d+%|expired|drop\s+rate|swap\s+rate|fishing\s+spawns|checklist\s+shiny|trainer\s+icon|world\s+boss/i.test(line))
      .filter((line) => !/global\s+bonuses|boosted\s+spawn\s+rates|player-activated\s+global\s+bonuses|activate\s+a\s+specific|event\s+vouchers\s+using|recent\s+player-activated\s+bonuses|activated\s+a\s+.*bonus/i.test(line))
      .slice(0, 10)
      .map((line) => ({
        text: sanitizeEventDisplayLine(line),
        active: !/expired|inactive/i.test(line),
      }));

    return { status, checklist, unlocks, modifiers };
  }, [focusedEventsRow]);

  const captchaDisplayBots = useMemo(
    () => runtimeDisplayBots.filter((bot) => {
      const channelCount = Number(bot?.captcha?.active_count || 0);
      const hasConfiguredCaptcha = Number(bot?.automations?.captcha_auto_max_attempts || 0) > 0;
      return channelCount > 0 || hasConfiguredCaptcha;
    }),
    [runtimeDisplayBots],
  );

  const captchaQueueRows = useMemo(() => {
    const rows = [];

    captchaDisplayBots.forEach((bot, idx) => {
      const draftKey = String(bot?.id || `${bot?.username || "bot"}-${idx}`);
      const channels = [
        { hint: "hunting", channelType: "HUNTING", state: bot?.captcha?.hunting || {} },
        { hint: "fishing", channelType: "FISHING", state: bot?.captcha?.fishing || {} },
      ];

      channels.forEach((entry) => {
        if (!entry.state?.active) {
          return;
        }
        const image = resolveCaptchaPreviewSrc(entry.state);
        rows.push({
          key: `${draftKey}-${entry.hint}`,
          bot,
          botIndex: idx,
          draftKey,
          hint: entry.hint,
          channelType: entry.channelType,
          channelId: String(entry.state?.channel_id || "").trim(),
          prediction: String(entry.state?.last_prediction || "-").trim() || "-",
          image,
          jumpUrl: String(entry.state?.jump_url || "").trim(),
          timeElapsed: formatRelativeTime(
            entry.state?.last_seen_utc
            || entry.state?.last_activity_utc
            || entry.state?.last_detected_utc
            || entry.state?.ts_utc,
          ),
          captcha_detected_utc: Number(entry.state?.last_detected_utc || entry.state?.detected_utc || entry.state?.ts_utc || 0),
        });
      });
    });

    return rows;
  }, [captchaDisplayBots]);

  const rareCatchCards = useMemo(
    () => (recentRareCatches || []).map((row, idx) => {
      const visual = rarityVisual(row.rarity);
      return {
        key: `${row.ts || "na"}-${row.account || "na"}-${idx}`,
        name: row.pokemon_name || "Unknown",
        rarity: row.rarity || "Rare",
        account: row.account || "unknown",
        time: formatRelativeTime(row.ts),
        sprite: row.sprite || "",
        ...visual,
      };
    }),
    [recentRareCatches],
  );

  const itemRetrieveCards = useMemo(
    () => (recentItemRetrieves || []).map((row, idx) => ({
      key: `${row.ts || "na"}-${row.account || "na"}-${row.item_name || "item"}-${idx}`,
      account: row.account || "unknown",
      itemName: row.item_name || "Unknown Item",
      itemEmoji: row.item_icon_emoji || "🎁",
      itemSprite: row.item_sprite || "",
      pokemonName: row.pokemon_name || "Unknown",
      pokemonSprite: row.pokemon_sprite || "",
      rarity: row.rarity || "Unknown",
      time: formatRelativeTime(row.ts),
    })),
    [recentItemRetrieves],
  );

  const closePokemonModal = () => {
    setSelectedCatch(null);
    setSelectedPokemonInfo(null);
    setSelectedPokemonError("");
    setSelectedPokemonLoading(false);
    setPokemonFallbackPrompt(null);
    setPokemonFallbackBusy(false);
  };

  const openPokemonDetails = (pokemon) => {
    setSelectedCatch(pokemon);
    setSelectedPokemonInfo(null);
    setSelectedPokemonError("");
    setSelectedPokemonLoading(true);
    setPokemonFallbackPrompt(null);
    setPokemonFallbackBusy(false);
  };

  const handleScrollRegionWheel = (event) => {
    const current = event.currentTarget;
    const deltaY = Number(event.deltaY || 0);
    if (!current || deltaY === 0) {
      return;
    }

    const canScroll = (node) => {
      if (!node || !(node instanceof HTMLElement)) {
        return false;
      }

      const style = window.getComputedStyle(node);
      const overflowY = String(style.overflowY || "").toLowerCase();
      const allowsScroll = overflowY === "auto" || overflowY === "scroll" || overflowY === "overlay";
      if (!allowsScroll || node.scrollHeight <= node.clientHeight + 1) {
        return false;
      }

      if (deltaY < 0) {
        return node.scrollTop > 0;
      }
      return node.scrollTop + node.clientHeight < node.scrollHeight - 1;
    };

    if (canScroll(current)) {
      return;
    }

    let parent = current.parentElement;
    while (parent) {
      if (canScroll(parent)) {
        event.preventDefault();
        parent.scrollTop += deltaY;
        return;
      }
      parent = parent.parentElement;
    }

    event.preventDefault();
    window.scrollBy({ top: deltaY, left: 0, behavior: "auto" });
  };

  const refreshAll = async () => {
    setStatus({ text: "Refreshing...", kind: "idle" });
    try {
      const [cfg, st, rt] = await Promise.all([
        fetchJsonWithFallback(`/api/config?ts=${Date.now()}`, buildFallbackConfigPayload()),
        fetchJsonWithFallback("/api/stats", buildFallbackStatsPayload()),
        fetchJsonWithFallback("/api/runtime/status", buildFallbackRuntimePayload()),
      ]);
      setConfigPath(cfg.path || "");
      if (!configDirty) {
        setConfigJson(String(cfg.config_text || JSON.stringify(cfg.config || {}, null, 2)));
        setConfigSyncedAt(Date.now());
      }
      setStatsPath(`${st.path || ""} | ${new Date(st.updated).toLocaleTimeString()}`);
      setStats(st.stats || {});
      setRuntime(rt || buildFallbackRuntimePayload());
      try {
        await fetchAntiDetectTelemetry();
      } catch {
        // Optional panel; keep dashboard functional if this endpoint is unavailable.
      }
      try {
        const rare = await fetchJson(`/api/telemetry/recent-rare-catches?hours=24&limit=8&ts=${Date.now()}`);
        setRecentRareCatches(Array.isArray(rare.rows) ? rare.rows : []);
      } catch {
        setRecentRareCatches([]);
      }
      try {
        const items = await fetchJson(`/api/telemetry/recent-item-retrieves?hours=24&limit=12&ts=${Date.now()}`);
        setRecentItemRetrieves(Array.isArray(items.rows) ? items.rows : []);
      } catch {
        setRecentItemRetrieves([]);
      }
      try {
        await fetchCaptchaTelemetry();
      } catch {
        setCaptchaTelemetry({
          counts: { attempts: 0, outcomes: 0, failed_candidates: 0, labels: 0 },
          paths: {},
          attempts: [],
          outcomes: [],
          failed_candidates: [],
          labels: [],
        });
      }
      const backendLikelyOffline = !rt?.available && !cfg?.path && !st?.path;
      setStatus(
        backendLikelyOffline
          ? { text: "Backend unavailable: using safe fallbacks", kind: "bad" }
          : { text: "Synced", kind: "ok" },
      );
    } catch (err) {
      setStatus({ text: `Error: ${err.message}`, kind: "bad" });
    }
  };

  const reloadConfigFromDisk = async () => {
    try {
      const cfg = await fetchJsonWithFallback(`/api/config?ts=${Date.now()}`, buildFallbackConfigPayload());
      setConfigPath(cfg.path || "");
      setConfigJson(String(cfg.config_text || JSON.stringify(cfg.config || {}, null, 2)));
      setConfigDirty(false);
      setConfigSyncedAt(Date.now());
      setStatus(cfg.path ? { text: "Config reloaded from disk", kind: "ok" } : { text: "Config endpoint unavailable: showing fallback", kind: "bad" });
    } catch (err) {
      setStatus({ text: `Reload failed: ${err.message}`, kind: "bad" });
    }
  };

  const refreshDiagnostics = useCallback(async () => {
    try {
      let res = await fetch("/api/diagnostics", { cache: "no-store" });
      if (res.status === 404) {
        res = await fetch("/api/runtime/diagnostics", { cache: "no-store" });
      }
      const text = await res.text();
      const data = JSON.parse(text);
      setDiagnostics(data);
      setDiagnosticsError(data.ok === false ? String(data.error || "") : "");
    } catch (e) {
      setDiagnostics(null);
      setDiagnosticsError(e.message || String(e));
    }
  }, []);

  useEffect(() => {
    document.title = "YveltalGo";
  }, []);

  useEffect(() => {
    if (activeTab !== "runtime") {
      return;
    }
    void refreshDiagnostics();
    const t = setInterval(() => void refreshDiagnostics(), 8000);
    return () => clearInterval(t);
  }, [activeTab, refreshDiagnostics]);

  useEffect(() => {
    refreshAll();
  }, []);

  useEffect(() => {
    const html = document.documentElement;
    const body = document.body;
    const prevHtmlOverflow = html.style.overflow;
    const prevBodyOverflow = body.style.overflow;

    html.style.overflow = "hidden";
    body.style.overflow = "hidden";

    return () => {
      html.style.overflow = prevHtmlOverflow;
      body.style.overflow = prevBodyOverflow;
    };
  }, []);

  useEffect(() => {
    const statsTimer = setInterval(async () => {
      try {
        const st = await fetchJsonWithFallback("/api/stats", buildFallbackStatsPayload());
        setStatsPath(`${st.path || ""} | ${new Date(st.updated).toLocaleTimeString()}`);
        setStats(st.stats || {});
      } catch {
        // Ignore noisy refresh errors.
      }
    }, statsRefreshMs);

    const runtimeTimer = setInterval(async () => {
      try {
        const rt = await fetchJsonWithFallback("/api/runtime/status", buildFallbackRuntimePayload());
        setRuntime(rt || buildFallbackRuntimePayload());
        if (activeTab === "overview") {
          const rare = await fetchJsonWithFallback(
            `/api/telemetry/recent-rare-catches?hours=24&limit=8&ts=${Date.now()}`,
            { rows: [] },
          );
          setRecentRareCatches(Array.isArray(rare.rows) ? rare.rows : []);
          const items = await fetchJsonWithFallback(
            `/api/telemetry/recent-item-retrieves?hours=24&limit=12&ts=${Date.now()}`,
            { rows: [] },
          );
          setRecentItemRetrieves(Array.isArray(items.rows) ? items.rows : []);
        }
      } catch {
        setRuntime(buildFallbackRuntimePayload());
      }
    }, runtimeRefreshMs);

    const antiDetectTimer = setInterval(async () => {
      if (activeTab !== "anti_detect") {
        return;
      }

      try {
        await fetchAntiDetectTelemetry();
      } catch {
        // Ignore periodic telemetry poll errors.
      }
    }, 3000);

    const captchaTelemetryTimer = setInterval(async () => {
      if (activeTab !== "captcha") {
        return;
      }

      try {
        await fetchCaptchaTelemetry();
      } catch {
        // Ignore periodic captcha telemetry poll errors.
      }
    }, 3000);

    const configTimer = setInterval(async () => {
      if (activeTab !== "config" || configDirty) {
        return;
      }

      try {
        const cfg = await fetchJsonWithFallback(`/api/config?ts=${Date.now()}`, buildFallbackConfigPayload());
        setConfigPath(cfg.path || "");
        setConfigJson(String(cfg.config_text || JSON.stringify(cfg.config || {}, null, 2)));
      } catch {
        // Ignore periodic config poll errors.
      }
    }, 5000);

    return () => {
      clearInterval(statsTimer);
      clearInterval(runtimeTimer);
      clearInterval(antiDetectTimer);
      clearInterval(captchaTelemetryTimer);
      clearInterval(configTimer);
    };
  }, [
    activeTab,
    configDirty,
    statsRefreshMs,
    runtimeRefreshMs,
    antiDetectLimit,
    telemetrySearchTrimmed,
    captchaTelemetryLimit,
    captchaTelemetrySearchTrimmed,
  ]);

  useEffect(() => {
    if (activeTab !== "anti_detect") {
      return;
    }

    const debounce = setTimeout(() => {
      fetchAntiDetectTelemetry().catch(() => {
        // Ignore search-triggered fetch errors.
      });
    }, 250);

    return () => clearTimeout(debounce);
  }, [activeTab, antiDetectLimit, telemetrySearchTrimmed]);

  useEffect(() => {
    if (activeTab !== "captcha") {
      return;
    }

    const debounce = setTimeout(() => {
      fetchCaptchaTelemetry().catch(() => {
        // Ignore search-triggered fetch errors.
      });
    }, 250);

    return () => clearTimeout(debounce);
  }, [activeTab, captchaTelemetryLimit, captchaTelemetrySearchTrimmed]);

  const fetchPokemonDetailsBySlug = useCallback(async (pokemonSlug, catchData) => {
    const pokemonRes = await fetch(`https://pokeapi.co/api/v2/pokemon/${encodeURIComponent(pokemonSlug)}`);
    if (!pokemonRes.ok) {
      throw new Error(`Could not load ${catchData?.name || pokemonSlug} from PokeAPI`);
    }

    const pokemonData = await pokemonRes.json();
    const speciesRes = await fetch(pokemonData?.species?.url || "");
    const speciesData = speciesRes.ok ? await speciesRes.json() : null;

    const officialArtwork = pokemonData?.sprites?.other?.["official-artwork"]?.front_default || "";
    const fallbackSprite = pokemonData?.sprites?.front_default || catchData?.sprite || "";

    return {
      id: pokemonData?.id || 0,
      name: toDisplayName(pokemonData?.name || catchData?.name || pokemonSlug),
      heightMeters: Number(pokemonData?.height || 0) / 10,
      weightKg: Number(pokemonData?.weight || 0) / 10,
      types: (pokemonData?.types || []).map((item) => toDisplayName(item?.type?.name)).filter(Boolean),
      abilities: (pokemonData?.abilities || []).map((item) => toDisplayName(item?.ability?.name)).filter(Boolean),
      generation: toDisplayName(speciesData?.generation?.name || ""),
      flavor: getFlavorText(speciesData),
      sprite: officialArtwork || fallbackSprite,
    };
  }, []);

  const discoverPokemonFallbackChoices = useCallback(async (slug) => {
    const probeCandidates = Array.from(new Set([
      slug,
      String(slug || "").split("-")[0],
      String(slug || "").replace(/-(male|female|form|mode|style|variant)$/i, ""),
    ].filter(Boolean)));

    const choiceSlugs = new Set();
    for (const candidate of probeCandidates) {
      const speciesRes = await fetch(`https://pokeapi.co/api/v2/pokemon-species/${encodeURIComponent(candidate)}`);
      if (!speciesRes.ok) {
        continue;
      }

      const speciesData = await speciesRes.json();
      const varieties = Array.isArray(speciesData?.varieties) ? speciesData.varieties : [];
      for (const variety of varieties) {
        const name = String(variety?.pokemon?.name || "").trim();
        if (name) {
          choiceSlugs.add(name);
        }
      }
    }

    return Array.from(choiceSlugs).map((choiceSlug) => ({
      slug: choiceSlug,
      label: toDisplayName(choiceSlug),
    }));
  }, []);

  const handlePokemonFallbackChoice = useCallback(async (choiceSlug) => {
    if (!selectedCatch?.name || !choiceSlug) {
      return;
    }

    setPokemonFallbackBusy(true);
    setSelectedPokemonLoading(true);
    try {
      const info = await fetchPokemonDetailsBySlug(choiceSlug, selectedCatch);
      setSelectedPokemonInfo(info);
      setSelectedPokemonError("");
      setPokemonFallbackPrompt(null);

      const baseSlug = toPokeApiSlug(selectedCatch.name);
      if (baseSlug) {
        const nextOverrides = { ...pokemonSlugOverrides, [baseSlug]: choiceSlug };
        setPokemonSlugOverrides(nextOverrides);
        writePokemonSlugOverrides(nextOverrides);
      }
    } catch (err) {
      setSelectedPokemonInfo(null);
      setSelectedPokemonError(err?.message || "Could not load Pokemon details");
    } finally {
      setSelectedPokemonLoading(false);
      setPokemonFallbackBusy(false);
    }
  }, [fetchPokemonDetailsBySlug, pokemonSlugOverrides, selectedCatch]);

  useEffect(() => {
    if (!selectedCatch?.name) {
      return;
    }

    let disposed = false;

    const fetchPokemonDetails = async () => {
      try {
        const baseSlug = toPokeApiSlug(selectedCatch.name);
        if (!baseSlug) {
          throw new Error("Pokemon name is unavailable");
        }

        const preferredSlug = String(pokemonSlugOverrides?.[baseSlug] || baseSlug || "").trim();
        const info = await fetchPokemonDetailsBySlug(preferredSlug, selectedCatch);
        if (disposed) {
          return;
        }

        setSelectedPokemonInfo(info);
        setSelectedPokemonError("");
        setPokemonFallbackPrompt(null);
      } catch (err) {
        if (disposed) {
          return;
        }

        const baseSlug = toPokeApiSlug(selectedCatch.name);
        const choices = baseSlug ? await discoverPokemonFallbackChoices(baseSlug) : [];
        if (disposed) {
          return;
        }

        setSelectedPokemonInfo(null);
        if (choices.length > 0) {
          setSelectedPokemonError("PokeAPI could not resolve this exact form. Please choose the correct Pokemon form below.");
          setPokemonFallbackPrompt({
            sourceName: selectedCatch.name,
            sourceSlug: baseSlug,
            choices,
          });
        } else {
          setSelectedPokemonError(err?.message || "Could not load Pokemon details");
          setPokemonFallbackPrompt(null);
        }
      } finally {
        if (!disposed) {
          setSelectedPokemonLoading(false);
        }
      }
    };

    fetchPokemonDetails();

    return () => {
      disposed = true;
    };
  }, [discoverPokemonFallbackChoices, fetchPokemonDetailsBySlug, pokemonSlugOverrides, selectedCatch]);

  useEffect(() => {
    if (!selectedCatch) {
      return;
    }

    const onEscape = (event) => {
      if (event.key === "Escape") {
        closePokemonModal();
      }
    };

    window.addEventListener("keydown", onEscape);
    return () => {
      window.removeEventListener("keydown", onEscape);
    };
  }, [selectedCatch]);

  // Timer effect: update captcha countdown every second
  useEffect(() => {
    const interval = setInterval(() => {
      setCaptchaTimers((prev) => {
        const now = Date.now() / 1000;
        const updated = {};
        captchaQueueRows.forEach((row) => {
          const captchaDetectedUTC = row.captcha_detected_utc || 0;
          const secondsElapsed = Math.max(0, now - captchaDetectedUTC);
          const secondsRemaining = Math.max(0, 90 - secondsElapsed);
          updated[row.key] = secondsRemaining;
        });
        return updated;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [captchaQueueRows]);

  const runAction = async (action, payload = {}) => {
    setBusyAction(action);
    setStatus({ text: `Running ${action}...`, kind: "idle" });
    try {
      const data = await fetchJson("/api/runtime/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, ...payload }),
      });
      if (data && data.ok === false) {
        const errText = data.error || data.message || "Action failed";
        setStatus({ text: errText, kind: "bad" });
        setActionHistory((prev) => [{ ts: new Date().toLocaleTimeString(), text: errText }, ...prev].slice(0, 12));
      } else {
        const msg = data.message || "Action complete";
        setStatus({ text: msg, kind: "ok" });
        setActionHistory((prev) => [{ ts: new Date().toLocaleTimeString(), text: msg }, ...prev].slice(0, 12));
      }
      const rt = await fetchJson("/api/runtime/status");
      setRuntime(rt || { available: false, data: { bots: [] } });
    } catch (err) {
      setStatus({ text: err.message, kind: "bad" });
      setActionHistory((prev) => [{ ts: new Date().toLocaleTimeString(), text: `Failed ${action}: ${err.message}` }, ...prev].slice(0, 12));
    } finally {
      setBusyAction("");
    }
  };

  const runBotAction = async (botId, action, payload = {}) => {
    if (!botId) {
      setStatus({ text: "Bot identifier missing for action", kind: "bad" });
      return;
    }

    await runAction(action, { target: botId, ...payload });
  };

  const runAccountAction = async (accountId, action, payload = {}) => {
    if (!accountId) {
      setStatus({ text: "Account identifier missing for action", kind: "bad" });
      return;
    }

    await runAction(action, { target: accountId, ...payload });
  };

  const openBrowserDashboard = () => {
    const targetUrl = "http://127.0.0.1:8787";
    window.open(targetUrl, "_blank", "noopener,noreferrer");
  };

  const getBotKey = (bot, idx) => bot?.id || `${bot?.username || "bot"}-${idx}`;
  const getBotTarget = (bot) => bot?.id || bot?.username || "";
  const getCaptchaDraftKey = (bot, idx) => String(bot?.id || getBotKey(bot, idx));

  const readCaptchaDraft = (draftMap, draftKey, fallback) => {
    if (Object.prototype.hasOwnProperty.call(draftMap, draftKey)) {
      return draftMap[draftKey];
    }
    return fallback;
  };

  const runCaptchaManualAnswer = async (bot, idx) => {
    const draftKey = getCaptchaDraftKey(bot, idx);
    const answer = String(readCaptchaDraft(captchaManualAnswers, draftKey, "") || "").trim();
    const channelHint = String(readCaptchaDraft(captchaChannelHints, draftKey, "auto") || "auto");
    if (!answer) {
      setStatus({ text: "Manual captcha answer cannot be empty", kind: "bad" });
      return;
    }

    await runBotAction(getBotTarget(bot), "captcha_manual_answer", {
      answer,
      channel_hint: channelHint,
    });
    setCaptchaManualAnswers((prev) => ({ ...prev, [draftKey]: "" }));
  };

  const saveCaptchaMaxAttempts = async (bot, idx) => {
    const draftKey = getCaptchaDraftKey(bot, idx);
    const valueRaw = String(
      readCaptchaDraft(
        captchaMaxAttemptsDraft,
        draftKey,
        String(bot?.automations?.captcha_auto_max_attempts || 3),
      ) || "",
    ).trim();
    if (!/^\d+$/.test(valueRaw) || Number(valueRaw) <= 0) {
      setStatus({ text: "Max attempts must be a positive number", kind: "bad" });
      return;
    }

    await runBotAction(getBotTarget(bot), "set_captcha_max_attempts", {
      max_attempts: Number(valueRaw),
    });
  };

  const saveCaptchaManualAllowedUsers = async (bot, idx) => {
    const draftKey = getCaptchaDraftKey(bot, idx);
    const valueRaw = String(
      readCaptchaDraft(
        captchaManualUsersDraft,
        draftKey,
        (bot?.automations?.captcha_manual_allowed_user_ids || []).join(","),
      ) || "",
    ).trim();

    const badPart = valueRaw
      .split(",")
      .map((part) => part.trim())
      .filter(Boolean)
      .find((part) => !/^\d+$/.test(part));
    if (badPart) {
      setStatus({ text: "Manual allowed IDs must be comma-separated numeric values", kind: "bad" });
      return;
    }

    await runBotAction(getBotTarget(bot), "set_captcha_manual_allowed_user_ids", {
      manual_allowed_user_ids: valueRaw,
    });
  };

  const saveCaptchaAlertPing = async (bot, idx) => {
    const draftKey = getCaptchaDraftKey(bot, idx);
    const value = String(
      readCaptchaDraft(
        captchaAlertPingDraft,
        draftKey,
        String(bot?.automations?.captcha_alert_ping || ""),
      ) || "",
    ).trim();

    await runBotAction(getBotTarget(bot), "set_captcha_alert_ping", {
      ping: value,
    });
  };

  const renderAutomationToggle = (bot, idx, key, label, action) => {
    const enabled = Boolean(bot?.automations?.[key]);
    const botReady = isBotDiscordReady(bot);
    return (
      <div className="flex items-center gap-1.5" key={`${getBotKey(bot, idx)}-${key}`}>
        <span className="text-[11px] text-slate-300">{label}</span>
        <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold border ${enabled ? "bg-[#E11D48]/15 text-[#FDA4AF] border-[#E11D48]/35" : "bg-slate-700/40 text-slate-300 border-slate-600"}`}>
          {enabled ? "ON" : "OFF"}
        </span>
        <button
          onClick={() => runBotAction(getBotTarget(bot), action, { enabled: !enabled })}
          disabled={!runtimeAvailable || busyAction !== "" || !botReady}
          className="px-2 py-1 rounded text-xs bg-[#140205] text-[#FECDD3] border border-[#4C0519] hover:bg-[#2A080D] disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {enabled ? "Turn Off" : "Turn On"}
        </button>
      </div>
    );
  };

  const rarityEntries = (rarityMap) => Object.entries(rarityMap || {}).sort((a, b) => Number(b[1]) - Number(a[1]));

  const RarityTable = ({ title, rarityMap }) => {
    const rows = rarityEntries(rarityMap);
    return (
      <div className="bg-slate-900 rounded-xl border border-slate-800 shadow-md overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-800">
          <h3 className="text-sm font-semibold text-slate-200">{title}</h3>
        </div>
        <div className="max-h-48 overflow-auto">
          <table className="w-full text-left text-sm text-slate-300">
            <thead className="bg-slate-950/60 text-slate-400 uppercase text-xs font-semibold sticky top-0">
              <tr>
                <th className="px-4 py-2">Rarity</th>
                <th className="px-4 py-2">Count</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {rows.length === 0 && (
                <tr>
                  <td className="px-4 py-2 text-slate-500" colSpan={2}>No catches yet</td>
                </tr>
              )}
              {rows.map(([name, count]) => (
                <tr key={name} className="hover:bg-slate-800/30">
                  <td className="px-4 py-2">{name}</td>
                  <td className="px-4 py-2 font-mono">{Number(count || 0).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  const handleSaveConfig = async () => {
    try {
      JSON.parse(configJson);
      const data = await fetchJson("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ config_text: configJson }),
      });
      setConfigDirty(false);
      setConfigSyncedAt(Date.now());
      setStatus({ text: data.ok ? "Config saved" : "Config save failed", kind: data.ok ? "ok" : "bad" });
      await reloadConfigFromDisk();
    } catch (err) {
      setStatus({ text: `Save failed: ${err.message}`, kind: "bad" });
    }
  };

  const handleFormatJson = () => {
    fetchJson("/api/config/format", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ config_text: configJson }),
    })
      .then((data) => {
        setConfigJson(String(data.config_text || configJson));
        setConfigDirty(true);
        setStatus({ text: "JSON formatted", kind: "ok" });
      })
      .catch((err) => {
        setStatus({ text: `Invalid JSON format: ${err.message}`, kind: "bad" });
      });
  };

  const clearAntiDetectLogs = async () => {
    try {
      await fetchJson("/api/telemetry/anti-detect/clear", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ truncate_file: false }),
      });
      setAntiDetect({ events: [], count: 0, log_path: antiDetect.log_path || "" });
      setStatus({ text: "Anti-detect logs cleared", kind: "ok" });
    } catch (err) {
      setStatus({ text: `Clear failed: ${err.message}`, kind: "bad" });
    }
  };

  const handleAddAccount = async (startNow = false) => {
    const token = String(newAccount.token || "").trim();
    const huntingChannelId = String(newAccount.huntingChannelId || "").trim();
    const fishingChannelId = String(newAccount.fishingChannelId || "").trim();
    const berryChannelId = String(newAccount.berryChannelId || "").trim();
    const requiredServerId = String(newAccount.requiredServerId || "").trim();
    const captchaMaxAutoAttempts = String(newAccount.captchaMaxAutoAttempts || "").trim();
    const captchaManualAllowedUserIds = String(newAccount.captchaManualAllowedUserIds || "").trim();
    const captchaAlertChannelId = String(newAccount.captchaAlertChannelId || "").trim();
    const captchaAlertCooldownSeconds = String(newAccount.captchaAlertCooldownSeconds || "").trim();

    if (!token) {
      setStatus({ text: "Add Account: token is required", kind: "bad" });
      return;
    }
    if (!/^\d+$/.test(huntingChannelId)) {
      setStatus({ text: "Add Account: HuntingChannel must be numeric", kind: "bad" });
      return;
    }
    if (!/^\d+$/.test(fishingChannelId)) {
      setStatus({ text: "Add Account: FishingChannel must be numeric", kind: "bad" });
      return;
    }
    if (berryChannelId && !/^\d+$/.test(berryChannelId)) {
      setStatus({ text: "Add Account: Berry Channel must be numeric", kind: "bad" });
      return;
    }
    if (requiredServerId && !/^\d+$/.test(requiredServerId)) {
      setStatus({ text: "Add Account: RequiredServerID must be numeric", kind: "bad" });
      return;
    }
    if (captchaMaxAutoAttempts && (!/^\d+$/.test(captchaMaxAutoAttempts) || Number(captchaMaxAutoAttempts) <= 0)) {
      setStatus({ text: "Add Account: Captcha max auto attempts must be a positive number", kind: "bad" });
      return;
    }
    if (captchaAlertCooldownSeconds && (!/^\d+$/.test(captchaAlertCooldownSeconds) || Number(captchaAlertCooldownSeconds) < 0)) {
      setStatus({ text: "Add Account: Captcha alert cooldown must be 0 or a positive number", kind: "bad" });
      return;
    }
    if (captchaAlertChannelId && (!/^\d+$/.test(captchaAlertChannelId) || Number(captchaAlertChannelId) <= 0)) {
      setStatus({ text: "Add Account: Captcha alert channel ID must be a positive number", kind: "bad" });
      return;
    }
    if (captchaManualAllowedUserIds) {
      const badManualId = captchaManualAllowedUserIds
        .split(",")
        .map((part) => part.trim())
        .filter(Boolean)
        .find((part) => !/^\d+$/.test(part));
      if (badManualId) {
        setStatus({ text: "Add Account: Captcha manual allowed user IDs must be comma-separated numbers", kind: "bad" });
        return;
      }
    }

    setBusyAction("add_account");
    setStatus({ text: "Adding account...", kind: "idle" });

    try {
      const data = await fetchJson("/api/config/add-account", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token,
          hunting_channel_id: huntingChannelId,
          fishing_channel_id: fishingChannelId,
          berry_channel_id: berryChannelId,
          required_server_id: requiredServerId,
          captcha_auto_answer_enabled: Boolean(newAccount.captchaAutoAnswerEnabled),
          captcha_max_auto_attempts: captchaMaxAutoAttempts,
          captcha_manual_allowed_user_ids: captchaManualAllowedUserIds,
          captcha_alerts_enabled: Boolean(newAccount.captchaAlertsEnabled),
          captcha_alert_channel_id: captchaAlertChannelId,
          captcha_alert_ping: String(newAccount.captchaAlertPing || ""),
          captcha_alert_webhook_url: String(newAccount.captchaAlertWebhookUrl || ""),
          captcha_alert_cooldown_seconds: captchaAlertCooldownSeconds,
        }),
      });

      if (data.config_text) {
        setConfigJson(String(data.config_text));
      }
      if (data.path) {
        setConfigPath(String(data.path));
      }

      setConfigDirty(false);
      setConfigSyncedAt(Date.now());
      setNewAccount({
        token: "",
        huntingChannelId: "",
        fishingChannelId: "",
        berryChannelId: "",
        requiredServerId: "",
        captchaAutoAnswerEnabled: true,
        captchaMaxAutoAttempts: "3",
        captchaManualAllowedUserIds: "",
        captchaAlertsEnabled: false,
        captchaAlertChannelId: "",
        captchaAlertPing: "",
        captchaAlertWebhookUrl: "",
        captchaAlertCooldownSeconds: "",
        startAfterAdd: Boolean(newAccount.startAfterAdd),
      });

      if (startNow) {
        const startRes = await fetchJson("/api/runtime/action", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "start_all" }),
        });
        const message = startRes?.message || data.message || "Account added and start requested";
        setStatus({ text: message, kind: "ok" });
      } else {
        setStatus({ text: data.message || "Account added", kind: "ok" });
      }
    } catch (err) {
      setStatus({ text: `Add Account failed: ${err.message}`, kind: "bad" });
    } finally {
      setBusyAction("");
    }
  };

  const pillStyles = {
    idle: "bg-slate-700/50 text-slate-200 border border-slate-600",
    ok: "bg-emerald-500/10 text-emerald-300 border border-emerald-500/30",
    bad: "bg-red-500/10 text-red-300 border border-red-500/30",
  };

  const uiTabs = [
    { key: "overview", label: "Overview", icon: <LayoutIcon className="w-5 h-5" /> },
    { key: "runtime", label: "Operations", icon: <PulseIcon className="w-5 h-5" /> },
    { key: "captcha", label: "Captcha", icon: <PokeBallIcon className="w-5 h-5" /> },
    { key: "anti_detect", label: "Telemetry", icon: <TerminalIcon className="w-5 h-5" /> },
    { key: "config", label: "Configuration", icon: <CogIcon className="w-5 h-5" /> },
  ];
  const activeTabLabel = uiTabs.find((tab) => tab.key === activeTab)?.label || "Overview";
  const overviewSectionTabs = [
    { key: "highlights", label: "Highlights" },
    { key: "events", label: "Bonuses" },
    { key: "stats", label: "Totals" },
    { key: "snapshot", label: "Bots" },
    { key: "rarity", label: "Rarity" },
    { key: "berry", label: "Berry" },
  ];

  return (
    <div className="sakura-theme text-slate-100 h-screen overflow-hidden antialiased selection:bg-rose-500/30 flex">
      <aside className="w-20 lg:w-64 bg-slate-900/90 backdrop-blur-xl border-r border-slate-800 flex flex-col shrink-0 relative z-20 transition-all duration-300 p-3">
        <div className="h-16 flex items-center justify-center lg:justify-start lg:px-3 border-b border-slate-800/70 mb-3">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#E11D48] to-[#881337] flex items-center justify-center shadow-[0_0_15px_rgba(225,29,72,0.35)] shrink-0">
            <div className="w-3.5 h-3.5 bg-[#030000] rounded-full border-2 border-white/80"></div>
          </div>
          <div className="hidden lg:block ml-3">
            <h1 className="text-base font-bold tracking-tight text-white leading-tight">YveltalGo</h1>
            <p className="text-[9px] uppercase tracking-widest text-[#E11D48] font-bold">Operations Core</p>
          </div>
        </div>

        <nav className="flex-1 py-2 flex flex-col gap-2">
          {uiTabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center justify-center lg:justify-start gap-3 px-3 py-3 rounded-2xl transition-all duration-300 group border ${
                activeTab === tab.key
                  ? "bg-[#E11D48]/20 text-white border-[#E11D48]/30 shadow-[inset_4px_0_0_#E11D48]"
                  : "text-slate-300 hover:text-white hover:bg-slate-800/70 border-transparent"
              }`}
              title={tab.label}
            >
              <span className={`${activeTab === tab.key ? "text-[#E11D48]" : "text-slate-400 group-hover:text-slate-200"}`}>{tab.icon}</span>
              <span className="hidden lg:block text-xs font-bold uppercase tracking-wider">{tab.label}</span>
            </button>
          ))}
        </nav>

        <div className="mt-2 px-2 py-3 border-t border-slate-800/70 flex items-center gap-2">
          <span className={`w-2.5 h-2.5 rounded-full ${status.kind === "ok" ? "bg-emerald-500 animate-pulse" : status.kind === "bad" ? "bg-red-500" : "bg-slate-400"}`}></span>
          <span className="hidden lg:inline text-[11px] text-slate-300 truncate">{status.text}</span>
        </div>
      </aside>

      <main className="flex-1 h-screen overflow-y-auto p-4 md:p-6 relative z-10">
        <div className="max-w-7xl mx-auto space-y-4">
          <header className="sakura-panel bg-slate-900 p-4 rounded-2xl border border-slate-800 shadow-lg">
            <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-3">
              <div>
                <h2 className="text-xl font-bold text-white tracking-tight">{activeTabLabel}</h2>
                <p className="text-slate-400 text-sm mt-1">Monitoring operations across selected users.</p>
                {!runtimeAvailable && (
                  <div className="mt-2 px-3 py-1.5 rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-300 text-xs font-medium">
                    Runtime not attached. Start main.py to enable automation controls.
                  </div>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <select
                  value={selectedUserScope}
                  onChange={(e) => setSelectedUserScope(e.target.value)}
                  className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-xs"
                >
                  {userScopeOptions.map((option) => (
                    <option key={option.id} value={option.id}>{option.label}</option>
                  ))}
                </select>
                <button onClick={refreshAll} className="bg-gradient-to-r from-[#E11D48] to-[#BE123C] text-white border border-[#E11D48]/35 px-4 py-2 rounded-lg transition-colors text-sm font-bold shadow-sm active:scale-95">
                  Refresh
                </button>
                <select value={runtimeRefreshMs} onChange={(e) => setRuntimeRefreshMs(Number(e.target.value))} className="bg-slate-800 border border-slate-700 rounded-lg px-2 py-1 text-xs">
                  <option value={2000}>RT 2s</option>
                  <option value={3000}>RT 3s</option>
                  <option value={5000}>RT 5s</option>
                </select>
                <select value={statsRefreshMs} onChange={(e) => setStatsRefreshMs(Number(e.target.value))} className="bg-slate-800 border border-slate-700 rounded-lg px-2 py-1 text-xs">
                  <option value={5000}>Stats 5s</option>
                  <option value={8000}>Stats 8s</option>
                  <option value={12000}>Stats 12s</option>
                </select>
              </div>
            </div>
          </header>

        {activeTab === "overview" && (
          <section className="space-y-4">
            <div className="bg-slate-900 rounded-xl border border-slate-800 shadow-md px-4 py-3">
              <div className="flex flex-wrap items-center gap-2 justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-slate-100">Overview Focus</h3>
                  <p className="text-xs text-slate-400 mt-1">Choose what to inspect right now to reduce cognitive load and scrolling.</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {overviewSectionTabs.map((tab) => (
                    <button
                      key={tab.key}
                      onClick={() => setOverviewSection(tab.key)}
                      className={`px-3 py-1.5 rounded-lg border text-xs font-semibold transition-colors ${
                        overviewSection === tab.key
                          ? "bg-[#E11D48]/20 text-[#FDA4AF] border-[#E11D48]/35"
                          : "bg-[#140205] text-slate-300 border-[#4C0519] hover:bg-[#2A080D]"
                      }`}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="bg-slate-900 p-4 rounded-xl border border-slate-800 shadow-md"><p className="text-xs text-slate-400 flex items-center gap-1.5"><PokeBallIcon className="w-3.5 h-3.5 sakura-icon" />Hunt Running</p><p className="text-2xl font-bold text-emerald-400">{runtimeSummary.huntRunning}</p></div>
              <div className="bg-slate-900 p-4 rounded-xl border border-slate-800 shadow-md"><p className="text-xs text-slate-400 flex items-center gap-1.5"><PokeBallIcon className="w-3.5 h-3.5 sakura-icon" />Fish Running</p><p className="text-2xl font-bold text-rose-400">{runtimeSummary.fishRunning}</p></div>
              <div className="bg-slate-900 p-4 rounded-xl border border-slate-800 shadow-md"><p className="text-xs text-slate-400 flex items-center gap-1.5"><PokeBallIcon className="w-3.5 h-3.5 sakura-icon" />Captcha Active</p><p className="text-2xl font-bold text-red-400">{runtimeSummary.captcha}</p></div>
              <div className="bg-slate-900 p-4 rounded-xl border border-slate-800 shadow-md"><p className="text-xs text-slate-400 flex items-center gap-1.5"><PokeBallIcon className="w-3.5 h-3.5 sakura-icon" />Limit Reached</p><p className="text-2xl font-bold text-amber-400">{runtimeSummary.limit}</p></div>
            </div>

            {overviewSection === "highlights" && (
            <>
            <div className="bg-slate-900 rounded-xl border border-slate-800 shadow-md overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-800 flex justify-between items-center gap-2">
                <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><PokeBallIcon className="w-4 h-4 sakura-icon" />Recent Legendary & Rare Highlights</h2>
                <span className="text-[11px] font-medium text-slate-500 bg-slate-800/50 px-2 py-1 rounded-md">Last 24 Hours</span>
              </div>
              <div className="p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                {rareCatchCards.length === 0 && (
                  <div className="col-span-full text-sm text-slate-500">No recent rare hunt catches in the selected window.</div>
                )}
                {rareCatchCards.map((pokemon) => (
                  <button key={pokemon.key} onClick={() => openPokemonDetails(pokemon)} className={`text-left w-full flex items-center p-3 rounded-xl border transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg ${pokemon.border} ${pokemon.bg}`}>
                    <div className="w-14 h-14 flex-shrink-0 flex items-center justify-center bg-slate-950/70 rounded-lg border border-slate-700/60 mr-3 overflow-hidden">
                      {pokemon.sprite ? (
                        <>
                          <img
                            src={pokemon.sprite}
                            alt={pokemon.name}
                            className="w-12 h-12 object-contain"
                            style={{ imageRendering: "pixelated" }}
                            onError={(e) => {
                              e.currentTarget.style.display = "none";
                              const fallback = e.currentTarget.nextElementSibling;
                              if (fallback) fallback.classList.remove("hidden");
                            }}
                          />
                          <div className="hidden text-lg">?</div>
                        </>
                      ) : (
                        <div className="text-lg">?</div>
                      )}
                    </div>
                    <div className="flex flex-col min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <span className="font-semibold text-slate-100 truncate">{pokemon.name}</span>
                        <span className="text-[10px] text-slate-400 whitespace-nowrap">{pokemon.time}</span>
                      </div>
                      <span className={`text-[11px] font-bold uppercase tracking-wide mt-0.5 ${pokemon.accent}`}>{pokemon.rarity}</span>
                      <span className="text-[10px] text-slate-500 mt-0.5 truncate">{pokemon.account}</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            <div className="bg-slate-900 rounded-xl border border-slate-800 shadow-md overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-800 flex justify-between items-center gap-2">
                <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><PokeBallIcon className="w-4 h-4 sakura-icon" />Recent Special Item Retrieves</h2>
                <span className="text-[11px] font-medium text-slate-500 bg-slate-800/50 px-2 py-1 rounded-md">Last 24 Hours</span>
              </div>
              <div className="p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {itemRetrieveCards.length === 0 && (
                  <div className="col-span-full text-sm text-slate-500">No recent item retrievals in the selected window.</div>
                )}
                {itemRetrieveCards.map((item) => (
                  <div key={item.key} className="text-left w-full flex items-center p-3 rounded-xl border transition-all duration-200 hover:-translate-y-0.5 bg-slate-800/50 border-slate-700">
                    <div className="w-12 h-12 flex-shrink-0 flex items-center justify-center bg-slate-950/70 rounded-lg border border-slate-700/60 mr-3 overflow-hidden text-xl">
                      {item.itemSprite ? (
                        <img
                          src={item.itemSprite}
                          alt={item.itemName}
                          className="w-9 h-9 object-contain"
                          onError={(e) => {
                            e.currentTarget.style.display = "none";
                            const fallback = e.currentTarget.nextElementSibling;
                            if (fallback) fallback.classList.remove("hidden");
                          }}
                        />
                      ) : null}
                      <span className={item.itemSprite ? "hidden" : ""}>{item.itemEmoji}</span>
                    </div>
                    <div className="flex flex-col min-w-0 w-full">
                      <div className="flex items-start justify-between gap-2">
                        <span className="font-semibold text-slate-100 truncate">{item.itemName}</span>
                        <span className="text-[10px] text-slate-400 whitespace-nowrap">{item.time}</span>
                      </div>
                      <span className="text-[11px] text-slate-300 mt-0.5 truncate">From {item.pokemonName}</span>
                      <span className="text-[10px] text-slate-500 mt-0.5 truncate">{item.rarity} • {item.account}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            </>
            )}

            {overviewSection === "events" && (
            <div className="bg-slate-900 rounded-xl border border-slate-800 shadow-md overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-800 flex flex-wrap justify-between gap-2 items-center">
                <div>
                  <h2 className="text-sm font-semibold text-slate-200">Limited Events & Bonuses</h2>
                  <p className="text-xs text-slate-500 mt-1">Global directives + per-operator telemetry from ;bonus ;events ;unlocks.</p>
                </div>
                <button
                  onClick={() => runAction("force_limited_events")}
                  disabled={!runtimeAvailable || busyAction !== ""}
                  className="bg-gradient-to-r from-[#E11D48] to-[#BE123C] text-white border border-[#E11D48]/35 px-3 py-1.5 rounded-lg transition-colors text-xs font-bold disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Refresh Bonuses Now
                </button>
              </div>

              <div className="p-4 space-y-4">
                <div className="rounded-2xl border border-[#4C0519]/60 bg-[#0A0102] p-3">
                  <div className="text-[10px] font-bold text-[#9F1239] uppercase tracking-widest mb-2">Global Network Directives</div>
                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2">
                    {globalDirectives.length === 0 && (
                      <div className="text-xs text-slate-500">No global directives extracted yet.</div>
                    )}
                    {globalDirectives.map((item, idx) => (
                      <div key={`directive-${idx}`} className="rounded-xl border border-[#380D16] bg-[#110305] px-3 py-2">
                        <div className="text-[10px] uppercase tracking-wider font-semibold text-[#FDA4AF]">{item.title}</div>
                        <div className={`text-xs mt-1 ${item.tone === "warn" ? "text-[#F43F5E]" : "text-slate-200"}`}>{item.detail}</div>
                      </div>
                    ))}
                  </div>
                </div>

                {limitedEventRows.length === 0 && (
                  <div className="text-sm text-slate-500">No active bots in this scope.</div>
                )}

                {limitedEventRows.length > 0 && focusedEventsRow && (
                  <div className="flex flex-col xl:flex-row gap-3">
                    <div className="w-full xl:w-64 shrink-0 space-y-2">
                      {limitedEventRows.map((row) => {
                        const selected = row.key === focusedEventsRow.key;
                        return (
                          <button
                            key={`op-${row.key}`}
                            onClick={() => setEventsFocusUser(row.key)}
                            className={`w-full rounded-xl border px-3 py-2.5 text-left transition-colors ${selected ? "bg-[#180508] border-[#E11D48]/50 shadow-[inset_3px_0_0_#E11D48]" : "bg-[#0A0102] border-[#380D16] hover:bg-[#110305]"}`}
                          >
                            <div className="text-sm font-semibold text-slate-100 truncate">{row.username}</div>
                            <div className="text-[10px] text-[#9F1239] uppercase tracking-wider mt-1">{row.lastChecked ? formatRelativeTime(row.lastChecked) : "never"}</div>
                          </button>
                        );
                      })}
                    </div>

                    <div className="flex-1 rounded-2xl border border-[#380D16] bg-[#0A0102] p-5 space-y-5 min-h-[420px]">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div>
                          <div className="text-base font-bold text-slate-100">{focusedEventsRow.username}</div>
                          <div className="text-[11px] text-slate-400">
                            Last check: {focusedEventsRow.lastChecked ? formatRelativeTime(focusedEventsRow.lastChecked) : "never"}
                            {focusedEventsRow.intervalSeconds > 0 ? ` • Every ${Math.max(1, Math.floor(focusedEventsRow.intervalSeconds / 60))}m` : ""}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={`px-2 py-1 rounded text-[10px] font-semibold border ${focusedEventsRow.status === "ok" ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/30" : focusedEventsRow.status === "partial" ? "bg-amber-500/10 text-amber-300 border-amber-500/30" : focusedEventsRow.status === "failed" ? "bg-red-500/10 text-red-300 border-red-500/30" : "bg-slate-700/40 text-slate-200 border-slate-600"}`}>{focusedEventsRow.status.toUpperCase()}</span>
                          <button
                            onClick={() => runBotAction(focusedEventsRow.target, "refresh_limited_events")}
                            disabled={!runtimeAvailable || busyAction !== ""}
                            className="px-2.5 py-1 rounded text-[11px] font-semibold bg-slate-700 hover:bg-slate-600 text-slate-200 disabled:opacity-40 disabled:cursor-not-allowed"
                          >
                            Refresh
                          </button>
                        </div>
                      </div>

                      <div className="flex flex-wrap gap-2 pb-4 border-b border-[#380D16]/50">
                        <div className="bg-[#110305] border border-[#380D16] px-3 py-2 rounded-xl flex items-center gap-2.5">
                          <span className="text-[10px] font-bold text-[#FDA4AF] uppercase tracking-widest flex items-center gap-1"><TicketIcon className="w-3 h-3" />Event Ticket</span>
                          <StatusBadge status={focusedEventDetails?.status?.ticket || "UNKNOWN"} />
                        </div>
                        <div className="bg-[#110305] border border-[#380D16] px-3 py-2 rounded-xl flex items-center gap-2.5">
                          <span className="text-[10px] font-bold text-[#FDA4AF] uppercase tracking-widest">Vote Bonus</span>
                          <StatusBadge status={focusedEventDetails?.status?.vote || "UNKNOWN"} />
                        </div>
                        <div className="bg-[#110305] border border-[#380D16] px-3 py-2 rounded-xl flex items-center gap-2.5">
                          <span className="text-[10px] font-bold text-[#FDA4AF] uppercase tracking-widest">2x Egg Hatch</span>
                          <StatusBadge status={focusedEventDetails?.status?.eggRate || "UNKNOWN"} />
                        </div>
                        <div className="bg-[#110305] border border-[#380D16] px-3 py-2 rounded-xl flex items-center gap-2.5">
                          <span className="text-[10px] font-bold text-[#FDA4AF] uppercase tracking-widest">Double EXP</span>
                          <StatusBadge status={focusedEventDetails?.status?.doubleExp || "UNKNOWN"} />
                        </div>
                      </div>

                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <div className="space-y-5">
                          <div>
                            <h4 className="text-[10px] font-bold text-[#E11D48] uppercase tracking-widest mb-2.5 flex items-center gap-1.5"><SparkleIcon className="w-3 h-3" />Pending Checklist Rewards</h4>
                            <div className="space-y-2">
                              {(focusedEventDetails?.checklist || []).length === 0 && (
                                <div className="text-xs text-slate-500">No checklist entries extracted yet.</div>
                              )}
                              {(focusedEventDetails?.checklist || []).map((item, idx) => (
                                <div key={`check-${idx}`} className={`p-3 rounded-xl border ${item.special ? "bg-[#180508] border-[#881337]" : "bg-[#110305] border-[#380D16]"}`}>
                                  <div className="text-xs font-semibold text-slate-100">{item.text}</div>
                                  {focusedEventsRow?.events?.event_end ? (
                                    <div className="text-[10px] text-[#FDA4AF] mt-1 flex items-center gap-1"><ClockIcon className="w-3 h-3" />{focusedEventsRow.events.event_end}</div>
                                  ) : null}
                                </div>
                              ))}
                            </div>
                          </div>

                          <div>
                            <h4 className="text-[10px] font-bold text-[#9F1239] uppercase tracking-widest mb-2.5 flex items-center gap-1.5"><UnlockIcon className="w-3 h-3" />Event Unlocks & Requirements</h4>
                            <div className="space-y-2">
                              {(focusedEventDetails?.unlocks || []).length === 0 && (
                                <div className="text-xs text-slate-500">No unlock rows extracted yet.</div>
                              )}
                              {(focusedEventDetails?.unlocks || []).map((item, idx) => (
                                <div key={`unlock-${idx}`} className="flex items-start justify-between gap-2 p-2.5 bg-[#110305] border border-[#380D16] rounded-xl">
                                  <span className="text-xs font-semibold text-slate-100">{item.text}</span>
                                  {item.req ? (
                                    <span className="text-[9px] text-orange-400 bg-orange-950/20 border border-orange-900/50 px-2 py-0.5 rounded inline-flex items-center gap-1 max-w-[170px] truncate" title={item.req}><WarningIcon className="w-2.5 h-2.5 shrink-0" />{item.req}</span>
                                  ) : (
                                    <span className="text-[9px] text-[#E11D48] bg-[#E11D48]/10 border border-[#E11D48]/20 px-2 py-0.5 rounded">UNLOCKED</span>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        </div>

                        <div>
                          <h4 className="text-[10px] font-bold text-[#9F1239] uppercase tracking-widest mb-2.5">Active Modifiers & Boosts</h4>
                          <div className="space-y-2">
                            {(focusedEventDetails?.modifiers || []).length === 0 && (
                              <div className="text-xs text-slate-500">No modifier rows extracted yet.</div>
                            )}
                            {(focusedEventDetails?.modifiers || []).map((mod, idx) => (
                              <div key={`mod-${idx}`} className={`p-3 rounded-xl border flex flex-col gap-1.5 ${mod.active ? "bg-[#180508] border-[#4C0519]" : "bg-[#0A0102] border-[#2A080D] opacity-70"}`}>
                                <div className="flex justify-between items-start gap-2">
                                  <span className={`text-xs font-semibold ${mod.active ? "text-slate-100" : "text-[#FDA4AF] line-through decoration-[#9F1239]"}`}>{mod.text}</span>
                                  <StatusBadge status={mod.active} text={mod.active ? "ACTIVE" : "EXPIRED"} />
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
            )}

            {overviewSection === "stats" && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="bg-slate-900 rounded-xl border border-slate-800 shadow-md overflow-hidden">
                <div className="px-4 py-2 border-b border-slate-800 text-xs text-slate-400 uppercase tracking-wide">Day Mode Details (Resets 12:00)</div>
                <div className="grid grid-cols-2 gap-3 p-4">
                  <div><p className="text-sm text-slate-400 mb-1">Encounters</p><p className="text-2xl font-bold text-white">{dayTotals.encounters.toLocaleString()}</p></div>
                  <div><p className="text-sm text-slate-400 mb-1">Catches</p><p className="text-2xl font-bold text-white">{dayTotals.catches.toLocaleString()}</p></div>
                  <div><p className="text-sm text-slate-400 mb-1">Fish E/C</p><p className="text-2xl font-bold text-white">{dayTotals.fishEncounters.toLocaleString()} / {dayTotals.fishCatches.toLocaleString()}</p></div>
                  <div><p className="text-sm text-slate-400 mb-1">Coins</p><p className="text-2xl font-bold text-yellow-500">{dayTotals.coins.toLocaleString()}</p></div>
                </div>
              </div>

              <div className="bg-slate-900 rounded-xl border border-slate-800 shadow-md overflow-hidden">
                <div className="px-4 py-2 border-b border-slate-800 text-xs text-slate-400 uppercase tracking-wide">Lifetime Details</div>
                <div className="grid grid-cols-2 gap-3 p-4">
                  <div><p className="text-sm text-slate-400 mb-1">Encounters</p><p className="text-2xl font-bold text-white">{lifetimeTotals.encounters.toLocaleString()}</p></div>
                  <div><p className="text-sm text-slate-400 mb-1">Catches</p><p className="text-2xl font-bold text-white">{lifetimeTotals.catches.toLocaleString()}</p></div>
                  <div><p className="text-sm text-slate-400 mb-1">Fish E/C</p><p className="text-2xl font-bold text-white">{lifetimeTotals.fishEncounters.toLocaleString()} / {lifetimeTotals.fishCatches.toLocaleString()}</p></div>
                  <div><p className="text-sm text-slate-400 mb-1">Coins</p><p className="text-2xl font-bold text-yellow-500">{lifetimeTotals.coins.toLocaleString()}</p></div>
                </div>
              </div>
            </div>
            )}

            {overviewSection === "snapshot" && (
            <div className="bg-slate-900 rounded-xl border border-slate-800 shadow-md overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-800 flex justify-between items-center">
                <h2 className="text-sm font-semibold text-slate-200">Bots Snapshot</h2>
                <span className="text-xs text-slate-500 font-mono">{statsPath}</span>
              </div>
              <div className="overflow-auto max-h-[48vh]" onWheel={handleScrollRegionWheel}>
                <table className="w-full text-left text-sm text-slate-300">
                  <thead className="bg-slate-950/60 text-slate-400 uppercase text-xs font-semibold sticky top-0">
                    <tr>
                      <th className="px-4 py-3">User</th>
                      <th className="px-4 py-3">Hunt</th>
                      <th className="px-4 py-3">Fish</th>
                      <th className="px-4 py-3">Day Mode</th>
                      <th className="px-4 py-3">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {bots.length === 0 && (<tr><td className="px-4 py-3 text-slate-500" colSpan={5}>No active bots</td></tr>)}
                    {bots.map((bot, idx) => {
                      const session = bot.day || bot.session || {};
                      return (
                        <tr key={getBotKey(bot, idx)} className="hover:bg-slate-800/30">
                          <td className="px-4 py-3 text-white font-medium">{bot.username}</td>
                          <td className="px-4 py-3">{bot.hunt_paused ? "Paused" : "Running"}</td>
                          <td className="px-4 py-3">{bot.fish_paused ? "Paused" : "Running"}</td>
                          <td className="px-4 py-3 font-mono text-xs">{session.encounters || 0}/{session.catches || 0}/{session.fish_encounters || 0}/{session.fish_catches || 0}/{session.coins || 0}</td>
                          <td className="px-4 py-3 text-emerald-400">{bot.hunting_status} | {bot.fishing_status}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
            )}

            {overviewSection === "rarity" && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              <RarityTable title="Hunt Rarity (Day Mode)" rarityMap={huntSessionRarity} />
              <RarityTable title="Hunt Rarity (Lifetime)" rarityMap={huntLifetimeRarity} />
              <RarityTable title="Fish Rarity (Day Mode)" rarityMap={fishSessionRarity} />
              <RarityTable title="Fish Rarity (Lifetime)" rarityMap={fishLifetimeRarity} />
            </div>
            )}

            {overviewSection === "berry" && (
            <div className="bg-slate-900 rounded-xl border border-slate-800 shadow-md overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-800 flex flex-wrap justify-between gap-2 items-center">
                <h2 className="text-sm font-semibold text-slate-200">Berry Automation</h2>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-500">Shows only actionable berry state per account</span>
                  <button onClick={() => runAction("force_berry_check")} disabled={!runtimeAvailable || busyAction !== ""} className="bg-gradient-to-r from-[#E11D48] to-[#BE123C] text-white border border-[#E11D48]/35 px-3 py-1.5 rounded-lg transition-colors text-xs font-bold disabled:opacity-40 disabled:cursor-not-allowed">
                    Check Now
                  </button>
                </div>
              </div>
              <div className="overflow-auto max-h-[36vh]" onWheel={handleScrollRegionWheel}>
                <table className="w-full text-left text-sm text-slate-300">
                  <thead className="bg-slate-950/60 text-slate-400 uppercase text-xs font-semibold sticky top-0">
                    <tr>
                      <th className="px-4 py-3">User</th>
                      <th className="px-4 py-3">State</th>
                      <th className="px-4 py-3">Planted</th>
                      <th className="px-4 py-3">Slots</th>
                      <th className="px-4 py-3">What It's Doing</th>
                      <th className="px-4 py-3">Pending Slots</th>
                      <th className="px-4 py-3">Last Check</th>
                      <th className="px-4 py-3">Source</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {berryRows.length === 0 && (<tr><td className="px-4 py-3 text-slate-500" colSpan={8}>No berry-enabled accounts configured</td></tr>)}
                    {berryRows.map((row, idx) => (
                      <tr key={`berry-${row.id || row.username}-${idx}`} className="hover:bg-slate-800/30">
                        <td className="px-4 py-3 text-white font-medium">{row.username}</td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-1 rounded text-xs font-semibold border ${row.stateKind === "working" ? "bg-[#E11D48]/15 text-[#FDA4AF] border-[#E11D48]/35" : row.stateKind === "attention" ? "bg-amber-500/10 text-amber-300 border-amber-500/30" : row.stateKind === "ok" ? "bg-[#9F1239]/20 text-[#FDA4AF] border-[#9F1239]/45" : "bg-slate-700/40 text-slate-200 border-slate-600"}`}>
                            {row.state}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-200">{row.plantedSummary}</td>
                        <td className="px-4 py-3">
                          <div className="flex flex-wrap gap-1.5">
                            {row.slotStates.length === 0 && (
                              <span className="px-2 py-1 rounded text-xs border border-slate-600 text-slate-400 bg-slate-800/40">No active berry slots</span>
                            )}
                            {row.slotStates.map((slotState, sIdx) => {
                              const slot = Number(slotState?.slot || 0);
                              const state = String(slotState?.state || "Unknown");
                              const detail = String(slotState?.detail || "");
                              const berryName = String(slotState?.berry || "").trim();
                              const cls = state === "Needs Water"
                                ? "bg-amber-500/10 text-amber-300 border-amber-500/30"
                                : state === "Ready"
                                  ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/30"
                                  : state === "Watering"
                                    ? "bg-[#E11D48]/15 text-[#FDA4AF] border-[#E11D48]/35"
                                    : state === "Healthy"
                                      ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/30"
                                      : state === "Drying"
                                        ? "bg-orange-500/10 text-orange-300 border-orange-500/30"
                                      : state === "Wilting"
                                        ? "bg-red-500/10 text-red-300 border-red-500/30"
                                        : "bg-slate-700/40 text-slate-200 border-slate-600";

                              return (
                                <span key={`slot-${slot}-${sIdx}`} title={detail} className={`px-2 py-1 rounded text-xs border ${cls}`}>
                                  S{slot} {berryName ? `(${berryName})` : ""}: {state}
                                </span>
                              );
                            })}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-xs">{row.activity}</td>
                        <td className="px-4 py-3">{row.pendingSlotsText} {row.pendingCount > 0 ? `(${row.pendingCount})` : ""}</td>
                        <td className="px-4 py-3">{row.ageLabel}</td>
                        <td className="px-4 py-3 font-mono text-xs">{row.source}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            )}
          </section>
        )}

        {activeTab === "runtime" && (
          <section className="space-y-4">
            <div className="bg-slate-900 rounded-3xl border border-slate-800 shadow-md overflow-hidden">
              <div className="p-4 border-b border-slate-800 flex flex-wrap gap-2 items-center">
                <button
                  onClick={openBrowserDashboard}
                  className="bg-sky-500/10 text-sky-300 border border-sky-500/30 hover:bg-sky-500 hover:text-white px-3.5 py-2 rounded-xl transition-colors text-xs font-bold tracking-wide"
                >
                  Open Browser UI
                </button>
                {runtimeActions.map((action) => {
                  const variant = action.key === "start_all" || action.key === "resume_all"
                    ? "bg-[#E11D48]/20 text-[#F43F5E] border border-[#E11D48]/35"
                    : action.key === "stop_all"
                      ? "bg-[#4C0519]/70 text-[#FDA4AF] border border-[#881337]/70"
                      : "bg-slate-800/80 text-slate-200 border border-slate-700";
                  return (
                    <button
                      key={action.key}
                      onClick={() => runAction(action.key)}
                      disabled={!runtimeAvailable || busyAction !== ""}
                      className={`${variant} px-3.5 py-2 rounded-xl transition-colors text-xs font-bold tracking-wide disabled:opacity-40 disabled:cursor-not-allowed`}
                    >
                      {action.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="bg-slate-900 rounded-3xl border border-slate-800 shadow-md overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-800 bg-slate-900/60">
                <h2 className="text-sm font-semibold text-slate-200">Configured Accounts</h2>
                <p className="text-xs text-slate-500 mt-1">Accounts start only when triggered from UI.</p>
              </div>
              <div className="p-4 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                {runtimeDisplayAccounts.length === 0 && (
                  <div className="col-span-full p-5 rounded-xl border border-dashed border-slate-700 text-sm text-slate-400 text-center">No configured accounts found.</div>
                )}
                {runtimeDisplayAccounts.map((account, idx) => {
                  const stateText = account.running ? "Running" : account.connecting ? "Connecting" : "Stopped";
                  const displayName = account.display_name || (account.username && account.username !== "Not ready" ? account.username : "") || account.label || `account#${idx + 1}`;
                  const stateCls = account.running
                    ? "bg-[#9F1239]/20 text-[#FDA4AF] border-[#9F1239]/45"
                    : account.connecting
                      ? "bg-[#E11D48]/15 text-[#FDA4AF] border-[#E11D48]/35"
                      : "bg-slate-700/40 text-slate-200 border-slate-600";

                  return (
                    <div key={account.id || `${displayName}-${idx}`} className="rounded-2xl border border-slate-700 bg-slate-950/40 p-4 space-y-3">
                      <div className="flex items-center justify-between gap-2">
                        <div>
                          <div className="text-sm font-bold text-slate-100">{displayName}</div>
                          <div className="text-[11px] font-mono text-slate-400">{account.mention_name || `...${account.token_suffix || ""}`}</div>
                        </div>
                        <span className={`px-2 py-1 rounded text-[10px] font-semibold border ${stateCls}`}>{stateText}</span>
                      </div>
                      <div className="text-[11px] text-slate-300 font-mono">H:{account.hunting_channel_id || 0} • F:{account.fishing_channel_id || 0}</div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => runAccountAction(account.id, "start_bot")}
                          disabled={!runtimeAvailable || busyAction !== "" || account.running || account.connecting}
                          className="flex-1 px-3 py-1.5 rounded-lg text-xs font-semibold bg-[#E11D48]/15 text-[#FDA4AF] border border-[#E11D48]/35 hover:bg-[#E11D48] hover:text-white disabled:opacity-40 disabled:cursor-not-allowed"
                        >
                          Start
                        </button>
                        <button
                          onClick={() => runAccountAction(account.id, "stop_bot")}
                          disabled={!runtimeAvailable || busyAction !== "" || (!account.running && !account.connecting)}
                          className="flex-1 px-3 py-1.5 rounded-lg text-xs font-semibold bg-red-500/10 text-red-300 border border-red-500/30 hover:bg-red-500 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed"
                        >
                          Stop
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
              {runtimeDisplayBots.length === 0 && (
                <div className="col-span-full p-8 rounded-2xl border border-dashed border-slate-700 text-sm text-slate-400 text-center">No active bots for this scope.</div>
              )}
              {runtimeDisplayBots.map((bot, idx) => {
                const botReady = isBotDiscordReady(bot);
                const acct = accountsById[String(bot?.id || "")] || null;
                const lastErr = String(acct?.last_error || "").trim();
                const catchbotStatus = String(bot?.catchbot_status || "Disabled").trim();
                const catchbotEnabled = Boolean(bot?.automations?.catchbot_enabled);
                const catchbotReturnEpoch =
                  parseCatchBotReturnTextToEpoch(bot?.catchbot?.next_expected_return_text || "")
                  || Number(bot?.catchbot?.next_expected_return_at || 0);
                const catchbotReturnLabel = formatCatchBotReturnLabel(catchbotReturnEpoch);
                const headerName =
                  bot.username && bot.username !== "Not ready"
                    ? bot.username
                    : String(acct?.display_name || acct?.label || acct?.mention_name || "Discord login…").trim() || "Discord login…";
                const statusTone = !botReady
                  ? "text-amber-300"
                  : bot.captcha_active || bot.limit
                    ? "text-amber-300"
                    : "text-emerald-300";
                const huntFishHint = [String(bot.hunting_status || "").trim(), String(bot.fishing_status || "").trim()]
                  .filter(Boolean)
                  .join(" · ");
                const activityLine = !botReady
                  ? lastErr || (huntFishHint ? `Connecting — ${huntFishHint}` : "Connecting — waiting for Discord (on_ready).")
                  : `${bot.hunting_status} | ${bot.fishing_status} | CB: ${catchbotStatus}${catchbotReturnLabel ? ` • ${catchbotReturnLabel}` : ""}`;
                return (
                  <div key={getBotKey(bot, idx)} className="bg-slate-900 rounded-3xl border border-slate-800 shadow-md overflow-hidden">
                    <div className="px-4 py-3 border-b border-slate-800 bg-slate-900/70">
                      <div className="flex items-center justify-between gap-2">
                        <div className="text-sm font-bold text-slate-100">{headerName}</div>
                        <div className="flex flex-wrap gap-1 justify-end">
                          {!botReady && (
                            <span className="px-2 py-1 rounded text-[10px] font-semibold border bg-amber-500/10 text-amber-200 border-amber-500/35">
                              Connecting
                            </span>
                          )}
                          <span className={`px-2 py-1 rounded text-[10px] font-semibold border ${bot.captcha_active ? "bg-red-500/10 text-red-300 border-red-500/30" : "bg-slate-700/40 text-slate-200 border-slate-600"}`}>
                            {bot.captcha_active ? "Captcha" : botReady ? "Stable" : "—"}
                          </span>
                        </div>
                      </div>
                      <div className={`mt-1 text-[11px] ${statusTone}`}>{activityLine}</div>
                      {!botReady && (
                        <p className="mt-1.5 text-[10px] text-slate-500 leading-snug">
                          Hunt and fish show &quot;Running&quot; only after login. If something fails, open Operations → Diagnostics below for errors and the log file path (also under PokeGrinder/logs/).
                        </p>
                      )}
                    </div>

                    <div className="p-4 space-y-3">
                      <div className="grid grid-cols-3 gap-2 text-xs">
                        <div className="rounded-xl border border-slate-700 bg-slate-950/40 p-2 text-center">
                          <div className="text-slate-400 uppercase tracking-wide">Hunt</div>
                          <div className={`font-bold mt-1 ${botReady ? "text-slate-100" : "text-slate-500"}`}>
                            {!botReady ? "Waiting" : bot.hunt_paused ? "Paused" : "Running"}
                          </div>
                        </div>
                        <div className="rounded-xl border border-slate-700 bg-slate-950/40 p-2 text-center">
                          <div className="text-slate-400 uppercase tracking-wide">Fish</div>
                          <div className={`font-bold mt-1 ${botReady ? "text-slate-100" : "text-slate-500"}`}>
                            {!botReady ? "Waiting" : bot.fish_paused ? "Paused" : "Running"}
                          </div>
                        </div>
                        <div className="rounded-xl border border-slate-700 bg-slate-950/40 p-2 text-center">
                          <div className="text-slate-400 uppercase tracking-wide">CatchBot</div>
                          <div className={`font-bold mt-1 ${catchbotEnabled ? "text-slate-100" : "text-slate-500"}`}>
                            {catchbotEnabled ? "Enabled" : "Disabled"}
                          </div>
                          {catchbotReturnLabel && (
                            <div className="mt-1 text-[10px] text-emerald-300">{catchbotReturnLabel}</div>
                          )}
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-2">
                        {renderAutomationToggle(bot, idx, "egg_hatching", "Egg", "toggle_egg_hatching")}
                        {renderAutomationToggle(bot, idx, "auto_hold_egg", "Hold", "toggle_auto_hold_egg")}
                        {renderAutomationToggle(bot, idx, "berry_enabled", "Berry", "toggle_berry")}
                        {renderAutomationToggle(bot, idx, "catchbot_enabled", "CatchBot", "toggle_catchbot")}
                        {renderAutomationToggle(bot, idx, "anti_detection_enabled", "AntiDet", "toggle_anti_detection")}
                        {renderAutomationToggle(bot, idx, "human_breaks_enabled", "Breaks", "toggle_human_breaks")}
                        {renderAutomationToggle(bot, idx, "max_speed_mode_enabled", "MaxSpeed", "toggle_max_speed_mode")}
                        {renderAutomationToggle(bot, idx, "super_low_risk_mode_enabled", "SuperLowRisk", "toggle_super_low_risk_mode")}
                      </div>

                      <div className="flex flex-wrap gap-2 pt-1">
                        <button onClick={() => runBotAction(getBotTarget(bot), bot.hunt_paused ? "resume_hunt_bot" : "pause_hunt_bot")} disabled={!runtimeAvailable || busyAction !== "" || !botReady} className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-700 hover:bg-slate-600 text-slate-200 disabled:opacity-40 disabled:cursor-not-allowed">
                          {bot.hunt_paused ? "Resume Hunt" : "Pause Hunt"}
                        </button>
                        <button onClick={() => runBotAction(getBotTarget(bot), bot.fish_paused ? "resume_fish_bot" : "pause_fish_bot")} disabled={!runtimeAvailable || busyAction !== "" || !botReady} className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-700 hover:bg-slate-600 text-slate-200 disabled:opacity-40 disabled:cursor-not-allowed">
                          {bot.fish_paused ? "Resume Fish" : "Pause Fish"}
                        </button>
                        <button onClick={() => runBotAction(getBotTarget(bot), "stop_bot")} disabled={!runtimeAvailable || busyAction !== ""} className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-red-500/10 text-red-300 border border-red-500/30 hover:bg-red-500 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed">
                          Stop Bot
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="bg-slate-900 rounded-xl border border-amber-900/40 shadow-md p-4 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="text-sm font-semibold text-amber-100">Diagnostics</h2>
                  <p className="text-[11px] text-slate-500 mt-0.5">Errors from the Python process (desktop mode hides the console).</p>
                </div>
                <button
                  type="button"
                  onClick={() => void refreshDiagnostics()}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-amber-950/80 text-amber-200 border border-amber-800/60 hover:bg-amber-900/80"
                >
                  Refresh
                </button>
              </div>
              {diagnosticsError && (
                <p className="text-xs text-red-300 whitespace-pre-wrap">{diagnosticsError}</p>
              )}
              {diagnostics?.runtime_log_path && (
                <p className="text-[11px] text-slate-400">
                  Log file: <span className="font-mono text-slate-300 break-all">{diagnostics.runtime_log_path}</span>
                </p>
              )}
              {diagnostics && diagnostics.ok !== false && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] text-slate-400">
                  <span>Headless: {String(diagnostics.headless)}</span>
                  <span>Main loop: {String(diagnostics.main_loop_ready)}</span>
                  <span>Bots in memory: {String(diagnostics.bots_count)}</span>
                </div>
              )}
              {diagnostics?.startup_failures_by_account_id && Object.keys(diagnostics.startup_failures_by_account_id).length > 0 && (
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-red-300/90 font-bold mb-1">Startup errors (by account id)</p>
                  <pre className="text-[11px] text-red-200/90 bg-black/40 border border-red-900/40 rounded-lg p-2 max-h-32 overflow-auto whitespace-pre-wrap font-mono">
                    {JSON.stringify(diagnostics.startup_failures_by_account_id, null, 2)}
                  </pre>
                </div>
              )}
              {diagnostics?.log_tail && diagnostics.log_tail.length > 0 && (
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-slate-500 font-bold mb-1">Recent log lines</p>
                  <pre className="text-[10px] text-slate-300 bg-black/50 border border-slate-700 rounded-lg p-2 max-h-56 overflow-auto whitespace-pre-wrap font-mono leading-relaxed">
                    {diagnostics.log_tail.join("\n")}
                  </pre>
                </div>
              )}
            </div>

            <div className="bg-slate-900 rounded-xl border border-slate-800 shadow-md p-4">
              <h2 className="text-sm font-semibold text-slate-200 mb-3">Recent Actions</h2>
              {actionHistory.length === 0 ? (
                <p className="text-slate-500 text-sm">No actions yet.</p>
              ) : (
                <ul className="space-y-2 max-h-36 overflow-y-auto pr-1">
                  {actionHistory.map((item, idx) => (
                    <li key={`${item.ts}-${idx}`} className="text-sm text-slate-300 flex gap-3">
                      <span className="text-slate-500 font-mono text-xs mt-0.5">{item.ts}</span>
                      <span>{item.text}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>
        )}

        {activeTab === "captcha" && (
          <section className="space-y-5">
            <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
              <div className="rounded-3xl border border-[#881337]/50 bg-[#4C0519]/30 px-4 py-3">
                <p className="text-[10px] uppercase tracking-widest text-[#FDA4AF] font-bold">Active Captchas</p>
                <p className="text-2xl font-bold text-[#F43F5E] mt-1">{captchaQueueRows.length}</p>
              </div>
              <div className="rounded-3xl border border-amber-600/40 bg-amber-950/25 px-4 py-3">
                <p className="text-[10px] uppercase tracking-widest text-amber-200/90 font-bold">Auto Attempts</p>
                <p className="text-2xl font-bold text-amber-300 mt-1">{Number(captchaTelemetry?.counts?.attempts || 0)}</p>
              </div>
              <div className="rounded-3xl border border-emerald-700/40 bg-emerald-950/25 px-4 py-3">
                <p className="text-[10px] uppercase tracking-widest text-emerald-200/90 font-bold">Auto Solved</p>
                <p className="text-2xl font-bold text-emerald-300 mt-1">{Number(captchaTelemetry?.counts?.resolved_outcomes || 0)}</p>
              </div>
              <div className="rounded-3xl border border-orange-700/40 bg-orange-950/25 px-4 py-3">
                <p className="text-[10px] uppercase tracking-widest text-orange-200/90 font-bold">Manual Needed</p>
                <p className="text-2xl font-bold text-orange-300 mt-1">{Number(captchaTelemetry?.counts?.failed_candidates || 0)}</p>
              </div>
            </div>

            <div className="space-y-3">
              <div className="border-b border-[#4C0519] pb-2 flex items-center justify-between gap-3">
                <h2 className="text-[10px] font-bold uppercase tracking-widest text-[#FDA4AF] flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full ${captchaQueueRows.length > 0 ? "bg-[#E11D48] animate-pulse" : "bg-emerald-500"}`}></span>
                  Resolution Queue (Active)
                </h2>
                <button
                  onClick={async () => {
                    const fallbackBot =
                      captchaDisplayBots.find((bot) => bot?.captcha?.any_active)
                      || captchaDisplayBots.find((bot) => Number(bot?.captcha?.hunting?.captcha_message_id || 0) > 0 || Number(bot?.captcha?.fishing?.captcha_message_id || 0) > 0 || Number(bot?.captcha?.autofight?.captcha_message_id || 0) > 0)
                      || captchaDisplayBots[0];
                    if (!fallbackBot) {
                      setStatus({ text: "No captcha state is available to resolve", kind: "bad" });
                      return;
                    }
                    await runBotAction(getBotTarget(fallbackBot), "captcha_mark_resolved", {});
                  }}
                  disabled={!runtimeAvailable || busyAction !== "" || captchaDisplayBots.length === 0}
                  className="px-3 py-1.5 rounded-lg border border-emerald-500/40 text-emerald-200 text-[10px] font-bold uppercase tracking-widest hover:bg-emerald-500/10 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Mark Latest Resolved
                </button>
              </div>

              {captchaQueueRows.length === 0 ? (
                <div className="bg-[#0A0102] border border-dashed border-[#4C0519] rounded-3xl p-8 flex flex-col items-center justify-center text-center">
                  <SparkleIcon className="w-8 h-8 text-emerald-400 mb-3 opacity-80" />
                  <p className="text-xs font-bold text-emerald-300 uppercase tracking-widest">All nodes clear. No active captchas.</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 2xl:grid-cols-2 gap-4">
                  {captchaQueueRows.map((row) => {
                    const manualAnswerValue = readCaptchaDraft(captchaManualAnswers, row.draftKey, "");
                    return (
                      <div key={row.key} className="bg-gradient-to-r from-[#1A0508] to-[#0A0102] border border-[#E11D48]/45 rounded-[2rem] p-4 shadow-[0_0_25px_rgba(225,29,72,0.18)] flex flex-col lg:flex-row gap-4 relative overflow-hidden">
                        <div className="absolute inset-0 opacity-5 bg-[repeating-linear-gradient(45deg,transparent,transparent_10px,#E11D48_10px,#E11D48_20px)] pointer-events-none"></div>

                        <div className="w-full lg:w-48 shrink-0 flex flex-col gap-2 relative z-10">
                          <div 
                            className="bg-[#050000] border border-[#4C0519] rounded-xl p-2 h-24 flex items-center justify-center overflow-hidden cursor-pointer hover:border-[#E11D48]/60 transition-colors group"
                            onClick={() => setSelectedCaptchaPreview(row)}
                          >
                            {row.image ? (
                              <img src={row.image} alt="captcha" className="w-full h-full object-contain rounded-lg group-hover:opacity-80 transition-opacity" loading="lazy" />
                            ) : (
                              <WarningIcon className="w-7 h-7 text-[#9F1239]" />
                            )}
                          </div>
                          <div className="flex justify-between items-center bg-[#050000] px-3 py-1.5 rounded-lg border border-[#4C0519]">
                            <span className="text-[9px] font-bold uppercase tracking-widest text-[#FDA4AF]">Timer</span>
                            <span className={`text-xs font-mono font-bold ${(captchaTimers[row.key] || 0) > 30 ? "text-emerald-400" : (captchaTimers[row.key] || 0) > 0 ? "text-orange-400" : "text-[#F43F5E]"}`}>
                              {Math.ceil(captchaTimers[row.key] || 0)}s
                            </span>
                          </div>
                          <div className="flex justify-between items-center bg-[#050000] px-3 py-1.5 rounded-lg border border-[#4C0519]">
                            <span className="text-[9px] font-bold uppercase tracking-widest text-[#FDA4AF]">Predict</span>
                            <span className="text-xs font-mono font-bold text-[#FEE2E2]">{row.prediction}</span>
                          </div>
                        </div>

                        <div className="flex-1 flex flex-col justify-between gap-3 relative z-10">
                          <div>
                            <div className="flex justify-between items-start mb-1 gap-2">
                              <h3 className="font-bold text-base text-[#FEE2E2]">{row.bot?.username || "Unknown"}</h3>
                              <span className="text-[10px] font-mono text-[#F43F5E] bg-[#4C0519]/50 px-2 py-1 rounded-md border border-[#E11D48]/30">Seen: {row.timeElapsed}</span>
                            </div>
                            <p className="text-[10px] font-mono text-[#FDA4AF]">{row.channelType} • {row.channelId || "Unknown Channel"}</p>
                          </div>

                          <div className="flex flex-wrap gap-2 text-[10px]">
                            {row.image ? (
                              <a href={row.image} target="_blank" rel="noreferrer" className="px-2 py-1 rounded-lg bg-[#140205] border border-[#4C0519] text-[#FDA4AF] hover:bg-[#2A080D]">View Image</a>
                            ) : (
                              <span className="px-2 py-1 rounded-lg bg-[#140205] border border-[#4C0519] text-[#9F1239]">No Image</span>
                            )}
                            {row.jumpUrl ? (
                              <a href={row.jumpUrl} target="_blank" rel="noreferrer" className="px-2 py-1 rounded-lg bg-[#140205] border border-[#4C0519] text-emerald-300 hover:bg-[#2A080D]">Discord Jump</a>
                            ) : null}
                          </div>

                          <div className="mt-1 flex gap-2">
                            <input
                              type="text"
                              value={manualAnswerValue}
                              onChange={(e) => setCaptchaManualAnswers((prev) => ({ ...prev, [row.draftKey]: e.target.value }))}
                              placeholder="Enter captcha text..."
                              className="bg-[#050000] border border-[#E11D48]/50 text-white px-4 py-2.5 rounded-xl text-sm font-mono flex-grow focus:outline-none focus:ring-2 focus:ring-[#E11D48]/40 shadow-inner placeholder:text-[#4C0519]"
                            />
                            <button
                              onClick={async () => {
                                const answer = String(readCaptchaDraft(captchaManualAnswers, row.draftKey, "") || "").trim();
                                if (!answer) {
                                  setStatus({ text: "Manual captcha answer cannot be empty", kind: "bad" });
                                  return;
                                }
                                await runBotAction(getBotTarget(row.bot), "captcha_manual_answer", {
                                  answer,
                                  channel_hint: row.hint,
                                });
                                setCaptchaManualAnswers((prev) => ({ ...prev, [row.draftKey]: "" }));
                                setCaptchaChannelHints((prev) => ({ ...prev, [row.draftKey]: row.hint }));
                              }}
                              disabled={!runtimeAvailable || busyAction !== ""}
                              className="bg-[#E11D48] hover:bg-[#BE123C] text-white px-6 py-2.5 rounded-xl text-xs font-bold uppercase tracking-widest transition-colors shadow-lg shadow-[#E11D48]/20 shrink-0 disabled:opacity-40 disabled:cursor-not-allowed"
                            >
                              Send
                            </button>
                            <button
                              onClick={async () => {
                                await runBotAction(getBotTarget(row.bot), "captcha_mark_resolved", {
                                  channel_hint: row.hint,
                                });
                              }}
                              disabled={!runtimeAvailable || busyAction !== ""}
                              className="bg-emerald-600 hover:bg-emerald-500 text-white px-5 py-2.5 rounded-xl text-xs font-bold uppercase tracking-widest transition-colors shadow-lg shadow-emerald-500/15 shrink-0 disabled:opacity-40 disabled:cursor-not-allowed"
                            >
                              Mark Resolved
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="bg-gradient-to-b from-[#110305] to-[#0A0102] rounded-[2rem] border border-[#380D16] shadow-[0_8px_30px_rgba(0,0,0,0.8)] overflow-hidden">
              <div className="px-6 py-4 border-b border-[#380D16]/60 flex justify-between items-center bg-[#0F0304]/80">
                <div className="flex items-center gap-3">
                  <span className="text-[#E11D48] p-2 bg-[#E11D48]/10 rounded-xl border border-[#E11D48]/20"><CogIcon className="w-4 h-4" /></span>
                  <h2 className="text-sm font-bold text-[#FEE2E2] tracking-tight">Fleet Captcha Configuration</h2>
                </div>
              </div>

              <div className="p-4 grid grid-cols-1 xl:grid-cols-2 2xl:grid-cols-3 gap-4">
                {captchaDisplayBots.length === 0 && (
                  <div className="col-span-full rounded-2xl border border-dashed border-[#4C0519] bg-[#0A0102] p-6 text-center text-xs text-[#FDA4AF] uppercase tracking-widest font-bold">
                    No captcha-enabled bots found for this scope.
                  </div>
                )}

                {captchaDisplayBots.map((bot, idx) => {
                  const draftKey = getCaptchaDraftKey(bot, idx);
                  const cardKey = String(getBotKey(bot, idx));
                  const hunt = bot?.captcha?.hunting || {};
                  const fish = bot?.captcha?.fishing || {};
                  const autoEnabled = Boolean(bot?.automations?.captcha_auto_answer_enabled);
                  const alertsEnabled = Boolean(bot?.automations?.captcha_alerts_enabled);
                  const maxAttemptsValue = readCaptchaDraft(captchaMaxAttemptsDraft, draftKey, String(bot?.automations?.captcha_auto_max_attempts || 3));
                  const manualUsersValue = readCaptchaDraft(captchaManualUsersDraft, draftKey, (bot?.automations?.captcha_manual_allowed_user_ids || []).join(","));
                  const alertPingValue = readCaptchaDraft(captchaAlertPingDraft, draftKey, String(bot?.automations?.captcha_alert_ping || ""));
                  const manualAnswerValue = readCaptchaDraft(captchaManualAnswers, draftKey, "");
                  const channelHintValue = readCaptchaDraft(captchaChannelHints, draftKey, "auto");
                  const expanded = expandedCaptchaConfig === cardKey;

                  return (
                    <div key={`captcha-config-${cardKey}`} className={`rounded-2xl border transition-colors ${expanded ? "bg-[#0F0304] border-[#881337]" : "bg-[#050000] border-[#380D16] hover:border-[#4C0519]"}`}>
                      <div className="p-4 flex justify-between items-center cursor-pointer" onClick={() => setExpandedCaptchaConfig(expanded ? "" : cardKey)}>
                        <div className="flex items-center gap-3 min-w-0">
                          <div className={`w-2 h-2 rounded-full ${bot?.captcha?.any_active ? "bg-[#E11D48] shadow-[0_0_8px_rgba(225,29,72,0.8)] animate-pulse" : "bg-emerald-500"}`}></div>
                          <div className="min-w-0">
                            <h3 className="font-bold text-[#FEE2E2] text-sm truncate">{bot?.username || "Unknown"}</h3>
                            <p className="text-[9px] font-mono text-[#FDA4AF] uppercase tracking-widest mt-0.5 truncate">
                              {autoEnabled ? "Auto: ON" : "Auto: OFF"} • {alertsEnabled ? "Alerts: ON" : "Alerts: OFF"} • {bot?.captcha?.any_active ? "Action Req" : "Clear"}
                            </p>
                          </div>
                        </div>
                        <span className="text-[10px] font-bold uppercase tracking-widest text-[#9F1239] bg-[#1A0508] px-3 py-1.5 rounded-lg border border-[#380D16]">
                          {expanded ? "Close" : "Config"}
                        </span>
                      </div>

                      {expanded && (
                        <div className="p-4 border-t border-[#380D16] bg-[#0A0102] rounded-b-2xl space-y-4">
                          <div className="grid grid-cols-2 gap-2 text-[10px] font-mono">
                            <div className="bg-[#050000] border border-[#380D16] rounded-xl px-3 py-2 text-[#FDA4AF]">Hunting: {String(hunt?.channel_id || "-")}</div>
                            <div className="bg-[#050000] border border-[#380D16] rounded-xl px-3 py-2 text-[#FDA4AF]">Fishing: {String(fish?.channel_id || "-")}</div>
                          </div>

                          <div className="flex gap-2">
                            <button
                              onClick={() => runBotAction(getBotTarget(bot), "toggle_captcha_auto_answer", { enabled: !autoEnabled })}
                              disabled={!runtimeAvailable || busyAction !== ""}
                              className={`flex-1 py-2 text-[10px] font-bold uppercase tracking-widest rounded-xl border transition-colors ${autoEnabled ? "bg-[#E11D48]/10 text-[#F43F5E] border-[#E11D48]/30" : "bg-[#180508] text-[#FDA4AF] border-[#380D16]"} disabled:opacity-40 disabled:cursor-not-allowed`}
                            >
                              Auto Answer: {autoEnabled ? "ON" : "OFF"}
                            </button>
                            <button
                              onClick={() => runBotAction(getBotTarget(bot), "toggle_captcha_alerts", { enabled: !alertsEnabled })}
                              disabled={!runtimeAvailable || busyAction !== ""}
                              className={`flex-1 py-2 text-[10px] font-bold uppercase tracking-widest rounded-xl border transition-colors ${alertsEnabled ? "bg-[#E11D48]/10 text-[#F43F5E] border-[#E11D48]/30" : "bg-[#180508] text-[#FDA4AF] border-[#380D16]"} disabled:opacity-40 disabled:cursor-not-allowed`}
                            >
                              Alerts: {alertsEnabled ? "ON" : "OFF"}
                            </button>
                          </div>

                          <div className="grid grid-cols-1 md:grid-cols-[1fr,auto] gap-2">
                            <input
                              value={maxAttemptsValue}
                              onChange={(e) => setCaptchaMaxAttemptsDraft((prev) => ({ ...prev, [draftKey]: e.target.value }))}
                              placeholder="Max auto attempts"
                              className="bg-[#050000] border border-[#380D16] text-[#FEE2E2] px-4 py-2 rounded-xl text-[11px] font-mono w-full focus:outline-none focus:border-[#E11D48]"
                            />
                            <button
                              onClick={() => saveCaptchaMaxAttempts(bot, idx)}
                              disabled={!runtimeAvailable || busyAction !== ""}
                              className="px-3 py-2 rounded-xl text-[10px] font-bold uppercase tracking-widest bg-[#1A0508] hover:bg-[#2A080D] text-[#FEE2E2] border border-[#4C0519] disabled:opacity-40 disabled:cursor-not-allowed"
                            >
                              Save Tries
                            </button>
                          </div>

                          <div className="grid grid-cols-1 md:grid-cols-[1fr,auto] gap-2">
                            <input
                              value={manualUsersValue}
                              onChange={(e) => setCaptchaManualUsersDraft((prev) => ({ ...prev, [draftKey]: e.target.value }))}
                              placeholder="Allowed User IDs (CSV)"
                              className="bg-[#050000] border border-[#380D16] text-[#FEE2E2] px-4 py-2 rounded-xl text-[11px] font-mono w-full focus:outline-none focus:border-[#E11D48]"
                            />
                            <button
                              onClick={() => saveCaptchaManualAllowedUsers(bot, idx)}
                              disabled={!runtimeAvailable || busyAction !== ""}
                              className="px-3 py-2 rounded-xl text-[10px] font-bold uppercase tracking-widest bg-[#1A0508] hover:bg-[#2A080D] text-[#FEE2E2] border border-[#4C0519] disabled:opacity-40 disabled:cursor-not-allowed"
                            >
                              Save IDs
                            </button>
                          </div>

                          <div className="grid grid-cols-1 md:grid-cols-[1fr,auto] gap-2">
                            <input
                              value={alertPingValue}
                              onChange={(e) => setCaptchaAlertPingDraft((prev) => ({ ...prev, [draftKey]: e.target.value }))}
                              placeholder="Alert ping (e.g. @here or <@123...>)"
                              className="bg-[#050000] border border-[#380D16] text-[#FEE2E2] px-4 py-2 rounded-xl text-[11px] font-mono w-full focus:outline-none focus:border-[#E11D48]"
                            />
                            <button
                              onClick={() => saveCaptchaAlertPing(bot, idx)}
                              disabled={!runtimeAvailable || busyAction !== ""}
                              className="px-3 py-2 rounded-xl text-[10px] font-bold uppercase tracking-widest bg-[#1A0508] hover:bg-[#2A080D] text-[#FEE2E2] border border-[#4C0519] disabled:opacity-40 disabled:cursor-not-allowed"
                            >
                              Save Ping
                            </button>
                          </div>

                          <div className="rounded-xl border border-[#380D16] bg-[#050000] p-3 space-y-2">
                            <p className="text-[10px] font-bold uppercase tracking-widest text-[#FDA4AF]">Manual Answer Console</p>
                            <div className="grid grid-cols-1 md:grid-cols-[130px,1fr,auto] gap-2">
                              <select
                                value={channelHintValue}
                                onChange={(e) => setCaptchaChannelHints((prev) => ({ ...prev, [draftKey]: e.target.value }))}
                                className="bg-[#050000] border border-[#380D16] text-[#FEE2E2] px-2 py-2 rounded-xl text-[11px]"
                              >
                                <option value="auto">Auto route</option>
                                <option value="hunting">Hunting</option>
                                <option value="fishing">Fishing</option>
                              </select>
                              <input
                                value={manualAnswerValue}
                                onChange={(e) => setCaptchaManualAnswers((prev) => ({ ...prev, [draftKey]: e.target.value }))}
                                placeholder="Enter captcha text"
                                className="bg-[#050000] border border-[#380D16] text-[#FEE2E2] px-3 py-2 rounded-xl text-[11px] font-mono"
                              />
                              <button
                                onClick={() => runCaptchaManualAnswer(bot, idx)}
                                disabled={!runtimeAvailable || busyAction !== ""}
                                className="px-4 py-2 rounded-xl text-[10px] font-bold uppercase tracking-widest bg-[#E11D48] hover:bg-[#BE123C] text-white disabled:opacity-40 disabled:cursor-not-allowed"
                              >
                                Send
                              </button>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="bg-gradient-to-b from-[#110305] to-[#0A0102] rounded-[2rem] border border-[#380D16] shadow-[0_8px_30px_rgba(0,0,0,0.8)] overflow-hidden">
              <div className="px-6 py-4 border-b border-[#380D16]/60 flex flex-wrap gap-2 items-center justify-between bg-[#0F0304]/80">
                <div className="space-y-1">
                  <h2 className="text-sm font-semibold text-[#FEE2E2]">Telemetry Feed</h2>
                  <p className="text-xs text-[#FDA4AF]/75">Latest attempts, outcomes, unresolved failures, and labels.</p>
                </div>
                <div className="flex gap-2 items-center">
                  <input
                    value={captchaTelemetrySearch}
                    onChange={(e) => setCaptchaTelemetrySearch(e.target.value)}
                    placeholder="Search account, channel, label, prediction..."
                    className="bg-[#050000] border border-[#380D16] rounded-xl px-3 py-1.5 text-xs min-w-[240px] text-[#FEE2E2]"
                  />
                  <select value={captchaTelemetryLimit} onChange={(e) => setCaptchaTelemetryLimit(Number(e.target.value))} className="bg-[#050000] border border-[#380D16] rounded-xl px-2 py-1 text-xs text-[#FEE2E2]">
                    <option value={40}>40 rows</option>
                    <option value={60}>60 rows</option>
                    <option value={120}>120 rows</option>
                  </select>
                </div>
              </div>

              <div className="p-4 grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div>
                  <h4 className="text-[10px] font-bold text-[#9F1239] uppercase tracking-widest mb-2 border-b border-[#380D16] pb-1.5">Auto Attempts</h4>
                  <div className="bg-[#050000] border border-[#380D16] rounded-xl overflow-hidden">
                    <div className="max-h-56 overflow-auto" onWheel={handleScrollRegionWheel}>
                      <table className="w-full text-left text-[10px] font-mono">
                        <thead className="bg-[#0A0102] text-[#FDA4AF] border-b border-[#380D16] sticky top-0">
                          <tr>
                            <th className="p-2 font-normal">WHEN</th>
                            <th className="p-2 font-normal">ACCOUNT</th>
                            <th className="p-2 font-normal">TRY</th>
                            <th className="p-2 font-normal">PRED</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[#380D16]/60 text-[#FEE2E2]">
                          {(captchaTelemetry?.attempts || []).length === 0 && (
                            <tr><td className="p-2 text-[#9F1239]" colSpan={4}>NO ATTEMPT ROWS</td></tr>
                          )}
                          {(captchaTelemetry?.attempts || []).map((row, idx) => (
                            <tr key={`cap-attempt-${idx}`} className="hover:bg-[#110305]">
                              <td className="p-2 text-[#9F1239]">{formatRelativeTime(row?.ts_utc)}</td>
                              <td className="p-2">{row?.account || "-"}</td>
                              <td className="p-2">{Number(row?.attempt_number || 0)}/{Number(row?.max_attempts || 0)}</td>
                              <td className="p-2 text-[#E11D48]">{row?.prediction || "-"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>

                <div>
                  <h4 className="text-[10px] font-bold text-[#9F1239] uppercase tracking-widest mb-2 border-b border-[#380D16] pb-1.5">Solver Outcomes</h4>
                  <div className="bg-[#050000] border border-[#380D16] rounded-xl overflow-hidden">
                    <div className="max-h-56 overflow-auto" onWheel={handleScrollRegionWheel}>
                      <table className="w-full text-left text-[10px] font-mono">
                        <thead className="bg-[#0A0102] text-[#FDA4AF] border-b border-[#380D16] sticky top-0">
                          <tr>
                            <th className="p-2 font-normal">WHEN</th>
                            <th className="p-2 font-normal">ACCOUNT</th>
                            <th className="p-2 font-normal">OUTCOME</th>
                            <th className="p-2 font-normal">TRIES</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[#380D16]/60 text-[#FEE2E2]">
                          {(captchaTelemetry?.outcomes || []).length === 0 && (
                            <tr><td className="p-2 text-[#9F1239]" colSpan={4}>NO OUTCOME ROWS</td></tr>
                          )}
                          {(captchaTelemetry?.outcomes || []).map((row, idx) => (
                            <tr key={`cap-outcome-${idx}`} className="hover:bg-[#110305]">
                              <td className="p-2 text-[#9F1239]">{formatRelativeTime(row?.ts_utc)}</td>
                              <td className="p-2">{row?.account || "-"}</td>
                              <td className="p-2">{row?.outcome || "-"}</td>
                              <td className="p-2">{Number(row?.attempts_used || 0)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>

                <div>
                  <h4 className="text-[10px] font-bold text-[#9F1239] uppercase tracking-widest mb-2 border-b border-[#380D16] pb-1.5">Failed Candidates</h4>
                  <div className="bg-[#050000] border border-[#380D16] rounded-xl overflow-hidden">
                    <div className="max-h-56 overflow-auto" onWheel={handleScrollRegionWheel}>
                      <table className="w-full text-left text-[10px] font-mono">
                        <thead className="bg-[#0A0102] text-[#FDA4AF] border-b border-[#380D16] sticky top-0">
                          <tr>
                            <th className="p-2 font-normal">WHEN</th>
                            <th className="p-2 font-normal">ACCOUNT</th>
                            <th className="p-2 font-normal">PRED</th>
                            <th className="p-2 font-normal">IMAGE</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[#380D16]/60 text-[#FEE2E2]">
                          {(captchaTelemetry?.failed_candidates || []).length === 0 && (
                            <tr><td className="p-2 text-[#9F1239]" colSpan={4}>NO FAILED CANDIDATES</td></tr>
                          )}
                          {(captchaTelemetry?.failed_candidates || []).map((row, idx) => (
                            <tr key={`cap-failed-${idx}`} className="hover:bg-[#110305]">
                              <td className="p-2 text-[#9F1239]">{formatRelativeTime(row?.ts_utc)}</td>
                              <td className="p-2">{row?.account || "-"}</td>
                              <td className="p-2">{row?.predicted_answer || "-"}</td>
                              <td className="p-2">
                                {row?.captcha_image_url ? (
                                  <a href={row.captcha_image_url} target="_blank" rel="noreferrer" className="text-[#FDA4AF] hover:underline">Open</a>
                                ) : (
                                  <span className="text-[#9F1239]">-</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>

                <div>
                  <h4 className="text-[10px] font-bold text-[#9F1239] uppercase tracking-widest mb-2 border-b border-[#380D16] pb-1.5">Training Labels</h4>
                  <div className="bg-[#050000] border border-[#380D16] rounded-xl overflow-hidden">
                    <div className="max-h-56 overflow-auto" onWheel={handleScrollRegionWheel}>
                      <table className="w-full text-left text-[10px] font-mono">
                        <thead className="bg-[#0A0102] text-[#FDA4AF] border-b border-[#380D16] sticky top-0">
                          <tr>
                            <th className="p-2 font-normal">WHEN</th>
                            <th className="p-2 font-normal">ACCOUNT</th>
                            <th className="p-2 font-normal">LABEL</th>
                            <th className="p-2 font-normal">SOURCE</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[#380D16]/60 text-[#FEE2E2]">
                          {(captchaTelemetry?.labels || []).length === 0 && (
                            <tr><td className="p-2 text-[#9F1239]" colSpan={4}>NO LABELS YET</td></tr>
                          )}
                          {(captchaTelemetry?.labels || []).map((row, idx) => (
                            <tr key={`cap-label-${idx}`} className="hover:bg-[#110305]">
                              <td className="p-2 text-[#9F1239]">{formatRelativeTime(row?.ts_utc)}</td>
                              <td className="p-2">{row?.account || "-"}</td>
                              <td className="p-2">{row?.label || "-"}</td>
                              <td className="p-2">{row?.label_source || "-"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>
        )}

        {activeTab === "anti_detect" && (
          <section className="space-y-4">
            <div className="bg-slate-900 rounded-3xl border border-slate-800 shadow-md overflow-hidden">
              <div className="p-4 border-b border-slate-800 flex flex-wrap gap-2 items-center justify-between">
                <div className="space-y-1">
                  <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><TerminalIcon className="w-4 h-4" />Anti-Detect Telemetry</h2>
                  <p className="text-xs text-slate-500 font-mono truncate max-w-[70vw]">{antiDetect.log_path || "No log path"}</p>
                </div>
                <div className="flex gap-2 items-center">
                  <input
                    value={telemetrySearch}
                    onChange={(e) => setTelemetrySearch(e.target.value)}
                    placeholder="Search account, module, event, channel, details..."
                    className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-xs min-w-[240px]"
                  />
                  <select value={antiDetectLimit} onChange={(e) => setAntiDetectLimit(Number(e.target.value))} className="bg-slate-800 border border-slate-700 rounded-lg px-2 py-1 text-xs">
                    <option value={100}>100 rows</option>
                    <option value={200}>200 rows</option>
                    <option value={500}>500 rows</option>
                  </select>
                  <button onClick={refreshAll} className="bg-[#1A0508] text-[#FEE2E2] border border-[#4C0519] hover:bg-[#2A080D] px-4 py-1.5 rounded-xl transition-colors text-sm font-bold">Refresh</button>
                  <button onClick={clearAntiDetectLogs} className="bg-[#4C0519]/50 text-[#F43F5E] border border-[#E11D48]/30 hover:bg-[#E11D48]/15 px-4 py-1.5 rounded-xl transition-colors text-sm font-bold">Clear Logs</button>
                </div>
              </div>
              <div className="p-4 border-b border-slate-800 text-sm text-slate-300">
                Total loaded events: <span className="font-mono text-[#FDA4AF]">{antiDetect.count || 0}</span>
                {telemetrySearchTrimmed && (
                  <span className="ml-2 text-slate-400">(query: <span className="font-mono">{telemetrySearchTrimmed}</span>)</span>
                )}
              </div>
              <div className="overflow-auto max-h-[60vh]" onWheel={handleScrollRegionWheel}>
                <table className="w-full text-left text-sm text-slate-300">
                  <thead className="bg-slate-950/60 text-slate-400 uppercase text-xs font-semibold sticky top-0">
                    <tr>
                      <th className="px-4 py-3">Time (UTC)</th>
                      <th className="px-4 py-3">Account</th>
                      <th className="px-4 py-3">Module</th>
                      <th className="px-4 py-3">Event</th>
                      <th className="px-4 py-3">Channel</th>
                      <th className="px-4 py-3">Details</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {(antiDetect.events || []).length === 0 && (
                      <tr><td className="px-4 py-3 text-slate-500" colSpan={6}>No telemetry events yet</td></tr>
                    )}
                    {(antiDetect.events || []).map((row, idx) => (
                      <tr key={`${row.ts || "na"}-${idx}`} className="hover:bg-slate-800/30 align-top">
                        <td className="px-4 py-3 font-mono text-xs whitespace-nowrap">{row.ts || "-"}</td>
                        <td className="px-4 py-3">{row.account || "-"}</td>
                        <td className="px-4 py-3">{row.module || "-"}</td>
                        <td className="px-4 py-3 text-[#FDA4AF]">{row.event || "-"}</td>
                        <td className="px-4 py-3 font-mono text-xs">{row.channel_id || 0}</td>
                        <td className="px-4 py-3 font-mono text-xs text-slate-400 break-words">{JSON.stringify(row.details || {})}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        )}

        {activeTab === "config" && (
          <section>
            <div className="bg-[#0f172a] rounded-3xl border border-slate-800 shadow-md overflow-hidden flex flex-col">
              <div className="p-4 border-b border-slate-800 bg-slate-900/70">
                <div className="text-xs font-semibold text-slate-300 mb-3 uppercase tracking-widest">Quick Add Account</div>

                <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
                  <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-3">
                    <div className="text-[11px] uppercase tracking-widest text-slate-400 mb-2">Core Channels</div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      <div>
                        <label className="block text-[11px] text-slate-400 mb-1">Token</label>
                        <input
                          value={newAccount.token}
                          onChange={(e) => setNewAccount((prev) => ({ ...prev, token: e.target.value }))}
                          placeholder="Token"
                          className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-2 text-xs text-slate-200"
                        />
                      </div>
                      <div>
                        <label className="block text-[11px] text-slate-400 mb-1">Required Server ID</label>
                        <input
                          value={newAccount.requiredServerId}
                          onChange={(e) => setNewAccount((prev) => ({ ...prev, requiredServerId: e.target.value }))}
                          placeholder="Optional"
                          className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-2 text-xs text-slate-200"
                        />
                      </div>
                      <div>
                        <label className="block text-[11px] text-slate-400 mb-1">Hunting Channel ID</label>
                        <input
                          value={newAccount.huntingChannelId}
                          onChange={(e) => setNewAccount((prev) => ({ ...prev, huntingChannelId: e.target.value }))}
                          placeholder="Required"
                          className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-2 text-xs text-slate-200"
                        />
                      </div>
                      <div>
                        <label className="block text-[11px] text-slate-400 mb-1">Fishing Channel ID</label>
                        <input
                          value={newAccount.fishingChannelId}
                          onChange={(e) => setNewAccount((prev) => ({ ...prev, fishingChannelId: e.target.value }))}
                          placeholder="Required"
                          className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-2 text-xs text-slate-200"
                        />
                      </div>
                      <div className="md:col-span-2">
                        <label className="block text-[11px] text-slate-400 mb-1">Berry Channel ID</label>
                        <input
                          value={newAccount.berryChannelId}
                          onChange={(e) => setNewAccount((prev) => ({ ...prev, berryChannelId: e.target.value }))}
                          placeholder="Optional"
                          className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-2 text-xs text-slate-200"
                        />
                      </div>
                    </div>
                  </div>

                  <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-3">
                    <div className="text-[11px] uppercase tracking-widest text-slate-400 mb-2">Captcha Settings</div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      <div>
                        <label className="block text-[11px] text-slate-400 mb-1">Max Auto Attempts</label>
                        <input
                          value={newAccount.captchaMaxAutoAttempts}
                          onChange={(e) => setNewAccount((prev) => ({ ...prev, captchaMaxAutoAttempts: e.target.value }))}
                          placeholder="Optional"
                          className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-2 text-xs text-slate-200"
                        />
                      </div>
                      <div>
                        <label className="block text-[11px] text-slate-400 mb-1">Manual Allowed User IDs</label>
                        <input
                          value={newAccount.captchaManualAllowedUserIds}
                          onChange={(e) => setNewAccount((prev) => ({ ...prev, captchaManualAllowedUserIds: e.target.value }))}
                          placeholder="CSV IDs"
                          className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-2 text-xs text-slate-200"
                        />
                      </div>
                      <label className="text-[11px] text-slate-300 flex items-center gap-2 px-2 py-2 bg-slate-800 border border-slate-700 rounded md:col-span-2">
                        <input
                          type="checkbox"
                          checked={Boolean(newAccount.captchaAutoAnswerEnabled)}
                          onChange={(e) => setNewAccount((prev) => ({ ...prev, captchaAutoAnswerEnabled: e.target.checked }))}
                        />
                        Captcha Auto Answer Enabled
                      </label>
                    </div>
                  </div>

                  <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-3 xl:col-span-2">
                    <div className="text-[11px] uppercase tracking-widest text-slate-400 mb-2">Alert Routing</div>
                    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-2">
                      <label className="text-[11px] text-slate-300 flex items-center gap-2 px-2 py-2 bg-slate-800 border border-slate-700 rounded">
                        <input
                          type="checkbox"
                          checked={Boolean(newAccount.captchaAlertsEnabled)}
                          onChange={(e) => setNewAccount((prev) => ({ ...prev, captchaAlertsEnabled: e.target.checked }))}
                        />
                        Alerts Enabled
                      </label>
                      <input
                        value={newAccount.captchaAlertChannelId}
                        onChange={(e) => setNewAccount((prev) => ({ ...prev, captchaAlertChannelId: e.target.value }))}
                        placeholder="Alert Channel ID"
                        className="bg-slate-800 border border-slate-700 rounded px-2 py-2 text-xs text-slate-200"
                      />
                      <input
                        value={newAccount.captchaAlertPing}
                        onChange={(e) => setNewAccount((prev) => ({ ...prev, captchaAlertPing: e.target.value }))}
                        placeholder="Alert Ping"
                        className="bg-slate-800 border border-slate-700 rounded px-2 py-2 text-xs text-slate-200"
                      />
                      <input
                        value={newAccount.captchaAlertCooldownSeconds}
                        onChange={(e) => setNewAccount((prev) => ({ ...prev, captchaAlertCooldownSeconds: e.target.value }))}
                        placeholder="Cooldown Seconds"
                        className="bg-slate-800 border border-slate-700 rounded px-2 py-2 text-xs text-slate-200"
                      />
                      <input
                        value={newAccount.captchaAlertWebhookUrl}
                        onChange={(e) => setNewAccount((prev) => ({ ...prev, captchaAlertWebhookUrl: e.target.value }))}
                        placeholder="Webhook URL"
                        className="bg-slate-800 border border-slate-700 rounded px-2 py-2 text-xs text-slate-200 md:col-span-2 xl:col-span-4"
                      />
                    </div>
                  </div>
                </div>

                <div className="mt-3 rounded-2xl border border-slate-800 bg-slate-950/30 px-3 py-2.5 flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-3">
                    <span className="text-[11px] text-slate-500">Required before add: token, hunting ID, fishing ID.</span>
                    <label className="text-[11px] text-slate-300 flex items-center gap-1.5">
                      <input
                        type="checkbox"
                        checked={Boolean(newAccount.startAfterAdd)}
                        onChange={(e) => setNewAccount((prev) => ({ ...prev, startAfterAdd: e.target.checked }))}
                      />
                      Start after add
                    </label>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleAddAccount(false)}
                      disabled={busyAction !== ""}
                      className="bg-[#1A0508] text-[#FEE2E2] border border-[#4C0519] hover:bg-[#2A080D] px-3 py-1.5 rounded-xl text-xs font-bold disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      Add Only
                    </button>
                    <button
                      onClick={() => handleAddAccount(Boolean(newAccount.startAfterAdd))}
                      disabled={busyAction !== ""}
                      className="bg-gradient-to-r from-[#E11D48] to-[#BE123C] text-white border border-[#E11D48]/40 hover:brightness-110 px-3 py-1.5 rounded-xl text-xs font-bold disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      Add + Start
                    </button>
                  </div>
                </div>
              </div>
              <div className="flex justify-between items-center p-3 bg-slate-900 border-b border-slate-800">
                <div className="text-xs text-slate-500 font-mono truncate pr-4">{configPath}</div>
                <div className="flex items-center gap-2">
                  <div className={`px-3 py-1.5 rounded-xl border ${configDirty ? "bg-amber-500/10 text-amber-200 border-amber-500/35" : "bg-[#E11D48]/12 text-[#FECDD3] border-[#E11D48]/35"}`}>
                    <div className="flex items-center gap-2">
                      <span className={`inline-block w-2 h-2 rounded-full ${configDirty ? "bg-amber-300" : "bg-[#F43F5E] animate-pulse"}`}></span>
                      <span className="text-xs font-bold tracking-wide uppercase">{configDirty ? "Needs Save" : "Synced"}</span>
                      {!configDirty && configSyncedAt && (
                        <span className="text-[11px] text-[#FDA4AF]">{new Date(configSyncedAt).toLocaleTimeString()}</span>
                      )}
                    </div>
                  </div>
                  <button onClick={reloadConfigFromDisk} className="bg-[#1A0508] text-[#FEE2E2] border border-[#4C0519] hover:bg-[#2A080D] px-4 py-1.5 rounded-xl transition-colors text-sm font-bold">Reload</button>
                  <button onClick={handleFormatJson} className="bg-[#1A0508] text-[#FEE2E2] border border-[#4C0519] hover:bg-[#2A080D] px-4 py-1.5 rounded-xl transition-colors text-sm font-bold">Format</button>
                  <button onClick={handleSaveConfig} className="bg-gradient-to-r from-[#E11D48] to-[#BE123C] text-white border border-[#E11D48]/40 hover:brightness-110 px-5 py-1.5 rounded-xl transition-colors text-sm font-bold shadow-sm active:scale-95">Save</button>
                </div>
              </div>
              <textarea
                value={configJson}
                onChange={(e) => {
                  setConfigJson(e.target.value);
                  setConfigDirty(true);
                }}
                onWheel={handleScrollRegionWheel}
                className="w-full h-[66vh] bg-[#030000] text-slate-200 p-4 font-mono text-sm leading-relaxed resize-none focus:outline-none focus:ring-1 focus:ring-[#E11D48]/50"
                spellCheck="false"
              />
            </div>
          </section>
        )}

        {selectedCatch && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <button
              className="absolute inset-0 bg-black/65 backdrop-blur-[2px]"
              aria-label="Close Pokemon details"
              onClick={closePokemonModal}
            />
            <div className="relative w-full max-w-2xl bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl overflow-hidden">
              <div className="px-5 py-4 border-b border-slate-700 flex items-center justify-between gap-3">
                <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
                  <PokeBallIcon className="w-5 h-5 sakura-icon" />
                  Pokemon Details: {selectedCatch.name}
                </h3>
                <button onClick={closePokemonModal} className="px-3 py-1.5 text-xs rounded-lg bg-slate-800 border border-slate-600 text-slate-200 hover:bg-slate-700">
                  Close
                </button>
              </div>

              <div className="p-5 max-h-[70vh] overflow-auto" onWheel={handleScrollRegionWheel}>
                {selectedPokemonLoading && (
                  <div className="text-sm text-slate-300">Loading online Pokemon data...</div>
                )}

                {!selectedPokemonLoading && selectedPokemonError && (
                  <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                    {selectedPokemonError}
                    {pokemonFallbackPrompt?.choices?.length > 0 && (
                      <div className="mt-3 space-y-2">
                        <div className="text-xs text-red-200/90">
                          Pick the right form for {pokemonFallbackPrompt?.sourceName || "this Pokemon"}. Your choice will be saved for next time.
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {pokemonFallbackPrompt.choices.map((choice) => (
                            <button
                              key={choice.slug}
                              onClick={() => handlePokemonFallbackChoice(choice.slug)}
                              disabled={pokemonFallbackBusy}
                              className="px-2.5 py-1 rounded-md text-xs font-semibold bg-[#E11D48]/20 text-[#FDA4AF] border border-[#E11D48]/35 hover:bg-[#E11D48] hover:text-white disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              {choice.label}
                            </button>
                          ))}
                        </div>
                        <div>
                          <button
                            onClick={() => {
                              const sourceSlug = String(pokemonFallbackPrompt?.sourceSlug || "").trim();
                              if (!sourceSlug) return;
                              const nextOverrides = { ...pokemonSlugOverrides };
                              delete nextOverrides[sourceSlug];
                              setPokemonSlugOverrides(nextOverrides);
                              writePokemonSlugOverrides(nextOverrides);
                            }}
                            className="px-2 py-1 rounded-md text-[11px] bg-slate-800/70 border border-slate-600 text-slate-200 hover:bg-slate-700"
                          >
                            Clear saved mapping for this name
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {!selectedPokemonLoading && !selectedPokemonError && selectedPokemonInfo && (
                  <div className="space-y-4">
                    <div className="flex flex-col sm:flex-row gap-4">
                      <div className="w-40 h-40 bg-slate-800/60 rounded-xl border border-slate-700 flex items-center justify-center overflow-hidden">
                        {selectedPokemonInfo.sprite ? (
                          <img src={selectedPokemonInfo.sprite} alt={selectedPokemonInfo.name} className="w-36 h-36 object-contain" />
                        ) : (
                          <PokeBallIcon className="w-16 h-16 sakura-icon opacity-80" />
                        )}
                      </div>
                      <div className="grid grid-cols-2 gap-2 flex-1 text-sm">
                        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-2"><span className="text-slate-400">Pokedex ID</span><div className="text-slate-100 font-semibold">#{selectedPokemonInfo.id || "-"}</div></div>
                        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-2"><span className="text-slate-400">Name</span><div className="text-slate-100 font-semibold">{selectedPokemonInfo.name}</div></div>
                        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-2"><span className="text-slate-400">Height</span><div className="text-slate-100 font-semibold">{selectedPokemonInfo.heightMeters || 0} m</div></div>
                        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-2"><span className="text-slate-400">Weight</span><div className="text-slate-100 font-semibold">{selectedPokemonInfo.weightKg || 0} kg</div></div>
                      </div>
                    </div>

                    <div className="text-sm">
                      <div className="mb-1 text-slate-400">Types</div>
                      <div className="flex flex-wrap gap-2">
                        {(selectedPokemonInfo.types || []).map((type) => (
                          <span key={type} className="px-2 py-1 rounded-md bg-[#E11D48]/15 border border-[#E11D48]/35 text-[#FDA4AF] text-xs font-semibold">
                            {type}
                          </span>
                        ))}
                      </div>
                    </div>

                    <div className="text-sm">
                      <div className="mb-1 text-slate-400">Abilities</div>
                      <div className="text-slate-200">{(selectedPokemonInfo.abilities || []).join(", ") || "-"}</div>
                    </div>

                    <div className="text-sm">
                      <div className="mb-1 text-slate-400">Generation</div>
                      <div className="text-slate-200">{selectedPokemonInfo.generation || "-"}</div>
                    </div>

                    <div className="text-sm">
                      <div className="mb-1 text-slate-400">Pokedex Flavor Text</div>
                      <div className="text-slate-200 leading-relaxed">{selectedPokemonInfo.flavor || "No flavor text found."}</div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {selectedCaptchaPreview && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <button
              className="absolute inset-0 bg-black/75 backdrop-blur-sm"
              aria-label="Close captcha preview"
              onClick={() => setSelectedCaptchaPreview(null)}
            />
            <div className="relative w-full max-w-2xl bg-[#0A0102] border border-[#E11D48]/50 rounded-3xl shadow-2xl overflow-hidden">
              <div className="px-6 py-4 border-b border-[#4C0519] flex items-center justify-between gap-3 bg-[#050000]">
                <div>
                  <h3 className="text-lg font-bold text-[#FEE2E2]">
                    {selectedCaptchaPreview.bot?.username || "Unknown"} - Captcha Preview
                  </h3>
                  <p className="text-[10px] text-[#FDA4AF] mt-1 uppercase tracking-widest">
                    {selectedCaptchaPreview.channelType} • {selectedCaptchaPreview.hint}
                  </p>
                </div>
                <button 
                  onClick={() => setSelectedCaptchaPreview(null)} 
                  className="px-4 py-2 text-xs rounded-lg bg-[#140205] border border-[#4C0519] text-[#FDA4AF] hover:bg-[#E11D48] hover:text-white transition-colors"
                >
                  Close
                </button>
              </div>

              <div className="p-8 bg-gradient-to-b from-[#1A0508] to-[#0A0102] flex flex-col items-center justify-center max-h-[80vh] overflow-auto">
                {selectedCaptchaPreview.image ? (
                  <div className="space-y-4">
                    <img 
                      src={selectedCaptchaPreview.image} 
                      alt="captcha-preview" 
                      className="max-w-full max-h-[500px] border border-[#E11D48]/30 rounded-xl" 
                    />
                    <div className="grid grid-cols-2 gap-4 text-center">
                      <div className="bg-[#050000] border border-[#4C0519] rounded-lg px-4 py-3">
                        <p className="text-[10px] font-bold uppercase tracking-widest text-[#FDA4AF] mb-1">Time Remaining</p>
                        <p className={`text-2xl font-bold font-mono ${(captchaTimers[selectedCaptchaPreview.key] || 0) > 30 ? "text-emerald-400" : (captchaTimers[selectedCaptchaPreview.key] || 0) > 0 ? "text-orange-400" : "text-[#F43F5E]"}`}>
                          {Math.ceil(captchaTimers[selectedCaptchaPreview.key] || 0)}s
                        </p>
                      </div>
                      <div className="bg-[#050000] border border-[#4C0519] rounded-lg px-4 py-3">
                        <p className="text-[10px] font-bold uppercase tracking-widest text-[#FDA4AF] mb-1">AI Prediction</p>
                        <p className="text-xl font-bold font-mono text-[#FEE2E2]">
                          {selectedCaptchaPreview.prediction}
                        </p>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-center">
                    <WarningIcon className="w-16 h-16 text-[#9F1239] mx-auto mb-4" />
                    <p className="text-[#FDA4AF] font-bold">No image available</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
      </main>
    </div>
  );
}
