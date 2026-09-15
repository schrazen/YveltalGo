from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
import re

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException
from modules.anti_detect_log import (
    anti_detect_log_path,
    clear_anti_detect_events,
    get_anti_detect_events,
)
from modules.rare_catch_log import get_recent_rare_catch_events, rare_catch_log_path
from modules.retrieved_item_log import get_recent_retrieved_item_events, retrieved_item_log_path
from modules.autofight_log import (
    autofight_log_path,
    clear_autofight_events,
    get_autofight_events,
)

BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = BASE_DIR / "config.json"
STATS_PATH = BASE_DIR / "stats.json"
UI_DIST_PATH = Path(__file__).resolve().parent / "react-app" / "dist"
CAPTCHA_SAMPLES_DIR = BASE_DIR / "assets" / "captcha_samples"
AUTO_SOLVER_ATTEMPTS_PATH = CAPTCHA_SAMPLES_DIR / "auto_solver_attempts.jsonl"
AUTO_SOLVER_OUTCOMES_PATH = CAPTCHA_SAMPLES_DIR / "auto_solver_outcomes.jsonl"
FAILED_CAPTCHA_CANDIDATES_PATH = CAPTCHA_SAMPLES_DIR / "failed_captcha_candidates.jsonl"
TRAINING_LABELS_PATH = CAPTCHA_SAMPLES_DIR / "training_labels.jsonl"

app = Flask(
    __name__,
    template_folder=str(Path(__file__).resolve().parent / "templates"),
    static_folder=str(Path(__file__).resolve().parent / "static"),
)

_runtime_status_provider: Callable[[], dict[str, Any]] | None = None
_runtime_action_handler: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None
_diagnostics_provider: Callable[[], dict[str, Any]] | None = None


def configure_diagnostics_provider(fn: Callable[[], dict[str, Any]] | None) -> None:
    global _diagnostics_provider
    _diagnostics_provider = fn


# Bumped when API surface changes; check GET /api/health or response header X-PokeGrinder-Build.
SERVER_BUILD = "2026-04-01-pokegrinder-ui-3"


def get_runtime_diagnostics():
    if _diagnostics_provider is None:
        return jsonify(
            {
                "ok": False,
                "error": "Diagnostics only available when main.py is running (not ui.server alone).",
            }
        ), 503

    try:
        return jsonify(_diagnostics_provider())
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.get("/api/runtime/diagnostics")
def get_runtime_diagnostics_view():
    return get_runtime_diagnostics()


@app.get("/api/diagnostics")
def get_runtime_diagnostics_alias():
    """Shorter alias (same payload) — easier to verify which server is on :8787."""
    return get_runtime_diagnostics()


@app.after_request
def _pokegrinder_server_identity(response):
    response.headers["X-PokeGrinder-Build"] = SERVER_BUILD
    return response


def read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def is_account_config(value: Any) -> bool:
    return isinstance(value, dict) and "HuntingChannel" in value and "FishingChannel" in value


def get_accounts_container(config: dict[str, Any], create_if_missing: bool = False) -> dict[str, Any]:
    accounts = config.get("Accounts")
    if isinstance(accounts, dict):
        return accounts

    if create_if_missing:
        config["Accounts"] = {}
        return config["Accounts"]

    return config


def list_account_keys(config: dict[str, Any]) -> list[str]:
    accounts = get_accounts_container(config, create_if_missing=False)
    keys: list[str] = []
    for key, value in accounts.items():
        if is_account_config(value):
            keys.append(key)
    return keys


