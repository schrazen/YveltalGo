from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("pokegrinder.quest_catalog")

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
CATALOG_FILE = DATA_DIR / "quest_catalog.json"
LOGS_DIR = BASE_DIR / "logs"

_catalog_lock = threading.RLock()

# Pre-seeded comprehensive knowledge base of all known PokéMeow quest templates
DEFAULT_QUEST_CATALOG: list[dict[str, Any]] = [
    # --- Mega Chamber (Impossible for standard grinding bot) ---
    {
        "id": "mega_chamber_defeat",
        "title": "Defeat Mega Chambers",
        "pattern": r"\b(defeat|complete|win)\b.*\bmega\s*chambers?\b|\bmega\s*chamber\b",
        "category": "mega_chamber",
        "description": "Challenging Mega Chamber dungeon. Requires dedicated Mega team and tickets; impossible for standard grinding.",
        "doable_auto": False,
        "is_impossible": True,
        "action": "auto_reset",
        "default_action": "auto_reset",
        "battle_mode": None,
        "times_seen": 0,
        "last_seen_utc": "",
        "sample_titles": [],
        "is_custom": False,
    },
    # --- Challengers & Battles (Doable via AutoFight) ---
    {
        "id": "defeat_basic_challenger",
        "title": "Defeat a Basic Challenger",
        "pattern": r"\bdefeats?\b.*\bbasic challenger\b",
        "category": "battle",
        "description": "Defeat Basic Challenger (Steven, ID 210) via ;battle npc 210.",
        "doable_auto": True,
        "is_impossible": False,
        "action": "auto_complete",
        "default_action": "auto_complete",
        "battle_mode": "npc 210",
        "times_seen": 0,
        "last_seen_utc": "",
        "sample_titles": [],
        "is_custom": False,
    },
    {
        "id": "defeat_master_challenger",
        "title": "Defeat a Master Challenger",
        "pattern": r"\bdefeats?\b.*\bmaster challenger\b",
        "category": "battle",
        "description": "Defeat Master tier Challenger NPC via ;battle npc in the battle channel.",
        "doable_auto": True,
        "is_impossible": False,
        "action": "auto_complete",
        "default_action": "auto_complete",
        "battle_mode": "master_challenger",
        "times_seen": 0,
        "last_seen_utc": "",
        "sample_titles": [],
        "is_custom": False,
    },
    {
        "id": "defeat_elite_challenger",
        "title": "Defeat an Elite Challenger",
        "pattern": r"\bdefeats?\b.*\belite challenger\b",
        "category": "battle",
        "description": "Defeat Elite tier Challenger NPC via ;battle npc in the battle channel.",
        "doable_auto": True,
        "is_impossible": False,
        "action": "auto_complete",
        "default_action": "auto_complete",
        "battle_mode": "elite_challenger",
        "times_seen": 0,
        "last_seen_utc": "",
        "sample_titles": [],
        "is_custom": False,
    },
    {
        "id": "defeat_champion_challenger",
        "title": "Defeat a Champion Challenger",
        "pattern": r"\bdefeats?\b.*\bchampion challenger\b",
        "category": "battle",
        "description": "Defeat Champion tier Challenger NPC via ;battle npc in the battle channel.",
        "doable_auto": True,
        "is_impossible": False,
        "action": "auto_complete",
        "default_action": "auto_complete",
        "battle_mode": "champion_challenger",
        "times_seen": 0,
        "last_seen_utc": "",
        "sample_titles": [],
        "is_custom": False,
    },
    {
        "id": "defeat_general_challengers",
        "title": "Defeat Challengers in battle",
        "pattern": r"\bdefeats?\b.*\bchallengers?\b",
        "category": "battle",
        "description": "Defeat one or more challengers via ;battle npc 210.",
        "doable_auto": True,
        "is_impossible": False,
        "action": "auto_complete",
        "default_action": "auto_complete",
        "battle_mode": "npc 210",
        "times_seen": 0,
        "last_seen_utc": "",
        "sample_titles": [],
        "is_custom": False,
    },
    {
        "id": "win_challenger_battles",
        "title": "Win Challenger battles",
        "pattern": r"\bwins?\b.*\bchallengers?\b",
        "category": "battle",
        "description": "Win one or more challenger battles via ;battle npc 210.",
        "doable_auto": True,
        "is_impossible": False,
        "action": "auto_complete",
        "default_action": "auto_complete",
        "battle_mode": "npc 210",
        "times_seen": 0,
        "last_seen_utc": "",
        "sample_titles": [],
        "is_custom": False,
    },
    {
        "id": "defeat_npcs",
        "title": "Defeat NPCs in battle",
        "pattern": r"\bdefeats?\b.*\bnpcs?\b|\bnpcs?\b.*\bdefeats?\b",
        "category": "battle",
        "description": "Defeat NPC trainers (;battle / ;npc 1) in the designated battle channel.",
        "doable_auto": True,
        "is_impossible": False,
        "action": "auto_complete",
        "default_action": "auto_complete",
        "battle_mode": "npc 1",
        "times_seen": 0,
        "last_seen_utc": "",
        "sample_titles": [],
        "is_custom": False,
    },
    {
        "id": "defeat_trainers",
        "title": "Defeat Trainers in battle",
        "pattern": r"\bdefeats?\b.*\btrainers?\b|\btrainers?\b.*\bdefeats?\b",
        "category": "battle",
        "description": "Defeat trainer opponents in battle.",
        "doable_auto": True,
        "is_impossible": False,
        "action": "auto_complete",
        "default_action": "auto_complete",
        "battle_mode": "npc 1",
        "times_seen": 0,
        "last_seen_utc": "",
        "sample_titles": [],
        "is_custom": False,
    },
    {
        "id": "win_trainer_battles",
        "title": "Win Trainer/NPC battles",
        "pattern": r"\bwins?\b.*\b(trainers?|npcs?|battles?)\b",
        "category": "battle",
        "description": "Win standard trainer or NPC battles.",
        "doable_auto": True,
        "is_impossible": False,
        "action": "auto_complete",
        "default_action": "auto_complete",
        "battle_mode": "npc 1",
        "times_seen": 0,
        "last_seen_utc": "",
        "sample_titles": [],
        "is_custom": False,
    },
    {
        "id": "defeat_pokemon_battle",
        "title": "Defeat Pokemon in battle",
        "pattern": r"\bdefeats?\b.*\bpokemon in battle\b|\bdefeats?\b\s*\d+\s*pokemon\b",
        "category": "battle",
        "description": "Knock out enemy Pokemon in battle.",
        "doable_auto": True,
        "is_impossible": False,
        "action": "auto_complete",
        "default_action": "auto_complete",
        "battle_mode": "npc 1",
        "times_seen": 0,
        "last_seen_utc": "",
        "sample_titles": [],
        "is_custom": False,
    },
    # --- Wild Encounters & Catches (Completed via Hunting) ---
    {
        "id": "encounter_wild_pokemon",
        "title": "Encounter Pokemon in the wild",
        "pattern": r"\bencounters?\b.*\bpokemon\b",
        "category": "wild_catch",
        "description": "Encounter wild Pokemon via hunting commands (;pokemon / /pokemon).",
        "doable_auto": True,
        "is_impossible": False,
        "action": "auto_complete",
        "default_action": "auto_complete",
        "battle_mode": None,
        "times_seen": 0,
        "last_seen_utc": "",
        "sample_titles": [],
        "is_custom": False,
    },
    {
        "id": "catch_any_pokemon",
        "title": "Catch Pokemon",
        "pattern": r"\bcatch\b\s*\d*\s*pokemon\b",
        "category": "wild_catch",
        "description": "Catch any wild Pokemon during normal hunting grinding.",
        "doable_auto": True,
        "is_impossible": False,
        "action": "auto_complete",
        "default_action": "auto_complete",
        "battle_mode": None,
        "times_seen": 0,
        "last_seen_utc": "",
        "sample_titles": [],
        "is_custom": False,
    },
    {
        "id": "catch_common_pokemon",
        "title": "Catch Common Pokemon",
        "pattern": r"\bcatch\b.*\bcommon\b",
        "category": "wild_catch",
        "description": "Catch Common tier Pokemon in wild encounters.",
        "doable_auto": True,
        "is_impossible": False,
        "action": "auto_complete",
        "default_action": "auto_complete",
        "battle_mode": None,
        "times_seen": 0,
        "last_seen_utc": "",
        "sample_titles": [],
        "is_custom": False,
    },
    {
        "id": "catch_uncommon_pokemon",
        "title": "Catch Uncommon Pokemon",
        "pattern": r"\bcatch\b.*\buncommon\b",
        "category": "wild_catch",
        "description": "Catch Uncommon tier Pokemon in wild encounters.",
        "doable_auto": True,
        "is_impossible": False,
        "action": "auto_complete",
        "default_action": "auto_complete",
        "battle_mode": None,
        "times_seen": 0,
        "last_seen_utc": "",
        "sample_titles": [],
        "is_custom": False,
    },
    {
        "id": "catch_rare_pokemon",
        "title": "Catch Rare Pokemon",
        "pattern": r"\bcatch\b.*\brare\b",
        "category": "wild_catch",
        "description": "Catch Rare tier Pokemon in wild encounters.",
        "doable_auto": True,
        "is_impossible": False,
        "action": "auto_complete",
        "default_action": "auto_complete",
        "battle_mode": None,
        "times_seen": 0,
        "last_seen_utc": "",
        "sample_titles": [],
        "is_custom": False,
    },
    {
        "id": "catch_super_rare_pokemon",
        "title": "Catch Super Rare Pokemon",
        "pattern": r"\bcatch\b.*\bsuper rare\b",
        "category": "wild_catch",
        "description": "Catch Super Rare tier Pokemon in wild encounters.",
        "doable_auto": True,
        "is_impossible": False,
        "action": "auto_complete",
        "default_action": "auto_complete",
        "battle_mode": None,
        "times_seen": 0,
        "last_seen_utc": "",
        "sample_titles": [],
        "is_custom": False,
    },
    {
        "id": "catch_legendary_pokemon",
        "title": "Catch Legendary Pokemon",
        "pattern": r"\bcatch\b.*\blegendary\b",
        "category": "wild_catch",
        "description": "Catch Legendary tier Pokemon. Rare encounter rate.",
        "doable_auto": False,
        "is_impossible": False,
        "action": "ignore",
        "default_action": "ignore",
        "battle_mode": None,
        "times_seen": 0,
        "last_seen_utc": "",
        "sample_titles": [],
        "is_custom": False,
    },
    {
        "id": "catch_shiny_pokemon",
        "title": "Catch Shiny Pokemon",
        "pattern": r"\bcatch\b.*\bshiny\b",
        "category": "wild_catch",
        "description": "Catch Shiny Pokemon (1/8192 base rate; impossible to reliably finish in a single day).",
        "doable_auto": False,
        "is_impossible": True,
        "action": "auto_reset",
        "default_action": "auto_reset",
        "battle_mode": None,
        "times_seen": 0,
        "last_seen_utc": "",
        "sample_titles": [],
        "is_custom": False,
    },
    {
        "id": "catch_typed_pokemon",
        "title": "Catch [Type] Pokemon",
        "pattern": r"\bcatch\b.*\b(water|fire|grass|electric|normal|ice|fighting|poison|ground|flying|psychic|bug|rock|ghost|dark|steel|dragon|fairy)[ -]type\b",
        "category": "wild_catch",
        "description": "Catch Pokemon of a specific elemental type (e.g. Water, Fire, Grass).",
        "doable_auto": True,
        "is_impossible": False,
        "action": "auto_complete",
        "default_action": "auto_complete",
        "battle_mode": None,
        "times_seen": 0,
        "last_seen_utc": "",
        "sample_titles": [],
        "is_custom": False,
    },
    {
        "id": "catch_with_pokeball",
        "title": "Catch Pokemon with Poke Ball",
        "pattern": r"\bcatch\b.*\bpoke\s*balls?\b",
        "category": "wild_catch",
        "description": "Catch wild Pokemon using regular Poke Balls.",
        "doable_auto": True,
        "is_impossible": False,
        "action": "auto_complete",
        "default_action": "auto_complete",
        "battle_mode": None,
        "times_seen": 0,
        "last_seen_utc": "",
        "sample_titles": [],
        "is_custom": False,
    },
    {
        "id": "catch_with_greatball",
        "title": "Catch Pokemon with Great Ball",
        "pattern": r"\bcatch\b.*\bgreat\s*balls?\b",
        "category": "wild_catch",
        "description": "Catch wild Pokemon using Great Balls.",
        "doable_auto": True,
        "is_impossible": False,
        "action": "auto_complete",
        "default_action": "auto_complete",
        "battle_mode": None,
        "times_seen": 0,
        "last_seen_utc": "",
        "sample_titles": [],
        "is_custom": False,
    },
    {
        "id": "catch_with_ultraball",
        "title": "Catch Pokemon with Ultra Ball",
        "pattern": r"\bcatch\b.*\bultra\s*balls?\b",
        "category": "wild_catch",
        "description": "Catch wild Pokemon using Ultra Balls.",
        "doable_auto": True,
        "is_impossible": False,
        "action": "auto_complete",
        "default_action": "auto_complete",
        "battle_mode": None,
        "times_seen": 0,
        "last_seen_utc": "",
        "sample_titles": [],
        "is_custom": False,
    },
    # --- Fishing ---
    {
        "id": "fish_times",
        "title": "Fish / Cast Rod",
        "pattern": r"\b(fish|cast.*rod)\b",
        "category": "fishing",
        "description": "Cast fishing rod in fishing channel (;fish).",
        "doable_auto": True,
        "is_impossible": False,
        "action": "auto_complete",
        "default_action": "auto_complete",
        "battle_mode": None,
        "times_seen": 0,
        "last_seen_utc": "",
        "sample_titles": [],
        "is_custom": False,
    },
    {
        "id": "catch_fish_water",
        "title": "Catch Fish / Water Pokemon",
        "pattern": r"\bcatch\b.*\bfish\b|\bcatch\b.*\bwhile fishing\b",
        "category": "fishing",
        "description": "Catch fish and water Pokemon while fishing.",
        "doable_auto": True,
        "is_impossible": False,
        "action": "auto_complete",
        "default_action": "auto_complete",
        "battle_mode": None,
        "times_seen": 0,
        "last_seen_utc": "",
        "sample_titles": [],
        "is_custom": False,
    },
    # --- Eggs & Daycare ---
    {
        "id": "hatch_eggs",
        "title": "Hatch Eggs",
        "pattern": r"\bhatch\b.*\beggs?\b",
        "category": "eggs",
        "description": "Hatch eggs from the Daycare.",
        "doable_auto": True,
        "is_impossible": False,
        "action": "auto_complete",
        "default_action": "auto_complete",
        "battle_mode": None,
        "times_seen": 0,
        "last_seen_utc": "",
        "sample_titles": [],
        "is_custom": False,
    },
    # --- Economy & Management ---
    {
        "id": "release_pokemon",
        "title": "Release Pokemon",
        "pattern": r"\brelease\b.*\bpokemon\b",
        "category": "economy",
        "description": "Release duplicate or unwanted Pokemon (;release).",
        "doable_auto": False,
        "is_impossible": False,
        "action": "ignore",
        "default_action": "ignore",
        "battle_mode": None,
        "times_seen": 0,
        "last_seen_utc": "",
        "sample_titles": [],
        "is_custom": False,
    },
    {
        "id": "swap_pokemon",
        "title": "Swap Pokemon",
        "pattern": r"\bswap\b.*\bpokemon\b",
        "category": "economy",
        "description": "Swap Pokemon (;swap).",
        "doable_auto": False,
        "is_impossible": False,
        "action": "ignore",
        "default_action": "ignore",
        "battle_mode": None,
        "times_seen": 0,
        "last_seen_utc": "",
        "sample_titles": [],
        "is_custom": False,
    },
    {
        "id": "trade_pokemon",
        "title": "Trade Pokemon",
        "pattern": r"\btrade\b.*\bpokemon\b",
        "category": "economy",
        "description": "Trade Pokemon with another player.",
        "doable_auto": False,
        "is_impossible": False,
        "action": "ignore",
        "default_action": "ignore",
        "battle_mode": None,
        "times_seen": 0,
        "last_seen_utc": "",
        "sample_titles": [],
        "is_custom": False,
    },
    {
        "id": "open_lootbox",
        "title": "Open Lootbox",
        "pattern": r"\bopen\b.*\bloot\s*box(es)?\b",
        "category": "economy",
        "description": "Open lootboxes (;lb open).",
        "doable_auto": False,
        "is_impossible": False,
        "action": "ignore",
        "default_action": "ignore",
        "battle_mode": None,
        "times_seen": 0,
        "last_seen_utc": "",
        "sample_titles": [],
        "is_custom": False,
    },
    {
        "id": "buy_shop_items",
        "title": "Buy items from Shop",
        "pattern": r"\bbuy\b.*\b(shop|items?)\b",
        "category": "economy",
        "description": "Purchase items from the in-game shop.",
        "doable_auto": False,
        "is_impossible": False,
        "action": "ignore",
        "default_action": "ignore",
        "battle_mode": None,
        "times_seen": 0,
        "last_seen_utc": "",
        "sample_titles": [],
        "is_custom": False,
    },
]

