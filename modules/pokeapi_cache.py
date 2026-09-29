from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import aiohttp
import aiosqlite

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "pokeapi_cache.sqlite3"
_POKEMON_ENDPOINT = "https://pokeapi.co/api/v2/pokemon/"
_MOVE_ENDPOINT = "https://pokeapi.co/api/v2/move/"
_session: aiohttp.ClientSession | None = None
_db_init_lock = asyncio.Lock()
_db_initialized = False


def _safe_json_loads(raw: str | None, fallback: Any) -> Any:
    try:
        return json.loads(raw or "")
    except Exception:
        return fallback


def _normalize_name(name: str) -> str:
    value = str(name or "").strip().lower().replace("_", " ")
    if not value:
        return ""

    # Keep only alphanumerics, spaces, and hyphens for stable token parsing.
    cleaned = "".join(ch if (ch.isalnum() or ch in {" ", "-"}) else " " for ch in value)
    tokens = [tok for tok in cleaned.replace("-", " ").split() if tok]
    if not tokens:
        return ""

    # PokeAPI form ids differ from display names for common prefixes/suffixes.
    if tokens[0] == "mega" and len(tokens) >= 2:
        base_tokens = tokens[1:]
        suffix = ""
        if base_tokens and base_tokens[-1] in {"x", "y"}:
            suffix = f"-{base_tokens[-1]}"
            base_tokens = base_tokens[:-1]
        if base_tokens:
            return f"{'-'.join(base_tokens)}-mega{suffix}"
    if tokens[0] == "primal" and len(tokens) >= 2:
        return f"{'-'.join(tokens[1:])}-primal"
    if tokens[0] == "alolan" and len(tokens) >= 2:
        return f"{'-'.join(tokens[1:])}-alola"
    if tokens[-1] == "alolan" and len(tokens) >= 2:
        return f"{'-'.join(tokens[:-1])}-alola"
    if tokens[0] == "galarian" and len(tokens) >= 2:
        return f"{'-'.join(tokens[1:])}-galar"
    if tokens[-1] == "galarian" and len(tokens) >= 2:
        return f"{'-'.join(tokens[:-1])}-galar"
    if tokens[0] == "hisuian" and len(tokens) >= 2:
        return f"{'-'.join(tokens[1:])}-hisui"
    if tokens[-1] == "hisuian" and len(tokens) >= 2:
        return f"{'-'.join(tokens[:-1])}-hisui"

    return "-".join(tokens)