def _default_account_template(config: dict[str, Any]) -> dict[str, Any]:
    accounts = get_accounts_container(config, create_if_missing=False)

    # Prefer cloning the first existing account so per-repo conventions are preserved.
    for key in list_account_keys(config):
        value = accounts.get(key)
        if isinstance(value, dict):
            return json.loads(json.dumps(value))

    # Fallback baseline when no account exists yet.
    return {
        "AutoBuy": {"gb": 50, "mb": 1, "pb": 100, "ub": 5},
        "AutoHoldEgg": True,
        "AutoReleaseDuplicates": 100,
        "Balls": {
            "Common": "pb",
            "Uncommon": "pb",
            "Rare": "gb",
            "Super Rare": "ub",
            "Legendary": "mb",
            "Shiny": "mb",
            "Shiny Event": "mb",
            "Shiny Full-odds": "prb",
        },
        "Berry": {
            "Channel": int(((config.get("BerryDefaults", {}) or {}).get("Channel", 0) or 0)),
            "Enabled": bool(((config.get("BerryDefaults", {}) or {}).get("Enabled", True))),
        },
        "CaptchaAlerts": {
            "ChannelID": int(((config.get("CaptchaAlerts", {}) or {}).get("ChannelID", 0) or 0)),
            "CooldownSeconds": int(((config.get("CaptchaAlerts", {}) or {}).get("CooldownSeconds", 60) or 60)),
            "Enabled": bool(((config.get("CaptchaAlerts", {}) or {}).get("Enabled", False))),
            "Ping": str(((config.get("CaptchaAlerts", {}) or {}).get("Ping", ""))),
            "WebhookURL": str(((config.get("CaptchaAlerts", {}) or {}).get("WebhookURL", ""))),
        },
        "CaptchaAnswerer": {
            "AutoAnswerEnabled": bool(((config.get("CaptchaAnswerer", {}) or {}).get("AutoAnswerEnabled", True))),
            "MaxAutoAttempts": max(1, int(((config.get("CaptchaAnswerer", {}) or {}).get("MaxAutoAttempts", 3) or 3))),
            "ManualAnswerAllowedUserIDs": list(((config.get("CaptchaAnswerer", {}) or {}).get("ManualAnswerAllowedUserIDs", []))),
        },
        "CustomDelays": {
            "FishingDelayMax": None,
            "FishingDelayMin": None,
            "HuntingDelayMax": None,
            "HuntingDelayMin": None,
            "PostCatchDelayMax": None,
            "PostCatchDelayMin": None,
        },
        "EggHatching": True,
        "ExceptionBalls": {"Crystal Onix": "mb"},
        "FishBalls": {
            "Common": "pb",
            "Uncommon": "gb",
            "Rare": "ub",
            "Super Rare": "ub",
            "Legendary": "db",
            "Shiny": "mb",
            "Golden": "mb",
        },
        "FishingChannel": 0,
        "HuntingChannel": 0,
        "RequiredServerID": int((config.get("RequiredServerID", 0) or 0)),
    }


def _parse_positive_int(raw: Any, field_name: str) -> tuple[int | None, str | None]:
    value = str(raw or "").strip()
    if not value:
        return None, f"Missing required field: {field_name}."
    if not value.isdigit():
        return None, f"{field_name} must be digits only."
    parsed = int(value)
    if parsed <= 0:
        return None, f"{field_name} must be greater than 0."
    return parsed, None


def configure_runtime_handlers(
    status_provider: Callable[[], dict[str, Any]] | None,
    action_handler: Callable[[str, dict[str, Any]], dict[str, Any]] | None,
) -> None:
    global _runtime_status_provider, _runtime_action_handler
    _runtime_status_provider = status_provider
    _runtime_action_handler = action_handler


def _is_high_rarity_label(value: str) -> bool:
    lowered = str(value or "").lower()
    return any(token in lowered for token in ("legendary", "shiny", "mythical", "ultra", "event", "golden"))


def _normalize_pokemon_slug(name: str) -> str:
    value = str(name or "").strip().lower()
    value = re.sub(r"[^a-z0-9\s\-]", "", value)
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value


def _pokemon_sprite_url(name: str, slug: str) -> str:
    safe_slug = _normalize_pokemon_slug(slug or name)
    if not safe_slug:
        return ""
    return f"https://img.pokemondb.net/sprites/home/normal/{safe_slug}.png"


def _normalize_item_slug(name: str) -> str:
    value = str(name or "").strip().lower()
    value = re.sub(r"[^a-z0-9\s\-]", "", value)
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")

    aliases = {
        "rarecandy": "rare-candy",
        "relic-vase": "relic-vase",
        "duskball": "dusk-ball",
        "greatball": "great-ball",
        "masterball": "master-ball",
        "ultraball": "ultra-ball",
        "premierball": "premier-ball",
        "quickball": "quick-ball",
        "moonball": "moon-ball",
        "heavyball": "heavy-ball",
        "fastball": "fast-ball",
        "friendball": "friend-ball",
        "pokeball": "poke-ball",
    }
    return aliases.get(value, value)


def _item_icon_emoji(item_name: str) -> str:
    lowered = str(item_name or "").strip().lower().replace(" ", "")
    mapping = {
        "nugget": "🪙",
        "pearl": "🦪",
        "rarecandy": "🍬",
        "relicvase": "🏺",
        "duskball": "⚫",
        "greatball": "🔵",
        "ultraball": "🟡",
        "masterball": "🟣",
        "pokeball": "⚪",
    }
    return mapping.get(lowered, "🎁")


def _item_sprite_url(item_name: str, item_slug: str) -> str:
    safe_slug = _normalize_item_slug(item_slug or item_name)
    if not safe_slug:
        return ""
    return f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/{safe_slug}.png"


def _stringify_for_search(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple, set)):
        try:
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        except Exception:
            return str(value)
    return str(value)


