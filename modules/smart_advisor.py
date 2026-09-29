from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiohttp

logger = logging.getLogger("pokegrinder.smart_advisor")

BASE_DIR = Path(__file__).resolve().parents[1]
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

QUOTA_FILE = LOGS_DIR / "ai_quota.json"
INBOX_FILE = LOGS_DIR / "agent_inbox.jsonl"
SURVEILLANCE_FILE = LOGS_DIR / "ai_surveillance.jsonl"

_quota_lock = threading.RLock()


def _resolve_gemini_api_key(config: dict[str, Any]) -> str:
    """Resolve Gemini API key from environment, .env, or config.json."""
    env_key = os.getenv("GEMINI_API_KEY", "").strip()
    if env_key:
        return env_key

    # Check .env file directly if os.environ doesn't have it yet
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("GEMINI_API_KEY="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val:
                        return val
        except Exception:
            pass

    advisor_cfg = config.get("SmartAdvisor", {}) if isinstance(config, dict) else {}
    if isinstance(advisor_cfg, dict):
        cfg_key = str(advisor_cfg.get("ApiKey", "") or advisor_cfg.get("GeminiApiKey", "") or "").strip()
        if cfg_key:
            return cfg_key

    return ""


def _resolve_groq_api_key(config: dict[str, Any]) -> str:
    """Resolve Groq API key from environment, .env, or config.json."""
    env_key = os.getenv("GROQ_API_KEY", "").strip()
    if env_key:
        return env_key

    env_file = BASE_DIR / ".env"
    if env_file.exists():
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("GROQ_API_KEY="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val:
                        return val
        except Exception:
            pass

    advisor_cfg = config.get("SmartAdvisor", {}) if isinstance(config, dict) else {}
    if isinstance(advisor_cfg, dict):
        cfg_key = str(advisor_cfg.get("GroqApiKey", "") or "").strip()
        if cfg_key:
            return cfg_key

    return ""


def _resolve_api_key(config: dict[str, Any]) -> str:
    """Backwards-compatible alias for Gemini API key."""
    return _resolve_gemini_api_key(config)


class SmartAdvisor:
    """Intelligent fallback and surveillance engine backed by Gemini & Groq.
    
    Operates strictly as an emergency rescue mechanism:
    - 0 API calls during normal routine grinding.
    - Tiered multi-provider fallback: Gemini Flash-Lite -> Groq LPU engine.
    - Quota guarded: max 10 RPM sliding window, hard daily cap (default 400 RPD).
    - Multi-layer validation: AI cannot perform unauthorized actions or inject rogue commands.
    - Full telemetry: Every incident logged to logs/agent_inbox.jsonl for Antigravity code patching.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        advisor_cfg = self.config.get("SmartAdvisor", {}) if isinstance(self.config, dict) else {}
        self.enabled: bool = bool(advisor_cfg.get("Enabled", True))
        self.model: str = str(advisor_cfg.get("Model", "gemini-3.1-flash-lite"))
        self.fallback_model: str = str(advisor_cfg.get("FallbackModel", "gemini-3.5-flash-lite"))
        self.groq_model: str = str(advisor_cfg.get("GroqModel", "openai/gpt-oss-20b"))
        self.max_rpm: int = int(advisor_cfg.get("MaxRequestsPerMinute", 10))
        self.max_rpd: int = int(advisor_cfg.get("MaxRequestsPerDay", 400))
        self.timeout_seconds: float = float(advisor_cfg.get("TimeoutSeconds", 8.0))

        self.gemini_api_key: str = _resolve_gemini_api_key(self.config)
        self.groq_api_key: str = _resolve_groq_api_key(self.config)
        self.api_key: str = self.gemini_api_key  # backwards-compatible
        self._minute_window: deque[float] = deque()
        self._consecutive_errors: int = 0
        self._circuit_broken_until: float = 0.0

    def refresh_config(self, config: dict[str, Any]) -> None:
        self.config = config or {}
        advisor_cfg = self.config.get("SmartAdvisor", {}) if isinstance(self.config, dict) else {}
        self.enabled = bool(advisor_cfg.get("Enabled", True))
        self.model = str(advisor_cfg.get("Model", "gemini-3.1-flash-lite"))
        self.fallback_model = str(advisor_cfg.get("FallbackModel", "gemini-3.5-flash-lite"))
        self.groq_model = str(advisor_cfg.get("GroqModel", "openai/gpt-oss-20b"))
        self.max_rpm = int(advisor_cfg.get("MaxRequestsPerMinute", 10))
        self.max_rpd = int(advisor_cfg.get("MaxRequestsPerDay", 400))
        self.gemini_api_key = _resolve_gemini_api_key(self.config)
        self.groq_api_key = _resolve_groq_api_key(self.config)
        self.api_key = self.gemini_api_key

    def get_quota_status(self) -> dict[str, Any]:
        """Read and normalize current daily quota usage."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with _quota_lock:
            data = {"date": today, "requests_today": 0, "total_all_time": 0, "last_request_utc": ""}
            if QUOTA_FILE.exists():
                try:
                    loaded = json.loads(QUOTA_FILE.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        if loaded.get("date") == today:
                            data["requests_today"] = int(loaded.get("requests_today", 0) or 0)
                        data["total_all_time"] = int(loaded.get("total_all_time", 0) or 0)
                        data["last_request_utc"] = str(loaded.get("last_request_utc", ""))
                except Exception as exc:
                    logger.warning("Failed to read quota file: %s", exc)
            return data

    def _increment_quota(self) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        now_iso = datetime.now(timezone.utc).isoformat()
        with _quota_lock:
            status = self.get_quota_status()
            reqs = status["requests_today"] + 1 if status.get("date") == today else 1
            total = status.get("total_all_time", 0) + 1
            payload = {
                "date": today,
                "requests_today": reqs,
                "total_all_time": total,
                "last_request_utc": now_iso,
                "max_rpd_limit": self.max_rpd,
            }
            try:
                QUOTA_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            except Exception as exc:
                logger.warning("Failed to save quota file: %s", exc)

    def can_request(self) -> tuple[bool, str]:
        """Check if request is permitted under rate limit and daily quota."""
        if not self.enabled:
            return False, "SmartAdvisor is disabled in config."
        if not self.gemini_api_key and not self.groq_api_key:
            return False, "No AI API key configured (neither Gemini nor Groq)."

        now = time.time()
        if now < self._circuit_broken_until:
            wait_rem = int(self._circuit_broken_until - now)
            return False, f"Circuit breaker active. Cooldown remaining: {wait_rem}s."

        quota = self.get_quota_status()
        if quota["requests_today"] >= self.max_rpd:
            return False, f"Daily limit reached ({quota['requests_today']}/{self.max_rpd} RPD). Conserving quota."

        # Sliding minute window
        while self._minute_window and now - self._minute_window[0] > 60.0:
            self._minute_window.popleft()

        if len(self._minute_window) >= self.max_rpm:
            return False, f"Minute limit reached ({len(self._minute_window)}/{self.max_rpm} RPM). Throttling."

        return True, "OK"

    async def _post_gemini(self, model: str, prompt: str, system_prompt: str = "") -> dict[str, Any]:
        """Execute raw async POST to Gemini REST API endpoint."""
        if not self.gemini_api_key:
            return {"success": False, "error": "No Gemini API key available"}

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.gemini_api_key}"
        
        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"SYSTEM INSTRUCTIONS:\n{system_prompt}"}]})
            contents.append({"role": "model", "parts": [{"text": "Understood. I will strictly follow these instructions and reply in valid JSON."}]})
        
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.1,
            },
        }

        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self._consecutive_errors = 0
                        self._increment_quota()
                        self._minute_window.append(time.time())
                        
                        try:
                            text = data["candidates"][0]["content"]["parts"][0]["text"]
                            return {"success": True, "data": json.loads(text), "model_used": f"gemini:{model}"}
                        except Exception as parse_err:
                            return {"success": False, "error": f"JSON parse error: {parse_err}", "raw": data}
                    else:
                        err_body = await resp.text()
                        return {"success": False, "status": resp.status, "error": err_body}
        except asyncio.TimeoutError:
            return {"success": False, "error": f"Gemini request timed out after {self.timeout_seconds}s"}
        except Exception as exc:
            return {"success": False, "error": f"Gemini network error: {exc}"}

    async def _post_groq(self, model: str, prompt: str, system_prompt: str = "") -> dict[str, Any]:
        """Execute raw async POST to Groq OpenAI-compatible chat completions endpoint."""
        if not self.groq_api_key:
            return {"success": False, "error": "No Groq API key available"}

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json",
            "User-Agent": "PokeGrinder/1.0 (Windows NT 10.0; Win64; x64)",
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }

        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self._consecutive_errors = 0
                        self._increment_quota()
                        self._minute_window.append(time.time())

                        try:
                            choice = data["choices"][0]["message"]["content"]
                            return {"success": True, "data": json.loads(choice), "model_used": f"groq:{model}"}
                        except Exception as parse_err:
                            return {"success": False, "error": f"Groq JSON parse error: {parse_err}", "raw": data}
                    else:
                        err_body = await resp.text()
                        return {"success": False, "status": resp.status, "error": f"Groq HTTP {resp.status}: {err_body}"}
        except asyncio.TimeoutError:
            return {"success": False, "error": f"Groq request timed out after {self.timeout_seconds}s"}
        except Exception as exc:
            return {"success": False, "error": f"Groq network error: {exc}"}

    async def query_ai(self, prompt: str, system_prompt: str = "") -> dict[str, Any]:
        """Query AI models with tiered multi-provider fallback.
        
        Tier 1: Primary Gemini model (gemini-3.1-flash-lite)
        Tier 2: Gemini fallback model (gemini-3.5-flash-lite)
        Tier 3: Groq LPU engine (openai/gpt-oss-20b)
        """
        allowed, reason = self.can_request()
        if not allowed:
            return {"success": False, "error": reason, "skipped": True}

        last_error = ""

        # 1. Primary Gemini
        if self.gemini_api_key:
            res = await self._post_gemini(self.model, prompt, system_prompt)
            if res.get("success"):
                return res
            last_error = str(res.get("error", ""))
            logger.warning("Primary Gemini model %s failed: %s. Trying fallback %s", self.model, last_error, self.fallback_model)

            # 2. Fallback Gemini
            if self.fallback_model and self.fallback_model != self.model:
                fallback_res = await self._post_gemini(self.fallback_model, prompt, system_prompt)
                if fallback_res.get("success"):
                    return fallback_res
                last_error = str(fallback_res.get("error", ""))
                logger.warning("Fallback Gemini model %s failed: %s", self.fallback_model, last_error)

        # 3. Groq LPU Ultra-Fast Fallback (sub-100ms)
        if self.groq_api_key:
            logger.info("Engaging Groq fallback model (%s)...", self.groq_model)
            groq_res = await self._post_groq(self.groq_model, prompt, system_prompt)
            if groq_res.get("success"):
                logger.info("Groq query succeeded with model %s", self.groq_model)
                return groq_res
            last_error = str(groq_res.get("error", ""))
            logger.warning("Groq fallback model %s failed: %s", self.groq_model, last_error)

        self._consecutive_errors += 1
        if self._consecutive_errors >= 3:
            self._circuit_broken_until = time.time() + 300.0  # 5 min cooldown
            logger.error("SmartAdvisor circuit breaker tripped after 3 consecutive failures. Cooling down for 5m.")

        return {"success": False, "error": last_error or "All AI providers failed"}

    # =========================================================================
    # Specialized Edge-Case Handlers
    # =========================================================================

    async def advise_unhandled_interaction(
        self,
        message_data: dict[str, Any],
        available_buttons: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Decide what button to click when PokéMeow presents an unhandled modal/prompt."""
        system_prompt = (
            "You are an AI assistant monitoring a Pokémon Discord game bot (PokéMeow). "
            "PokéMeow displayed an interactive prompt that the bot's deterministic regex did not recognize. "
            "Your objective: Choose the safest, correct action to handle or dismiss the prompt. "
            "CRITICAL: If selecting an action, the 'target' MUST match one of the available button labels or custom_ids exactly. "
            "Output JSON with keys: 'action' ('CLICK_BUTTON' | 'DISMISS' | 'WAIT'), 'target' (matching button label), "
            "'reason' (1 short sentence), 'confidence' (0.0 to 1.0)."
        )

        prompt = (
            f"Message Content: {json.dumps(message_data.get('content', ''))}\n"
            f"Embed Titles: {json.dumps(message_data.get('embed_titles', []))}\n"
            f"Embed Descriptions: {json.dumps(message_data.get('embed_descriptions', []))}\n"
            f"Available Clickable Buttons: {json.dumps(available_buttons)}\n\n"
            "Which button should the bot click to safely proceed or dismiss?"
        )

        res = await self.query_ai(prompt, system_prompt)
        if not res.get("success"):
            return {"action": "NONE", "reason": res.get("error", "AI query failed")}

        data = res.get("data", {})
        target = str(data.get("target", "")).strip().lower()

        # Strict validator: ensure target matches an available button
        matched_button = None
        for btn in available_buttons:
            label = str(btn.get("label", "")).strip().lower()
            cid = str(btn.get("custom_id", "")).strip().lower()
            if target == label or target == cid or (target and (target in label or target in cid)):
                matched_button = btn
                break

        if matched_button:
            data["validated_button"] = matched_button
            self.record_incident(
                trigger="UNHANDLED_INTERACTION",
                context=message_data,
                ai_output=data,
                suggested_patch=f"Add pattern for embed '{message_data.get('embed_titles')}' -> click '{matched_button.get('label')}'",
            )
            return data

        return {"action": "NONE", "reason": f"Target '{target}' not found in active buttons."}

    async def advise_combat_action(
        self,
        boss_name: str,
        active_pokemon: str,
        ally_hp_percent: float,
        available_moves: list[str],
        available_switches: list[str],
        recent_log: str = "",
    ) -> dict[str, Any]:
        """Tactical combat fallback when hardcoded battle decider has no matching rule."""
        system_prompt = (
            "You are a competitive Pokémon combat tactician for PokéMeow battles. "
            "The hardcoded sequence encountered an unprogrammed board state. "
            "Pick the single best action among available moves or switches to maximize damage or survival. "
            "Output JSON with keys: 'type' ('move' | 'switch'), 'target' (name of move or switch Pokémon), 'reason'."
        )

        prompt = (
            f"Opponent: {boss_name}\n"
            f"Active Ally: {active_pokemon} (HP: {ally_hp_percent}%)\n"
            f"Available Moves: {json.dumps(available_moves)}\n"
            f"Available Switch Targets: {json.dumps(available_switches)}\n"
            f"Recent Battle Log: {recent_log}\n\n"
            "What is the best tactical move or switch?"
        )

        res = await self.query_ai(prompt, system_prompt)
        if not res.get("success"):
            return {"action": "NONE", "reason": res.get("error", "AI combat failed")}

        data = res.get("data", {})
        self.record_incident(
            trigger="COMBAT_DEADLOCK",
            context={"boss": boss_name, "active": active_pokemon, "hp": ally_hp_percent, "moves": available_moves, "switches": available_switches},
            ai_output=data,
            suggested_patch=f"Update strategy for {boss_name} vs {active_pokemon} to handle low HP / stalled turns.",
        )
        return data

    async def classify_new_quest(self, quest_text: str) -> dict[str, Any]:
        """Classify an unknown quest template into a structured catalog entry."""
        system_prompt = (
            "You are an expert on PokéMeow Discord bot quests. "
            "Classify the given quest description into a structured JSON configuration. "
            "Fields required:\n"
            "- 'id': unique lowercase snake_case identifier\n"
            "- 'category': 'catch' | 'fish' | 'battle' | 'release' | 'egg' | 'mega_chamber' | 'other'\n"
            "- 'is_impossible': boolean (true if Mega Chamber or impossible requirements)\n"
            "- 'action': 'auto_complete' | 'auto_reset' | 'manual'\n"
            "- 'battle_mode': null or NPC command identifier (e.g. 'npc 210' or 'master_challenger')\n"
            "- 'suggested_pattern': regex pattern string matching this quest"
        )

        prompt = f"Quest text: {quest_text}"
        res = await self.query_ai(prompt, system_prompt)
        if not res.get("success"):
            return {}

        data = res.get("data", {})
        self.record_incident(
            trigger="NEW_QUEST_LEARNED",
            context={"quest_text": quest_text},
            ai_output=data,
            suggested_patch=f"Registered new quest '{data.get('id')}' to quest_catalog.json",
        )
        return data

    async def diagnose_inactivity(
        self,
        recent_messages: list[dict[str, Any]],
        bot_locks: dict[str, Any],
    ) -> dict[str, Any]:
        """Diagnose why the bot stopped doing anything and prescribe an unblocking action."""
        system_prompt = (
            "You are a diagnostic engineer monitoring an automated Discord gaming bot that has stalled. "
            "Analyze the recent channel messages and current bot state locks. "
            "Determine what blocked the bot and prescribe the recovery action. "
            "Output JSON with keys:\n"
            "- 'diagnosis': brief explanation of why the bot stopped\n"
            "- 'action': 'RESET_LOCKS' | 'CLICK_BUTTON' | 'KICKSTART_COMMAND' | 'PAUSE_ALERT'\n"
            "- 'target': button label or command string (allowed commands: ';p', ';fish spawn', ';wb fight', ';quests')\n"
            "- 'reason': 1 sentence"
        )

        prompt = (
            f"Current Bot Locks: {json.dumps(bot_locks)}\n"
            f"Recent Messages in Channel:\n{json.dumps(recent_messages, indent=2)}\n\n"
            "Why is the bot inactive and how can it be safely restarted?"
        )

        res = await self.query_ai(prompt, system_prompt)
        if not res.get("success"):
            return {"action": "KICKSTART_COMMAND", "target": ";p", "reason": "AI unavailable, defaulting to pulse"}

        data = res.get("data", {})
        self.record_incident(
            trigger="WATCHDOG_INACTIVITY_DIAGNOSED",
            context={"bot_locks": bot_locks, "messages": recent_messages},
            ai_output=data,
            suggested_patch=f"Fix roadblock: {data.get('diagnosis')}",
        )
        return data

    # =========================================================================
    # Telemetry, Incident Logging, & Antigravity Surveillance Bridge
    # =========================================================================

    def record_incident(
        self,
        trigger: str,
        context: Any,
        ai_output: Any,
        suggested_patch: str = "",
        success: bool = True,
    ) -> None:
        """Record structured incident to both surveillance and agent inbox."""
        now_iso = datetime.now(timezone.utc).isoformat()
        entry = {
            "timestamp": now_iso,
            "trigger": trigger,
            "success": success,
            "context": context,
            "ai_output": ai_output,
            "suggested_patch": suggested_patch,
        }

        # 1. Full surveillance log (never expires)
        try:
            with open(SURVEILLANCE_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as exc:
            logger.warning("Failed writing surveillance log: %s", exc)

        # 2. Antigravity Agent Inbox (for agent to review and auto-fix code)
        try:
            with open(INBOX_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as exc:
            logger.warning("Failed writing agent inbox: %s", exc)

        print(f"[SmartAdvisor] Incident recorded: {trigger} -> {suggested_patch or 'Resolved'}")


# Global singleton instance
smart_advisor = SmartAdvisor()

