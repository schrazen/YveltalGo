export async function fetchJson(url, options) {
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

export async function fetchJsonWithFallback(url, fallbackValue, options) {
  try {
    return await fetchJson(url, options);
  } catch {
    return fallbackValue;
  }
}

export function formatRelativeTime(ts) {
  if (!ts) return "unknown";
  const when = new Date(ts).getTime();
  if (Number.isNaN(when)) return "unknown";
  const deltaSec = Math.max(0, Math.floor((Date.now() - when) / 1000));
  if (deltaSec < 60) return `${deltaSec}s ago`;
  if (deltaSec < 3600) return `${Math.floor(deltaSec / 60)}m ago`;
  if (deltaSec < 86400) return `${Math.floor(deltaSec / 3600)}h ago`;
  return `${Math.floor(deltaSec / 86400)}d ago`;
}

export function toPokeApiSlug(name) {
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

export function toDisplayName(value) {
  const raw = String(value || "").replace(/-/g, " ").trim();
  if (!raw) return "Unknown";
  return raw.replace(/\b\w/g, (c) => c.toUpperCase());
}

export const POKEMON_SLUG_OVERRIDES_KEY = "pg_pokemon_slug_overrides_v1";

export function readPokemonSlugOverrides() {
  try {
    const raw = window.localStorage.getItem(POKEMON_SLUG_OVERRIDES_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

export function writePokemonSlugOverrides(map) {
  try {
    window.localStorage.setItem(POKEMON_SLUG_OVERRIDES_KEY, JSON.stringify(map || {}));
  } catch {
    // Ignore persistence failures.
  }
}

export function getFlavorText(speciesData) {
  const entries = Array.isArray(speciesData?.flavor_text_entries) ? speciesData.flavor_text_entries : [];
  const english = entries.find((entry) => entry?.language?.name === "en");
  return String(english?.flavor_text || "").replace(/\f|\n|\r/g, " ").trim();
}

export function getBotKey(bot, idx) {
  return bot?.id || bot?.username || `bot-${idx}`;
}