def _matches_search_query(query: str, *parts: Any) -> bool:
    needle = str(query or "").strip().lower()
    if not needle:
        return True

    haystack = " ".join(_stringify_for_search(part) for part in parts).lower()
    return needle in haystack


def _read_jsonl_rows(path: Path, limit: int = 100) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []

    rows: list[dict[str, Any]] = []
    for raw in reversed(lines):
        text = str(raw or "").strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
        if len(rows) >= limit:
            break

    return rows


@app.get("/api/captcha/image")
def get_captcha_image():
    relative_path = str(request.args.get("path", "") or "").strip().replace("\\", "/")
    if not relative_path:
        return jsonify({"ok": False, "error": "Missing path"}), 400

    requested = Path(relative_path)
    # Only allow image files under assets/captcha_samples/images.
    allowed_root = (CAPTCHA_SAMPLES_DIR / "images").resolve()
    candidate = (BASE_DIR / requested).resolve()
    if allowed_root not in candidate.parents:
        return jsonify({"ok": False, "error": "Forbidden path"}), 403
    if candidate.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}:
        return jsonify({"ok": False, "error": "Unsupported file type"}), 400
    if not candidate.exists() or not candidate.is_file():
        return jsonify({"ok": False, "error": "Image not found"}), 404

    return send_from_directory(str(candidate.parent), candidate.name)


@app.get("/")
def index():
    if (UI_DIST_PATH / "index.html").exists():
        return send_from_directory(str(UI_DIST_PATH), "index.html")

    return jsonify(
        {
            "ok": True,
            "message": "YveltalGo backend is API-only. Use YveltalGo UI.",
            "react_dev_url": "http://127.0.0.1:5173",
            "api_base": "/api",
        }
    )


@app.get("/api/health")
def health():
    return jsonify(
        {
            "ok": True,
            "time": datetime.now(timezone.utc).isoformat(),
            "server_build": SERVER_BUILD,
        }
    )


@app.get("/favicon.ico")
def favicon():
    return ("", 204)


@app.get("/assets/<path:asset_path>")
def serve_dist_assets(asset_path: str):
    """Vite build output; do not use a catch-all /path — it can shadow /api/* in Werkzeug."""
    if not UI_DIST_PATH.exists():
        return jsonify({"ok": False, "error": "UI build not found"}), 404
    assets_root = (UI_DIST_PATH / "assets").resolve()
    if not assets_root.is_dir():
        return jsonify({"ok": False, "error": "UI assets folder missing"}), 404
    try:
        candidate = (assets_root / asset_path).resolve()
    except OSError:
        return jsonify({"ok": False, "error": "Invalid path"}), 400
    if candidate != assets_root and assets_root not in candidate.parents:
        return jsonify({"ok": False, "error": "Forbidden"}), 403
    if not candidate.is_file():
        return jsonify({"ok": False, "error": "Not found"}), 404
    rel = candidate.relative_to(assets_root)
    return send_from_directory(str(assets_root), rel.as_posix())


@app.get("/api/config")
def get_config():
    raw_text = "{}"
    if CONFIG_PATH.exists():
        try:
            raw_text = CONFIG_PATH.read_text(encoding="utf-8")
        except Exception:
            raw_text = "{}"

    config = read_json(CONFIG_PATH, {})
    return jsonify(
        {
            "config": config,
            "config_text": raw_text if str(raw_text).strip() else "{}",
            "accounts": list_account_keys(config),
            "path": str(CONFIG_PATH),
        }
    )


@app.post("/api/config")
def save_config():
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"ok": False, "error": "Missing config payload."}), 400

    if "config_text" in payload:
        config_text = payload.get("config_text")
        if not isinstance(config_text, str):
            return jsonify({"ok": False, "error": "config_text must be a JSON string."}), 400

        try:
            parsed = json.loads(config_text)
        except Exception as exc:
            return jsonify({"ok": False, "error": f"Invalid JSON: {exc}"}), 400

        if not isinstance(parsed, dict):
            return jsonify({"ok": False, "error": "Config root must be a JSON object."}), 400

        try:
            CONFIG_PATH.write_text(config_text, encoding="utf-8")
            return jsonify({"ok": True})
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500

    if "config" not in payload:
        return jsonify({"ok": False, "error": "Missing config payload."}), 400

    config = payload["config"]
    if not isinstance(config, dict):
        return jsonify({"ok": False, "error": "Config must be a JSON object."}), 400

    try:
        write_json(CONFIG_PATH, config)
        return jsonify({"ok": True})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.post("/api/config/format")
