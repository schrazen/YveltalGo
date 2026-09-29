import asyncio
import re
import json
import hashlib
from urllib.parse import urlparse
from datetime import datetime, timezone
from pathlib import Path
from time import time
from random import randint
import os
import requests
from discord import Message
from discord.ext import commands

from cogs.startup import Config
from modules.captcha_solver import solve_captcha
from modules.anti_detect_log import record_anti_detect_event


BASE_DIR = Path(__file__).resolve().parents[1]
CAPTCHA_SAMPLES_DIR = BASE_DIR / "assets" / "captcha_samples"
CAPTCHA_IMAGES_DIR = CAPTCHA_SAMPLES_DIR / "images"
AUTO_SOLVER_ATTEMPTS_PATH = CAPTCHA_SAMPLES_DIR / "auto_solver_attempts.jsonl"
AUTO_SOLVER_OUTCOMES_PATH = CAPTCHA_SAMPLES_DIR / "auto_solver_outcomes.jsonl"
FAILED_CAPTCHA_CANDIDATES_PATH = CAPTCHA_SAMPLES_DIR / "failed_captcha_candidates.jsonl"
TRAINING_LABELS_PATH = CAPTCHA_SAMPLES_DIR / "training_labels.jsonl"
TRAINING_DATASET_PATH = CAPTCHA_SAMPLES_DIR / "training_dataset.jsonl"
POKEMEOW_APP_ID = 664508672713424926
CAPTCHA_DIGIT_MIN_LENGTH = 3
CAPTCHA_DIGIT_MAX_LENGTH = 6
CAPTCHA_MANUAL_MAX_ATTEMPTS = 2
CAPTCHA_TOTAL_MAX_ATTEMPTS = 5
CAPTCHA_TIMEOUT_SECONDS = 90