async def _ensure_db() -> None:
    global _db_initialized
    if _db_initialized:
        return

    async with _db_init_lock:
        if _db_initialized:
            return
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS pokemon (
                        name TEXT PRIMARY KEY,
                        types TEXT NOT NULL,
                        stats TEXT NOT NULL,
                        abilities TEXT NOT NULL DEFAULT '[]',
                        movepool TEXT NOT NULL,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                async with db.execute("PRAGMA table_info(pokemon)") as cur:
                    columns = await cur.fetchall()
                col_names = {str(row[1]).strip().lower() for row in (columns or []) if len(row) > 1}
                if "abilities" not in col_names:
                    await db.execute("ALTER TABLE pokemon ADD COLUMN abilities TEXT NOT NULL DEFAULT '[]'")
                await db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS moves (
                        name TEXT PRIMARY KEY,
                        type TEXT NOT NULL,
                        damage_class TEXT NOT NULL,
                        power INTEGER NOT NULL,
                        accuracy INTEGER NOT NULL,
                        priority INTEGER NOT NULL,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                await db.commit()
            _db_initialized = True
        except Exception:
            _db_initialized = False


async def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        timeout = aiohttp.ClientTimeout(total=8)
        _session = aiohttp.ClientSession(timeout=timeout, headers={"User-Agent": "PokeGrinder/AutoFight"})
    return _session


async def _http_json(url: str) -> dict[str, Any] | None:
    try:
        session = await _get_session()
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            return await resp.json(content_type=None)
    except Exception:
        return None


async def get_pokemon_brief(name: str) -> dict[str, Any] | None:
    key = _normalize_name(name)
    if not key:
        return None

    await _ensure_db()
    if _db_initialized:
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("SELECT name, types, stats, abilities, movepool FROM pokemon WHERE name = ?", (key,)) as cur:
                    row = await cur.fetchone()
                if row:
                    return {
                        "name": row[0],
                        "types": _safe_json_loads(row[1], []),
                        "stats": _safe_json_loads(row[2], {}),
                        "abilities": _safe_json_loads(row[3], []),
                        "movepool": _safe_json_loads(row[4], []),
                    }
        except Exception:
            pass

    payload = await _http_json(_POKEMON_ENDPOINT + key)
    if not isinstance(payload, dict):
        return None

    types = []
    for item in payload.get("types", []) or []:
        info = item.get("type", {}) if isinstance(item, dict) else {}
        tname = str(info.get("name", "") or "").strip().lower()
        if tname:
            types.append(tname)

    stats: dict[str, int] = {}
    for item in payload.get("stats", []) or []:
        if not isinstance(item, dict):
            continue
        info = item.get("stat", {}) if isinstance(item.get("stat", {}), dict) else {}
        sname = str(info.get("name", "") or "").strip().lower()
        if sname:
            stats[sname] = int(item.get("base_stat", 0) or 0)

    abilities: list[str] = []
    for item in payload.get("abilities", []) or []:
        if not isinstance(item, dict):
            continue
        ainfo = item.get("ability", {}) if isinstance(item.get("ability", {}), dict) else {}
        aname = str(ainfo.get("name", "") or "").strip().lower().replace("-", " ")
        if aname:
            abilities.append(aname)

    movepool: list[str] = []
    for item in payload.get("moves", []) or []:
        minfo = item.get("move", {}) if isinstance(item, dict) else {}
        mname = str(minfo.get("name", "") or "").strip().lower().replace("-", " ")
        if mname:
            movepool.append(mname)

    result = {
        "name": str(payload.get("name", key) or key),
        "types": types,
        "stats": stats,
        "abilities": sorted(set(abilities)),
        "movepool": sorted(set(movepool)),
    }

    if _db_initialized:
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    """
                                        INSERT INTO pokemon(name, types, stats, abilities, movepool, updated_at)
                                        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(name) DO UPDATE SET
                      types = excluded.types,
                      stats = excluded.stats,
                                            abilities = excluded.abilities,
                      movepool = excluded.movepool,
                      updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        key,
                        json.dumps(result["types"], ensure_ascii=True),
                        json.dumps(result["stats"], ensure_ascii=True),
                                                json.dumps(result["abilities"], ensure_ascii=True),
                        json.dumps(result["movepool"], ensure_ascii=True),
                    ),
                )
                await db.commit()
        except Exception:
            pass

    return result


async def get_move_brief(name: str) -> dict[str, Any] | None:
    key = _normalize_name(name)
    if not key:
        return None

    await _ensure_db()
    if _db_initialized:
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT name, type, damage_class, power, accuracy, priority FROM moves WHERE name = ?",
                    (key,),
                ) as cur:
                    row = await cur.fetchone()
                if row:
                    return {
                        "name": row[0],
                        "type": row[1],
                        "damage_class": row[2],
                        "power": int(row[3] or 0),
                        "accuracy": int(row[4] or 0),
                        "priority": int(row[5] or 0),
                    }
        except Exception:
            pass

    payload = await _http_json(_MOVE_ENDPOINT + key.replace(" ", "-"))
    if not isinstance(payload, dict):
        return None

    move_type = str(((payload.get("type") or {}).get("name") or "")).strip().lower()
    damage_class = str(((payload.get("damage_class") or {}).get("name") or "")).strip().lower()
    result = {
        "name": str(payload.get("name", key) or key).replace("-", " "),
        "type": move_type,
        "damage_class": damage_class,
        "power": int(payload.get("power", 0) or 0),
        "accuracy": int(payload.get("accuracy", 0) or 0),
        "priority": int(payload.get("priority", 0) or 0),
    }

    if _db_initialized:
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    """
                    INSERT INTO moves(name, type, damage_class, power, accuracy, priority, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(name) DO UPDATE SET
                      type = excluded.type,
                      damage_class = excluded.damage_class,
                      power = excluded.power,
                      accuracy = excluded.accuracy,
                      priority = excluded.priority,
                      updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        key,
                        result["type"],
                        result["damage_class"],
                        result["power"],
                        result["accuracy"],
                        result["priority"],
                    ),
                )
                await db.commit()
        except Exception:
            pass

    return result