def format_config_text():
    payload = request.get_json(silent=True) or {}
    config_text = payload.get("config_text", "")
    if not isinstance(config_text, str):
        return jsonify({"ok": False, "error": "config_text must be a JSON string."}), 400

    try:
        parsed = json.loads(config_text)
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Invalid JSON: {exc}"}), 400

    if not isinstance(parsed, dict):
        return jsonify({"ok": False, "error": "Config root must be a JSON object."}), 400

    formatted = json.dumps(parsed, indent=2, ensure_ascii=False)
    return jsonify({"ok": True, "config_text": formatted})


@app.post("/api/config/add-account")
def add_account_to_config():
    payload = request.get_json(silent=True) or {}
    token = str(payload.get("token", "") or "").strip()
    hunting_raw = payload.get("hunting_channel_id", "")
    fishing_raw = payload.get("fishing_channel_id", "")
    berry_raw = payload.get("berry_channel_id", "")
    required_server_raw = payload.get("required_server_id", "")
    captcha_auto_answer_enabled_raw = payload.get("captcha_auto_answer_enabled", None)
    captcha_max_auto_attempts_raw = payload.get("captcha_max_auto_attempts", "")
    captcha_manual_allowed_user_ids_raw = payload.get("captcha_manual_allowed_user_ids", None)
    captcha_alerts_enabled_raw = payload.get("captcha_alerts_enabled", None)
    captcha_alert_ping_raw = payload.get("captcha_alert_ping", None)
    captcha_alert_webhook_url_raw = payload.get("captcha_alert_webhook_url", None)
    captcha_alert_channel_id_raw = payload.get("captcha_alert_channel_id", "")
    captcha_alert_cooldown_seconds_raw = payload.get("captcha_alert_cooldown_seconds", "")

    if not token:
        return jsonify({"ok": False, "error": "Token is required."}), 400

    hunting_id, err = _parse_positive_int(hunting_raw, "HuntingChannel")
    if err:
        return jsonify({"ok": False, "error": err}), 400

    fishing_id, err = _parse_positive_int(fishing_raw, "FishingChannel")
    if err:
        return jsonify({"ok": False, "error": err}), 400

    berry_id: int | None = None
    berry_text = str(berry_raw or "").strip()
    if berry_text:
        berry_id, err = _parse_positive_int(berry_text, "Berry.Channel")
        if err:
            return jsonify({"ok": False, "error": err}), 400

    required_server_id: int | None = None
    required_server_text = str(required_server_raw or "").strip()
    if required_server_text:
        required_server_id, err = _parse_positive_int(required_server_text, "RequiredServerID")
        if err:
            return jsonify({"ok": False, "error": err}), 400

    captcha_max_auto_attempts: int | None = None
    captcha_max_auto_attempts_text = str(captcha_max_auto_attempts_raw or "").strip()
    if captcha_max_auto_attempts_text:
        if not captcha_max_auto_attempts_text.isdigit() or int(captcha_max_auto_attempts_text) <= 0:
            return jsonify({"ok": False, "error": "captcha_max_auto_attempts must be a positive integer."}), 400
        captcha_max_auto_attempts = int(captcha_max_auto_attempts_text)

    captcha_alert_cooldown_seconds: int | None = None
    captcha_alert_cooldown_seconds_text = str(captcha_alert_cooldown_seconds_raw or "").strip()
    if captcha_alert_cooldown_seconds_text:
        if not captcha_alert_cooldown_seconds_text.isdigit() or int(captcha_alert_cooldown_seconds_text) < 0:
            return jsonify({"ok": False, "error": "captcha_alert_cooldown_seconds must be 0 or a positive integer."}), 400
        captcha_alert_cooldown_seconds = int(captcha_alert_cooldown_seconds_text)

    captcha_alert_channel_id: int | None = None
    captcha_alert_channel_id_text = str(captcha_alert_channel_id_raw or "").strip()
    if captcha_alert_channel_id_text:
        if not captcha_alert_channel_id_text.isdigit() or int(captcha_alert_channel_id_text) <= 0:
            return jsonify({"ok": False, "error": "captcha_alert_channel_id must be a positive integer."}), 400
        captcha_alert_channel_id = int(captcha_alert_channel_id_text)

    captcha_manual_allowed_user_ids: list[int] | None = None
    if captcha_manual_allowed_user_ids_raw is not None:
        if isinstance(captcha_manual_allowed_user_ids_raw, list):
            raw_values = [str(v).strip() for v in captcha_manual_allowed_user_ids_raw]
        else:
            raw_values = [part.strip() for part in str(captcha_manual_allowed_user_ids_raw).split(",")]

        parsed_ids: list[int] = []
        for value in raw_values:
            if not value:
                continue
            if not value.isdigit() or int(value) <= 0:
                return jsonify({"ok": False, "error": "captcha_manual_allowed_user_ids must contain comma-separated numeric Discord user IDs."}), 400
            parsed_ids.append(int(value))

        # Keep order while removing duplicates.
        seen: set[int] = set()
        captcha_manual_allowed_user_ids = [
            uid for uid in parsed_ids if not (uid in seen or seen.add(uid))
        ]

    config = read_json(CONFIG_PATH, {})
    if not isinstance(config, dict):
        return jsonify({"ok": False, "error": "Invalid config structure on disk."}), 500

    accounts = get_accounts_container(config, create_if_missing=True)
    if not isinstance(accounts, dict):
        return jsonify({"ok": False, "error": "Invalid Accounts structure in config."}), 500

    legacy_entry = config.get(token)
    if token in accounts or (isinstance(legacy_entry, dict) and is_account_config(legacy_entry)):
        return jsonify({"ok": False, "error": "This token already exists in config."}), 400

    template = _default_account_template(config)
    template["HuntingChannel"] = int(hunting_id)
    template["FishingChannel"] = int(fishing_id)

    berry_cfg = template.get("Berry") if isinstance(template.get("Berry"), dict) else {"Enabled": True, "Channel": 0}
    if berry_id is not None:
        berry_cfg["Channel"] = int(berry_id)
        berry_cfg["Enabled"] = True
    template["Berry"] = berry_cfg

    if required_server_id is not None:
        template["RequiredServerID"] = int(required_server_id)

    if captcha_auto_answer_enabled_raw is not None:
        if isinstance(captcha_auto_answer_enabled_raw, bool):
            enabled_value = captcha_auto_answer_enabled_raw
        else:
            enabled_value = str(captcha_auto_answer_enabled_raw).strip().lower() in ("1", "true", "yes", "on")
        captcha_answerer_cfg = template.get("CaptchaAnswerer") if isinstance(template.get("CaptchaAnswerer"), dict) else {}
        captcha_answerer_cfg["AutoAnswerEnabled"] = bool(enabled_value)
        template["CaptchaAnswerer"] = captcha_answerer_cfg

    if captcha_max_auto_attempts is not None:
        captcha_answerer_cfg = template.get("CaptchaAnswerer") if isinstance(template.get("CaptchaAnswerer"), dict) else {}
        captcha_answerer_cfg["MaxAutoAttempts"] = int(captcha_max_auto_attempts)
        template["CaptchaAnswerer"] = captcha_answerer_cfg

    if captcha_manual_allowed_user_ids is not None:
        captcha_answerer_cfg = template.get("CaptchaAnswerer") if isinstance(template.get("CaptchaAnswerer"), dict) else {}
        captcha_answerer_cfg["ManualAnswerAllowedUserIDs"] = captcha_manual_allowed_user_ids
        template["CaptchaAnswerer"] = captcha_answerer_cfg

    if captcha_alerts_enabled_raw is not None:
        if isinstance(captcha_alerts_enabled_raw, bool):
            alerts_enabled_value = captcha_alerts_enabled_raw
        else:
            alerts_enabled_value = str(captcha_alerts_enabled_raw).strip().lower() in ("1", "true", "yes", "on")
        captcha_alerts_cfg = template.get("CaptchaAlerts") if isinstance(template.get("CaptchaAlerts"), dict) else {}
        captcha_alerts_cfg["Enabled"] = bool(alerts_enabled_value)
        template["CaptchaAlerts"] = captcha_alerts_cfg

    if captcha_alert_ping_raw is not None:
        captcha_alerts_cfg = template.get("CaptchaAlerts") if isinstance(template.get("CaptchaAlerts"), dict) else {}
        captcha_alerts_cfg["Ping"] = str(captcha_alert_ping_raw or "")
        template["CaptchaAlerts"] = captcha_alerts_cfg

    if captcha_alert_webhook_url_raw is not None:
        captcha_alerts_cfg = template.get("CaptchaAlerts") if isinstance(template.get("CaptchaAlerts"), dict) else {}
        captcha_alerts_cfg["WebhookURL"] = str(captcha_alert_webhook_url_raw or "")
        template["CaptchaAlerts"] = captcha_alerts_cfg

    if captcha_alert_channel_id is not None:
        captcha_alerts_cfg = template.get("CaptchaAlerts") if isinstance(template.get("CaptchaAlerts"), dict) else {}
        captcha_alerts_cfg["ChannelID"] = int(captcha_alert_channel_id)
        template["CaptchaAlerts"] = captcha_alerts_cfg

    if captcha_alert_cooldown_seconds is not None:
        captcha_alerts_cfg = template.get("CaptchaAlerts") if isinstance(template.get("CaptchaAlerts"), dict) else {}
        captcha_alerts_cfg["CooldownSeconds"] = int(captcha_alert_cooldown_seconds)
        template["CaptchaAlerts"] = captcha_alerts_cfg

    accounts[token] = template

    try:
        write_json(CONFIG_PATH, config)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500

    try:
        raw_text = CONFIG_PATH.read_text(encoding="utf-8")
    except Exception:
        raw_text = json.dumps(config, indent=2, ensure_ascii=False)

    return jsonify({
        "ok": True,
        "message": "Account added to config.",
        "config_text": raw_text,
        "path": str(CONFIG_PATH),
    })