class Captcha(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config: Config = bot.config
        self.last_alert_at = 0.0
        self.reminder_task: asyncio.Task | None = None
        self.last_captcha_message: Message | None = None
        self.max_auto_attempts = max(1, int(getattr(self.config, "captcha_auto_max_attempts", 3) or 3))
        self.channel_attempt_state: dict[int, dict[str, object]] = {}
        self.channel_attempt_locks: dict[int, asyncio.Lock] = {}
        self._captcha_runtime_snapshot: dict[str, object] | None = None

    def _build_channel_state_snapshot(self, channel_id: int, active: bool) -> dict[str, object]:
        state = self.channel_attempt_state.get(int(channel_id), {})
        jump_url = ""
        if self.last_captcha_message is not None and int(getattr(self.last_captcha_message.channel, "id", 0) or 0) == int(channel_id):
            jump_url = str(getattr(self.last_captcha_message, "jump_url", "") or "")

        return {
            "channel_id": int(channel_id),
            "active": bool(active),
            "attempts": int(state.get("attempts", 0) or 0),
            "last_detected_utc": float(state.get("last_detected_utc", state.get("detected_at", 0.0)) or 0.0),
            "detected_utc": float(state.get("detected_at", 0.0) or 0.0),
            "warned_manual": bool(state.get("warned_manual", False)),
            "last_prediction": str(state.get("last_prediction", "") or ""),
            "last_image_url": str(state.get("last_image_url", "") or ""),
            "last_image_path": str(state.get("last_image_path", "") or ""),
            "last_manual_answer": str(state.get("last_manual_answer", "") or ""),
            "captcha_message_id": int(state.get("captcha_message_id", 0) or 0),
            "jump_url": jump_url,
        }

    def get_live_state_snapshot(self) -> dict[str, object]:
        hunting_active = bool(getattr(self.bot, "hunting_captcha_active", False))
        fishing_active = bool(getattr(self.bot, "fishing_captcha_active", False))
        autofight_active = bool(getattr(self.bot, "autofight_captcha_active", False))

        hunting = self._build_channel_state_snapshot(int(getattr(self.config, "hunting_channel_id", 0) or 0), hunting_active)
        fishing = self._build_channel_state_snapshot(int(getattr(self.config, "fishing_channel_id", 0) or 0), fishing_active)
        autofight = self._build_channel_state_snapshot(int(getattr(self.config, "autofight_channel_id", 0) or 0), autofight_active)

        return {
            "hunting": hunting,
            "fishing": fishing,
            "autofight": autofight,
            "active_count": int((1 if hunting_active else 0) + (1 if fishing_active else 0) + (1 if autofight_active else 0)),
            "any_active": bool(hunting_active or fishing_active or autofight_active),
        }

    def _sync_global_captcha_flag(self) -> None:
        hunt_active = bool(getattr(self.bot, "hunting_captcha_active", False))
        fish_active = bool(getattr(self.bot, "fishing_captcha_active", False))
        autofight_active = bool(getattr(self.bot, "autofight_captcha_active", False))
        self.bot.captcha_active = hunt_active or fish_active or autofight_active

    def _is_tracked_captcha_channel(self, channel_id: int) -> bool:
        return int(channel_id) in {
            int(getattr(self.config, "hunting_channel_id", 0) or 0),
            int(getattr(self.config, "fishing_channel_id", 0) or 0),
            int(getattr(self.config, "autofight_channel_id", 0) or 0),
        }

    def _is_relevant_captcha_event(self, message: Message) -> bool:
        channel_id = int(getattr(message.channel, "id", 0) or 0)
        if not self._is_tracked_captcha_channel(channel_id):
            return False

        interaction = getattr(message, "interaction", None)
        interaction_user_id = int(getattr(getattr(interaction, "user", None), "id", 0) or 0)
        bot_user_id = int(getattr(getattr(self.bot, "user", None), "id", 0) or 0)
        if interaction is not None and interaction_user_id == bot_user_id:
            return True

        author_id = int(getattr(getattr(message, "author", None), "id", 0) or 0)
        return author_id == POKEMEOW_APP_ID

    @staticmethod
    def _extract_captcha_image_url(message: Message) -> str:
        if message.embeds and message.embeds[0].image:
            return str(message.embeds[0].image.url or "")
        return ""

    @staticmethod
    def _append_jsonl(path: Path, record: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(record, ensure_ascii=True) + "\n")

    def _get_state(self, channel_id: int) -> dict[str, object]:
        state = self.channel_attempt_state.get(channel_id)
        if state is None:
            state = {
                "attempts": 0,
                "manual_attempts": 0,
                "warned_manual": False,
                "last_prediction": "",
                "last_image_url": "",
                "last_image_path": "",
                "last_manual_answer": "",
                "captcha_message_id": 0,
                "detected_at": 0.0,
                "last_detected_utc": 0.0,
                "terminal_failure": False,
                "failure_reason": "",
            }
            self.channel_attempt_state[channel_id] = state
        return state

    def _mark_captcha_present(self, message: Message, image_path: str = "", reset_attempts: bool = True) -> None:
        state = self._get_state(int(message.channel.id))
        now_ts = float(time())
        if reset_attempts:
            state["attempts"] = 0
            state["manual_attempts"] = 0
            state["warned_manual"] = False
            state["last_prediction"] = ""
            state["last_manual_answer"] = ""
            state["terminal_failure"] = False
            state["failure_reason"] = ""
            state["detected_at"] = now_ts
        elif float(state.get("detected_at", 0.0) or 0.0) <= 0.0:
            state["detected_at"] = now_ts
        state["last_detected_utc"] = float(state.get("detected_at", now_ts) or now_ts)
        state["captcha_message_id"] = int(message.id)
        extracted_image_url = self._extract_captcha_image_url(message)
        if extracted_image_url:
            state["last_image_url"] = extracted_image_url
        if image_path:
            state["last_image_path"] = str(image_path)

    def _get_channel_lock(self, channel_id: int) -> asyncio.Lock:
        lock = self.channel_attempt_locks.get(int(channel_id))
        if lock is None:
            lock = asyncio.Lock()
            self.channel_attempt_locks[int(channel_id)] = lock
        return lock

    @staticmethod
    def _extract_image_extension(image_url: str) -> str:
        parsed_path = urlparse(str(image_url or "")).path
        suffix = Path(parsed_path).suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}:
            return suffix
        return ".png"

    def _snapshot_runtime_state_for_captcha(self) -> None:
        if self._captcha_runtime_snapshot is not None:
            return
        self._captcha_runtime_snapshot = {
            "pause_hunting": bool(getattr(self.bot, "pause_hunting", False)),
            "pause_fishing": bool(getattr(self.bot, "pause_fishing", False)),
            "autofight_active": bool(getattr(self.bot, "autofight_active", False)),
            "hunting_status": str(getattr(self.bot, "hunting_status", "") or ""),
            "fishing_status": str(getattr(self.bot, "fishing_status", "") or ""),
            "autofight_status": str(getattr(self.bot, "autofight_status", "") or ""),
        }

        self.bot.pause_hunting = True
        self.bot.pause_fishing = True
        if bool(getattr(self.bot, "autofight_active", False)):
            self.bot.autofight_active = False

        if int(getattr(self.config, "hunting_channel_id", 0) or 0) != 0:
            self.bot.hunting_status = "Paused (captcha)"
        if int(getattr(self.config, "fishing_channel_id", 0) or 0) != 0:
            self.bot.fishing_status = "Paused (captcha)"
        if int(getattr(self.config, "autofight_channel_id", 0) or 0) != 0:
            self.bot.autofight_status = "Paused (captcha)"

    async def _restore_runtime_state_after_captcha(self) -> None:
        snapshot = self._captcha_runtime_snapshot
        if not snapshot:
            return

        self.bot.pause_hunting = bool(snapshot.get("pause_hunting", False))
        self.bot.pause_fishing = bool(snapshot.get("pause_fishing", False))
        self.bot.autofight_active = bool(snapshot.get("autofight_active", False))

        self.bot.hunting_status = str(snapshot.get("hunting_status", self.bot.hunting_status) or self.bot.hunting_status)
        self.bot.fishing_status = str(snapshot.get("fishing_status", self.bot.fishing_status) or self.bot.fishing_status)
        self.bot.autofight_status = str(snapshot.get("autofight_status", self.bot.autofight_status) or self.bot.autofight_status)
        self._captcha_runtime_snapshot = None
        await self.bot.log()

    async def _persist_captcha_image(self, message: Message) -> str:
        image_url = self._extract_captcha_image_url(message)
        if not image_url:
            return ""

        suffix = self._extract_image_extension(image_url)
        # Same Discord message can be edited with a new captcha image; key file by image URL hash.
        image_hash = hashlib.sha256(str(image_url).encode("utf-8")).hexdigest()[:16]
        image_name = f"{int(message.id)}_{image_hash}{suffix}"
        CAPTCHA_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        image_path = CAPTCHA_IMAGES_DIR / image_name
        if not image_path.exists():
            try:
                response = await asyncio.to_thread(requests.get, image_url, timeout=20)
                if response.status_code < 300:
                    image_path.write_bytes(response.content)
            except Exception:
                return ""

        if image_path.exists():
            return image_path.relative_to(BASE_DIR).as_posix()
        return ""

    def _resolve_state_image_path(self, message: Message) -> str:
        channel_id = int(message.channel.id)
        state = self.channel_attempt_state.get(channel_id, {})
        image_path = str(state.get("last_image_path", "") or "")
        if image_path:
            return image_path
        return ""

    def _record_training_label(self, message: Message, label: str, label_source: str) -> None:
        clean_label = str(label or "").strip()
        if not clean_label:
            return

        channel_id = int(message.channel.id)
        state = self.channel_attempt_state.get(channel_id, {})
        image_path = str(state.get("last_image_path", "") or "")
        image_url = str(state.get("last_image_url", "") or self._extract_captcha_image_url(message))
        captcha_message_id = int(state.get("captcha_message_id", 0) or message.id)

        self._append_jsonl(
            TRAINING_LABELS_PATH,
            {
                "ts_utc": datetime.now(timezone.utc).isoformat(),
                "account": str(self.bot.user) if self.bot.user else "unknown",
                "channel_id": channel_id,
                "captcha_message_id": captcha_message_id,
                "captcha_image_url": image_url,
                "captcha_image_path": image_path,
                "label": clean_label,
                "label_source": str(label_source),
            },
        )

        self._export_training_dataset()

    def _export_training_dataset(self) -> None:
        if not TRAINING_LABELS_PATH.exists():
            return

        deduped: dict[str, dict] = {}
        with TRAINING_LABELS_PATH.open("r", encoding="utf-8") as fp:
            for line in fp:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    row = json.loads(raw)
                except Exception:
                    continue

                captcha_message_id = int(row.get("captcha_message_id", 0) or 0)
                image_path = str(row.get("captcha_image_path", "") or "")
                label = str(row.get("label", "") or "").strip()
                if captcha_message_id <= 0 or not image_path or not label:
                    continue

                dedupe_key = f"{captcha_message_id}:{image_path}"

                # Prefer resolved manual labels over auto labels when both exist.
                previous = deduped.get(dedupe_key)
                current_source = str(row.get("label_source", "") or "")
                if previous is not None:
                    previous_source = str(previous.get("label_source", "") or "")
                    if previous_source.startswith("manual") and not current_source.startswith("manual"):
                        continue

                deduped[dedupe_key] = {
                    "captcha_message_id": captcha_message_id,
                    "image_path": image_path,
                    "label": label,
                    "label_source": current_source,
                }

        TRAINING_DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)
        with TRAINING_DATASET_PATH.open("w", encoding="utf-8") as fp:
            for row in deduped.values():
                absolute_image_path = BASE_DIR / row["image_path"]
                if not absolute_image_path.exists():
                    continue
                fp.write(json.dumps(row, ensure_ascii=True) + "\n")

    async def _send_alert_notification(self, content: str) -> None:
        webhook_ok = False
        if self.config.captcha_alert_webhook_url:
            payload = {
                "content": content,
                "allowed_mentions": {
                    "parse": ["users", "roles", "everyone"],
                },
            }
            try:
                response = await asyncio.to_thread(
                    requests.post,
                    self.config.captcha_alert_webhook_url,
                    json=payload,
                    timeout=10,
                )
                if response.status_code >= 300:
                    print(f"[Captcha] Alert webhook failed with status {response.status_code}")
                else:
                    webhook_ok = True
            except Exception:
                print("[Captcha] Alert webhook failed with an exception.")

        alert_channel_id = int(getattr(self.config, "captcha_alert_channel_id", 0) or 0)
        if alert_channel_id <= 0:
            if not webhook_ok:
                print("[Captcha] Alert was not delivered (no valid webhook or alert channel configured).")
            return

        try:
            channel = self.bot.get_channel(alert_channel_id)
            if channel is None:
                channel = await self.bot.fetch_channel(alert_channel_id)
            if channel is not None:
                await channel.send(content)
        except Exception as exc:
            if not webhook_ok:
                print(f"[Captcha] Alert channel delivery failed: {exc}")

    async def _warn_manual_required(self, message: Message, attempts_used: int) -> None:
        account_name = str(self.bot.user) if self.bot.user else "Unknown"
        warn_text = (
            f"{self.resolve_ping_target(message)} CAPTCHA auto-attempt limit reached "
            f"({attempts_used}/{self.max_auto_attempts}). Please answer manually in channel {message.channel.id}.\n"
            f"Use: answer <digits>"
        )

        print(
            f"[Captcha] Auto-attempt limit reached for {account_name} in channel {message.channel.id} "
            f"({attempts_used}/{self.max_auto_attempts}). Manual answer required."
        )

        if self.config.captcha_alerts_enabled:
            await self._send_alert_notification(warn_text)

    def _record_solver_attempt(
        self,
        message: Message,
        attempt_number: int,
        prediction: str,
        source: str,
    ) -> None:
        self._append_jsonl(
            AUTO_SOLVER_ATTEMPTS_PATH,
            {
                "ts_utc": datetime.now(timezone.utc).isoformat(),
                "account": str(self.bot.user) if self.bot.user else "unknown",
                "channel_id": int(message.channel.id),
                "captcha_message_id": int(message.id),
                "captcha_image_url": self._extract_captcha_image_url(message),
                "captcha_image_path": self._resolve_state_image_path(message),
                "attempt_number": int(attempt_number),
                "max_attempts": int(self.max_auto_attempts),
                "prediction": str(prediction),
                "source": source,
            },
        )

    def _record_solver_outcome(
        self,
        message: Message,
        outcome: str,
        attempts_used: int,
        state_override: dict[str, object] | None = None,
    ) -> None:
        state = state_override or self.channel_attempt_state.get(int(message.channel.id), {})
        self._append_jsonl(
            AUTO_SOLVER_OUTCOMES_PATH,
            {
                "ts_utc": datetime.now(timezone.utc).isoformat(),
                "account": str(self.bot.user) if self.bot.user else "unknown",
                "channel_id": int(message.channel.id),
                "captcha_message_id": int(state.get("captcha_message_id", 0) or message.id),
                "captcha_image_url": str(state.get("last_image_url", "") or self._extract_captcha_image_url(message)),
                "captcha_image_path": str(state.get("last_image_path", "") or self._resolve_state_image_path(message)),
                "attempts_used": int(attempts_used),
                "manual_attempts_used": int(state.get("manual_attempts", 0) or 0),
                "max_attempts": int(self.max_auto_attempts),
                "last_prediction": str(state.get("last_prediction", "") or ""),
                "outcome": str(outcome),
            },
        )

    @staticmethod
    def _total_attempts_used(state: dict[str, object]) -> int:
        auto_attempts = int(state.get("attempts", 0) or 0)
        manual_attempts = int(state.get("manual_attempts", 0) or 0)
        return max(0, auto_attempts + manual_attempts)

    def _is_captcha_timed_out(self, state: dict[str, object]) -> bool:
        detected_at = float(state.get("detected_at", 0.0) or 0.0)
        if detected_at <= 0:
            return False
        return (time() - detected_at) >= float(CAPTCHA_TIMEOUT_SECONDS)

    async def _finalize_captcha_failure(self, channel_id: int, reason: str) -> None:
        state = self._get_state(channel_id)
        if bool(state.get("terminal_failure", False)):
            return

        state["terminal_failure"] = True
        state["failure_reason"] = str(reason or "failure")

        pseudo_message = self.last_captcha_message
        if pseudo_message is not None and int(getattr(pseudo_message.channel, "id", 0) or 0) == int(channel_id):
            self._record_solver_outcome(
                pseudo_message,
                outcome=f"failed_terminal:{reason}",
                attempts_used=int(state.get("attempts", 0) or 0),
                state_override=state,
            )

        if channel_id == int(getattr(self.config, "hunting_channel_id", 0) or 0):
            self.bot.hunting_captcha_active = False
            self.bot.pause_hunting = True
            self.bot.hunting_status = "Paused (captcha failed - manual intervention required)"
        elif channel_id == int(getattr(self.config, "fishing_channel_id", 0) or 0):
            self.bot.fishing_captcha_active = False
            self.bot.pause_fishing = True
            self.bot.fishing_status = "Paused (captcha failed - manual intervention required)"
        elif channel_id == int(getattr(self.config, "autofight_channel_id", 0) or 0):
            self.bot.autofight_captcha_active = False
            self.bot.autofight_active = False
            self.bot.autofight_status = "Paused (captcha failed - manual intervention required)"

        self._sync_global_captcha_flag()
        self.stop_reminder_loop()
        await self.bot.log()

        if self.config.captcha_alerts_enabled and self.last_captcha_message is not None:
            alert_text = (
                f"{self.resolve_ping_target(self.last_captcha_message)} CAPTCHA entered terminal failure state "
                f"for channel {channel_id} ({reason}). Automation paused to prevent spam. "
                f"Use Resume controls after manual verification."
            )
            await self._send_alert_notification(alert_text)

    async def _finalize_captcha_resolution(
        self,
        channel_id: int,
        resolution_source: str,
        *,
        allow_command_redispatch: bool,
        message: Message | None = None,
    ) -> tuple[bool, str]:
        state = self.channel_attempt_state.get(channel_id, {})
        active_channel = self._is_active_captcha_channel(channel_id)
        if not active_channel and not state and self._captcha_runtime_snapshot is None:
            return False, "No active captcha to resolve."

        source_message = message or self.last_captcha_message
        attempts_used = int(state.get("attempts", 0) or 0)
        manual_label = str(state.get("last_manual_answer", "") or "").strip()
        auto_label = str(state.get("last_prediction", "") or "").strip()

        if source_message is not None and int(getattr(source_message.channel, "id", 0) or 0) == int(channel_id):
            self._record_solver_outcome(source_message, outcome="resolved", attempts_used=attempts_used, state_override=state)

            if manual_label:
                self._record_training_label(source_message, manual_label, label_source="manual_resolved")
            elif auto_label and attempts_used > 0:
                self._record_training_label(source_message, auto_label, label_source="auto_resolved")

        self.channel_attempt_state.pop(channel_id, None)
        self.channel_attempt_locks.pop(channel_id, None)

        record_anti_detect_event(
            str(self.bot.user) if self.bot.user else "unknown",
            "captcha_resolved",
            module="captcha",
            channel_id=channel_id,
            details={
                "source": str(resolution_source or "unknown"),
                "manual_label_present": bool(manual_label),
                "auto_label_present": bool(auto_label),
            },
        )

        if channel_id == int(getattr(self.config, "hunting_channel_id", 0) or 0):
            self.bot.hunting_captcha_active = False
        elif channel_id == int(getattr(self.config, "fishing_channel_id", 0) or 0):
            self.bot.fishing_captcha_active = False
        elif channel_id == int(getattr(self.config, "autofight_channel_id", 0) or 0):
            self.bot.autofight_captcha_active = False

        self._sync_global_captcha_flag()
        if not bool(getattr(self.bot, "captcha_active", False)):
            await self._restore_runtime_state_after_captcha()

        self.stop_reminder_loop()
        await self.bot.log()

        await asyncio.sleep(
            self.config.retry_cooldown
            + randint(0, self.config.suspicion_avoidance) / 1000
        )

        if not allow_command_redispatch or source_message is None:
            return True, "Captcha marked resolved."

        interaction_name = str(getattr(getattr(source_message, "interaction", None), "name", "") or "").strip()
        if channel_id == self.config.hunting_channel_id:
            command_name = interaction_name or "pokemon"
            command_map = getattr(self.bot, "hunting_channel_commands", None) or {}
        elif channel_id == self.config.fishing_channel_id:
            command_name = interaction_name or "fish spawn"
            command_map = getattr(self.bot, "fishing_channel_commands", None) or {}
        else:
            command_name = interaction_name or ""
            command_map = {}

        command = command_map.get(command_name)
        if not manual_label and command is not None:
            await command()
        elif not manual_label:
            print(f"[Captcha] Warning: unable to resume command '{command_name}' after captcha resolution.")

        return True, "Captcha marked resolved."

    def _extract_manual_resolution_command(self, content: str) -> bool:
        value = str(content or "").strip().lower()
        return value in {"resolved", "captcha resolved", "mark resolved", "captcha mark resolved", "clear captcha"}

    async def _handle_manual_resolution_command(self, message: Message) -> bool:
        if message.author.id == getattr(self.bot.user, "id", 0):
            return False

        author_id = int(getattr(message.author, "id", 0) or 0)
        if not self._is_manual_answer_authorized(author_id):
            print(f"[Captcha] Ignored manual resolution from unauthorized user {author_id} in channel {message.channel.id}.")
            return False

        channel_id = int(message.channel.id)
        if not self._is_tracked_captcha_channel(channel_id):
            return False

        if not self._is_active_captcha_channel(channel_id) and not self.channel_attempt_state.get(channel_id):
            return False

        ok, message_text = await self._finalize_captcha_resolution(
            channel_id,
            "manual_chat",
            allow_command_redispatch=True,
            message=self.last_captcha_message,
        )
        if ok:
            print(f"[Captcha] Manual resolution accepted for channel {channel_id} requested by {message.author}.")
        else:
            print(f"[Captcha] Manual resolution rejected for channel {channel_id} requested by {message.author}: {message_text}")
        return ok

    def _record_failed_candidate(
        self,
        message: Message,
        attempts_used: int,
        state_snapshot: dict[str, object],
    ) -> None:
        image_path = str(state_snapshot.get("last_image_path", "") or "")
        image_url = str(state_snapshot.get("last_image_url", "") or "")
        prediction = str(state_snapshot.get("last_prediction", "") or "").strip()
        if not image_path and not image_url:
            return

        self._append_jsonl(
            FAILED_CAPTCHA_CANDIDATES_PATH,
            {
                "ts_utc": datetime.now(timezone.utc).isoformat(),
                "account": str(self.bot.user) if self.bot.user else "unknown",
                "channel_id": int(message.channel.id),
                "captcha_message_id": int(state_snapshot.get("captcha_message_id", 0) or message.id),
                "captcha_image_url": image_url,
                "captcha_image_path": image_path,
                "attempts_used": int(attempts_used),
                "predicted_answer": prediction,
                "candidate_type": "failed_auto_attempt",
                "needs_label": True,
            },
        )

    @staticmethod
    def _normalize_captcha_digits(value: str) -> str:
        # Keep only digits to avoid sending non-numeric OCR artifacts.
        return "".join(ch for ch in str(value or "") if ch.isdigit())

    @staticmethod
    def _is_valid_captcha_answer(value: str) -> bool:
        return bool(re.fullmatch(rf"\d{{{CAPTCHA_DIGIT_MIN_LENGTH},{CAPTCHA_DIGIT_MAX_LENGTH}}}", str(value or "")))

    async def _warn_manual_low_confidence(self, message: Message, raw_prediction: str) -> None:
        account_name = str(self.bot.user) if self.bot.user else "Unknown"
        print(
            f"[Captcha] Solver output out-of-spec for {account_name} in channel {message.channel.id}. "
            f"raw='{raw_prediction}'. Waiting for manual answer."
        )

        warn_text = (
            f"{self.resolve_ping_target(message)} CAPTCHA detected but auto-solver prediction was low-confidence/out-of-spec. "
            f"Please answer manually in channel {message.channel.id}.\n"
            f"Use: answer <{CAPTCHA_DIGIT_MIN_LENGTH}-{CAPTCHA_DIGIT_MAX_LENGTH} digits>"
        )
        if self.config.captcha_alerts_enabled:
            await self._send_alert_notification(warn_text)

    async def _attempt_auto_solver(self, message: Message, source: str) -> None:
        if not bool(getattr(self.config, "captcha_auto_answer_enabled", True)):
            return

        channel_id = int(message.channel.id)
        lock = self._get_channel_lock(channel_id)
        async with lock:
            state = self._get_state(channel_id)
            if bool(state.get("terminal_failure", False)):
                return

            if self._is_captcha_timed_out(state):
                await self._finalize_captcha_failure(channel_id, reason="timeout_90s")
                return

            attempts_used = int(state.get("attempts", 0) or 0)
            if attempts_used >= self.max_auto_attempts:
                if not bool(state.get("warned_manual", False)):
                    state["warned_manual"] = True
                    await self._warn_manual_required(message, attempts_used)

                status_text = f"Captcha Pending (manual after {self.max_auto_attempts} auto attempts)"
                if message.channel.id == self.config.hunting_channel_id:
                    self.bot.hunting_status = status_text
                elif message.channel.id == self.config.fishing_channel_id:
                    self.bot.fishing_status = status_text

                await self.bot.log()
                return

            if self._total_attempts_used(state) >= CAPTCHA_TOTAL_MAX_ATTEMPTS:
                await self._finalize_captcha_failure(channel_id, reason="max_total_attempts")
                return

            captcha_image_url = self._extract_captcha_image_url(message)
            if not captcha_image_url:
                return

            await asyncio.sleep(
                self.config.retry_cooldown
                + randint(0, self.config.suspicion_avoidance) / 1000
            )

            raw_prediction = solve_captcha(captcha_image_url)
            prediction = self._normalize_captcha_digits(raw_prediction)
            if not self._is_valid_captcha_answer(prediction):
                state["last_prediction"] = str(raw_prediction)
                state["last_image_url"] = captcha_image_url
                status_text = "Captcha Pending (manual: low-confidence auto prediction)"
                if message.channel.id == self.config.hunting_channel_id:
                    self.bot.hunting_status = status_text
                elif message.channel.id == self.config.fishing_channel_id:
                    self.bot.fishing_status = status_text

                await self._warn_manual_low_confidence(message, str(raw_prediction))
                await self.bot.log()
                return

            next_attempt = attempts_used + 1
            state["attempts"] = next_attempt
            state["last_prediction"] = prediction
            state["last_image_url"] = captcha_image_url
            self._record_solver_attempt(message, next_attempt, prediction, source)
            await message.channel.send(prediction)

            print(
                f"[Captcha] Auto attempt {next_attempt}/{self.max_auto_attempts} "
                f"sent in channel {message.channel.id}: {prediction}"
            )

    def _extract_manual_answer(self, content: str) -> str | None:
        value = str(content or "").strip()
        match = re.match(
            rf"^answer\s+(\d{{{CAPTCHA_DIGIT_MIN_LENGTH},{CAPTCHA_DIGIT_MAX_LENGTH}}})$",
            value,
            flags=re.IGNORECASE,
        )
        if not match:
            return None
        return match.group(1)

    def _is_active_captcha_channel(self, channel_id: int) -> bool:
        if channel_id == self.config.hunting_channel_id and bool(getattr(self.bot, "hunting_captcha_active", False)):
            return True
        if channel_id == self.config.fishing_channel_id and bool(getattr(self.bot, "fishing_captcha_active", False)):
            return True
        if channel_id == self.config.autofight_channel_id and bool(getattr(self.bot, "autofight_captcha_active", False)):
            return True
        return False

    def _is_manual_answer_authorized(self, user_id: int) -> bool:
        allowed_user_ids = list(getattr(self.config, "captcha_manual_allowed_user_ids", []) or [])
        if not allowed_user_ids:
            return True
        return int(user_id) in {int(value) for value in allowed_user_ids}

    async def _handle_manual_answer_command(self, message: Message, answer_text: str) -> bool:
        if message.author.id == getattr(self.bot.user, "id", 0):
            return False

        author_id = int(getattr(message.author, "id", 0) or 0)
        if not self._is_manual_answer_authorized(author_id):
            print(f"[Captcha] Ignored manual answer from unauthorized user {author_id} in channel {message.channel.id}.")
            return False

        if not self._is_active_captcha_channel(int(message.channel.id)):
            return False

        state = self._get_state(int(message.channel.id))
        if bool(state.get("terminal_failure", False)):
            return False

        if self._is_captcha_timed_out(state):
            await self._finalize_captcha_failure(int(message.channel.id), reason="timeout_90s")
            return True

        manual_attempts = int(state.get("manual_attempts", 0) or 0)
        if manual_attempts >= CAPTCHA_MANUAL_MAX_ATTEMPTS:
            await self._finalize_captcha_failure(int(message.channel.id), reason="max_manual_attempts")
            return True

        if self._total_attempts_used(state) >= CAPTCHA_TOTAL_MAX_ATTEMPTS:
            await self._finalize_captcha_failure(int(message.channel.id), reason="max_total_attempts")
            return True

        await asyncio.sleep(self.config.retry_cooldown + randint(0, self.config.suspicion_avoidance) / 1000)
        await message.channel.send(answer_text)

        state = self._get_state(int(message.channel.id))
        state["manual_attempts"] = int(state.get("manual_attempts", 0) or 0) + 1
        state["last_manual_answer"] = str(answer_text)

        if message.channel.id == self.config.hunting_channel_id:
            self.bot.hunting_status = "Captcha Pending (manual answer sent)"
        elif message.channel.id == self.config.fishing_channel_id:
            self.bot.fishing_status = "Captcha Pending (manual answer sent)"

        record_anti_detect_event(
            str(self.bot.user) if self.bot.user else "unknown",
            "captcha_manual_answer_sent",
            module="captcha",
            channel_id=message.channel.id,
            details={
                "answer_length": len(answer_text),
                "requested_by": int(getattr(message.author, "id", 0) or 0),
            },
        )
        await self.bot.log()
        print(f"[Captcha] Relayed manual answer for channel {message.channel.id} requested by {message.author}.")
        return True

    async def submit_manual_answer_from_dashboard(self, answer_text: str, channel_hint: str = "") -> tuple[bool, str]:
        value = str(answer_text or "").strip()
        if not self._is_valid_captcha_answer(value):
            return False, f"Manual answer must be {CAPTCHA_DIGIT_MIN_LENGTH}-{CAPTCHA_DIGIT_MAX_LENGTH} digits."

        hint = str(channel_hint or "").strip().lower()
        target_channel_id = 0
        if hint in {"hunt", "hunting"}:
            target_channel_id = int(getattr(self.config, "hunting_channel_id", 0) or 0)
        elif hint in {"fish", "fishing"}:
            target_channel_id = int(getattr(self.config, "fishing_channel_id", 0) or 0)
        elif hint in {"autofight", "battle", "battles", "af"}:
            target_channel_id = int(getattr(self.config, "autofight_channel_id", 0) or 0)
        else:
            if bool(getattr(self.bot, "hunting_captcha_active", False)):
                target_channel_id = int(getattr(self.config, "hunting_channel_id", 0) or 0)
            elif bool(getattr(self.bot, "fishing_captcha_active", False)):
                target_channel_id = int(getattr(self.config, "fishing_channel_id", 0) or 0)
            elif bool(getattr(self.bot, "autofight_captcha_active", False)):
                target_channel_id = int(getattr(self.config, "autofight_channel_id", 0) or 0)

        if target_channel_id <= 0:
            return False, "No active captcha channel to answer right now."

        if not self._is_active_captcha_channel(target_channel_id):
            return False, "Captcha is not active on the selected channel."

        state = self._get_state(target_channel_id)
        if bool(state.get("terminal_failure", False)):
            return False, "Captcha entered terminal failure state. Resume module manually first."

        if self._is_captcha_timed_out(state):
            await self._finalize_captcha_failure(target_channel_id, reason="timeout_90s")
            return False, "Captcha expired (90s timeout). Automation paused."

        manual_attempts = int(state.get("manual_attempts", 0) or 0)
        if manual_attempts >= CAPTCHA_MANUAL_MAX_ATTEMPTS:
            await self._finalize_captcha_failure(target_channel_id, reason="max_manual_attempts")
            return False, "Manual attempt limit reached. Automation paused."

        if self._total_attempts_used(state) >= CAPTCHA_TOTAL_MAX_ATTEMPTS:
            await self._finalize_captcha_failure(target_channel_id, reason="max_total_attempts")
            return False, "Total attempt limit reached. Automation paused."

        channel = self.bot.get_channel(target_channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(target_channel_id)
            except Exception:
                return False, "Could not resolve target channel for manual answer."

        await asyncio.sleep(self.config.retry_cooldown + randint(0, self.config.suspicion_avoidance) / 1000)
        await channel.send(value)

        state = self._get_state(target_channel_id)
        state["manual_attempts"] = int(state.get("manual_attempts", 0) or 0) + 1
        state["last_manual_answer"] = value

        if target_channel_id == self.config.hunting_channel_id:
            self.bot.hunting_status = "Captcha Pending (manual answer sent)"
        elif target_channel_id == self.config.fishing_channel_id:
            self.bot.fishing_status = "Captcha Pending (manual answer sent)"

        record_anti_detect_event(
            str(self.bot.user) if self.bot.user else "unknown",
            "captcha_manual_answer_sent_dashboard",
            module="captcha",
            channel_id=target_channel_id,
            details={
                "answer_length": len(value),
            },
        )
        await self.bot.log()
        return True, "Manual captcha answer sent."

    async def submit_manual_resolution_from_dashboard(self, channel_hint: str = "") -> tuple[bool, str]:
        hint = str(channel_hint or "").strip().lower()
        target_channel_id = 0
        if hint in {"hunt", "hunting"}:
            target_channel_id = int(getattr(self.config, "hunting_channel_id", 0) or 0)
        elif hint in {"fish", "fishing"}:
            target_channel_id = int(getattr(self.config, "fishing_channel_id", 0) or 0)
        elif hint in {"autofight", "battle", "battles", "af"}:
            target_channel_id = int(getattr(self.config, "autofight_channel_id", 0) or 0)
        else:
            if bool(getattr(self.bot, "hunting_captcha_active", False)):
                target_channel_id = int(getattr(self.config, "hunting_channel_id", 0) or 0)
            elif bool(getattr(self.bot, "fishing_captcha_active", False)):
                target_channel_id = int(getattr(self.config, "fishing_channel_id", 0) or 0)
            elif bool(getattr(self.bot, "autofight_captcha_active", False)):
                target_channel_id = int(getattr(self.config, "autofight_channel_id", 0) or 0)
            elif self.last_captcha_message is not None:
                target_channel_id = int(getattr(self.last_captcha_message.channel, "id", 0) or 0)
            else:
                for active_channel_id, state in self.channel_attempt_state.items():
                    if bool(state.get("terminal_failure", False)) or int(state.get("captcha_message_id", 0) or 0) > 0:
                        target_channel_id = int(active_channel_id)
                        break

        if target_channel_id <= 0:
            return False, "No active captcha channel to resolve right now."

        return await self._finalize_captcha_resolution(
            target_channel_id,
            "dashboard_manual_resolution",
            allow_command_redispatch=True,
            message=self.last_captcha_message,
        )

    @staticmethod
    def is_captcha_message(message: Message) -> bool:
        haystack = Captcha._build_detection_haystack(message)
        lowered = haystack.lower()
        signal_patterns = (
            "captcha",
            "a wild captcha appeared",
            "type your answer",
            "you must type your answer",
            "you have 1 min 30s",
            "temporarily banned",
            "captcha-help",
            "official support server",
            "click on the image",
            "ignore any invisible",
        )
        return any(pattern in lowered for pattern in signal_patterns)

    @staticmethod
    def _build_detection_haystack(message: Message) -> str:
        parts: list[str] = [str(getattr(message, "content", "") or "")]
        for embed in getattr(message, "embeds", []) or []:
            parts.extend([
                str(getattr(embed, "title", "") or ""),
                str(getattr(embed, "description", "") or ""),
                str(getattr(getattr(embed, "author", None), "name", "") or ""),
                str(getattr(getattr(embed, "footer", None), "text", "") or ""),
            ])
            for field in getattr(embed, "fields", []) or []:
                parts.append(str(getattr(field, "name", "") or ""))
                parts.append(str(getattr(field, "value", "") or ""))
        return "\n".join(part for part in parts if str(part or "").strip())

    def _captcha_detection_details(self, message: Message) -> dict[str, object]:
        haystack = self._build_detection_haystack(message)
        lowered = haystack.lower()
        matched_tokens = [
            token
            for token in (
                "captcha",
                "a wild captcha appeared",
                "type your answer",
                "you must type your answer",
                "you have 1 min 30s",
                "temporarily banned",
                "captcha-help",
                "official support server",
                "click on the image",
                "ignore any invisible",
            )
            if token in lowered
        ]
        return {
            "matched": bool(matched_tokens),
            "matched_tokens": matched_tokens,
            "author_id": int(getattr(message.author, "id", 0) or 0),
            "channel_id": int(getattr(message.channel, "id", 0) or 0),
            "has_embeds": bool(getattr(message, "embeds", []) or []),
            "text_preview": haystack[:400],
        }

    async def send_local_alert(self, message: Message) -> None:
        account_name = str(self.bot.user) if self.bot.user else "Unknown"
        channel_id = message.channel.id
        jump_url = message.jump_url

        print("\n" + "=" * 76)
        print("CAPTCHA DETECTED - MANUAL ACTION NEEDED NOW")
        print(f"Account: {account_name}")
        print(f"Channel: {channel_id}")
        print(f"Open: {jump_url}")
        print("=" * 76 + "\n")

        try:
            if os.name == "nt":
                import winsound

                winsound.MessageBeep(winsound.MB_ICONHAND)
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                winsound.MessageBeep(winsound.MB_ICONHAND)
            else:
                print("\a\a\a", end="", flush=True)
        except Exception:
            print("\a\a\a", end="", flush=True)

    async def send_captcha_alert(self, message: Message) -> None:
        if not self.config.captcha_alerts_enabled:
            return

        now = time()
        if now - self.last_alert_at < self.config.captcha_alert_cooldown_seconds:
            print(
                f"[Captcha] Alert suppressed by cooldown ({self.config.captcha_alert_cooldown_seconds}s)."
            )
            return

        self.last_alert_at = now

        channel_id = message.channel.id
        account_name = str(self.bot.user) if self.bot.user else "Unknown"
        interaction_name = message.interaction.name if message.interaction else "unknown"
        captcha_url = (
            message.embeds[0].image.url if message.embeds and message.embeds[0].image else ""
        )
        ping_text = self.resolve_ping_target(message)

        alert_text = (
            f"{ping_text} CAPTCHA detected. "
            f"Account: {account_name} | Channel: {channel_id} | Command: {interaction_name}\n"
            f"Jump: {message.jump_url}\n"
            f"Image: {captcha_url}"
        )
        await self._send_alert_notification(alert_text)

    def resolve_ping_target(self, message: Message) -> str:
        raw = (self.config.captcha_alert_ping or "").strip()
        if not raw:
            return "@everyone"

        if raw in {"@everyone", "@here"}:
            return raw

        if raw.startswith("<@") and raw.endswith(">"):
            return raw

        if raw.isdigit():
            return f"<@{raw}>"

        if raw.startswith("@") and message.guild is not None:
            name = raw[1:].strip()
            if name.isdigit():
                return f"<@{name}>"
            member = message.guild.get_member_named(name)
            if member is not None:
                return member.mention
            lowered = name.lower()
            for candidate in getattr(message.guild, "members", []):
                candidate_name = str(getattr(candidate, "name", "") or "").lower()
                candidate_display = str(getattr(candidate, "display_name", "") or "").lower()
                if lowered in {candidate_name, candidate_display}:
                    return candidate.mention

        return raw

    async def activate_captcha_mode(self, message: Message) -> None:
        record_anti_detect_event(
            str(self.bot.user) if self.bot.user else "unknown",
            "captcha_detected",
            module="captcha",
            channel_id=message.channel.id,
            details={
                "interaction": message.interaction.name if message.interaction else "unknown",
                "auto_answer_enabled": bool(getattr(self.config, "captcha_auto_answer_enabled", True)),
            },
        )
        self._snapshot_runtime_state_for_captcha()
        if message.channel.id == self.config.hunting_channel_id:
            self.bot.hunting_captcha_active = True
        elif message.channel.id == self.config.fishing_channel_id:
            self.bot.fishing_captcha_active = True
        elif message.channel.id == self.config.autofight_channel_id:
            self.bot.autofight_captcha_active = True
            self.bot.autofight_status = "Paused (captcha)"

        self._sync_global_captcha_flag()
        self.last_captcha_message = message
        state = self._get_state(int(message.channel.id))
        previous_captcha_message_id = int(state.get("captcha_message_id", 0) or 0)
        should_reset_attempts = previous_captcha_message_id <= 0 or previous_captcha_message_id != int(message.id)
        image_path = await self._persist_captcha_image(message)
        self._mark_captcha_present(message, image_path=image_path, reset_attempts=should_reset_attempts)
        await self.send_local_alert(message)
        await self.send_captcha_alert(message)
        self.start_reminder_loop()

    def start_reminder_loop(self) -> None:
        if self.reminder_task is None or self.reminder_task.done():
            self.reminder_task = asyncio.create_task(self.captcha_reminder_loop())

    def stop_reminder_loop(self) -> None:
        if self.reminder_task and not self.reminder_task.done():
            self.reminder_task.cancel()

        self.reminder_task = None

    async def captcha_reminder_loop(self) -> None:
        try:
            while bool(getattr(self.bot, "captcha_active", False)):
                await asyncio.sleep(5)
                if not bool(getattr(self.bot, "captcha_active", False)):
                    break

                for active_channel_id in (
                    int(getattr(self.config, "hunting_channel_id", 0) or 0),
                    int(getattr(self.config, "fishing_channel_id", 0) or 0),
                    int(getattr(self.config, "autofight_channel_id", 0) or 0),
                ):
                    if active_channel_id <= 0:
                        continue
                    if not self._is_active_captcha_channel(active_channel_id):
                        continue
                    state = self._get_state(active_channel_id)
                    if self._is_captcha_timed_out(state):
                        await self._finalize_captcha_failure(active_channel_id, reason="timeout_90s")
                        break

                if not bool(getattr(self.bot, "captcha_active", False)):
                    break

                if self.last_captcha_message is not None:
                    await self.send_local_alert(self.last_captcha_message)
        except asyncio.CancelledError:
            pass

    @commands.Cog.listener()
    async def on_message(self, message: Message) -> None:
        if self._extract_manual_resolution_command(message.content or ""):
            handled_resolution = await self._handle_manual_resolution_command(message)
            if handled_resolution:
                return

        manual_answer = self._extract_manual_answer(message.content or "")
        if manual_answer is not None:
            handled = await self._handle_manual_answer_command(message, manual_answer)
            if handled:
                return

        detection = self._captcha_detection_details(message)
        if detection["matched"]:
            record_anti_detect_event(
                str(self.bot.user) if self.bot.user else "unknown",
                "captcha_detection_probe",
                module="captcha",
                channel_id=int(getattr(message.channel, "id", 0) or 0),
                details=detection,
            )

        if not self._is_relevant_captcha_event(message):
            return

        if not bool(detection["matched"]):
            return

        channel_id = int(getattr(message.channel, "id", 0) or 0)
        existing_state = self._get_state(channel_id)
        existing_captcha_message_id = int(existing_state.get("captcha_message_id", 0) or 0)
        if bool(existing_state.get("terminal_failure", False)) and existing_captcha_message_id == int(getattr(message, "id", 0) or 0):
            return

        await self.activate_captcha_mode(message)

        if channel_id == self.config.hunting_channel_id:
            if bool(getattr(self.config, "captcha_auto_answer_enabled", True)):
                self.bot.hunting_status = "Solving Captcha..."
            else:
                self.bot.hunting_status = "Captcha Pending (manual)"
        elif channel_id == self.config.fishing_channel_id:
            if bool(getattr(self.config, "captcha_auto_answer_enabled", True)):
                self.bot.fishing_status = "Solving Captcha..."
            else:
                self.bot.fishing_status = "Captcha Pending (manual)"
        elif channel_id == self.config.autofight_channel_id:
            if bool(getattr(self.config, "captcha_auto_answer_enabled", True)):
                self.bot.autofight_status = "Paused (captcha solving)"
            else:
                self.bot.autofight_status = "Paused (captcha manual)"

        await self.bot.log()
        await self._attempt_auto_solver(message, source="on_message")

    @commands.Cog.listener()
    async def on_message_edit(self, before, after: Message) -> None:
        detection = self._captcha_detection_details(after)
        if detection["matched"]:
            record_anti_detect_event(
                str(self.bot.user) if self.bot.user else "unknown",
                "captcha_detection_probe",
                module="captcha",
                channel_id=int(getattr(after.channel, "id", 0) or 0),
                details=detection,
            )

        if not self._is_relevant_captcha_event(after):
            return

        if after.content == before.content:
            if after.embeds != []:
                if before.embeds != []:
                    if after.embeds[0].description == before.embeds[0].description:
                        return
            else:
                return

        if "Thank you" in after.content:
            await self._finalize_captcha_resolution(
                int(after.channel.id),
                "message_edit_thank_you",
                allow_command_redispatch=True,
                message=after,
            )
            return

        if not bool(detection["matched"]):
            return

        channel_id = int(getattr(after.channel, "id", 0) or 0)
        existing_state = self._get_state(channel_id)
        existing_captcha_message_id = int(existing_state.get("captcha_message_id", 0) or 0)
        if bool(existing_state.get("terminal_failure", False)) and existing_captcha_message_id == int(getattr(after, "id", 0) or 0):
            return

        prev_state = self.channel_attempt_state.get(int(after.channel.id), {})
        prev_attempts_used = int(prev_state.get("attempts", 0) or 0)
        if prev_attempts_used > 0:
            self._record_solver_outcome(
                after,
                outcome="wrong_or_still_pending_after_attempt",
                attempts_used=prev_attempts_used,
                state_override=prev_state,
            )
            self._record_failed_candidate(after, prev_attempts_used, prev_state)

        await self.activate_captcha_mode(after)

        if channel_id == self.config.hunting_channel_id:
            if bool(getattr(self.config, "captcha_auto_answer_enabled", True)):
                self.bot.hunting_status = "Solving Captcha..."
            else:
                self.bot.hunting_status = "Captcha Pending (manual)"
        elif channel_id == self.config.fishing_channel_id:
            if bool(getattr(self.config, "captcha_auto_answer_enabled", True)):
                self.bot.fishing_status = "Solving Captcha..."
            else:
                self.bot.fishing_status = "Captcha Pending (manual)"
        elif channel_id == self.config.autofight_channel_id:
            if bool(getattr(self.config, "captcha_auto_answer_enabled", True)):
                self.bot.autofight_status = "Paused (captcha solving)"
            else:
                self.bot.autofight_status = "Paused (captcha manual)"

        await self.bot.log()
        await self._attempt_auto_solver(after, source="on_message_edit")