CATEGORIES_META: dict[str, dict[str, str]] = {
    "mega_chamber": {"label": "Mega Chamber", "icon": "💥", "color": "amber"},
    "battle": {"label": "Challengers & Battling", "icon": "⚔️", "color": "rose"},
    "wild_catch": {"label": "Wild Encounters & Catches", "icon": "🌲", "color": "emerald"},
    "fishing": {"label": "Fishing & Water", "icon": "🎣", "color": "cyan"},
    "eggs": {"label": "Breeding & Eggs", "icon": "🥚", "color": "yellow"},
    "economy": {"label": "Economy & Management", "icon": "🔄", "color": "purple"},
    "custom": {"label": "Custom Rules", "icon": "⚙️", "color": "slate"},
}


class QuestCatalog:
    """Manages PokéMeow quest templates, runtime matching, and persistent user automation rules."""

    def __init__(self, catalog_path: Path = CATALOG_FILE) -> None:
        self.catalog_path = catalog_path
        self._items: list[dict[str, Any]] = []
        self._load()

    def _ensure_data_dir(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    def _load(self) -> None:
        with _catalog_lock:
            self._ensure_data_dir()
            if not self.catalog_path.exists():
                self._items = [dict(item) for item in DEFAULT_QUEST_CATALOG]
                self._save()
                return

            try:
                raw = json.loads(self.catalog_path.read_text(encoding="utf-8"))
                if isinstance(raw, list):
                    # Merge with default catalog to ensure any newly added defaults are present
                    existing_by_id = {item.get("id"): item for item in raw if isinstance(item, dict) and item.get("id")}
                    merged: list[dict[str, Any]] = []

                    for def_item in DEFAULT_QUEST_CATALOG:
                        def_id = def_item["id"]
                        if def_id in existing_by_id:
                            # Preserve user customizations (action, times_seen, last_seen_utc, sample_titles)
                            cur = existing_by_id.pop(def_id)
                            item_copy = dict(def_item)
                            item_copy["action"] = cur.get("action", def_item["action"])
                            item_copy["times_seen"] = int(cur.get("times_seen", 0) or 0)
                            item_copy["last_seen_utc"] = cur.get("last_seen_utc", "")
                            item_copy["sample_titles"] = list(cur.get("sample_titles") or [])
                            if item_copy.get("battle_mode") == "challenger":
                                item_copy["battle_mode"] = "npc 210"
                            merged.append(item_copy)
                        else:
                            merged.append(dict(def_item))

                    # Retain any remaining items (e.g. user custom rules or auto-discovered rules)
                    for remaining_id, remaining_item in existing_by_id.items():
                        if remaining_item.get("battle_mode") == "challenger":
                            remaining_item["battle_mode"] = "npc 210"
                        merged.append(remaining_item)

                    self._items = merged
                else:
                    self._items = [dict(item) for item in DEFAULT_QUEST_CATALOG]
                    self._save()
            except Exception as exc:
                logger.error(f"[QuestCatalog] Failed loading {self.catalog_path}: {exc}. Using defaults.")
                self._items = [dict(item) for item in DEFAULT_QUEST_CATALOG]

    def _save(self) -> None:
        with _catalog_lock:
            try:
                self._ensure_data_dir()
                self.catalog_path.write_text(json.dumps(self._items, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception as exc:
                logger.error(f"[QuestCatalog] Failed saving {self.catalog_path}: {exc}")

    def get_catalog(self) -> list[dict[str, Any]]:
        with _catalog_lock:
            return [dict(item) for item in self._items]

    def get_stats(self) -> dict[str, Any]:
        with _catalog_lock:
            total = len(self._items)
            auto_complete = sum(1 for it in self._items if it.get("action") == "auto_complete")
            auto_reset = sum(1 for it in self._items if it.get("action") == "auto_reset")
            ignore = sum(1 for it in self._items if it.get("action") == "ignore")
            observed_total = sum(int(it.get("times_seen", 0) or 0) for it in self._items)
            observed_types = sum(1 for it in self._items if int(it.get("times_seen", 0) or 0) > 0)
            return {
                "total_quests": total,
                "auto_complete_count": auto_complete,
                "auto_reset_count": auto_reset,
                "ignore_count": ignore,
                "observed_total": observed_total,
                "observed_types": observed_types,
            }

    def update_rule(self, quest_id: str, action: str) -> bool:
        """Update the automation action for a quest ('auto_complete', 'auto_reset', 'ignore')."""
        action = str(action or "").lower().strip()
        if action not in ("auto_complete", "auto_reset", "ignore"):
            return False

        with _catalog_lock:
            found = False
            for item in self._items:
                if item.get("id") == quest_id:
                    item["action"] = action
                    found = True
                    break

            if found:
                self._save()
                return True
            return False

    def add_custom_rule(
        self,
        title: str,
        pattern: str,
        category: str = "custom",
        action: str = "auto_reset",
        description: str = "",
        battle_mode: str | None = None,
    ) -> dict[str, Any] | None:
        title = str(title or "").strip()
        pattern = str(pattern or "").strip()
        if not title or not pattern:
            return None

        clean_slug = re.sub(r"[^\w]+", "_", title.lower()).strip("_")
        custom_id = f"custom_{clean_slug}_{int(time.time())}"

        with _catalog_lock:
            new_item: dict[str, Any] = {
                "id": custom_id,
                "title": title,
                "pattern": pattern,
                "category": category if category in CATEGORIES_META else "custom",
                "description": description or f"Custom rule for '{title}'",
                "doable_auto": bool(battle_mode or category == "battle"),
                "is_impossible": action == "auto_reset",
                "action": action if action in ("auto_complete", "auto_reset", "ignore") else "auto_reset",
                "default_action": action,
                "battle_mode": battle_mode,
                "times_seen": 0,
                "last_seen_utc": "",
                "sample_titles": [],
                "is_custom": True,
            }
            self._items.insert(0, new_item)
            self._save()
            return new_item

    def delete_rule(self, quest_id: str) -> bool:
        with _catalog_lock:
            orig_len = len(self._items)
            self._items = [it for it in self._items if it.get("id") != quest_id or not it.get("is_custom")]
            if len(self._items) < orig_len:
                self._save()
                return True
            return False

    def reset_defaults(self) -> None:
        with _catalog_lock:
            self._items = [dict(item) for item in DEFAULT_QUEST_CATALOG]
            self._save()

    def register_observed_quest(self, raw_title: str) -> dict[str, Any]:
        """Record an observed quest from live discord messages or logs.
        Updates observation counts and samples. If quest is unseen, dynamically adds it.
        """
        title = str(raw_title or "").strip()
        if not title:
            return {}

        now_utc = datetime.now(timezone.utc).isoformat()
        with _catalog_lock:
            # Try to match against existing rules
            matched_item = None
            for item in self._items:
                pat = item.get("pattern", "")
                try:
                    if re.search(pat, title, re.IGNORECASE):
                        matched_item = item
                        break
                except Exception:
                    pass

            if matched_item is not None:
                matched_item["times_seen"] = int(matched_item.get("times_seen", 0) or 0) + 1
                matched_item["last_seen_utc"] = now_utc
                samples = list(matched_item.get("sample_titles") or [])
                if title not in samples:
                    samples.append(title)
                    matched_item["sample_titles"] = samples[:8]
                self._save()
                return matched_item

            # If not matched, auto-discover and create a new catalog entry!
            is_mega = "mega chamber" in title.lower() or "megachamber" in title.lower()
            is_challenger = "challenger" in title.lower()
            is_battle = is_challenger or bool(re.search(r"\b(battle|npc|trainer)\b", title, re.IGNORECASE))
            is_fish = bool(re.search(r"\b(fish|rod)\b", title, re.IGNORECASE))
            is_egg = bool(re.search(r"\b(hatch|egg)\b", title, re.IGNORECASE))

            cat = "wild_catch"
            action = "auto_complete"
            b_mode = None

            if is_mega:
                cat = "mega_chamber"
                action = "auto_reset"
            elif is_challenger:
                cat = "battle"
                action = "auto_complete"
                b_mode = "challenger"
            elif is_battle:
                cat = "battle"
                action = "auto_complete"
                b_mode = "npc 1"
            elif is_fish:
                cat = "fishing"
                action = "auto_complete"
            elif is_egg:
                cat = "eggs"
                action = "auto_complete"

            slug = re.sub(r"[^\w]+", "_", title.lower()).strip("_")
            auto_id = f"auto_{slug[:30]}_{int(time.time())}"

            new_entry: dict[str, Any] = {
                "id": auto_id,
                "title": title,
                "pattern": re.escape(title),
                "category": cat,
                "description": f"Auto-discovered PokéMeow quest: '{title}'",
                "doable_auto": bool(b_mode or cat in ("battle", "wild_catch", "fishing")),
                "is_impossible": is_mega,
                "action": action,
                "default_action": action,
                "battle_mode": b_mode,
                "times_seen": 1,
                "last_seen_utc": now_utc,
                "sample_titles": [title],
                "is_custom": False,
            }
            self._items.append(new_entry)
            self._save()
            return new_entry

    def resolve_quest_action(self, title: str) -> dict[str, Any]:
        """Resolves the user's configured automation action for a given quest title.

        Returns dict with:
            action: 'auto_reset' | 'auto_complete' | 'ignore'
            matched_id: str
            matched_title: str
            category: str
            is_impossible: bool
            doable_auto: bool
            battle_mode: str | None ('challenger' | 'npc 1' | None)
        """
        raw = str(title or "").strip()
        if not raw:
            return {
                "action": "ignore",
                "matched_id": "",
                "matched_title": "",
                "category": "unknown",
                "is_impossible": False,
                "doable_auto": False,
                "battle_mode": None,
            }

        with _catalog_lock:
            # Custom rules take precedence
            for item in self._items:
                if not item.get("is_custom"):
                    continue
                pat = item.get("pattern", "")
                try:
                    if re.search(pat, raw, re.IGNORECASE):
                        return {
                            "action": item.get("action", "ignore"),
                            "matched_id": item.get("id", ""),
                            "matched_title": item.get("title", ""),
                            "category": item.get("category", "custom"),
                            "is_impossible": bool(item.get("is_impossible", False)),
                            "doable_auto": bool(item.get("doable_auto", False)),
                            "battle_mode": item.get("battle_mode"),
                        }
                except Exception:
                    pass

            # Standard rules
            for item in self._items:
                if item.get("is_custom"):
                    continue
                pat = item.get("pattern", "")
                try:
                    if re.search(pat, raw, re.IGNORECASE):
                        return {
                            "action": item.get("action", "auto_complete"),
                            "matched_id": item.get("id", ""),
                            "matched_title": item.get("title", ""),
                            "category": item.get("category", "wild_catch"),
                            "is_impossible": bool(item.get("is_impossible", False)),
                            "doable_auto": bool(item.get("doable_auto", True)),
                            "battle_mode": item.get("battle_mode"),
                        }
                except Exception:
                    pass

        # Fallback heuristic if somehow uncataloged
        lowered = raw.lower()
        if "mega chamber" in lowered or "megachamber" in lowered or "shiny" in lowered:
            return {
                "action": "auto_reset",
                "matched_id": "fallback_impossible",
                "matched_title": raw,
                "category": "mega_chamber",
                "is_impossible": True,
                "doable_auto": False,
                "battle_mode": None,
            }

        if "challenger" in lowered:
            return {
                "action": "auto_complete",
                "matched_id": "fallback_challenger",
                "matched_title": raw,
                "category": "battle",
                "is_impossible": False,
                "doable_auto": True,
                "battle_mode": "challenger",
            }

        if any(w in lowered for w in ("battle", "npc", "trainer")):
            return {
                "action": "auto_complete",
                "matched_id": "fallback_battle",
                "matched_title": raw,
                "category": "battle",
                "is_impossible": False,
                "doable_auto": True,
                "battle_mode": "npc 1",
            }

        return {
            "action": "auto_complete",
            "matched_id": "fallback_default",
            "matched_title": raw,
            "category": "wild_catch",
            "is_impossible": False,
            "doable_auto": True,
            "battle_mode": None,
        }

    def scan_historical_logs(self) -> dict[str, Any]:
        """Harvests past quest entries from log files."""
        discovered: list[str] = []
        now_utc = datetime.now(timezone.utc).isoformat()

        # 1. Harvest from logs/pokemeow_events.jsonl
        events_file = LOGS_DIR / "pokemeow_events.jsonl"
        if events_file.exists():
            try:
                with events_file.open("r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            item = json.loads(line)
                            cat = item.get("category")
                            raw_text = item.get("raw_text", "")
                            # Check quest_complete events
                            if cat == "quest_complete" or "completed the quest" in raw_text:
                                m = re.search(r"completed the quest\s+(.+?)\s+and received:", raw_text, re.IGNORECASE)
                                if m:
                                    q_name = m.group(1).strip()
                                    if q_name:
                                        discovered.append(q_name)

                            # Check quest_board events
                            if cat == "quest_board" or "Quest #" in raw_text:
                                parts = re.split(r"Quest\s*#\d+:", raw_text, flags=re.IGNORECASE)
                                for p in parts[1:]:
                                    title_part = re.split(r">\s*.*Rewards:", p, flags=re.IGNORECASE)
                                    if title_part:
                                        clean_t = re.sub(r"^[^\w]+", "", title_part[0]).strip()
                                        if clean_t:
                                            discovered.append(clean_t)

                                nq_m = re.search(r"your next quest is\s*(?:[^\w\s]*\s*)*([^!]+!?)", raw_text, re.IGNORECASE)
                                if nq_m:
                                    nq = re.sub(r"^[^\w]+", "", nq_m.group(1)).strip()
                                    nq = re.split(r"complete your quests", nq, flags=re.IGNORECASE)[0].strip()
                                    if nq:
                                        discovered.append(nq)
                        except Exception:
                            continue
            except Exception as exc:
                logger.error(f"[QuestCatalog] Error scanning {events_file}: {exc}")

        # 2. Harvest from pokegrinder_runtime.log
        runtime_log = LOGS_DIR / "pokegrinder_runtime.log"
        if runtime_log.exists():
            try:
                with runtime_log.open("r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if "[QuestManager]" not in line:
                            continue
                        # Look for quest names in quotes
                        matches = re.findall(r"['\"]([^'\"]*?(?:quest|chamber|challenger|battle|defeat|catch|encounter)[^'\"]*?)['\"]", line, re.IGNORECASE)
                        for q in matches:
                            clean_q = q.strip()
                            if len(clean_q) > 4 and not clean_q.startswith("impossible_quest:"):
                                discovered.append(clean_q)
            except Exception as exc:
                logger.error(f"[QuestCatalog] Error scanning {runtime_log}: {exc}")

        # Register all discovered quests
        unique_discovered = sorted(set(discovered))
        for q_title in unique_discovered:
            self.register_observed_quest(q_title)

        stats = self.get_stats()
        return {
            "ok": True,
            "harvested_count": len(discovered),
            "unique_harvested_count": len(unique_discovered),
            "unique_samples": unique_discovered[:10],
            "stats": stats,
        }


# Singleton instance
quest_catalog = QuestCatalog()