@app.get("/api/stats")
def get_stats():
    stats = read_json(STATS_PATH, {})
    return jsonify(
        {
            "stats": stats,
            "path": str(STATS_PATH),
            "updated": datetime.now(timezone.utc).isoformat(),
        }
    )


@app.get("/api/runtime/status")
def get_runtime_status():
    if _runtime_status_provider is None:
        return jsonify(
            {
                "available": False,
                "message": "Runtime control is not attached to this process.",
            }
        )

    try:
        return jsonify({"available": True, "data": _runtime_status_provider()})
    except Exception as exc:
        return jsonify({"available": False, "message": str(exc)}), 500


@app.get("/api/telemetry/anti-detect")
def get_anti_detect_telemetry():
    limit_raw = request.args.get("limit", "200")
    query = str(request.args.get("q", "") or "").strip()
    try:
        limit = int(limit_raw)
    except ValueError:
        limit = 200

    limit = max(1, min(limit, 2000))

    scan_limit = max(limit * 10, 1000) if query else limit
    events = get_anti_detect_events(limit=scan_limit)

    if query:
        matched = [
            event
            for event in events
            if _matches_search_query(
                query,
                event.get("ts"),
                event.get("account"),
                event.get("module"),
                event.get("event"),
                event.get("channel_id"),
                event.get("details"),
            )
        ]
        events = matched[:limit]
        matched_count = len(matched)
    else:
        matched_count = len(events)

    return jsonify(
        {
            "ok": True,
            "count": len(events),
            "matched_count": matched_count,
            "query": query,
            "log_path": anti_detect_log_path(),
            "events": events,
        }
    )


@app.post("/api/telemetry/anti-detect/clear")
def clear_anti_detect_telemetry():
    payload = request.get_json(silent=True) or {}
    truncate_file = bool(payload.get("truncate_file", False))
    clear_anti_detect_events(truncate_file=truncate_file)
    return jsonify({"ok": True, "message": "Anti-detect telemetry cleared."})


@app.get("/api/telemetry/autofight")
def get_autofight_telemetry():
    limit_raw = request.args.get("limit", "250")
    query = str(request.args.get("q", "") or "").strip().lower()

    try:
        limit = max(1, min(int(limit_raw), 2000))
    except ValueError:
        limit = 250

    events = get_autofight_events(limit=limit)
    if query:
        matched: list[dict[str, Any]] = []
        for event in events:
            haystack = " ".join(
                [
                    str(event.get("event", "") or ""),
                    str(event.get("account", "") or ""),
                    str(event.get("channel_id", "") or ""),
                    json.dumps(event.get("details", {}), ensure_ascii=False),
                ]
            ).lower()
            if query in haystack:
                matched.append(event)
        events = matched

    return jsonify(
        {
            "ok": True,
            "count": len(events),
            "limit": limit,
            "query": query,
            "log_path": autofight_log_path(),
            "events": events,
        }
    )


@app.post("/api/telemetry/autofight/clear")
def clear_autofight_telemetry():
    payload = request.get_json(silent=True) or {}
    truncate_file = bool(payload.get("truncate_file", False))
    clear_autofight_events(truncate_file=truncate_file)
    return jsonify({"ok": True, "message": "AutoFight telemetry cleared."})


@app.get("/api/telemetry/recent-rare-catches")
def get_recent_rare_catches():
    limit_raw = request.args.get("limit", "12")
    hours_raw = request.args.get("hours", "24")

    try:
        limit = max(1, min(int(limit_raw), 50))
    except ValueError:
        limit = 12

    try:
        hours = max(1, min(int(hours_raw), 168))
    except ValueError:
        hours = 24

    cutoff = datetime.now(timezone.utc).timestamp() - (hours * 3600)
    events = get_recent_rare_catch_events(limit=max(limit * 40, 1000))

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for event in events:
        rarity = str(event.get("rarity", "Unknown"))
        if not _is_high_rarity_label(rarity):
            continue

        ts_raw = str(event.get("ts", "") or "")
        try:
            ts_epoch = datetime.fromisoformat(ts_raw).timestamp()
        except Exception:
            continue
        if ts_epoch < cutoff:
            continue

        pokemon_name = str(event.get("pokemon_name", "") or "").strip() or "Unknown"
        pokemon_slug = str(event.get("pokemon_slug", "") or "").strip()
        if pokemon_name == "Unknown" and not pokemon_slug:
            continue

        account = str(event.get("account", "") or "unknown")
        dedupe_key = (ts_raw, account, pokemon_name)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        rows.append(
            {
                "ts": ts_raw,
                "account": account,
                "channel_id": int(event.get("channel_id", 0) or 0),
                "rarity": rarity,
                "pokemon_name": pokemon_name,
                "pokemon_slug": pokemon_slug or _normalize_pokemon_slug(pokemon_name),
                "sprite": _pokemon_sprite_url(pokemon_name, pokemon_slug),
            }
        )

        if len(rows) >= limit:
            break

    if len(rows) < limit:
        fallback_events = get_anti_detect_events(limit=2000)
        for event in fallback_events:
            if str(event.get("module", "")).lower() != "hunting":
                continue
            if str(event.get("event", "")).lower() != "catch":
                continue

            details = event.get("details") if isinstance(event.get("details"), dict) else {}
            rarity = str(details.get("rarity", "Unknown"))
            if not _is_high_rarity_label(rarity):
                continue

            ts_raw = str(event.get("ts", "") or "")
            try:
                ts_epoch = datetime.fromisoformat(ts_raw).timestamp()
            except Exception:
                continue
            if ts_epoch < cutoff:
                continue

            pokemon_name = str(details.get("pokemon_name", "") or "").strip() or "Unknown"
            pokemon_slug = str(details.get("pokemon_slug", "") or "").strip()
            if pokemon_name == "Unknown" and not pokemon_slug:
                continue

            account = str(event.get("account", "") or "unknown")
            dedupe_key = (ts_raw, account, pokemon_name)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            rows.append(
                {
                    "ts": ts_raw,
                    "account": account,
                    "channel_id": int(event.get("channel_id", 0) or 0),
                    "rarity": rarity,
                    "pokemon_name": pokemon_name,
                    "pokemon_slug": pokemon_slug or _normalize_pokemon_slug(pokemon_name),
                    "sprite": _pokemon_sprite_url(pokemon_name, pokemon_slug),
                }
            )

            if len(rows) >= limit:
                break

    if len(rows) == 0:
        latest_events = get_recent_rare_catch_events(limit=limit)
        for event in latest_events:
            rarity = str(event.get("rarity", "Unknown"))
            if not _is_high_rarity_label(rarity):
                continue

            ts_raw = str(event.get("ts", "") or "")
            pokemon_name = str(event.get("pokemon_name", "") or "").strip() or "Unknown"
            pokemon_slug = str(event.get("pokemon_slug", "") or "").strip()
            if pokemon_name == "Unknown" and not pokemon_slug:
                continue

            account = str(event.get("account", "") or "unknown")
            dedupe_key = (ts_raw, account, pokemon_name)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            rows.append(
                {
                    "ts": ts_raw,
                    "account": account,
                    "channel_id": int(event.get("channel_id", 0) or 0),
                    "rarity": rarity,
                    "pokemon_name": pokemon_name,
                    "pokemon_slug": pokemon_slug or _normalize_pokemon_slug(pokemon_name),
                    "sprite": _pokemon_sprite_url(pokemon_name, pokemon_slug),
                }
            )

            if len(rows) >= limit:
                break

    return jsonify(
        {
            "ok": True,
            "count": len(rows),
            "hours": hours,
            "limit": limit,
            "rare_log_path": rare_catch_log_path(),
            "rows": rows,
        }
    )


@app.get("/api/telemetry/recent-item-retrieves")
def get_recent_item_retrieves():
    limit_raw = request.args.get("limit", "12")
    hours_raw = request.args.get("hours", "24")

    try:
        limit = max(1, min(int(limit_raw), 60))
    except ValueError:
        limit = 12

    try:
        hours = max(1, min(int(hours_raw), 168))
    except ValueError:
        hours = 24

    cutoff = datetime.now(timezone.utc).timestamp() - (hours * 3600)
    events = get_recent_retrieved_item_events(limit=max(limit * 40, 1000))

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()

    for event in events:
        ts_raw = str(event.get("ts", "") or "")
        try:
            ts_epoch = datetime.fromisoformat(ts_raw).timestamp()
        except Exception:
            continue
        if ts_epoch < cutoff:
            continue

        item_name = str(event.get("item_name", "") or "").strip()
        item_slug = str(event.get("item_slug", "") or "").strip()
        pokemon_name = str(event.get("pokemon_name", "") or "Unknown").strip() or "Unknown"
        pokemon_slug = str(event.get("pokemon_slug", "") or "").strip()
        rarity = str(event.get("rarity", "Unknown") or "Unknown")
        account = str(event.get("account", "") or "unknown")
        if not item_name:
            continue

        dedupe_key = (ts_raw, account, pokemon_name, item_name)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        rows.append(
            {
                "ts": ts_raw,
                "account": account,
                "channel_id": int(event.get("channel_id", 0) or 0),
                "rarity": rarity,
                "pokemon_name": pokemon_name,
                "pokemon_slug": pokemon_slug or _normalize_pokemon_slug(pokemon_name),
                "pokemon_sprite": _pokemon_sprite_url(pokemon_name, pokemon_slug),
                "item_name": item_name,
                "item_slug": _normalize_item_slug(item_slug or item_name),
                "item_icon_emoji": _item_icon_emoji(item_name),
                "item_sprite": _item_sprite_url(item_name, item_slug),
            }
        )

        if len(rows) >= limit:
            break

    return jsonify(
        {
            "ok": True,
            "count": len(rows),
            "hours": hours,
            "limit": limit,
            "retrieved_item_log_path": retrieved_item_log_path(),
            "rows": rows,
        }
    )


@app.get("/api/telemetry/captcha")
def get_captcha_telemetry():
    limit_raw = request.args.get("limit", "60")
    query = str(request.args.get("q", "") or "").strip()

    try:
        limit = max(1, min(int(limit_raw), 300))
    except ValueError:
        limit = 60

    attempts = _read_jsonl_rows(AUTO_SOLVER_ATTEMPTS_PATH, limit=limit)
    outcomes = _read_jsonl_rows(AUTO_SOLVER_OUTCOMES_PATH, limit=limit)
    failed_candidates = _read_jsonl_rows(FAILED_CAPTCHA_CANDIDATES_PATH, limit=limit)
    labels = _read_jsonl_rows(TRAINING_LABELS_PATH, limit=limit)

    if query:
        attempts = [row for row in attempts if _matches_search_query(query, row)]
        outcomes = [row for row in outcomes if _matches_search_query(query, row)]
        failed_candidates = [row for row in failed_candidates if _matches_search_query(query, row)]
        labels = [row for row in labels if _matches_search_query(query, row)]

    resolved_outcomes = [
        row
        for row in outcomes
        if str(row.get("outcome", "") or "").strip().lower() == "resolved"
    ]

    return jsonify(
        {
            "ok": True,
            "limit": limit,
            "query": query,
            "counts": {
                "attempts": len(attempts),
                "outcomes": len(outcomes),
                "resolved_outcomes": len(resolved_outcomes),
                "failed_candidates": len(failed_candidates),
                "labels": len(labels),
            },
            "paths": {
                "attempts": str(AUTO_SOLVER_ATTEMPTS_PATH),
                "outcomes": str(AUTO_SOLVER_OUTCOMES_PATH),
                "failed_candidates": str(FAILED_CAPTCHA_CANDIDATES_PATH),
                "labels": str(TRAINING_LABELS_PATH),
            },
            "attempts": attempts,
            "outcomes": outcomes,
            "failed_candidates": failed_candidates,
            "labels": labels,
        }
    )


@app.post("/api/runtime/action")
def runtime_action():
    if _runtime_action_handler is None:
        return jsonify({"ok": False, "error": "Runtime action handler unavailable."}), 400

    payload = request.get_json(silent=True) or {}
    action = str(payload.get("action", "")).strip().lower()
    if not action:
        return jsonify({"ok": False, "error": "Missing action."}), 400

    try:
        result = _runtime_action_handler(action, payload)
        return jsonify({"ok": bool(result.get("ok", False)), **result})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


def run_dashboard(host: str = "127.0.0.1", port: int = 8787) -> None:
    import logging
    import sys
    import traceback

    for name in ("werkzeug", "werkzeug.serving"):
        logging.getLogger(name).setLevel(logging.ERROR)

    print(
        f"[Flask] binding http://{host}:{port} build={SERVER_BUILD}",
        file=sys.stderr,
        flush=True,
    )
    print(f"[Flask] ui.server loaded from {__file__}", file=sys.stderr, flush=True)

    try:
        app.run(host=host, port=port, debug=False, use_reloader=False)
    except OSError as exc:
        print(
            f"[Flask] FAILED to bind {host}:{port} (another process may already use this port): {exc}",
            file=sys.stderr,
            flush=True,
        )
        traceback.print_exc()
        raise


@app.errorhandler(404)
def handle_not_found(err: HTTPException):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": f"Unknown API route: {request.path}"}), 404
    return err


@app.errorhandler(500)
def handle_server_error(err: HTTPException):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "Internal server error"}), 500
    return err


if __name__ == "__main__":
    run_dashboard()
