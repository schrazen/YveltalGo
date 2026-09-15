import asyncio
import re
import time
from random import randint

from discord import InvalidData, Message
from discord.ext import commands

from cogs.startup import Config
from modules.anti_detect_log import record_anti_detect_event
from modules.autofight_log import record_autofight_event
from modules.cloudflare_indicator import notify_cloudflare_in_channel
from modules.pokeapi_cache import get_move_brief, get_pokemon_brief

POKEMEOW_APP_ID = 664508672713424926

_CLOUDFLARE_GUARD_TRIGGER_STRIKES = 3
_CLOUDFLARE_GUARD_COOLDOWN_SECONDS = 600.0

_STAT_TOKENS = {
    "attack": "atk",
    "special-attack": "spa",
    "special attack": "spa",
    "defense": "def",
    "special-defense": "spd",
    "special defense": "spd",
    "speed": "spe",
    "accuracy": "acc",
    "evasion": "eva",
}

_SETUP_MOVE_TO_STATS = {
    "calm mind": {"spa", "spd"},
    "iron defense": {"def"},
    "swords dance": {"atk"},
    "nasty plot": {"spa"},
    "dragon dance": {"atk", "spe"},
    "bulk up": {"atk", "def"},
    "quiver dance": {"spa", "spd", "spe"},
    "agility": {"spe"},
    "harden": {"def"},
    "focus energy": set(),
    "acupressure": {"atk", "def", "spa", "spd", "spe", "acc", "eva"},
    "defense curl": {"def"},
    "charge beam": {"spa"},
    "curse": {"atk", "def"},
}

_SETUP_MOVE_MAX_USES = {
    # User-observed Pokemeow cap behavior.
    "focus energy": 2,
}

_MOVE_HEURISTICS = {
    # Setup
    "swords dance": {"role": "setup", "base_score": 40, "boosts": {"atk": 2}, "tags": ["physical_sweeper"]},
    "nasty plot": {"role": "setup", "base_score": 40, "boosts": {"spa": 2}, "tags": ["special_sweeper"]},
    "dragon dance": {"role": "setup", "base_score": 50, "boosts": {"atk": 1, "spe": 1}, "tags": ["physical_sweeper", "speed_control"]},
    "quiver dance": {"role": "setup", "base_score": 60, "boosts": {"spa": 1, "spd": 1, "spe": 1}, "tags": ["special_sweeper", "speed_control"]},
    "shell smash": {"role": "setup", "base_score": 70, "boosts": {"atk": 2, "spa": 2, "spe": 2}, "tags": ["high_risk_sweeper"]},
    "bulk up": {"role": "setup", "base_score": 40, "boosts": {"atk": 1, "def": 1}, "tags": ["physical_bruiser"]},
    "calm mind": {"role": "setup", "base_score": 40, "boosts": {"spa": 1, "spd": 1}, "tags": ["special_bruiser"]},
    "shift gear": {"role": "setup", "base_score": 55, "boosts": {"atk": 1, "spe": 2}, "tags": ["physical_sweeper", "speed_control"]},
    "geomancy": {"role": "setup", "base_score": 70, "boosts": {"spa": 2, "spd": 1, "spe": 1}, "tags": ["special_sweeper", "speed_control"]},
    "agility": {"role": "setup", "base_score": 30, "boosts": {"spe": 2}, "tags": ["speed_control"]},
    "belly drum": {"role": "setup", "base_score": 80, "boosts": {"atk": 6}, "tags": ["all_in_sweeper"]},
    "iron defense": {"role": "setup", "base_score": 35, "boosts": {"def": 2}, "tags": ["physical_wall"]},
    "acid armor": {"role": "setup", "base_score": 35, "boosts": {"def": 2}, "tags": ["physical_wall"]},
    "amnesia": {"role": "setup", "base_score": 35, "boosts": {"spd": 2}, "tags": ["special_wall"]},
    "cosmic power": {"role": "setup", "base_score": 40, "boosts": {"def": 1, "spd": 1}, "tags": ["mixed_wall"]},
    "cotton guard": {"role": "setup", "base_score": 45, "boosts": {"def": 3}, "tags": ["physical_wall"]},
    "focus energy": {"role": "setup", "base_score": -5, "tags": ["crit_setup", "low_utility"]},

    # Sustain
    "recover": {"role": "sustain", "base_score": 0, "heal_ratio": 0.5, "tags": ["instant_heal"]},
    "roost": {"role": "sustain", "base_score": 0, "heal_ratio": 0.5, "tags": ["instant_heal"]},
    "soft-boiled": {"role": "sustain", "base_score": 0, "heal_ratio": 0.5, "tags": ["instant_heal"]},
    "slack off": {"role": "sustain", "base_score": 0, "heal_ratio": 0.5, "tags": ["instant_heal"]},
    "milk drink": {"role": "sustain", "base_score": 0, "heal_ratio": 0.5, "tags": ["instant_heal"]},
    "synthesis": {"role": "sustain", "base_score": 0, "heal_ratio": 0.5, "tags": ["weather_dependent"]},
    "morning sun": {"role": "sustain", "base_score": 0, "heal_ratio": 0.5, "tags": ["weather_dependent"]},
    "moonlight": {"role": "sustain", "base_score": 0, "heal_ratio": 0.5, "tags": ["weather_dependent"]},
    "shore up": {"role": "sustain", "base_score": 0, "heal_ratio": 0.5, "tags": ["instant_heal"]},

    # Scaling and utility damage
    "stored power": {"role": "damage_scaling", "base_score": 0, "tags": ["requires_setup"]},
    "power trip": {"role": "damage_scaling", "base_score": 0, "tags": ["requires_setup"]},
    "draining kiss": {"role": "damage_sustain", "base_score": 30, "tags": ["healing_attack", "special"]},
    "oblivion wing": {"role": "damage_sustain", "base_score": 30, "tags": ["healing_attack", "special"]},
    "drain punch": {"role": "damage_sustain", "base_score": 25, "tags": ["healing_attack", "physical"]},
    "mega drain": {"role": "damage_sustain", "base_score": 25, "tags": ["healing_attack", "special"]},
    "absorb": {"role": "damage_sustain", "base_score": 20, "tags": ["healing_attack", "special"]},
    "giga drain": {"role": "damage_sustain", "base_score": 25, "tags": ["healing_attack", "special"]},
    "parabolic charge": {"role": "damage_sustain", "base_score": 20, "tags": ["healing_attack", "special", "speed_control"]},
    "horn leech": {"role": "damage_sustain", "base_score": 25, "tags": ["healing_attack", "physical"]},
    "leech life": {"role": "damage_sustain", "base_score": 25, "tags": ["healing_attack", "physical"]},
    "bitter blade": {"role": "damage_sustain", "base_score": 30, "tags": ["healing_attack", "physical"]},
    "facade": {"role": "damage_conditional", "base_score": 0, "tags": ["boosted_if_statused"]},
    "knock off": {"role": "damage_utility", "base_score": 20, "tags": ["removes_item", "high_utility"]},
    "foul play": {"role": "damage_conditional", "base_score": 0, "tags": ["uses_enemy_attack_stat"]},
    "body press": {"role": "damage_conditional", "base_score": 0, "tags": ["uses_user_defense_stat"]},

    # Damage plus debuff
    "acid spray": {"role": "damage_debuff", "base_score": 35, "tags": ["drops_spd_sharply", "bypasses_substitute"]},
    "lumina crash": {"role": "damage_debuff", "base_score": 40, "tags": ["drops_spd_sharply"]},
    "apple acid": {"role": "damage_debuff", "base_score": 30, "tags": ["drops_spd"]},
    "grav apple": {"role": "damage_debuff", "base_score": 30, "tags": ["drops_def"]},
    "fire lash": {"role": "damage_debuff", "base_score": 30, "tags": ["drops_def"]},
    "thunderous kick": {"role": "damage_debuff", "base_score": 30, "tags": ["drops_def"]},
    "lunge": {"role": "damage_debuff", "base_score": 30, "tags": ["drops_atk"]},
    "trop kick": {"role": "damage_debuff", "base_score": 30, "tags": ["drops_atk"]},
    "chilling water": {"role": "damage_debuff", "base_score": 25, "tags": ["drops_atk"]},
    "mystical fire": {"role": "damage_debuff", "base_score": 30, "tags": ["drops_spa"]},
    "snarl": {"role": "damage_debuff", "base_score": 25, "tags": ["drops_spa", "bypasses_substitute"]},
    "skitter smack": {"role": "damage_debuff", "base_score": 30, "tags": ["drops_spa"]},
    "spirit break": {"role": "damage_debuff", "base_score": 30, "tags": ["drops_spa"]},
    "icy wind": {"role": "damage_debuff", "base_score": 25, "tags": ["drops_spe", "speed_control"]},
    "electroweb": {"role": "damage_debuff", "base_score": 25, "tags": ["drops_spe", "speed_control"]},
    "bulldoze": {"role": "damage_debuff", "base_score": 25, "tags": ["drops_spe", "speed_control"]},
    "mud shot": {"role": "damage_debuff", "base_score": 25, "tags": ["drops_spe", "speed_control"]},
    "rock tomb": {"role": "damage_debuff", "base_score": 25, "tags": ["drops_spe", "speed_control"]},
    "low sweep": {"role": "damage_debuff", "base_score": 25, "tags": ["drops_spe", "speed_control"]},
    "pounce": {"role": "damage_debuff", "base_score": 25, "tags": ["drops_spe", "speed_control"]},
    "play rough": {"role": "damage_debuff", "base_score": 10, "tags": ["chance_drop_atk"]},
    "liquidation": {"role": "damage_debuff", "base_score": 10, "tags": ["chance_drop_def"]},
    "crunch": {"role": "damage_debuff", "base_score": 10, "tags": ["chance_drop_def"]},
    "shadow ball": {"role": "damage_debuff", "base_score": 10, "tags": ["chance_drop_spd"]},
    "energy ball": {"role": "damage_debuff", "base_score": 10, "tags": ["chance_drop_spd"]},
    "bug buzz": {"role": "damage_debuff", "base_score": 10, "tags": ["chance_drop_spd"]},
    "earth power": {"role": "damage_debuff", "base_score": 10, "tags": ["chance_drop_spd"]},
    "flash cannon": {"role": "damage_debuff", "base_score": 10, "tags": ["chance_drop_spd"]},
    "focus blast": {"role": "damage_debuff", "base_score": 10, "tags": ["chance_drop_spd", "low_accuracy"]},

    # Damage plus buff
    "power-up punch": {"role": "damage_buff", "base_score": 35, "tags": ["raises_atk"]},
    "meteor mash": {"role": "damage_buff", "base_score": 15, "tags": ["chance_raise_atk"]},
    "metal claw": {"role": "damage_buff", "base_score": 10, "tags": ["chance_raise_atk"]},
    "torch song": {"role": "damage_buff", "base_score": 40, "tags": ["raises_spa", "bypasses_substitute"]},
    "fiery dance": {"role": "damage_buff", "base_score": 30, "tags": ["chance_raise_spa"]},
    "charge beam": {"role": "damage_buff", "base_score": 25, "tags": ["chance_raise_spa"]},
    "flame charge": {"role": "damage_buff", "base_score": 35, "tags": ["raises_spe", "speed_control"]},
    "trailblaze": {"role": "damage_buff", "base_score": 35, "tags": ["raises_spe", "speed_control"]},
    "aqua step": {"role": "damage_buff", "base_score": 40, "tags": ["raises_spe", "speed_control"]},
    "esper wing": {"role": "damage_buff", "base_score": 35, "tags": ["raises_spe", "speed_control"]},
    "rapid spin": {"role": "damage_buff", "base_score": 30, "tags": ["raises_spe", "clears_hazards"]},

    # Utility damage
    "brick break": {"role": "damage_utility", "base_score": 20, "tags": ["breaks_screens"]},
    "psychic fangs": {"role": "damage_utility", "base_score": 20, "tags": ["breaks_screens"]},
    "raging bull": {"role": "damage_utility", "base_score": 20, "tags": ["breaks_screens"]},
    "clear smog": {"role": "damage_utility", "base_score": 35, "tags": ["resets_enemy_stats"]},
    "smack down": {"role": "damage_utility", "base_score": 20, "tags": ["grounds_flying_types"]},

    # Variable damage
    "tera blast": {"role": "damage_variable", "base_score": 0, "tags": ["changes_type_with_tera"]},
    "weather ball": {"role": "damage_variable", "base_score": 0, "tags": ["changes_type_in_weather"]},
    "judgment": {"role": "damage_variable", "base_score": 0, "tags": ["changes_type_with_plate"]},
    "multi-attack": {"role": "damage_variable", "base_score": 0, "tags": ["changes_type_with_memory"]},

    # Lock-in damage
    "uproar": {"role": "damage_lock", "base_score": -10, "tags": ["locks_move_3_turns", "prevents_sleep"]},
    "outrage": {"role": "damage_lock", "base_score": -15, "tags": ["locks_move", "causes_confusion"]},
    "thrash": {"role": "damage_lock", "base_score": -15, "tags": ["locks_move", "causes_confusion"]},
    "petal dance": {"role": "damage_lock", "base_score": -15, "tags": ["locks_move", "causes_confusion"]},
    "rollout": {"role": "damage_lock", "base_score": -20, "tags": ["locks_move", "scales_damage"]},
    "ice ball": {"role": "damage_lock", "base_score": -20, "tags": ["locks_move", "scales_damage"]},

    # Damage plus status
    "sludge": {"role": "damage_status", "base_score": 10, "tags": ["chance_poison"]},
    "sludge bomb": {"role": "damage_status", "base_score": 20, "tags": ["high_chance_poison"]},
    "poison jab": {"role": "damage_status", "base_score": 20, "tags": ["high_chance_poison"]},
    "scald": {"role": "damage_status", "base_score": 25, "tags": ["high_chance_burn"]},
    "lava plume": {"role": "damage_status", "base_score": 25, "tags": ["high_chance_burn"]},
    "discharge": {"role": "damage_status", "base_score": 25, "tags": ["high_chance_paralysis"]},
    "body slam": {"role": "damage_status", "base_score": 25, "tags": ["high_chance_paralysis"]},
    "zap cannon": {"role": "damage_status", "base_score": -10, "tags": ["guaranteed_paralysis", "low_accuracy"]},
    "inferno": {"role": "damage_status", "base_score": -10, "tags": ["guaranteed_burn", "low_accuracy"]},
    "dynamic punch": {"role": "damage_status", "base_score": -10, "tags": ["guaranteed_confusion", "low_accuracy"]},
    "iron head": {"role": "damage_status", "base_score": 20, "tags": ["high_chance_flinch"]},
    "air slash": {"role": "damage_status", "base_score": 20, "tags": ["high_chance_flinch"]},
    "dark pulse": {"role": "damage_status", "base_score": 15, "tags": ["chance_flinch"]},

    # Priority
    "extreme speed": {"role": "damage_priority", "base_score": 30, "priority": 2, "tags": ["revenge_kill"]},
    "sucker punch": {"role": "damage_priority", "base_score": 20, "priority": 1, "tags": ["revenge_kill"]},
    "bullet punch": {"role": "damage_priority", "base_score": 15, "priority": 1, "tags": ["revenge_kill"]},
    "mach punch": {"role": "damage_priority", "base_score": 15, "priority": 1, "tags": ["revenge_kill"]},
    "aqua jet": {"role": "damage_priority", "base_score": 15, "priority": 1, "tags": ["revenge_kill"]},
    "ice shard": {"role": "damage_priority", "base_score": 15, "priority": 1, "tags": ["revenge_kill"]},
    "fake out": {"role": "damage_priority", "base_score": 50, "priority": 3, "tags": ["first_turn_only", "flinch"]},

    # Drawback nukes
    "close combat": {"role": "damage_drawback", "base_score": 0, "tags": ["defense_drop"]},
    "superpower": {"role": "damage_drawback", "base_score": 0, "tags": ["offense_drop"]},
    "draco meteor": {"role": "damage_drawback", "base_score": -20, "tags": ["spammable_only_once"]},
    "overheat": {"role": "damage_drawback", "base_score": -20, "tags": ["spammable_only_once"]},
    "leaf storm": {"role": "damage_drawback", "base_score": -20, "tags": ["spammable_only_once"]},
    "fleur cannon": {"role": "damage_drawback", "base_score": -20, "tags": ["spammable_only_once"]},
    "hyper beam": {"role": "damage_drawback", "base_score": -50, "tags": ["must_recharge"]},
    "giga impact": {"role": "damage_drawback", "base_score": -50, "tags": ["must_recharge"]},

    # Pivot and control
    "baton pass": {"role": "pivot_setup", "base_score": 10, "tags": ["passes_stages"]},
    "u-turn": {"role": "pivot_damage", "base_score": 10, "tags": ["momentum"]},
    "volt switch": {"role": "pivot_damage", "base_score": 10, "tags": ["momentum"]},
    "flip turn": {"role": "pivot_damage", "base_score": 10, "tags": ["momentum"]},
    "parting shot": {"role": "pivot_debuff", "base_score": 25, "tags": ["momentum", "softens_enemy"]},
    "teleport": {"role": "pivot_slow", "base_score": 10, "tags": ["safe_switch"]},
    "whirlwind": {"role": "phazing", "base_score": 10, "tags": ["forces_switch"]},
    "roar": {"role": "phazing", "base_score": 10, "tags": ["forces_switch"]},

    # Status and debuffs
    "toxic": {"role": "status", "base_score": 30, "tags": ["wall_breaker"]},
    "will-o-wisp": {"role": "status", "base_score": 40, "tags": ["cripples_physical_attackers"]},
    "thunder wave": {"role": "status", "base_score": 35, "tags": ["speed_control"]},
    "spore": {"role": "status", "base_score": 60, "tags": ["free_turns"]},
    "sleep powder": {"role": "status", "base_score": 40, "tags": ["free_turns"]},
    "leech seed": {"role": "status", "base_score": 40, "tags": ["sustain"]},
    "memento": {"role": "sacrifice", "base_score": -50, "tags": ["creates_setup_window"]},
    "fake tears": {"role": "debuff", "base_score": 20, "tags": ["wall_breaker"]},
    "metal sound": {"role": "debuff", "base_score": 20, "tags": ["wall_breaker"]},
}

_TYPE_IMMUNITIES = {
    "normal": {"ghost"},
    "fighting": {"ghost"},
    "poison": {"steel"},
    "ground": {"flying"},
    "electric": {"ground"},
    "psychic": {"dark"},
    "ghost": {"normal"},
    "dragon": {"fairy"},
}

_TYPE_EFFECTIVENESS = {
    "normal": {"rock": 0.5, "ghost": 0.0, "steel": 0.5},
    "fire": {"fire": 0.5, "water": 0.5, "grass": 2.0, "ice": 2.0, "bug": 2.0, "rock": 0.5, "dragon": 0.5, "steel": 2.0},
    "water": {"fire": 2.0, "water": 0.5, "grass": 0.5, "ground": 2.0, "rock": 2.0, "dragon": 0.5},
    "electric": {"water": 2.0, "electric": 0.5, "grass": 0.5, "ground": 0.0, "flying": 2.0, "dragon": 0.5},
    "grass": {"fire": 0.5, "water": 2.0, "grass": 0.5, "poison": 0.5, "ground": 2.0, "flying": 0.5, "bug": 0.5, "rock": 2.0, "dragon": 0.5, "steel": 0.5},
    "ice": {"fire": 0.5, "water": 0.5, "grass": 2.0, "ground": 2.0, "flying": 2.0, "dragon": 2.0, "steel": 0.5},
    "fighting": {"normal": 2.0, "ice": 2.0, "poison": 0.5, "flying": 0.5, "psychic": 0.5, "bug": 0.5, "rock": 2.0, "ghost": 0.0, "dark": 2.0, "steel": 2.0, "fairy": 0.5},
    "poison": {"grass": 2.0, "poison": 0.5, "ground": 0.5, "rock": 0.5, "ghost": 0.5, "steel": 0.0, "fairy": 2.0},
    "ground": {"fire": 2.0, "electric": 2.0, "grass": 0.5, "poison": 2.0, "flying": 0.0, "bug": 0.5, "rock": 2.0, "steel": 2.0},
    "flying": {"electric": 0.5, "grass": 2.0, "fighting": 2.0, "bug": 2.0, "rock": 0.5, "steel": 0.5},
    "psychic": {"fighting": 2.0, "poison": 2.0, "psychic": 0.5, "dark": 0.0, "steel": 0.5},
    "bug": {"fire": 0.5, "grass": 2.0, "fighting": 0.5, "poison": 0.5, "flying": 0.5, "psychic": 2.0, "ghost": 0.5, "dark": 2.0, "steel": 0.5, "fairy": 0.5},
    "rock": {"fire": 2.0, "ice": 2.0, "fighting": 0.5, "ground": 0.5, "flying": 2.0, "bug": 2.0, "steel": 0.5},
    "ghost": {"normal": 0.0, "psychic": 2.0, "ghost": 2.0, "dark": 0.5},
    "dragon": {"dragon": 2.0, "steel": 0.5, "fairy": 0.0},
    "dark": {"fighting": 0.5, "psychic": 2.0, "ghost": 2.0, "dark": 0.5, "fairy": 0.5},
    "steel": {"fire": 0.5, "water": 0.5, "electric": 0.5, "ice": 2.0, "rock": 2.0, "steel": 0.5, "fairy": 2.0},
    "fairy": {"fire": 0.5, "fighting": 2.0, "poison": 0.5, "dragon": 2.0, "dark": 2.0, "steel": 0.5},
}

_ENEMY_ID_PATTERN = re.compile(r"enemy\s*id\s*:\s*(\d+)", re.IGNORECASE)
_MOVES_TAKEN_PATTERN = re.compile(r"moves\s*taken\s*:\s*(\d+)", re.IGNORECASE)
_SENT_OUT_PATTERN = re.compile(r"sent out\s+[^\n!]*?([A-Za-z][A-Za-z0-9'\- ]+)!", re.IGNORECASE)
_HP_STATUS_PATTERN = re.compile(
    r"(?:<:\w+:\d+>|:\d+_?:)\s*([A-Za-z][A-Za-z0-9'\- ]+)\s+(?:(?:<:\w+:\d+>|:\w+:)\s+)*HP\s+(\d+)/(\d+)(\s+:fnt:)?",
    re.IGNORECASE,
)
_HP_LINE_PATTERN = re.compile(
    r"(?:<:\w+:\d+>|:\d+_?:)\s*([A-Za-z][A-Za-z0-9'\- ]+)\s+(?:(?:<:\w+:\d+>|:\w+:)\s+)*HP\s+(\d+)/(\d+)",
    re.IGNORECASE,
)
_HP_FALLBACK_PATTERN = re.compile(r"\b([A-Za-z][A-Za-z0-9'\- ]{1,40}?)\s+HP\s+(\d+)/(\d+)", re.IGNORECASE)
_STAT_DELTA_PATTERN = re.compile(r"\[([+-])(\d+)\]")
_USED_MOVE_PATTERN = re.compile(r"used\s+([^!]+)!", re.IGNORECASE)
_WHO_USED_PATTERN = re.compile(r":\d+_?:\s*([A-Za-z][A-Za-z0-9'\- ]+)\s+used", re.IGNORECASE)
_WHO_USED_CLEAN_PATTERN = re.compile(r"\b([A-Za-z][A-Za-z0-9'\- ]+)\s+used\s+[^!]+!", re.IGNORECASE)
_DMG_DEALT_PATTERN = re.compile(r"dealt\s+\**([\d,]+)\**\s*dmg", re.IGNORECASE)
_MOVE_TYPE_LINE_PATTERN = re.compile(r":([a-z]+)type:\s", re.IGNORECASE)
_TEAM_MOVES_HEADER_PATTERN = re.compile(r"your\s+team'?s\s+moves", re.IGNORECASE)
_TEAM_MON_HEADER_PATTERN = re.compile(r"^\s*Mon\s*#\d+\s*-\s*(?:<:[^>]+>\s*|:[^\s]+:\s*)*([^\n:]+?)'s\s+Moves\s*:\s*$", re.IGNORECASE)
_TEAM_MOVE_LINE_PATTERN = re.compile(r"^\s*\[Move\s*#\d+\]\s*(?:<:[^>]+>\s*|:[a-z]+type:\s*)*([^|\n]+)", re.IGNORECASE)
_TEAM_HEADER_PATTERN = re.compile(r"([A-Za-z][A-Za-z0-9_'\- ]{1,40})'s\s+Team", re.IGNORECASE)
_BATTLE_VS_PATTERN = re.compile(r"\b([A-Za-z][A-Za-z0-9_'\- ]{1,40})\s+vs\.\s+([A-Za-z][A-Za-z0-9_'\- ]{1,40})\b", re.IGNORECASE)
_BATTLE_END_PATTERN = re.compile(r"\b(won|lost)\s+the\s+battle\b", re.IGNORECASE)

_AUTOFIGHT_STRATEGY_MODES = {"standard", "ev", "level"}
_LOOKUP_TIMEOUT_SECONDS = 1.5


def _clean_battle_line(line: str) -> str:
    cleaned = re.sub(r"<:[^>]+>", " ", str(line or ""))
    cleaned = re.sub(r":[A-Za-z0-9_]+:", " ", cleaned)
    # Discord embed text often wraps names/moves in markdown (**, ~~); remove it
    # before applying parser regexes like sent-out and HP-line extraction.
    cleaned = re.sub(r"\*\*|__|~~|`", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


class AutoFight(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config: Config = bot.config
        self.bot.autofight_active = False
        self.bot.autofight_status = "Idle"
        self._last_clicked_by_message: dict[int, str] = {}
        self._inflight_message_ids: set[int] = set()
        self._deferred_messages_by_id: dict[int, tuple[Message, str]] = {}
        self._action_lock = asyncio.Lock()
        self._deferred_while_busy: tuple[Message, str] | None = None
        self._last_action_signature: str = ""
        self._last_action_signature_message_id: int = 0
        self._battle_state: dict[str, object] = {
            "enemy_id": -1,
            "moves_taken": -1,
            "last_index": -1,
            "recent_incoming_damage": 0.0,
            "recent_outgoing_damage": 0.0,
            "recent_incoming_critical": False,
            "recent_outgoing_critical": False,
        }
        self._known_moves_by_pokemon: dict[str, set[str]] = {}
        self._active_pokemon: str = ""
        self._profiled_pokemon: set[str] = set()
        self._capped_stats_by_pokemon: dict[str, set[str]] = {}
        self._stat_stage_by_pokemon: dict[str, dict[str, int]] = {}
        self._move_type_by_name: dict[str, str] = {}
        self._immune_moves_by_enemy: dict[str, set[str]] = {}
        self._enemy_active_pokemon: str = ""
        self._enemy_offense_profile: dict[str, dict[str, int]] = {}
        self._enemy_seen_moves_by_battle: dict[str, set[str]] = {}
        self._enemy_stat_stage_by_battle: dict[str, dict[str, int]] = {}
        self._enemy_knowledge_by_battle: dict[str, dict[str, object]] = {}
        self._planned_switch_target: str = ""
        self._level_locked_target: str = ""
        self._pending_baton_stages: dict[str, int] | None = None
        self._used_setup_moves_by_pokemon: dict[str, set[str]] = {}
        self._enemy_confirmed_status_by_battle: dict[str, set[str]] = {}
        self._preview_move_meta_by_pokemon: dict[str, dict[str, dict[str, object]]] = {}
        self._move_use_count_by_battle: dict[str, dict[str, int]] = {}
        self._run_target_battles: int = 0
        self._run_completed_battles: int = 0
        self._run_indefinite: bool = False;
        self._run_paused_state: dict[str, object] | None = None
        self._humanizer_next_break_after: int = 0
        self._humanizer_breaks_taken: int = 0
        self._battle_mode_args: str = ""
        self._battle_strategy_mode: str = "standard"
        self._paused_automation_snapshot: dict[str, object] | None = None
        self._last_battle_dispatch_at: float = 0.0
        self._last_battle_activity_at: float = 0.0
        self._dispatch_watchdog_task: asyncio.Task | None = None
        self._run_no_response_retries: int = 0
        self._run_dispatch_error_retries: int = 0
        self._cloudflare_backoff_until: float = 0.0
        self._cloudflare_1015_strikes: int = 0
        self._last_cloudflare_1015_at: float = 0.0
        self._cloudflare_guard_until: float = 0.0
        self._cloudflare_guard_reason: str = ""
        self._last_action_state_key: str = ""
        self._last_action_state_at: float = 0.0
        self._next_battle_task: asyncio.Task | None = None
        self._latest_battle_message_id: int = 0
        self._counted_battle_end_message_ids: set[int] = set()
        self._announced_battle_prompt_message_ids: set[int] = set()
        self._pokemon_brief_mem_cache: dict[str, dict[str, object] | None] = {}
        self._move_brief_mem_cache: dict[str, dict[str, object] | None] = {}

    @staticmethod
    def _is_cloudflare_1015_error(error_text: str) -> bool:
        lowered = str(error_text or "").lower()
        return "429 too many requests" in lowered and "1015" in lowered

    def _cloudflare_backoff_remaining(self) -> float:
        return max(0.0, float(self._cloudflare_backoff_until or 0.0) - time.monotonic())

    def _cloudflare_guard_remaining(self) -> float:
        return max(0.0, float(self._cloudflare_guard_until or 0.0) - time.monotonic())

    def _sync_cloudflare_guard_status(self) -> None:
        remaining = self._cloudflare_guard_remaining()
        if remaining > 0:
            self.bot.autofight_status = f"Paused (Cloudflare safeguard: {int(remaining)}s)"
            self.bot.autofight_guard_status = f"1015 x{int(self._cloudflare_1015_strikes or 0)} | {int(remaining)}s left"
            return

        if self._cloudflare_guard_reason:
            self._cloudflare_guard_reason = ""
            self.bot.autofight_guard_status = ""
            if bool(getattr(self.bot, "autofight_active", False)):
                self.bot.autofight_status = "Active"

    def _register_cloudflare_1015(self, *, source: str, message_id: int, error_text: str) -> None:
        now = time.monotonic()
        # Decay strike count if the previous 1015 happened long ago.
        if now - float(self._last_cloudflare_1015_at or 0.0) > 120.0:
            self._cloudflare_1015_strikes = 0

        self._cloudflare_1015_strikes = min(8, int(self._cloudflare_1015_strikes or 0) + 1)
        self._last_cloudflare_1015_at = now

        # Use bounded linear backoff so we cool down without stalling for minutes.
        base_seconds = min(45.0, 6.0 + (self._cloudflare_1015_strikes - 1) * 5.0)
        jitter_seconds = float(randint(1, 4))
        proposed_until = now + base_seconds + jitter_seconds
        self._cloudflare_backoff_until = max(float(self._cloudflare_backoff_until or 0.0), proposed_until)

        if self._cloudflare_1015_strikes >= _CLOUDFLARE_GUARD_TRIGGER_STRIKES:
            self._cloudflare_guard_reason = f"Cloudflare 1015 x{self._cloudflare_1015_strikes}"
            self._cloudflare_guard_until = max(float(self._cloudflare_guard_until or 0.0), now + _CLOUDFLARE_GUARD_COOLDOWN_SECONDS)
            self._cloudflare_backoff_until = max(float(self._cloudflare_backoff_until or 0.0), self._cloudflare_guard_until)
            self._sync_cloudflare_guard_status()
            self._log_event(
                "cloudflare_1015_guard_armed",
                {
                    "source": source,
                    "message_id": int(message_id or 0),
                    "strikes": self._cloudflare_1015_strikes,
                    "guard_seconds": round(self._cloudflare_guard_remaining(), 2),
                    "status": str(getattr(self.bot, "autofight_status", "") or ""),
                    "guard_status": str(getattr(self.bot, "autofight_guard_status", "") or ""),
                },
            )
        else:
            self._sync_cloudflare_guard_status()

        # Visible channel indicator so users can distinguish Cloudflare pauses from strategy issues.
        asyncio.create_task(
            notify_cloudflare_in_channel(
                self.bot,
                channel_id=int(self.config.autofight_channel_id or 0),
                module_name="AutoFight",
                error_text=str(error_text or ""),
                cooldown_seconds=60.0,
                wait_seconds=self._cloudflare_backoff_remaining(),
            )
        )

        self._log_event(
            "cloudflare_1015_backoff",
            {
                "source": source,
                "message_id": int(message_id or 0),
                "strikes": self._cloudflare_1015_strikes,
                "backoff_seconds": round(self._cloudflare_backoff_remaining(), 2),
                "error": str(error_text or "")[:180],
            },
        )

    async def _maybe_wait_for_cloudflare_backoff(self, *, source: str) -> None:
        remaining = self._cloudflare_backoff_remaining()
        if remaining <= 0:
            return
        event_name = "dispatch_cloudflare_safeguard_wait" if self._cloudflare_guard_remaining() > 0 else "dispatch_cloudflare_backoff_wait"
        self._log_event(
            event_name,
            {
                "source": source,
                "wait_seconds": round(remaining, 2),
                "status": str(getattr(self.bot, "autofight_status", "") or ""),
                "guard_status": str(getattr(self.bot, "autofight_guard_status", "") or ""),
            },
        )
        await asyncio.sleep(remaining)

    def _reset_battle_knowledge(self) -> None:
        self._capped_stats_by_pokemon.clear()
        self._stat_stage_by_pokemon.clear()
        self._immune_moves_by_enemy.clear()
        self._enemy_offense_profile.clear()
        self._enemy_seen_moves_by_battle.clear()
        self._enemy_stat_stage_by_battle.clear()
        self._enemy_knowledge_by_battle.clear()
        self._enemy_active_pokemon = ""
        self._active_pokemon = ""
        self._planned_switch_target = ""
        self._level_locked_target = ""
        self._pending_baton_stages = None
        self._used_setup_moves_by_pokemon.clear()
        self._enemy_confirmed_status_by_battle.clear()
        self._preview_move_meta_by_pokemon.clear()
        self._move_use_count_by_battle.clear()
        self._inflight_message_ids.clear()
        self._deferred_messages_by_id.clear()
        self._deferred_while_busy = None
        self._latest_battle_message_id = 0
        self._last_action_signature = ""
        self._last_action_signature_message_id = 0
        self._battle_state["recent_incoming_damage"] = 0.0
        self._battle_state["recent_outgoing_damage"] = 0.0
        self._battle_state["recent_incoming_critical"] = False
        self._battle_state["recent_outgoing_critical"] = False

    async def _cached_get_pokemon_brief(self, name: str) -> dict[str, object] | None:
        key = self._normalize_pokemon_name(name)
        if not key:
            return None

        if key in self._pokemon_brief_mem_cache:
            return self._pokemon_brief_mem_cache.get(key)

        try:
            info = await asyncio.wait_for(get_pokemon_brief(key), timeout=_LOOKUP_TIMEOUT_SECONDS)
        except Exception:
            info = None

        self._pokemon_brief_mem_cache[key] = info
        return info

    async def _cached_get_move_brief(self, name: str) -> dict[str, object] | None:
        key = self._normalize_move_name(name)
        if not key:
            return None

        if key in self._move_brief_mem_cache:
            return self._move_brief_mem_cache.get(key)

        try:
            info = await asyncio.wait_for(get_move_brief(key), timeout=_LOOKUP_TIMEOUT_SECONDS)
        except Exception:
            info = None

        self._move_brief_mem_cache[key] = info
        return info

    def _pause_other_automation(self) -> None:
        if self._paused_automation_snapshot is not None:
            return

        self._paused_automation_snapshot = {
            "pause_hunting": bool(getattr(self.bot, "pause_hunting", False)),
            "pause_fishing": bool(getattr(self.bot, "pause_fishing", False)),
            "hunting_status": str(getattr(self.bot, "hunting_status", "") or ""),
            "fishing_status": str(getattr(self.bot, "fishing_status", "") or ""),
        }

        self.bot.pause_hunting = True
        self.bot.pause_fishing = True
        if int(getattr(self.config, "hunting_channel_id", 0) or 0) != 0:
            self.bot.hunting_status = "Paused (AutoFight)"
        if int(getattr(self.config, "fishing_channel_id", 0) or 0) != 0:
            self.bot.fishing_status = "Paused (AutoFight)"

    async def _restore_other_automation(self) -> None:
        snapshot = self._paused_automation_snapshot
        if not snapshot:
            return

        self.bot.pause_hunting = bool(snapshot.get("pause_hunting", False))
        self.bot.pause_fishing = bool(snapshot.get("pause_fishing", False))
        self.bot.hunting_status = str(snapshot.get("hunting_status", self.bot.hunting_status) or self.bot.hunting_status)
        self.bot.fishing_status = str(snapshot.get("fishing_status", self.bot.fishing_status) or self.bot.fishing_status)
        self._paused_automation_snapshot = None
        await self.bot.log()

    async def _temporarily_resume_during_break(self) -> None:
        snapshot = self._paused_automation_snapshot
        if not snapshot:
            return

        self.bot.pause_hunting = bool(snapshot.get("pause_hunting", False))
        self.bot.pause_fishing = bool(snapshot.get("pause_fishing", False))
        self.bot.hunting_status = str(snapshot.get("hunting_status", "") or "")
        self.bot.fishing_status = str(snapshot.get("fishing_status", "") or "")
        self._log_event(
            "autofight_humanizer_break_resumed_other_systems",
            {
                "pause_hunting": self.bot.pause_hunting,
                "pause_fishing": self.bot.pause_fishing,
                "hunting_status": str(self.bot.hunting_status or "")[:80],
                "fishing_status": str(self.bot.fishing_status or "")[:80],
            },
        )
        await self.bot.log()

    async def _re_pause_before_next_battle(self) -> None:
        snapshot = self._paused_automation_snapshot
        if not snapshot:
            return

        self.bot.pause_hunting = True
        self.bot.pause_fishing = True
        if int(getattr(self.config, "hunting_channel_id", 0) or 0) != 0:
            self.bot.hunting_status = "Paused (AutoFight)"
        if int(getattr(self.config, "fishing_channel_id", 0) or 0) != 0:
            self.bot.fishing_status = "Paused (AutoFight)"
        self._log_event(
            "autofight_resuming_paused_other_systems",
            {
                "pause_hunting": self.bot.pause_hunting,
                "pause_fishing": self.bot.pause_fishing,
                "hunting_status": str(self.bot.hunting_status or "")[:80],
                "fishing_status": str(self.bot.fishing_status or "")[:80],
            },
        )
        await self.bot.log()

    @staticmethod
    def _split_strategy_mode(mode: str) -> tuple[str, str]:
        raw = str(mode or "").strip()
        if not raw:
            return "", "standard"

        parts = raw.rsplit(None, 1)
        if len(parts) == 2 and parts[1].strip().lower() in _AUTOFIGHT_STRATEGY_MODES - {"standard"}:
            battle_mode = parts[0].strip()
            strategy_mode = parts[1].strip().lower()
            return battle_mode, strategy_mode

        return raw, "standard"

    def _cancel_next_battle_task(self) -> None:
        task = self._next_battle_task
        if task and not task.done():
            task.cancel()
        self._next_battle_task = None

    def _cancel_dispatch_watchdog(self) -> None:
        task = self._dispatch_watchdog_task
        if task and not task.done():
            task.cancel()
        self._dispatch_watchdog_task = None

    def _release_inflight_and_replay(self, message_id: int) -> None:
        self._inflight_message_ids.discard(int(message_id or 0))
        deferred = self._deferred_messages_by_id.pop(int(message_id or 0), None)
        if deferred is not None:
            deferred_message, deferred_source = deferred
            self._log_event(
                "replay_deferred_inflight_message",
                {"source": deferred_source, "message_id": int(message_id or 0)},
            )
            asyncio.create_task(self._handle_message(deferred_message, source=deferred_source))

    def _ensure_stat_stage_row(self, pokemon_name: str) -> dict[str, int]:
        key = self._normalize_pokemon_name(pokemon_name)
        if not key:
            return {}
        row = self._stat_stage_by_pokemon.get(key)
        if row is None:
            row = {"atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0, "acc": 0, "eva": 0}
            self._stat_stage_by_pokemon[key] = row
        return row

    def _ensure_enemy_knowledge_row(self, enemy_id: int | None, species_name: str = "") -> dict[str, object]:
        key = self._enemy_battle_key(enemy_id)
        row = self._enemy_knowledge_by_battle.get(key)
        if row is None:
            row = {
                "species": "",
                "seeded": False,
                "ability": {"confirmed": "", "candidates": set(), "evidence": []},
                "item": {"confirmed": "", "candidates": set(), "evidence": []},
                "moves": {"revealed": set(), "possible": set(), "evidence": []},
            }
            self._enemy_knowledge_by_battle[key] = row
        if species_name and not str(row.get("species", "") or ""):
            row["species"] = species_name
        return row

    def _enemy_knowledge_snapshot(self, enemy_id: int | None) -> dict[str, object]:
        key = self._enemy_battle_key(enemy_id)
        row = self._enemy_knowledge_by_battle.get(key, {}) or {}
        ability = row.get("ability", {}) if isinstance(row.get("ability", {}), dict) else {}
        item = row.get("item", {}) if isinstance(row.get("item", {}), dict) else {}
        moves = row.get("moves", {}) if isinstance(row.get("moves", {}), dict) else {}
        status_key = self._enemy_battle_key(enemy_id)
        return {
            "species": str(row.get("species", "") or ""),
            "seeded": bool(row.get("seeded", False)),
            "ability": {
                "confirmed": str(ability.get("confirmed", "") or ""),
                "candidates": sorted(str(v) for v in (ability.get("candidates", set()) or set())),
                "evidence_count": len(ability.get("evidence", []) or []),
            },
            "item": {
                "confirmed": str(item.get("confirmed", "") or ""),
                "candidates": sorted(str(v) for v in (item.get("candidates", set()) or set())),
                "evidence_count": len(item.get("evidence", []) or []),
            },
            "moves": {
                "revealed": sorted(str(v) for v in (moves.get("revealed", set()) or set())),
                "possible_count": len(moves.get("possible", set()) or set()),
                "evidence_count": len(moves.get("evidence", []) or []),
            },
            "confirmed_status": sorted(str(v) for v in (self._enemy_confirmed_status_by_battle.get(status_key, set()) or set())),
            "stat_stages": dict(sorted((self._enemy_stat_stage_by_battle.get(status_key, {}) or {}).items())),
        }

    def _log_enemy_knowledge(self, event: str, enemy_id: int | None, details: dict | None = None) -> None:
        payload = {
            "enemy_id": int(enemy_id or 0),
            "enemy": str(self._enemy_active_pokemon or "")[:80],
            "knowledge": self._enemy_knowledge_snapshot(enemy_id),
        }
        if details:
            payload.update(details)
        self._log_event(event, payload)

    async def _seed_enemy_knowledge_from_species(self, enemy_id: int | None, species_name: str, source: str = "battle_parse") -> None:
        normalized = self._normalize_pokemon_name(species_name)
        if not normalized:
            return

        row = self._ensure_enemy_knowledge_row(enemy_id, normalized)
        if bool(row.get("seeded", False)) and str(row.get("species", "") or "") == normalized:
            return

        info = await self._cached_get_pokemon_brief(normalized)
        if not info:
            self._log_enemy_knowledge("enemy_knowledge_seed_missing", enemy_id, {"source": source, "species": normalized})
            return

        ability_row = row.setdefault("ability", {"confirmed": "", "candidates": set(), "evidence": []})
        item_row = row.setdefault("item", {"confirmed": "", "candidates": set(), "evidence": []})
        moves_row = row.setdefault("moves", {"revealed": set(), "possible": set(), "evidence": []})

        abilities = [self._normalize_move_name(name) for name in (info.get("abilities", []) or []) if str(name or "").strip()]
        movepool = [self._normalize_move_name(name) for name in (info.get("movepool", []) or []) if str(name or "").strip()]

        ability_row["candidates"] = set(abilities)
        moves_row["possible"] = set(movepool)
        row["seeded"] = True

        self._log_enemy_knowledge(
            "enemy_knowledge_seeded",
            enemy_id,
            {
                "source": source,
                "species": normalized,
                "ability_candidate_count": len(abilities),
                "move_candidate_count": len(movepool),
                "ability_candidates": abilities[:8],
                "move_candidates": movepool[:8],
                "item_candidate_count": len(item_row.get("candidates", set()) or set()),
            },
        )

    def _learn_enemy_ability_from_text(self, text: str, enemy_id: int | None) -> None:
        enemy_name = self._normalize_pokemon_name(self._enemy_active_pokemon)
        if not enemy_name:
            return

        row = self._ensure_enemy_knowledge_row(enemy_id, enemy_name)
        ability_row = row.setdefault("ability", {"confirmed": "", "candidates": set(), "evidence": []})
        candidates = {str(v).strip().lower() for v in (ability_row.get("candidates", set()) or set()) if str(v).strip()}
        lowered = str(text or "").lower()
        matched = [ability for ability in sorted(candidates) if ability and ability in lowered]
        if not matched:
            return

        evidence = ability_row.setdefault("evidence", [])
        for ability in matched:
            if ability not in evidence:
                evidence.append(ability)

        if not str(ability_row.get("confirmed", "") or ""):
            ability_row["confirmed"] = matched[0]

        self._log_enemy_knowledge(
            "enemy_ability_revealed",
            enemy_id,
            {
                "matched": matched[:4],
                "confirmed": str(ability_row.get("confirmed", "") or ""),
            },
        )

    def _learn_enemy_item_from_text(self, text: str, enemy_id: int | None) -> None:
        enemy_name = self._normalize_pokemon_name(self._enemy_active_pokemon)
        if not enemy_name:
            return

        row = self._ensure_enemy_knowledge_row(enemy_id, enemy_name)
        item_row = row.setdefault("item", {"confirmed": "", "candidates": set(), "evidence": []})
        lowered = str(text or "").lower()

        explicit_items = [
            "choice band",
            "choice scarf",
            "choice specs",
            "life orb",
            "leftovers",
            "black sludge",
            "focus sash",
            "rocky helmet",
            "eviolite",
            "air balloon",
            "sitrus berry",
            "oran berry",
            "lum berry",
            "shell bell",
            "scope lens",
            "expert belt",
        ]
        matched = [item for item in explicit_items if item in lowered]
        if not matched:
            return

        candidates = item_row.setdefault("candidates", set())
        evidence = item_row.setdefault("evidence", [])
        for item in matched:
            candidates.add(item)
            if item not in evidence:
                evidence.append(item)

        if not str(item_row.get("confirmed", "") or ""):
            item_row["confirmed"] = matched[0]

        self._log_enemy_knowledge(
            "enemy_item_revealed",
            enemy_id,
            {
                "matched": matched[:4],
                "confirmed": str(item_row.get("confirmed", "") or ""),
            },
        )

    def _log_event(self, event: str, details: dict | None = None) -> None:
        record_autofight_event(
            str(self.bot.user) if self.bot.user else "unknown",
            event,
            channel_id=int(self.config.autofight_channel_id or 0),
            details=details or {},
        )

    def _log_parser_snapshot(
        self,
        *,
        message: Message,
        source: str,
        combined_text: str,
        looks_like_battle: bool,
        enemy_id: int | None,
        moves_taken: int | None,
        switch_prompt: bool,
        has_enabled_buttons: bool,
        active_candidate: str,
        enemy_candidate: str,
        active_before: str,
        enemy_before: str,
    ) -> None:
        try:
            self_trainer, enemy_trainer = self._extract_trainer_names(combined_text)
            sent_out_all = self._extract_sent_out_events(combined_text)
            sent_out_self = self._extract_sent_out_events_for_trainer(combined_text, self_trainer) if self_trainer else []
            sent_out_enemy = self._extract_sent_out_events_for_trainer(combined_text, enemy_trainer) if enemy_trainer else []
            team_status = self._extract_team_status(combined_text)
            combat_self, combat_enemy = self._extract_combat_actor_candidates(combined_text, set(team_status.keys()))
            enemy_knowledge = self._enemy_knowledge_snapshot(enemy_id)
            enabled_buttons = self._enabled_buttons(message)
            button_details = [
                {
                    "label": str(getattr(button, "label", "") or "")[:80],
                    "kind": "switch" if self._is_switch_button(button) else "move",
                    "custom_id": str(getattr(button, "custom_id", "") or "")[:120],
                }
                for button in enabled_buttons
            ]
            switch_button_details = [
                {
                    "slot_index": idx,
                    "label": str(getattr(button, "label", "") or "")[:80],
                    "fainted": bool(team_status.get(str(getattr(button, "label", "") or "").strip().lower(), {}).get("fainted", False)),
                    "hp_ratio": round(float(team_status.get(str(getattr(button, "label", "") or "").strip().lower(), {}).get("hp_ratio", 1.0) or 1.0), 4),
                }
                for idx, button in enumerate(enabled_buttons)
                if self._is_switch_button(button)
            ]
            self._log_event(
                "parser_snapshot",
                {
                    "source": source,
                    "message_id": int(getattr(message, "id", 0) or 0),
                    "looks_like_battle": bool(looks_like_battle),
                    "enemy_id": enemy_id,
                    "moves_taken": moves_taken,
                    "switch_prompt": bool(switch_prompt),
                    "has_enabled_buttons": bool(has_enabled_buttons),
                    "trainers": {"self": self_trainer, "enemy": enemy_trainer},
                    "strategy_mode": self._battle_strategy_mode,
                    "sent_out": {
                        "all": sent_out_all,
                        "self": sent_out_self,
                        "enemy": sent_out_enemy,
                    },
                    "team_status": team_status,
                    "switch_buttons": switch_button_details,
                    "combat_actor_candidates": {"self": combat_self, "enemy": combat_enemy},
                    "active": {
                        "before": active_before,
                        "candidate": active_candidate,
                        "after": self._active_pokemon,
                    },
                    "enemy": {
                        "before": enemy_before,
                        "candidate": enemy_candidate,
                        "after": self._enemy_active_pokemon,
                    },
                    "enabled_buttons": button_details,
                    "enemy_knowledge": enemy_knowledge,
                    "text_preview": combined_text[:600],
                },
            )
        except Exception as exc:
            self._log_event(
                "parser_snapshot_error",
                {
                    "source": source,
                    "message_id": int(getattr(message, "id", 0) or 0),
                    "error": str(exc)[:180],
                },
            )

    def _is_target_channel(self, message: Message) -> bool:
        return int(getattr(message.channel, "id", 0) or 0) == int(self.config.autofight_channel_id or 0)

    @staticmethod
    def _combine_message_text(message: Message) -> str:
        parts = [str(message.content or "")]
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
        return "\n".join(parts)

    def _is_on_command(self, content: str) -> bool:
        normalized = str(content or "").strip().lower()
        return normalized in {
            str(self.config.autofight_on_command or "").strip().lower(),
            "autofight on",
            ";autofight on",
            "af on",
            ";af on",
            "af",
            ";af",
        }

    def _is_off_command(self, content: str) -> bool:
        normalized = str(content or "").strip().lower()
        return normalized in {
            str(self.config.autofight_off_command or "").strip().lower(),
            "autofight off",
            ";autofight off",
            "af off",
            ";af off",
        }

    async def _dispatch_initial_fight(self, channel, battle_mode: str = "") -> bool:
        if self._cloudflare_guard_remaining() > 0:
            self._sync_cloudflare_guard_status()
            self._log_event(
                "dispatch_cloudflare_safeguard_blocked",
                {
                    "source": "dispatch_initial",
                    "wait_seconds": round(self._cloudflare_guard_remaining(), 2),
                    "status": str(getattr(self.bot, "autofight_status", "") or ""),
                    "guard_status": str(getattr(self.bot, "autofight_guard_status", "") or ""),
                },
            )
            return False
        await self._maybe_wait_for_cloudflare_backoff(source="dispatch_initial")
        await asyncio.sleep(randint(250, 1400) / 1000)
        mode = str(battle_mode or "").strip()
        if mode:
            normalized = mode
            lowered = mode.lower()
            if lowered.startswith(";battle"):
                normalized = mode[7:].strip()
            elif lowered.startswith("battle"):
                normalized = mode[6:].strip()
            cmd = ";battle" + (f" {normalized}" if normalized else "")
            try:
                await channel.send(cmd)
                self._last_battle_dispatch_at = time.monotonic()
                self._run_dispatch_error_retries = 0
                self._schedule_dispatch_watchdog(channel)
                self._log_event("initial_dispatch_success", {"mode": "text", "command": cmd})
                return True
            except Exception as exc:
                if self._is_cloudflare_1015_error(str(exc)):
                    self._register_cloudflare_1015(source="dispatch_text", message_id=0, error_text=str(exc))
                self._log_event("initial_dispatch_error", {"mode": "text", "command": cmd, "error": str(exc)[:180]})
                return False

        command_map = getattr(self.bot, "autofight_channel_commands", None) or {}
        exact_priority = [
            "battle",
            "duel",
            "fight",
            "trainer battle",
            "npc battle",
            "battle npc",
            "battle trainer",
        ]

        for command_name in exact_priority:
            command = command_map.get(command_name)
            if command is None:
                continue
            try:
                await command()
                self._last_battle_dispatch_at = time.monotonic()
                self._run_dispatch_error_retries = 0
                self._schedule_dispatch_watchdog(channel)
                self._log_event("initial_dispatch_success", {"mode": "slash", "command": command_name})
                return True
            except Exception as exc:
                if self._is_cloudflare_1015_error(str(exc)):
                    self._register_cloudflare_1015(source="dispatch_slash", message_id=0, error_text=str(exc))
                self._log_event("initial_dispatch_error", {"mode": "slash", "command": command_name, "error": str(exc)[:180]})
                continue

        # Minimal fallback so user can still test in channels where command name differs.
        try:
            await channel.send(";battle")
            self._last_battle_dispatch_at = time.monotonic()
            self._run_dispatch_error_retries = 0
            self._schedule_dispatch_watchdog(channel)
            self._log_event("initial_dispatch_success", {"mode": "text", "command": ";battle"})
            return True
        except Exception as exc:
            if self._is_cloudflare_1015_error(str(exc)):
                self._register_cloudflare_1015(source="dispatch_fallback", message_id=0, error_text=str(exc))
            self._log_event("initial_dispatch_error", {"mode": "text", "command": ";battle", "error": str(exc)[:180]})
            return False

    def _schedule_dispatch_watchdog(self, channel) -> None:
        if self._run_target_battles <= 0 and not self._run_indefinite:
            return
        if self._dispatch_watchdog_task and not self._dispatch_watchdog_task.done():
            self._dispatch_watchdog_task.cancel()

        scheduled_dispatch_at = float(self._last_battle_dispatch_at or 0.0)

        async def _watchdog() -> None:
            try:
                # Wait for first Pokemeow battle prompt activity after dispatch.
                await asyncio.sleep(18.0)
                if not bool(getattr(self.bot, "autofight_active", False)):
                    return
                if self._run_target_battles <= 0 and not self._run_indefinite:
                    return
                if scheduled_dispatch_at <= 0:
                    return

                activity_after_dispatch = float(self._last_battle_activity_at or 0.0) > scheduled_dispatch_at
                if activity_after_dispatch:
                    self._run_no_response_retries = 0
                    return

                # No response: retry with bounded attempts to avoid infinite spam.
                self._run_no_response_retries += 1
                if self._run_no_response_retries > 3:
                    self._log_event(
                        "dispatch_no_response_give_up",
                        {
                            "completed": self._run_completed_battles,
                            "target": self._run_target_battles,
                            "mode": self._battle_mode_args,
                        },
                    )
                    return

                self._log_event(
                    "dispatch_no_response_retry",
                    {
                        "retry": self._run_no_response_retries,
                        "completed": self._run_completed_battles,
                        "target": self._run_target_battles,
                    },
                )
                await asyncio.sleep(randint(1800, 4200) / 1000)
                await self._dispatch_initial_fight(channel, self._battle_mode_args)
            except asyncio.CancelledError:
                return

        self._dispatch_watchdog_task = asyncio.create_task(_watchdog())

    @staticmethod
    def _parse_run_command(content: str) -> tuple[int, str] | None:
        raw = str(content or "").strip()
        if not raw:
            return None
        # Support both "autofight run" and "af run" patterns
        patterns = [
            r"^;?autofight\s+run\s+(\d+)(?:\s+(.*))?$",
            r"^;?af\s+run\s+(\d+)(?:\s+(.*))?$",
        ]
        for pattern in patterns:
            m = re.match(pattern, raw, flags=re.IGNORECASE)
            if m:
                count = int(m.group(1) or 0)
                mode = str(m.group(2) or "").strip()
                return count, mode
        return None

    @staticmethod
    def _parse_once_command(content: str) -> str | None:
        raw = str(content or "").strip()
        if not raw:
            return None
        # Support both "autofight once" and "af once" patterns
        patterns = [
            r"^;?autofight\s+once(?:\s+(.*))?$",
            r"^;?af\s+once(?:\s+(.*))?$",
        ]
        for pattern in patterns:
            m = re.match(pattern, raw, flags=re.IGNORECASE)
            if m:
                return str(m.group(1) or "").strip()
        return None

    @staticmethod
    def _is_stop_command(content: str) -> bool:
        raw = str(content or "").strip().lower()
        return raw in {"autofight stop", ";autofight stop", "af stop", ";af stop"}

    @staticmethod
    def _is_status_command(content: str) -> bool:
        raw = str(content or "").strip().lower()
        return raw in {"autofight status", ";autofight status", "af status", ";af status"}

    @staticmethod
    def _parse_indefinite_command(content: str) -> str | None:
        raw = str(content or "").strip()
        if not raw:
            return None
        patterns = [
            r"^;?autofight\s+indefinite(?:\s+(.*))?$",
            r"^;?autofight\s+inf(?:\s+(.*))?$",
            r"^;?af\s+indefinite(?:\s+(.*))?$",
            r"^;?af\s+inf(?:\s+(.*))?$",
        ]
        for pattern in patterns:
            m = re.match(pattern, raw, flags=re.IGNORECASE)
            if m:
                return str(m.group(1) or "").strip()
        return None

    @staticmethod
    def _is_pause_command(content: str) -> bool:
        raw = str(content or "").strip().lower()
        return raw in {"autofight pause", ";autofight pause", "af pause", ";af pause"}

    @staticmethod
    def _is_resume_command(content: str) -> bool:
        raw = str(content or "").strip().lower()
        return raw in {"autofight resume", ";autofight resume", "af resume", ";af resume"}

    def _eligible_for_human_break(self) -> bool:
        if self._run_indefinite:
            return True
        return int(self._run_target_battles or 0) >= 15

    def _arm_next_human_break(self) -> None:
        if not self._eligible_for_human_break():
            self._humanizer_next_break_after = 0
            self._humanizer_breaks_taken = 0
            return

        if self._run_indefinite:
            low, high = (7, 18) if self._humanizer_breaks_taken <= 0 else (10, 24)
        else:
            low, high = (9, 16) if self._humanizer_breaks_taken <= 0 else (14, 24)
        self._humanizer_next_break_after = int(self._run_completed_battles or 0) + randint(low, high)

    async def _schedule_next_battle_after_cooldown(self, channel) -> None:
        # Pokemeow enforces ~90s minimum between battles.
        elapsed = max(0.0, time.monotonic() - float(self._last_battle_dispatch_at or 0.0))
        base_wait_seconds = max(0.0, 90.0 - elapsed)
        extra_wait_seconds = 0.0

        # Humanizer for long runs: sometimes take a realistic longer break.
        if (
            self._eligible_for_human_break()
            and self._humanizer_next_break_after > 0
            and int(self._run_completed_battles or 0) >= int(self._humanizer_next_break_after)
        ):
            is_allowed = self._run_indefinite or self._humanizer_breaks_taken < 1
            chance = 22 if self._run_indefinite else 16
            if is_allowed and randint(1, 100) <= chance:
                extra_wait_seconds = float(randint(75, 300))
                self._humanizer_breaks_taken += 1
                self._arm_next_human_break()
                await self._temporarily_resume_during_break()
                self._log_event(
                    "battle_humanizer_break",
                    {
                        "extra_wait_seconds": round(extra_wait_seconds, 2),
                        "completed": self._run_completed_battles,
                        "target": self._run_target_battles,
                        "indefinite": self._run_indefinite,
                        "breaks_taken": self._humanizer_breaks_taken,
                    },
                )
            else:
                # Defer the next check window so pauses stay occasional.
                self._humanizer_next_break_after = int(self._run_completed_battles or 0) + randint(4, 9)

        wait_seconds = base_wait_seconds + extra_wait_seconds
        self._log_event(
            "battle_cooldown_wait",
            {
                "wait_seconds": round(wait_seconds, 2),
                "base_wait_seconds": round(base_wait_seconds, 2),
                "extra_wait_seconds": round(extra_wait_seconds, 2),
                "completed": self._run_completed_battles,
                "target": self._run_target_battles,
            },
        )
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)

        if not bool(getattr(self.bot, "autofight_active", False)):
            return
        
        if extra_wait_seconds > 0:
            await self._re_pause_before_next_battle()
        dispatched = await self._dispatch_initial_fight(channel, self._battle_mode_args)
        if not dispatched:
            self._run_dispatch_error_retries += 1
            self._log_event(
                "battle_restart_failed",
                {
                    "completed": self._run_completed_battles,
                    "target": self._run_target_battles,
                    "retry": self._run_dispatch_error_retries,
                },
            )
            if (
                bool(getattr(self.bot, "autofight_active", False))
                and (self._run_target_battles > 0 or self._run_indefinite)
                and self._run_dispatch_error_retries <= 3
            ):
                backoff = randint(7, 16)
                self._log_event(
                    "battle_restart_retry",
                    {
                        "retry": self._run_dispatch_error_retries,
                        "backoff_seconds": backoff,
                    },
                )
                await asyncio.sleep(float(backoff))
                await self._dispatch_initial_fight(channel, self._battle_mode_args)

    @staticmethod
    def _enabled_buttons(message: Message):
        buttons = []
        components = getattr(message, "components", None) or []
        for component in components:
            for child in getattr(component, "children", []) or []:
                if bool(getattr(child, "disabled", False)):
                    continue
                buttons.append(child)
        return buttons

    @staticmethod
    def _find_enabled_button(message: Message, button_id: str, button_label: str):
        for button in AutoFight._enabled_buttons(message):
            if str(getattr(button, "custom_id", "") or "") != str(button_id or ""):
                continue
            if str(getattr(button, "label", "") or "") != str(button_label or ""):
                continue
            return button
        return None

    async def _click_button_with_refresh_retry(
        self,
        message: Message,
        button,
        *,
        message_id: int,
        source: str,
        button_id: str,
        button_label: str,
    ) -> None:
        # Keep click latency low to avoid stale components near turn deadlines.
        await asyncio.sleep(randint(320, 780) / 1000)
        click_timeout_seconds = 2.8
        first_error: Exception | None = None
        try:
            await asyncio.wait_for(button.click(), timeout=click_timeout_seconds)
            return
        except (InvalidData, asyncio.TimeoutError) as exc:
            first_error = exc

        refreshed_message = None
        try:
            refreshed_message = await message.channel.fetch_message(message_id)
        except Exception as exc:
            self._log_event(
                "click_retry_fetch_failed",
                {
                    "source": source,
                    "message_id": message_id,
                    "error": str(exc)[:180],
                },
            )
            if first_error is not None:
                raise first_error
            raise

        refreshed_button = self._find_enabled_button(refreshed_message, button_id, button_label)
        if refreshed_button is None:
            self._log_event(
                "click_retry_button_not_found",
                {
                    "source": source,
                    "message_id": message_id,
                    "id": str(button_id or "")[:120],
                    "label": str(button_label or "")[:80],
                },
            )
            if first_error is not None:
                raise first_error
            raise InvalidData

        self._log_event(
            "click_retry_refreshed_message",
            {
                "source": source,
                "message_id": message_id,
                "id": str(button_id or "")[:120],
                "label": str(button_label or "")[:80],
            },
        )
        await asyncio.sleep(randint(120, 280) / 1000)
        await asyncio.wait_for(refreshed_button.click(), timeout=click_timeout_seconds)

    @staticmethod
    def _extract_battle_progress(text: str) -> tuple[int | None, int | None]:
        raw = str(text or "")
        enemy_match = _ENEMY_ID_PATTERN.search(raw)
        moves_match = _MOVES_TAKEN_PATTERN.search(raw)
        enemy_id = int(enemy_match.group(1)) if enemy_match else None
        moves_taken = int(moves_match.group(1)) if moves_match else None
        return enemy_id, moves_taken

    def _extract_active_pokemon(self, text: str) -> str:
        raw = str(text or "")
        self_trainer, _ = self._extract_trainer_names(raw)

        # Use the robust trainer-filtered sent-out extraction.
        sent_out = self._extract_sent_out_events_for_trainer(raw, self_trainer)
        if sent_out:
            return sent_out[-1]

        if self._active_pokemon:
            return self._active_pokemon
        return ""

    @staticmethod
    def _extract_trainer_names(text: str) -> tuple[str, str]:
        lines = [str(line or "") for line in str(text or "").splitlines()]
        for line in lines:
            cleaned = _clean_battle_line(line)
            m = _BATTLE_VS_PATTERN.search(cleaned)
            if m:
                return str(m.group(1) or "").strip().lower(), str(m.group(2) or "").strip().lower()

        headers: list[str] = []
        for line in lines:
            cleaned = _clean_battle_line(line)
            m = _TEAM_HEADER_PATTERN.search(cleaned)
            if not m:
                continue
            name = str(m.group(1) or "").strip().lower()
            if name:
                headers.append(name)
        if len(headers) >= 2:
            return headers[0], headers[1]

        return "", ""

    @staticmethod
    def _extract_sent_out_events(text: str) -> list[str]:
        """Extract all Pokémon sent out in order (not trainer-filtered)."""
        events: list[str] = []
        for line in str(text or "").splitlines():
            cleaned = _clean_battle_line(line)
            lowered = cleaned.lower()
            if "sent out" not in lowered or "pivoted with" in lowered:
                continue
            pokemon_match = _SENT_OUT_PATTERN.search(cleaned)
            if not pokemon_match:
                continue
            pokemon = str(pokemon_match.group(1) or "").strip(" :*")
            if pokemon:
                events.append(pokemon)
        return events

    @staticmethod
    def _extract_sent_out_events_for_trainer(text: str, trainer_name: str) -> list[str]:
        """Extract sent-out events for a specific trainer by filtering on name."""
        trainer_norm = str(trainer_name or "").strip().lower()
        if not trainer_norm:
            return []

        events: list[str] = []
        for line in str(text or "").splitlines():
            cleaned = _clean_battle_line(line)
            lowered = cleaned.lower()
            if "sent out" not in lowered or "pivoted with" in lowered:
                continue
            if trainer_norm not in lowered:
                continue
            pokemon_match = _SENT_OUT_PATTERN.search(cleaned)
            if not pokemon_match:
                continue
            pokemon = str(pokemon_match.group(1) or "").strip(" :*")
            if pokemon:
                events.append(pokemon)
        return events

    def _extract_combat_actor_candidates(self, text: str, self_species: set[str] | None = None) -> tuple[str, str]:
        """Infer the latest self and enemy actors from move-usage lines."""
        self_species_norm = {self._normalize_pokemon_name(name) for name in (self_species or set())}
        self_species_norm.discard("")

        self_candidate = ""
        enemy_candidate = ""
        for line in reversed(str(text or "").splitlines()):
            if not _USED_MOVE_PATTERN.search(line):
                continue
            who_match = _WHO_USED_PATTERN.search(line)
            if not who_match:
                continue
            who = str(who_match.group(1) or "").strip(" :*")
            if not who:
                continue
            who_norm = self._normalize_pokemon_name(who)
            if not self_candidate and who_norm in self_species_norm:
                self_candidate = who
            if not enemy_candidate and who_norm and who_norm not in self_species_norm:
                enemy_candidate = who
            if self_candidate and enemy_candidate:
                break
        return self_candidate, enemy_candidate

    @staticmethod
    def _extract_team_status(text: str) -> dict[str, dict[str, float | bool]]:
        status: dict[str, dict[str, float | bool]] = {}
        for line in str(text or "").splitlines():
            cleaned_line = _clean_battle_line(line)
            status_match = _HP_STATUS_PATTERN.search(cleaned_line)
            fallback_match = _HP_FALLBACK_PATTERN.search(cleaned_line) if not status_match else None
            m = status_match or fallback_match
            if m is None:
                continue
            name = str(m.group(1) or "").strip()
            current = float(m.group(2) or 0)
            total = float(m.group(3) or 1)
            fainted_marker = ""
            if status_match is not None:
                fainted_marker = str(status_match.group(4) or "")
            elif ":fnt:" in cleaned_line.lower():
                fainted_marker = ":fnt:"
            fainted = bool(fainted_marker) or current <= 0
            ratio = 0.0 if total <= 0 else max(0.0, min(current / total, 1.0))
            status[name.lower()] = {"fainted": fainted, "hp_ratio": ratio}
        return status

    def _extract_enemy_active_pokemon(self, text: str) -> str:
        raw = str(text or "")
        lines = raw.splitlines()
        self_trainer, enemy_trainer = self._extract_trainer_names(raw)

        # Build self species set from self team block.
        self_species: set[str] = set()
        enemy_species_all: list[str] = []
        enemy_species_live: list[str] = []

        headers: list[tuple[str, int]] = []
        for idx, line in enumerate(lines):
            m = _TEAM_HEADER_PATTERN.search(_clean_battle_line(line))
            if m:
                headers.append((str(m.group(1) or "").strip().lower(), idx))

        self_header_idx = -1
        enemy_header_idx = -1
        if self_trainer:
            for t_name, h_idx in headers:
                if t_name == self_trainer:
                    self_header_idx = h_idx
                    break
        if enemy_trainer:
            for t_name, h_idx in headers:
                if t_name == enemy_trainer:
                    enemy_header_idx = h_idx
                    break
        if self_header_idx == -1 and headers:
            self_header_idx = headers[0][1]
        if enemy_header_idx == -1 and len(headers) >= 2:
            enemy_header_idx = headers[1][1]

        if self_header_idx != -1:
            for j in range(self_header_idx + 1, len(lines)):
                if _TEAM_HEADER_PATTERN.search(_clean_battle_line(lines[j])):
                    break
                cleaned_line = _clean_battle_line(lines[j])
                m = _HP_LINE_PATTERN.search(cleaned_line)
                if not m:
                    m = _HP_FALLBACK_PATTERN.search(cleaned_line)
                if not m:
                    m = _HP_STATUS_PATTERN.search(cleaned_line)
                if not m:
                    continue
                nm = self._normalize_pokemon_name(str(m.group(1) or "").strip(" :*"))
                if nm:
                    self_species.add(nm)

        # Use robust trainer-filtered sent-out extraction for enemy.
        if enemy_trainer:
            sent_out = self._extract_sent_out_events_for_trainer(raw, enemy_trainer)
            for pokemon in reversed(sent_out):
                if self._normalize_pokemon_name(pokemon) not in self_species:
                    return pokemon

        if enemy_header_idx != -1:
            for j in range(enemy_header_idx + 1, min(enemy_header_idx + 18, len(lines))):
                lowered = lines[j].lower()
                if any(x in lowered for x in ["enemy id", "moves taken", "wins against", "your moves", "your team"]):
                    break
                cleaned_line = _clean_battle_line(lines[j])
                m = _HP_LINE_PATTERN.search(cleaned_line)
                if not m:
                    m = _HP_FALLBACK_PATTERN.search(cleaned_line)
                if not m:
                    m = _HP_STATUS_PATTERN.search(cleaned_line)
                if not m:
                    continue
                candidate = str(m.group(1) or "").strip(" :*")
                if not candidate:
                    continue
                enemy_species_all.append(candidate)
                if int(m.group(2) or 0) > 0:
                    enemy_species_live.append(candidate)

            # Extract from enemy team block (live first, then all).
            for candidate in reversed(enemy_species_live):
                if self._normalize_pokemon_name(candidate) not in self_species:
                    return candidate
            for candidate in reversed(enemy_species_all):
                if self._normalize_pokemon_name(candidate) not in self_species:
                    return candidate

        # Keep last known enemy only if it is not one of our team species.
        if self._enemy_active_pokemon and self._normalize_pokemon_name(self._enemy_active_pokemon) not in self_species:
            return self._enemy_active_pokemon
        return ""

    async def _maybe_profile_pokemon(self, name: str, role: str) -> None:
        normalized = str(name or "").strip().lower()
        if not normalized:
            return
        if normalized in self._profiled_pokemon:
            return
        self._profiled_pokemon.add(normalized)

        info = await self._cached_get_pokemon_brief(normalized)
        if not info:
            self._log_event("pokeapi_profile_missing", {"role": role, "pokemon": name})
            return

        self._log_event(
            "pokeapi_profile",
            {
                "role": role,
                "pokemon": str(info.get("name", name)),
                "types": info.get("types", []),
                "stats": info.get("stats", {}),
            },
        )

    @staticmethod
    def _normalize_pokemon_name(name: str) -> str:
        return str(name or "").strip().lower()

    @staticmethod
    def _normalize_move_name(name: str) -> str:
        return str(name or "").strip().lower()

    def _enemy_battle_key(self, enemy_id: int | None) -> str:
        enemy_token = str(enemy_id if enemy_id is not None else "?")
        enemy_name = self._normalize_pokemon_name(self._enemy_active_pokemon)
        if enemy_name:
            return f"{enemy_token}:{enemy_name}"
        return enemy_token

    def _get_move_uses(self, enemy_id: int | None, move_name: str) -> int:
        battle_token = str(enemy_id if enemy_id is not None else "?")
        active_token = self._normalize_pokemon_name(self._active_pokemon) or "unknown"
        key = f"{battle_token}:{active_token}"
        move = self._normalize_move_name(move_name)
        return int((self._move_use_count_by_battle.get(key, {}) or {}).get(move, 0) or 0)

    def _record_move_use(self, enemy_id: int | None, move_name: str) -> None:
        battle_token = str(enemy_id if enemy_id is not None else "?")
        active_token = self._normalize_pokemon_name(self._active_pokemon) or "unknown"
        key = f"{battle_token}:{active_token}"
        move = self._normalize_move_name(move_name)
        if not move:
            return
        row = self._move_use_count_by_battle.setdefault(key, {})
        row[move] = int(row.get(move, 0) or 0) + 1

    @staticmethod
    def _type_multiplier(attacking_type: str, defender_types: list[str]) -> float:
        at = str(attacking_type or "").strip().lower()
        if not at:
            return 1.0
        chart = _TYPE_EFFECTIVENESS.get(at, {})
        mult = 1.0
        for dt in defender_types or []:
            mult *= float(chart.get(str(dt).lower(), 1.0))
        return mult

    async def _has_super_effective_stab_move(self, pokemon_name: str, enemy_types: list[str]) -> bool:
        info = await self._cached_get_pokemon_brief(pokemon_name)
        if not info:
            return False
        my_types = [str(t).lower() for t in (info.get("types", []) or [])]
        movepool = [str(m).strip().lower() for m in (info.get("movepool", []) or [])]
        candidates = movepool[:48]
        briefs = await asyncio.gather(*(self._cached_get_move_brief(move) for move in candidates), return_exceptions=True)
        for m in briefs:
            if isinstance(m, Exception):
                continue
            if not m:
                continue
            mtype = str(m.get("type", "") or "").strip().lower()
            dclass = str(m.get("damage_class", "") or "").strip().lower()
            power = int(m.get("power", 0) or 0)
            if dclass == "status" or power <= 0:
                continue
            if mtype not in my_types:
                continue
            if self._type_multiplier(mtype, enemy_types) > 1.0:
                return True
        return False

    async def _calculate_threat_state(self, enemy_name: str, bot_active_name: str, bot_hp_ratio: float) -> dict:
        enemy = await self._cached_get_pokemon_brief(enemy_name) if enemy_name else None
        bot = await self._cached_get_pokemon_brief(bot_active_name) if bot_active_name else None

        enemy_stats = (enemy or {}).get("stats", {}) if isinstance((enemy or {}).get("stats", {}), dict) else {}
        bot_stats = (bot or {}).get("stats", {}) if isinstance((bot or {}).get("stats", {}), dict) else {}
        enemy_speed = int(enemy_stats.get("speed", 0) or 0)
        bot_speed = int(bot_stats.get("speed", 0) or 0)
        if bot_speed > enemy_speed:
            speed_advantage = "BOT_FASTER"
        elif enemy_speed > bot_speed:
            speed_advantage = "ENEMY_FASTER"
        else:
            speed_advantage = "TIE"

        enemy_types = [str(t).lower() for t in ((enemy or {}).get("types", []) or [])]
        bot_types = [str(t).lower() for t in ((bot or {}).get("types", []) or [])]
        movepool = [str(m).strip().lower() for m in ((enemy or {}).get("movepool", []) or [])]
        enemy_key = self._enemy_battle_key(self._battle_state.get("enemy_id", -1))
        seen_moves = list(self._enemy_seen_moves_by_battle.get(enemy_key, set()))

        max_threat_score = 0.0
        highest_threat_type = ""
        enemy_atk = int(enemy_stats.get("attack", 100) or 100)
        enemy_spa = int(enemy_stats.get("special-attack", 100) or 100)
        candidate_moves = seen_moves if seen_moves else movepool[:48]
        briefs = await asyncio.gather(*(self._cached_get_move_brief(move) for move in candidate_moves), return_exceptions=True)
        for m in briefs:
            if isinstance(m, Exception):
                continue
            if not m:
                continue
            dmg_class = str(m.get("damage_class", "") or "").strip().lower()
            if dmg_class == "status":
                continue
            power = int(m.get("power", 0) or 0)
            if power <= 0:
                continue
            move_type = str(m.get("type", "") or "").strip().lower()
            stab = 1.5 if move_type in enemy_types else 1.0
            effectiveness = self._type_multiplier(move_type, bot_types)
            use_attack = str(dmg_class) == "physical"
            offense_stat = enemy_atk if use_attack else enemy_spa
            score = float(power) * stab * effectiveness * max(0.6, float(offense_stat) / 100.0)
            if score > max_threat_score:
                max_threat_score = score
                highest_threat_type = move_type

        # Theoretical movepool-only threat is noisy; treat it as lower confidence.
        if not seen_moves:
            max_threat_score *= 0.65

        is_lethal = bool(speed_advantage == "ENEMY_FASTER" and max_threat_score >= 240 and bot_hp_ratio <= 0.5)
        return {
            "speed_advantage": speed_advantage,
            "enemy_faster": speed_advantage == "ENEMY_FASTER",
            "max_threat_score": max_threat_score,
            "highest_threat_type": highest_threat_type,
            "is_lethal": is_lethal,
            "enemy_types": enemy_types,
            "bot_types": bot_types,
            "enemy_stats": enemy_stats,
            "bot_stats": bot_stats,
        }

    async def _score_action(self, button, state: dict) -> float:
        label = str(getattr(button, "label", "") or "").strip()
        cid = str(getattr(button, "custom_id", "") or "").strip().lower()
        threat = state.get("threat", {})
        switch_prompt = bool(state.get("switch_prompt", False))
        strategy_mode = str(state.get("strategy_mode", "standard") or "standard").strip().lower()
        level_target = str(state.get("level_target", "") or "").strip().lower()
        level_phase_target = str(state.get("level_phase_target", "") or "").strip().lower()
        hp_ratio = float(state.get("bot_hp_ratio", 1.0) or 1.0)
        stage_budget = int(state.get("stage_budget", 0) or 0)
        setup_moves_used = int(state.get("setup_moves_used", 0) or 0)
        setup_move_turns = int(state.get("setup_move_turns", 0) or 0)
        no_damaging_moves_available = bool(state.get("no_damaging_moves_available", False))
        has_viable_offensive_teammate = bool(state.get("has_viable_offensive_teammate", True))

        if cid == "ff" or "forfeit" in label.lower():
            return -9999.0

        if self._is_switch_button(button):
            score = 0.0 if switch_prompt else (-1000.0 if strategy_mode == "ev" else -120.0)
            enemy_hp_ratio = float(state.get("enemy_hp_ratio", 1.0) or 1.0)
            recent_outgoing_damage = float(state.get("recent_outgoing_damage", 0.0) or 0.0)
            if bool(state.get("baton_ready", False)) and state.get("baton_target") and setup_moves_used > 0 and not switch_prompt:
                # After setup investment, prefer passing boosts over hard switching.
                score -= 220.0
            if bool(state.get("baton_ready", False)) and setup_moves_used > 0 and stage_budget >= 6 and not no_damaging_moves_available and not switch_prompt:
                score -= 180.0
            if no_damaging_moves_available and has_viable_offensive_teammate and not switch_prompt:
                # If this mon cannot pressure directly, prefer pivoting to an attacker.
                score += 40.0 if bool(state.get("baton_ready", False)) else 200.0
            if not switch_prompt and strategy_mode == "standard":
                # Standard mode: allow pivots in clearly bad matchup states.
                enemy_types = [str(t).lower() for t in (threat.get("enemy_types", []) or [])]
                active_types = [str(t).lower() for t in (threat.get("bot_types", []) or [])]
                active_defensive_load = 1.0
                if enemy_types and active_types:
                    active_defensive_load = max(self._type_multiplier(et, active_types) for et in enemy_types)
                if active_defensive_load > 1.0:
                    score += (active_defensive_load - 1.0) * 180.0
                if active_defensive_load >= 1.8 and bool(threat.get("enemy_faster", False)):
                    score += 120.0
                if enemy_hp_ratio >= 0.6 and recent_outgoing_damage <= 2.0:
                    score += 90.0
            if strategy_mode == "level" and level_phase_target:
                if label.lower() == level_phase_target:
                    score += 260.0 if not switch_prompt else 360.0
                elif enemy_hp_ratio <= 0.42 and level_target:
                    score -= 30.0
            if threat.get("is_lethal") and threat.get("enemy_faster") and hp_ratio <= 0.5:
                score += 420.0
            if self._planned_switch_target and label.lower() == self._planned_switch_target.lower():
                score += 200.0

            target_info = await self._cached_get_pokemon_brief(label)
            target_types = [str(t).lower() for t in ((target_info or {}).get("types", []) or [])]
            incoming = str(threat.get("highest_threat_type", "") or "")
            if incoming and self._type_multiplier(incoming, target_types) < 1.0:
                score += 50.0

            enemy_types = [str(t).lower() for t in (threat.get("enemy_types", []) or [])]
            if await self._has_super_effective_stab_move(label, enemy_types):
                score += 50.0

            enemy_speed = int((threat.get("enemy_stats", {}) or {}).get("speed", 0) or 0)
            target_speed = int(((target_info or {}).get("stats", {}) or {}).get("speed", 0) or 0)
            if target_speed > enemy_speed:
                score += 30.0

            return score

        move_name = self._normalize_move_name(label)
        heur = _MOVE_HEURISTICS.get(move_name, {})
        heur_role = str(heur.get("role", "") or "")
        heur_base = float(heur.get("base_score", 0.0) or 0.0)
        heur_tags = {str(t).strip().lower() for t in (heur.get("tags", []) or [])}
        active_key = self._normalize_pokemon_name(self._active_pokemon)
        preview_meta = (self._preview_move_meta_by_pokemon.get(active_key, {}) or {}).get(move_name, {})
        if preview_meta:
            power = int(preview_meta.get("power", 0) or 0)
            move_type = str(preview_meta.get("type", "") or "").strip().lower()
            damage_class = "status" if power <= 0 and not self._is_damaging_move(move_name) else ""
            move_info = None
        else:
            move_info = await self._cached_get_move_brief(move_name)
            power = int((move_info or {}).get("power", 0) or 0)
            damage_class = str((move_info or {}).get("damage_class", "") or "").strip().lower()
            move_type = str((move_info or {}).get("type", "") or "").strip().lower()

        bot_types = [str(t).lower() for t in (threat.get("bot_types", []) or [])]
        enemy_types = [str(t).lower() for t in (threat.get("enemy_types", []) or [])]
        stab = 1.5 if move_type in bot_types else 1.0
        effectiveness = self._type_multiplier(move_type, enemy_types)
        bot_stats = threat.get("bot_stats", {}) or {}
        enemy_id = state.get("enemy_id", None)
        enemy_key = self._enemy_battle_key(enemy_id)
        enemy_seen_moves = self._enemy_seen_moves_by_battle.get(enemy_key, set())
        enemy_has_setup_history = any(self._is_setup_move(move) for move in enemy_seen_moves)
        move_priority = int((heur.get("priority", 0) or 0))
        if move_priority <= 0 and not preview_meta and "move_info" in locals():
            move_priority = int((move_info or {}).get("priority", 0) or 0)
        stages = state.get("stages", {}) or {}
        stage_budget = int(state.get("stage_budget", 0) or 0)
        allow_setup_first = bool(state.get("allow_setup_first", False))
        moves_taken = int(state.get("moves_taken", -1) or -1)
        force_offense_last_resort = bool(state.get("force_offense_last_resort", False))
        has_viable_offensive_teammate = bool(state.get("has_viable_offensive_teammate", True))
        enemy_hp_ratio = float(state.get("enemy_hp_ratio", 1.0) or 1.0)
        uses = self._get_move_uses(enemy_id, move_name)
        confirmed_statuses = self._enemy_confirmed_status_by_battle.get(enemy_key, set())
        status_move_target = self._status_effect_for_move(move_name)

        bot_max_hp_est = float(bot_stats.get("hp", 0) or 0)
        if bot_max_hp_est <= 0:
            bot_max_hp_est = 1.0
        recent_incoming_damage = float(state.get("recent_incoming_damage", 0.0) or 0.0)
        recent_outgoing_damage = float(state.get("recent_outgoing_damage", 0.0) or 0.0)
        recent_incoming_critical = bool(state.get("recent_incoming_critical", False))
        incoming_pressure_ratio = max(0.0, min(1.6, recent_incoming_damage / bot_max_hp_est))
        outgoing_pressure_ratio = max(0.0, min(2.0, recent_outgoing_damage / bot_max_hp_est))
        if recent_incoming_critical:
            incoming_pressure_ratio += 0.12
        dynamic_setup_threshold = 0.56 + min(0.22, incoming_pressure_ratio * 0.7)
        if threat.get("enemy_faster"):
            dynamic_setup_threshold += 0.08
        dynamic_setup_threshold = max(0.52, min(0.86, dynamic_setup_threshold))
        late_fight_pressure = 0.0 if moves_taken < 0 else min(0.32, float(moves_taken) * 0.02)
        low_setup_budget = stage_budget <= 2
        setup_progress = state.get("setup_progress", {}) or {}
        setup_progress_moves = setup_progress.get("moves", {}) if isinstance(setup_progress.get("moves", {}), dict) else {}
        setup_remaining_total = int(setup_progress.get("total_remaining", 0) or 0)
        setup_plus_two_remaining = int(setup_progress.get("plus_two_remaining", 0) or 0)

        # Immunity guard must happen before role-specific early returns.
        if power > 0 and damage_class != "status":
            if effectiveness == 0.0:
                return -999.0
            if not self._move_hits_enemy(label, enemy_id):
                return -999.0

        # Endgame conversion override: secure KOs instead of over-setup/heal loops.
        if power > 0 and damage_class != "status" and effectiveness > 0.0 and self._move_hits_enemy(label, enemy_id):
            acc = preview_meta.get("accuracy", None)
            if acc is None and "move_info" in locals():
                raw_acc = (move_info or {}).get("accuracy", None)
                acc = int(raw_acc) if isinstance(raw_acc, int) else None
            if enemy_hp_ratio <= 0.15:
                if isinstance(acc, int) and acc == 100:
                    return 9000.0 if move_priority > 0 else 8400.0
                return 7600.0 if move_priority > 0 else 6800.0

        if self._is_setup_move(label):
            # HARD BLOCK for max uses first - no exceptions
            max_uses = int(_SETUP_MOVE_MAX_USES.get(move_name, 0) or 0)
            if max_uses > 0 and uses >= max_uses:
                # Absolutely don't allow any more uses of this move
                return -999.0
            progress_row = setup_progress_moves.get(move_name, {}) if isinstance(setup_progress_moves, dict) else {}
            remaining_uses = int(progress_row.get("remaining_uses", max(0, max_uses - uses) if max_uses > 0 else 99) or 0)
            plus_two_count = int(progress_row.get("plus_two_count", 0) or 0)
            effective_gain = int(progress_row.get("effective_gain", 0) or 0)
            if max_uses > 0 and remaining_uses <= 0:
                return -999.0
            
            score = 40.0 + heur_base
            if threat.get("is_lethal"):
                score -= 100.0
            targets = _SETUP_MOVE_TO_STATS.get(move_name, set())
            heur_boosts = heur.get("boosts", {}) if isinstance(heur.get("boosts", {}), dict) else {}
            if heur_boosts:
                targets = set(heur_boosts.keys())
            if targets and all(int(stages.get(stat, 0)) >= 6 for stat in targets):
                score -= 200.0
            if "all_in_sweeper" in heur_tags and hp_ratio <= 0.6:
                score -= 280.0
            if "high_risk_sweeper" in heur_tags and hp_ratio <= 0.7:
                score -= 110.0
            if "spe" in targets and threat.get("enemy_faster"):
                score += 50.0
            if allow_setup_first and not threat.get("is_lethal"):
                # Aggressively prefer setup while healthy and still below cap budget.
                # But exclude low_utility setup moves like Focus Energy (crit chance only)
                if "low_utility" not in heur_tags:
                    score += 130.0
                    if stage_budget < 8:
                        score += 40.0
            if (
                move_name in {"swords dance", "nasty plot", "calm mind", "bulk up", "dragon dance", "quiver dance"}
                and hp_ratio >= 0.82
                and enemy_hp_ratio >= 0.6
                and stage_budget <= 0
                and not threat.get("is_lethal")
                and incoming_pressure_ratio <= 0.24
                and moves_taken <= 10
            ):
                # Safe opener setup window for sweepers (e.g., Arceus) before committing to attacks.
                score += 220.0
            if no_damaging_moves_available and has_viable_offensive_teammate and stage_budget <= 2:
                # Don't spend early turns on setup when this slot cannot capitalize with damage.
                score -= 220.0
            if hp_ratio < 0.42:
                score -= 40.0
            # Dynamic risk gate: if we just took heavy damage, avoid greedy setup.
            if incoming_pressure_ratio >= 0.20:
                score -= float(95.0 + (incoming_pressure_ratio * 140.0))
            if hp_ratio < dynamic_setup_threshold:
                score -= 180.0

            # Continue setup to capped use where safe, with extra priority on +2 setup lines.
            safe_to_continue_setup = (
                (not threat.get("is_lethal"))
                and hp_ratio >= max(0.62, dynamic_setup_threshold - 0.12)
                and incoming_pressure_ratio <= 0.26
                and enemy_hp_ratio >= 0.42
            )
            if safe_to_continue_setup and setup_remaining_total > 0:
                score += 110.0
                score += float(min(3, remaining_uses) * 38)
                score += float(min(4, effective_gain) * 26)
                if plus_two_count > 0:
                    # Explicitly value +2 setup increments while they are still available.
                    score += 120.0 + float(min(2, plus_two_count) * 35)
                if setup_plus_two_remaining > 0:
                    score += 40.0

            # Diminishing setup EV as boosts accumulate.
            if stage_budget >= 4:
                score -= float((stage_budget - 3) * 32)
            if stage_budget >= 8:
                score -= 140.0
            if late_fight_pressure > 0 and not low_setup_budget:
                score -= float(late_fight_pressure * 240.0)
            # Global anti-looping pressure for setup lines - much stronger now
            score -= float(uses * 55)  # Increased from 28 to 55 to prevent spam
            return score

        if self._is_recovery_move(label):
            # ONLY use recovery if truly needed or actively low
            # Heavy penalty for unnecessary healing - don't waste turns
            if hp_ratio > 0.75:
                return -300.0  # Don't recover at high HP
            
            score = heur_base
            # Recovery bonuses only trigger at meaningful thresholds
            if hp_ratio < 0.45:
                score += 280.0  # Critical HP - heal aggressively
            elif hp_ratio < 0.5:
                score += 200.0  # Getting low
            elif hp_ratio < 0.6 and not threat.get("is_lethal"):
                score += 140.0  # Preventive healing
            elif hp_ratio < 0.35 and not threat.get("enemy_faster"):
                score += 120.0  # Emergency heal
            else:
                # Mid-high HP with no emergency - strongly discourage
                score -= 250.0
            
            if hp_ratio < 0.3 and threat.get("enemy_faster") and threat.get("is_lethal"):
                score -= 80.0  # Already low and enemy faster = risky
            # Dynamic recover EV from recent incoming damage.
            if incoming_pressure_ratio >= 0.20:
                score += float(90.0 + (incoming_pressure_ratio * 200.0))
            if incoming_pressure_ratio <= 0.06 and hp_ratio >= 0.55:
                score -= 120.0
            # If baton pass is ready with high boosts and safe HP, avoid wasting the turn on healing.
            if stage_budget >= 10 and state.get("baton_target") and hp_ratio >= 0.38 and not threat.get("is_lethal"):
                score -= 220.0
            # Prevent heal spam: each additional use gets heavily penalized
            if uses >= 1:
                score -= float(uses * 200)  # Massive penalty for repeated healing
            
            return score

        if self._is_baton_pass_move(label):
            stage_budget = int(state.get("stage_budget", 0) or 0)
            setup_moves_used = int(state.get("setup_moves_used", 0) or 0)
            setup_move_turns = int(state.get("setup_move_turns", 0) or 0)
            baton_ready = bool(state.get("baton_ready", False))
            recent_setup_window = setup_move_turns > 0 and (moves_taken < 0 or moves_taken <= 6)
            baton_target_name = str(state.get("baton_target", "") or "").strip()
            if not baton_target_name:
                # Never attempt Baton Pass when there is no valid receiver.
                return -420.0
            if not has_viable_offensive_teammate and setup_moves_used <= 0 and stage_budget <= 0 and not self._pending_baton_stages:
                return -220.0
            if no_damaging_moves_available and state.get("baton_target") and not threat.get("is_lethal"):
                # When current mon cannot pressure, Baton Pass should be preferred over plain switching.
                pivot_score = 240.0 + heur_base
                if setup_moves_used >= 1:
                    pivot_score += 70.0
                if setup_move_turns >= 2:
                    # Explicit user requirement: 2+ setup uses => high-priority Baton Pass.
                    pivot_score += 260.0
                if threat.get("enemy_faster") and hp_ratio <= 0.6:
                    pivot_score += 80.0
                return pivot_score
            if setup_moves_used == 0 and stage_budget <= 0 and not self._pending_baton_stages:
                # Baton Pass should not preempt setup; pass value must exist first.
                return -220.0
            if stage_budget < 6 and setup_moves_used == 0 and not self._pending_baton_stages:
                # Keep baton available as a pivot option when this mon has no offense.
                if no_damaging_moves_available:
                    return 40.0 + heur_base
                return 0.0 + heur_base

            # Dynamic baton pass preconditions: pass only when value transfer is real.
            if not state.get("baton_target"):
                return -160.0
            if stage_budget < 4 and setup_moves_used <= 0 and not self._pending_baton_stages:
                if no_damaging_moves_available and setup_move_turns >= 1:
                    return 80.0 + heur_base
                return -120.0
            if stage_budget < 6 and setup_moves_used <= 1 and not self._pending_baton_stages:
                if setup_move_turns >= 2:
                    return 220.0 + heur_base
                return -20.0
            if hp_ratio < 0.34 and incoming_pressure_ratio > 0.12:
                return -180.0
            
            score = 170.0 + heur_base + float(setup_moves_used * 22)
            if setup_moves_used > 0:
                score += 120.0
            if no_damaging_moves_available and has_viable_offensive_teammate:
                score += 120.0
            if recent_setup_window:
                score += 90.0
            if setup_move_turns >= 2:
                # User rule: 2+ setup uses should make baton pass high priority.
                score += 260.0
            if self._pending_baton_stages:
                score += 80.0
            if stage_budget > 0:
                score += float(stage_budget * 18)
            if baton_ready and setup_moves_used > 0 and stage_budget >= 6:
                score += 160.0
            # Preemptive pass window: if enemy is faster, pass before HP gets too low.
            if threat.get("enemy_faster") and hp_ratio <= 0.78 and not threat.get("is_lethal"):
                score += 90.0
            if threat.get("enemy_faster") and hp_ratio <= 0.68 and stage_budget >= 8:
                score += 80.0
            # Unsafe pass when we are likely to get hit first and fall before passing.
            if threat.get("enemy_faster") and hp_ratio <= 0.6:
                score -= 180.0
            if threat.get("is_lethal") and hp_ratio <= 0.55:
                score -= 260.0
            if hp_ratio <= 0.35:
                score -= 220.0
            # High-priority handoff: when boosts are already high/maxed and pass is safe, force baton pass preference.
            if (stage_budget >= 10 or (setup_moves_used > 1 and stage_budget >= 6) or self._pending_baton_stages) and hp_ratio >= 0.38 and not threat.get("is_lethal"):
                score += 220.0
            if (stage_budget >= 12 or setup_moves_used > 1) and hp_ratio >= 0.45 and (not threat.get("enemy_faster") or hp_ratio >= 0.55):
                score += 260.0
            if incoming_pressure_ratio >= 0.24 and hp_ratio <= 0.5:
                score -= 220.0
            return score

        if damage_class == "status" or power <= 0:
            # Generic status/debuff move handling with diminishing returns.
            score = -15.0 + heur_base
            major_statuses = {"poison", "burn", "paralysis", "sleep"}
            enemy_has_major_status = any(s in confirmed_statuses for s in major_statuses)
            if status_move_target in major_statuses and enemy_has_major_status and status_move_target not in confirmed_statuses:
                # Enemy already has a major status; don't waste a turn trying to override it.
                return -500.0
            if status_move_target and status_move_target in confirmed_statuses:
                score -= 260.0
            if heur_role == "debuff" or "wall_breaker" in heur_tags:
                score += 40.0 if uses == 0 else (10.0 if uses == 1 else -80.0)
            if any(k in move_name for k in ("toxic", "will-o-wisp", "thunder wave", "leech seed")):
                score += 35.0 if uses == 0 else -30.0
            if heur_role in {"status", "debuff"} and uses == 0:
                score += 20.0
            if heur_role in {"status", "debuff"} and uses >= 2 and status_move_target and status_move_target in confirmed_statuses:
                score -= 120.0
            if "free_turns" in heur_tags and uses == 0:
                score += 30.0
            if "creates_setup_window" in heur_tags and stage_budget < 4:
                score -= 120.0
            score -= float(max(0, uses - 1) * 24)
            return score

        if heur_role == "damage_debuff":
            score = float(power) * stab * effectiveness + heur_base
            enemy_debuff_stages = self._enemy_stat_stage_by_battle.get(enemy_key, {}) or {}
            debuff_targets = self._debuff_targets_from_tags(heur_tags)
            if debuff_targets:
                for stat_key, drop_amount in debuff_targets.items():
                    current = int(enemy_debuff_stages.get(stat_key, 0) or 0)
                    if current > 0:
                        current = 0
                    room = max(0, 6 - abs(current))
                    if room <= 0:
                        score -= 120.0
                        continue
                    score += float(min(room, int(drop_amount or 1)) * 22)
                    if room <= int(drop_amount or 1):
                        score -= 10.0
            if "drops_spe" in heur_tags or "speed_control" in heur_tags:
                score += 45.0 if threat.get("enemy_faster") else 10.0
                if threat.get("enemy_faster") and hp_ratio <= 0.75:
                    score += 30.0
            if "drops_atk" in heur_tags:
                enemy_physical_bias = int((threat.get("enemy_stats", {}) or {}).get("attack", 0) or 0)
                enemy_special_bias = int((threat.get("enemy_stats", {}) or {}).get("special-attack", 0) or 0)
                if enemy_physical_bias >= enemy_special_bias:
                    score += 40.0
                if threat.get("enemy_faster"):
                    score += 10.0
            if "drops_spa" in heur_tags:
                enemy_physical_bias = int((threat.get("enemy_stats", {}) or {}).get("attack", 0) or 0)
                enemy_special_bias = int((threat.get("enemy_stats", {}) or {}).get("special-attack", 0) or 0)
                if enemy_special_bias >= enemy_physical_bias:
                    score += 40.0
            if "drops_def" in heur_tags:
                score += 25.0 if stage_budget >= 2 else 10.0
            if "drops_spd" in heur_tags:
                score += 20.0 if hp_ratio <= 0.8 else 10.0
            if "bypasses_substitute" in heur_tags:
                score += 20.0
            if any(tag.startswith("chance_drop") for tag in heur_tags):
                score += 12.0
                if threat.get("enemy_faster") or stage_budget >= 4:
                    score += 10.0
            if "low_accuracy" in heur_tags:
                score -= 20.0
            if enemy_has_setup_history and ("resets_enemy_stats" in heur_tags or "drops_atk" in heur_tags or "drops_spa" in heur_tags):
                score += 45.0
            if recent_incoming_damage > 0:
                score += min(35.0, incoming_pressure_ratio * 80.0)
            if recent_outgoing_damage > 0:
                score += min(20.0, outgoing_pressure_ratio * 40.0)
            if uses >= 2:
                score -= float((uses - 1) * 35)
            return score

        if heur_role == "damage_buff":
            score = float(power) * stab * effectiveness + heur_base
            if "raises_spe" in heur_tags or "speed_control" in heur_tags:
                score += 35.0 if threat.get("enemy_faster") else 12.0
            if "raises_atk" in heur_tags or "raises_spa" in heur_tags:
                score += 22.0 if hp_ratio >= 0.45 else -20.0
            if "chance_raise_atk" in heur_tags or "chance_raise_spa" in heur_tags:
                score += 8.0 if uses == 0 else -20.0
            if "clears_hazards" in heur_tags:
                score += 20.0
            if "bypasses_substitute" in heur_tags:
                score += 15.0
            if threat.get("is_lethal") and hp_ratio <= 0.55:
                score -= 80.0
            if hp_ratio < dynamic_setup_threshold:
                score -= 60.0
            if stage_budget >= 4:
                score += 18.0
            if recent_outgoing_damage > 0:
                score += min(30.0, outgoing_pressure_ratio * 60.0)
            if uses >= 2:
                score -= float((uses - 1) * 30)
            return score

        if heur_role == "damage_sustain":
            score = float(power) * stab * effectiveness + heur_base
            if hp_ratio <= 0.6:
                score += 150.0
            if hp_ratio <= 0.4:
                score += 250.0
            if incoming_pressure_ratio >= 0.20:
                score += float(100.0 + (incoming_pressure_ratio * 150.0))
            if recent_outgoing_damage > 0:
                score += min(24.0, outgoing_pressure_ratio * 45.0)
            if threat.get("enemy_faster") and hp_ratio <= 0.55:
                score += 35.0
            if uses >= 2:
                score -= float((uses - 1) * 28)
            return score

        if heur_role == "damage_utility":
            score = float(power) * stab * effectiveness + heur_base
            if "breaks_screens" in heur_tags:
                score += 18.0
            if "grounds_flying_types" in heur_tags:
                score += 20.0 if threat.get("enemy_faster") else 8.0
            if "resets_enemy_stats" in heur_tags:
                score += 50.0 if enemy_has_setup_history else 15.0
            if "removes_item" in heur_tags:
                score += 25.0 if uses == 0 else 8.0
            if "high_utility" in heur_tags:
                score += 10.0
            if recent_incoming_damage > 0:
                score += min(18.0, incoming_pressure_ratio * 35.0)
            if uses >= 2:
                score -= float((uses - 1) * 25)
            return score

        if heur_role == "damage_variable":
            score = float(power) * stab * effectiveness + heur_base
            if move_name in {"tera blast", "weather ball", "judgment", "multi-attack"}:
                score += 12.0
            if effectiveness >= 1.5:
                score += 25.0
            elif effectiveness <= 0.5:
                score -= 20.0
            if recent_outgoing_damage > 0:
                score += min(15.0, outgoing_pressure_ratio * 30.0)
            return score

        if heur_role == "damage_lock":
            score = float(power) * stab * effectiveness + heur_base
            if "locks_move" in heur_tags:
                score -= 15.0
            if "scales_damage" in heur_tags:
                score += float(min(4, max(0, uses)) * 20)
            if move_name in {"outrage", "thrash", "petal dance"}:
                if threat.get("is_lethal") or hp_ratio <= 0.5:
                    score -= 120.0
                elif stage_budget >= 4 and hp_ratio >= 0.7:
                    score += 35.0
            if move_name in {"rollout", "ice ball"}:
                score += 18.0 if uses == 0 else float(max(0, 30 - uses * 6))
            if uses >= 2:
                score -= float((uses - 1) * 40)
            return score

        if heur_role == "damage_status":
            score = float(power) * stab * effectiveness + heur_base
            if "high_chance_poison" in heur_tags or "chance_poison" in heur_tags:
                score += 22.0 if hp_ratio >= 0.35 else 10.0
            if "high_chance_burn" in heur_tags or "guaranteed_burn" in heur_tags:
                enemy_physical_bias = int((threat.get("enemy_stats", {}) or {}).get("attack", 0) or 0)
                enemy_special_bias = int((threat.get("enemy_stats", {}) or {}).get("special-attack", 0) or 0)
                if enemy_physical_bias >= enemy_special_bias:
                    score += 45.0
            if "high_chance_paralysis" in heur_tags or "guaranteed_paralysis" in heur_tags:
                score += 35.0 if threat.get("enemy_faster") else 12.0
            if "high_chance_flinch" in heur_tags or "chance_flinch" in heur_tags:
                score += 18.0 if threat.get("enemy_faster") else 8.0
            if "low_accuracy" in heur_tags:
                score -= 25.0
            if recent_incoming_damage > 0:
                score += min(18.0, incoming_pressure_ratio * 30.0)
            if uses >= 2:
                score -= float((uses - 1) * 25)
            return score

        stab = 1.5 if move_type in bot_types else 1.0
        score = float(power) * stab * effectiveness + heur_base
        level_target = str(state.get("level_target", "") or "").strip().lower()
        if move_name == "stored power":
            # Stored Power scales with stat boosts; reward setup payoff.
            score += float(stage_budget * 18)
        if move_name == "power trip":
            score += float(stage_budget * 18)

        if heur_role == "damage_priority" and threat.get("enemy_faster"):
            score += 45.0
        if move_priority > 0:
            score += float(move_priority * 18)
            if threat.get("enemy_faster"):
                score += float(move_priority * 22)
            if hp_ratio <= 0.55:
                score += float(move_priority * 10)
            if enemy_hp_ratio <= 0.35:
                score += float((0.35 - enemy_hp_ratio) * 220.0 + move_priority * 12)
            if enemy_hp_ratio <= 0.2 and threat.get("enemy_faster"):
                score += 55.0
            if hp_ratio <= 0.4 and threat.get("enemy_faster"):
                score += 20.0
        if "first_turn_only" in heur_tags and moves_taken not in (0, 1):
            score -= 80.0
        if heur_role == "damage_drawback" and "spammable_only_once" in heur_tags and uses >= 1:
            score -= 140.0
        if heur_role == "damage_drawback" and "must_recharge" in heur_tags and (hp_ratio < 0.5 or threat.get("is_lethal")):
            score -= 120.0
        if move_name == "knock off" and uses == 0:
            score += 35.0
        if move_name == "body press":
            score += float(int(stages.get("def", 0) or 0) * 14)
        if move_name == "foul play":
            enemy_key = self._enemy_battle_key(enemy_id)
            profile = self._enemy_offense_profile.get(enemy_key, {})
            if int(profile.get("physical", 0) or 0) >= int(profile.get("special", 0) or 0):
                score += 25.0

        # Dynamic offensive EV: reward stable pressure when setup is already done
        # or when incoming risk is growing.
        if stage_budget >= 6:
            score += 55.0
        if strategy_mode == "level" and level_phase_target and active_key != level_phase_target and enemy_hp_ratio <= 0.35:
            if power > 0 and damage_class != "status":
                score -= 700.0
                if move_priority > 0:
                    score -= 120.0
        if incoming_pressure_ratio >= 0.18:
            score += float(35.0 + incoming_pressure_ratio * 110.0)
        if recent_outgoing_damage > 0 and outgoing_pressure_ratio >= 0.25:
            score += min(120.0, outgoing_pressure_ratio * 90.0)
        if late_fight_pressure > 0 and effectiveness >= 1.0:
            score += float(late_fight_pressure * 180.0)
        if move_priority > 0 and effectiveness >= 1.0:
            if enemy_hp_ratio <= 0.25:
                score += 45.0
            if threat.get("enemy_faster") and enemy_hp_ratio <= 0.45:
                score += 25.0

        # Accuracy-aware scoring from preview/API metadata.
        acc = preview_meta.get("accuracy", None)
        if acc is None and 'move_info' in locals():
            raw_acc = (move_info or {}).get("accuracy", None)
            acc = int(raw_acc) if isinstance(raw_acc, int) else None
        if isinstance(acc, int) and 0 < acc < 100:
            score *= max(0.72, float(acc) / 100.0)

        atk = int(bot_stats.get("attack", 0) or 0)
        spa = int(bot_stats.get("special-attack", 0) or 0)
        best_class = "physical" if atk >= spa else "special"
        if damage_class == best_class:
            score *= 1.5
        if allow_setup_first and not threat.get("is_lethal") and stage_budget < 8 and not force_offense_last_resort:
            # Avoid flipping to offense too early when setup plan is still active.
            score -= 90.0
        if (
            setup_remaining_total > 0
            and allow_setup_first
            and not threat.get("is_lethal")
            and hp_ratio >= max(0.62, dynamic_setup_threshold - 0.12)
            and incoming_pressure_ratio <= 0.24
            and enemy_hp_ratio >= 0.45
            and moves_taken <= 8
        ):
            # Keep setup line prioritized to remaining capped uses before pivoting to offense.
            score -= 180.0
            if setup_plus_two_remaining > 0:
                score -= 80.0
        if (
            allow_setup_first
            and stage_budget <= 0
            and hp_ratio >= 0.82
            and enemy_hp_ratio >= 0.6
            and incoming_pressure_ratio <= 0.24
            and not threat.get("is_lethal")
            and moves_taken <= 10
            and move_name not in {"stored power", "power trip"}
        ):
            # Stronger offense dampening in safe opener windows so setup moves can win.
            score -= 140.0
        if (
            allow_setup_first
            and stage_budget <= 0
            and setup_moves_used <= 0
            and hp_ratio >= 0.95
            and enemy_hp_ratio >= 0.7
            and moves_taken in (0, 1)
            and not threat.get("is_lethal")
        ):
            # Prevent early priority/offense from stealing turn 1 setup windows.
            score -= 260.0
        if allow_setup_first and stage_budget <= 1 and setup_moves_used <= 0 and hp_ratio >= 0.9 and enemy_hp_ratio >= 0.65 and not threat.get("is_lethal") and moves_taken <= 2:
            # Favor early setup for damage-oriented mons in clean opener windows.
            score -= 260.0
        # Small diminishing returns for repeatedly selecting the same non-finishing damage move.
        if uses >= 3 and effectiveness <= 1.0 and power < 90:
            score -= float((uses - 2) * 18)
        if force_offense_last_resort:
            score += 130.0
            if move_name in {"stored power", "power trip"}:
                score += 120.0
        return score

    def _parse_self_stat_caps_and_drops(self, text: str) -> None:
        active_name = self._normalize_pokemon_name(self._active_pokemon)
        if not active_name:
            return

        caps = self._capped_stats_by_pokemon.setdefault(active_name, set())
        stages = self._ensure_stat_stage_row(active_name)
        lines = str(text or "").splitlines()
        for line in lines:
            lowered = line.lower()
            if active_name not in lowered:
                continue

            delta_match = _STAT_DELTA_PATTERN.search(lowered)
            parsed_delta = 0
            if delta_match:
                sign = 1 if delta_match.group(1) == "+" else -1
                parsed_delta = sign * int(delta_match.group(2) or 0)

            for token, short in _STAT_TOKENS.items():
                if token not in lowered:
                    continue
                if "won't go any higher" in lowered:
                    caps.add(short)

                # Stage estimation from combat lines to avoid wasting a setup turn at cap.
                if " rose" in lowered:
                    if parsed_delta > 0:
                        delta = parsed_delta
                    elif "harshly rose" in lowered:
                        delta = 2
                    else:
                        delta = 1
                    stages[short] = max(-6, min(6, int(stages.get(short, 0)) + delta))

                if " fell" in lowered:
                    if parsed_delta < 0:
                        delta = parsed_delta
                    elif "harshly fell" in lowered:
                        delta = -2
                    else:
                        delta = -1
                    stages[short] = max(-6, min(6, int(stages.get(short, 0)) + delta))

                if int(stages.get(short, 0)) >= 6:
                    caps.add(short)
                else:
                    caps.discard(short)

    def _learn_move_type_from_text(self, text: str) -> None:
        # Learns from lines like: "Arceus used Judgment!" and next lines ":normaltype: ..."
        lines = str(text or "").splitlines()
        pending_move = ""
        our_name = self._normalize_pokemon_name(self._active_pokemon)
        for line in lines:
            used = _USED_MOVE_PATTERN.search(line)
            if used:
                who = self._normalize_pokemon_name(self._extract_move_actor(line))
                move_name = self._normalize_move_name(used.group(1))
                if who and our_name and who == our_name:
                    pending_move = move_name
                else:
                    pending_move = ""

            type_match = _MOVE_TYPE_LINE_PATTERN.search(line)
            if pending_move and type_match:
                mtype = str(type_match.group(1) or "").strip().lower()
                if mtype:
                    self._move_type_by_name[pending_move] = mtype
                pending_move = ""

            if pending_move and "doesn't affect" in line.lower():
                # Even without type, we can still mark this move as immune on the current enemy.
                enemy_key = self._enemy_battle_key(None)
                blocked = self._immune_moves_by_enemy.setdefault(enemy_key, set())
                blocked.add(pending_move)
                pending_move = ""

    def _learn_immunity_from_text(self, text: str, enemy_id: int | None) -> None:
        lines = str(text or "").splitlines()
        enemy_key = self._enemy_battle_key(enemy_id)
        blocked = self._immune_moves_by_enemy.setdefault(enemy_key, set())
        pending_our_move = ""
        our_name = self._normalize_pokemon_name(self._active_pokemon)
        for line in lines:
            used = _USED_MOVE_PATTERN.search(line)
            if used:
                who = self._normalize_pokemon_name(self._extract_move_actor(line))
                move_name = self._normalize_move_name(used.group(1))
                pending_our_move = move_name if (who and our_name and who == our_name) else ""
                continue

            if pending_our_move and "doesn't affect" in line.lower():
                blocked.add(pending_our_move)
                pending_our_move = ""

    @staticmethod
    def _status_effect_for_move(move_name: str) -> str:
        m = str(move_name or "").strip().lower()
        if m in {"toxic", "poison powder", "poison gas", "poison fang"}:
            return "poison"
        if m in {"will o wisp", "will-o-wisp"}:
            return "burn"
        if m in {"thunder wave", "stun spore", "glare", "nuzzle"}:
            return "paralysis"
        if m in {"spore", "sleep powder", "hypnosis", "lovely kiss", "dark void", "yawn"}:
            return "sleep"
        if m in {"leech seed"}:
            return "seed"
        return ""

    def _learn_enemy_status_from_text(self, text: str, enemy_id: int | None) -> None:
        enemy_key = self._enemy_battle_key(enemy_id)
        statuses = self._enemy_confirmed_status_by_battle.setdefault(enemy_key, set())
        before = set(statuses)
        for line in str(text or "").splitlines():
            lowered = line.lower()
            if "was badly poisoned" in lowered or "was poisoned" in lowered:
                statuses.add("poison")
            if "was burned" in lowered:
                statuses.add("burn")
            if "was paralyzed" in lowered:
                statuses.add("paralysis")
            if "fell asleep" in lowered or "was put to sleep" in lowered:
                statuses.add("sleep")
            if "was seeded" in lowered:
                statuses.add("seed")
        if statuses != before:
            self._log_enemy_knowledge(
                "enemy_status_revealed",
                enemy_id,
                {
                    "new_statuses": sorted(statuses - before),
                },
            )

    @staticmethod
    def _debuff_targets_from_tags(heur_tags: set[str]) -> dict[str, int]:
        targets: dict[str, int] = {}
        for tag in heur_tags:
            if tag == "drops_atk":
                targets["atk"] = max(targets.get("atk", 0), 1)
            elif tag == "drops_def":
                targets["def"] = max(targets.get("def", 0), 1)
            elif tag == "drops_spa":
                targets["spa"] = max(targets.get("spa", 0), 1)
            elif tag == "drops_spd":
                targets["spd"] = max(targets.get("spd", 0), 1)
            elif tag == "drops_spd_sharply":
                targets["spd"] = max(targets.get("spd", 0), 2)
            elif tag == "drops_spe":
                targets["spe"] = max(targets.get("spe", 0), 1)
            elif tag.startswith("chance_drop_atk"):
                targets["atk"] = max(targets.get("atk", 0), 1)
            elif tag.startswith("chance_drop_def"):
                targets["def"] = max(targets.get("def", 0), 1)
            elif tag.startswith("chance_drop_spa"):
                targets["spa"] = max(targets.get("spa", 0), 1)
            elif tag.startswith("chance_drop_spd"):
                targets["spd"] = max(targets.get("spd", 0), 1)
            elif tag.startswith("chance_drop_spe"):
                targets["spe"] = max(targets.get("spe", 0), 1)
        return targets

    def _learn_enemy_stat_drops_from_text(self, text: str, enemy_id: int | None) -> None:
        enemy_name = self._normalize_pokemon_name(self._enemy_active_pokemon)
        if not enemy_name:
            return

        enemy_key = self._enemy_battle_key(enemy_id)
        stages = self._enemy_stat_stage_by_battle.setdefault(enemy_key, {})
        updates: list[dict[str, object]] = []
        for line in str(text or "").splitlines():
            lowered = line.lower()
            if enemy_name not in lowered:
                continue

            delta_match = _STAT_DELTA_PATTERN.search(lowered)
            parsed_delta = 0
            if delta_match:
                sign = 1 if delta_match.group(1) == "+" else -1
                parsed_delta = sign * int(delta_match.group(2) or 0)

            for token, short in _STAT_TOKENS.items():
                if token not in lowered:
                    continue

                if " fell" in lowered:
                    if parsed_delta < 0:
                        delta = parsed_delta
                    elif "harshly fell" in lowered:
                        delta = -2
                    else:
                        delta = -1
                    before = int(stages.get(short, 0) or 0)
                    after = max(-6, min(6, before + delta))
                    stages[short] = after
                    if after != before:
                        updates.append({"stat": short, "before": before, "after": after, "delta": after - before})

                if " rose" in lowered:
                    if parsed_delta > 0:
                        delta = parsed_delta
                    elif "harshly rose" in lowered:
                        delta = 2
                    else:
                        delta = 1
                    before = int(stages.get(short, 0) or 0)
                    after = max(-6, min(6, before + delta))
                    stages[short] = after
                    if after != before:
                        updates.append({"stat": short, "before": before, "after": after, "delta": after - before})

                if "won't go any lower" in lowered:
                    before = int(stages.get(short, 0) or 0)
                    stages[short] = -6
                    if before != -6:
                        updates.append({"stat": short, "before": before, "after": -6, "delta": -6 - before})

        if updates:
            self._log_enemy_knowledge(
                "enemy_stat_stage_updated",
                enemy_id,
                {
                    "updates": updates[:6],
                },
            )

    async def _learn_enemy_offense_from_text(self, text: str, enemy_id: int | None) -> None:
        enemy_name = self._normalize_pokemon_name(self._enemy_active_pokemon)
        enemy_key = self._enemy_battle_key(enemy_id)
        profile = self._enemy_offense_profile.setdefault(enemy_key, {"physical": 0, "special": 0})
        seen = self._enemy_seen_moves_by_battle.setdefault(enemy_key, set())
        our_name = self._normalize_pokemon_name(self._active_pokemon)
        knowledge = self._ensure_enemy_knowledge_row(enemy_id, enemy_name)
        moves_row = knowledge.setdefault("moves", {"revealed": set(), "possible": set(), "evidence": []})
        revealed_moves = moves_row.setdefault("revealed", set())

        for line in str(text or "").splitlines():
            used = _USED_MOVE_PATTERN.search(line)
            if not used:
                continue
            who = self._normalize_pokemon_name(self._extract_move_actor(line))

            # If we know enemy name, enforce it; otherwise treat non-self users as enemy actors.
            if enemy_name and who and who != enemy_name:
                continue
            if (not enemy_name) and our_name and who == our_name:
                continue

            move_name = self._normalize_move_name(used.group(1))
            if not move_name:
                continue
            new_move = move_name not in seen
            seen.add(move_name)
            revealed_moves.add(move_name)
            move_info = await self._cached_get_move_brief(move_name)
            damage_class = str((move_info or {}).get("damage_class", "")).strip().lower()
            if damage_class in ("physical", "special"):
                profile[damage_class] = int(profile.get(damage_class, 0) or 0) + 1
            if new_move:
                self._log_enemy_knowledge(
                    "enemy_move_revealed",
                    enemy_id,
                    {
                        "move": move_name,
                        "damage_class": damage_class,
                        "enemy": enemy_name,
                    },
                )

    @staticmethod
    def _extract_move_actor(line: str) -> str:
        raw = str(line or "")
        who_match = _WHO_USED_PATTERN.search(raw)
        if who_match:
            return str(who_match.group(1) or "").strip(" :*")

        cleaned = _clean_battle_line(raw)
        clean_match = _WHO_USED_CLEAN_PATTERN.search(cleaned)
        if clean_match:
            return str(clean_match.group(1) or "").strip(" :*")

        used_idx = cleaned.lower().find(" used ")
        if used_idx > 0:
            prefix = cleaned[:used_idx].strip(" -*:\t")
            if prefix:
                return prefix

        return ""

    def _extract_recent_damage_signals(self, text: str) -> dict[str, object]:
        incoming_damage = 0
        outgoing_damage = 0
        incoming_critical = False
        outgoing_critical = False

        our_name = self._normalize_pokemon_name(self._active_pokemon)
        enemy_name = self._normalize_pokemon_name(self._enemy_active_pokemon)
        last_actor = ""
        last_actor_is_enemy = False
        last_actor_is_self = False
        last_was_critical = False

        for line in str(text or "").splitlines():
            lowered = line.lower()
            used = _USED_MOVE_PATTERN.search(line)
            if used:
                actor = self._normalize_pokemon_name(self._extract_move_actor(line))
                last_actor = actor
                last_actor_is_self = bool(actor and our_name and actor == our_name)
                last_actor_is_enemy = bool(actor and enemy_name and actor == enemy_name)
                if not enemy_name and actor and our_name and actor != our_name:
                    last_actor_is_enemy = True
                if not our_name and actor and enemy_name and actor != enemy_name:
                    last_actor_is_self = True
                last_was_critical = "critical hit" in lowered
                continue

            dmg = _DMG_DEALT_PATTERN.search(lowered)
            if dmg:
                value = int(str(dmg.group(1) or "0").replace(",", "") or 0)
                if last_actor_is_enemy:
                    incoming_damage += value
                    if last_was_critical:
                        incoming_critical = True
                elif last_actor_is_self:
                    outgoing_damage += value
                    if last_was_critical:
                        outgoing_critical = True
                elif enemy_name and enemy_name in lowered:
                    outgoing_damage += value
                elif our_name and our_name in lowered:
                    incoming_damage += value
                continue

            if "critical hit" in lowered and last_actor:
                if last_actor_is_enemy:
                    incoming_critical = True
                elif last_actor_is_self:
                    outgoing_critical = True

        return {
            "incoming_damage": int(incoming_damage),
            "outgoing_damage": int(outgoing_damage),
            "incoming_critical": bool(incoming_critical),
            "outgoing_critical": bool(outgoing_critical),
        }

    def _learn_team_moves_preview(self, text: str) -> None:
        raw = str(text or "")
        if not _TEAM_MOVES_HEADER_PATTERN.search(raw):
            return

        current_mon = ""
        learned_count = 0
        for line in raw.splitlines():
            mon_match = _TEAM_MON_HEADER_PATTERN.search(line)
            if mon_match:
                current_mon = str(mon_match.group(1) or "").strip(" :*")
                self._known_moves_by_pokemon.setdefault(current_mon, set())
                continue

            move_match = _TEAM_MOVE_LINE_PATTERN.search(line)
            if not move_match or not current_mon:
                continue

            move_name = str(move_match.group(1) or "").strip(" :*")
            if not move_name:
                continue

            known = self._known_moves_by_pokemon.setdefault(current_mon, set())
            current_key = self._normalize_pokemon_name(current_mon)
            move_key = self._normalize_move_name(move_name)
            before = len(known)
            known.add(move_name)
            if len(known) > before:
                learned_count += 1

            type_match = re.search(r":([a-z]+)type:", line, flags=re.IGNORECASE)
            power_match = re.search(r"\|\s*Power\s+([^|]+)", line, flags=re.IGNORECASE)
            accuracy_match = re.search(r"\|\s*Accuracy\s+([^|\n]+)", line, flags=re.IGNORECASE)

            power_raw = str(power_match.group(1) if power_match else "").strip().lower()
            accuracy_raw = str(accuracy_match.group(1) if accuracy_match else "").strip().lower()
            power_val = int(power_raw) if power_raw.isdigit() else 0
            accuracy_val = int(accuracy_raw) if accuracy_raw.isdigit() else None

            per_pokemon = self._preview_move_meta_by_pokemon.setdefault(current_key, {})
            per_pokemon[move_key] = {
                "type": str(type_match.group(1) if type_match else "").strip().lower(),
                "power": power_val,
                "accuracy": accuracy_val,
            }

        if learned_count > 0:
            self._log_event(
                "team_moves_preview_learned",
                {
                    "pokemon_count": len(self._known_moves_by_pokemon),
                    "moves_added": learned_count,
                },
            )

    def _preferred_defensive_stat(self, enemy_id: int | None) -> str | None:
        enemy_key = self._enemy_battle_key(enemy_id)
        profile = self._enemy_offense_profile.get(enemy_key, {})
        physical = int(profile.get("physical", 0) or 0)
        special = int(profile.get("special", 0) or 0)
        if physical > special:
            return "def"
        if special > physical:
            return "spd"

        # Fallback removed from sync path; async threat assessor handles deeper prediction.
        return None

    def _choose_best_setup_button(self, setup_buttons, enemy_id: int | None):
        if not setup_buttons:
            return None
        preferred = self._preferred_defensive_stat(enemy_id)
        active = self._normalize_pokemon_name(self._active_pokemon)
        capped = self._capped_stats_by_pokemon.get(active, set())
        stages = self._ensure_stat_stage_row(active)
        used_setup = self._used_setup_moves_by_pokemon.get(active, set())

        best = None
        best_score = (-1.0, -99.0, -1.0)
        for button in setup_buttons:
            label = str(getattr(button, "label", "") or "")
            move = self._normalize_move_name(label)
            targets = _SETUP_MOVE_TO_STATS.get(move, set())
            uncapped_targets = [s for s in targets if s not in capped and int(stages.get(s, 0)) < 6]
            useful_targets = len(uncapped_targets)
            preferred_hit = 1 if (preferred and preferred in uncapped_targets) else 0
            # Favor the most under-boosted target to spread setup across all useful setup stats.
            min_stage = min([int(stages.get(s, 0)) for s in uncapped_targets], default=-6)
            unseen_bonus = 1.0 if move and move not in used_setup else 0.0
            score = (float(preferred_hit), float(unseen_bonus + useful_targets), float(-min_stage))
            if score > best_score:
                best_score = score
                best = button
        return best if best is not None else setup_buttons[0]

    def _setup_move_is_still_useful(self, label: str) -> bool:
        move = self._normalize_move_name(label)
        active = self._normalize_pokemon_name(self._active_pokemon)
        if not move or not active:
            return True

        targeted_stats = _SETUP_MOVE_TO_STATS.get(move, set())
        if not targeted_stats:
            return True

        stages = self._stat_stage_by_pokemon.get(active, {})
        if stages:
            # If any targeted stat is below +6, the setup is still useful.
            if any(int(stages.get(stat, 0)) < 6 for stat in targeted_stats):
                return True
            return False

        capped = self._capped_stats_by_pokemon.get(active, set())
        return not targeted_stats.issubset(capped)

    def _build_setup_progress(self, move_buttons, enemy_id: int | None, stages: dict[str, int]) -> dict[str, object]:
        setup_moves: dict[str, dict[str, object]] = {}
        total_remaining = 0
        plus_two_remaining = 0
        for button in move_buttons:
            label = str(getattr(button, "label", "") or "").strip()
            if not label or not self._is_setup_move(label) or not self._setup_move_is_still_useful(label):
                continue

            move_name = self._normalize_move_name(label)
            uses = self._get_move_uses(enemy_id, move_name)
            max_uses = int(_SETUP_MOVE_MAX_USES.get(move_name, 0) or 0)
            remaining_uses = max(0, max_uses - uses) if max_uses > 0 else 99
            if max_uses > 0 and remaining_uses <= 0:
                continue

            heur = _MOVE_HEURISTICS.get(move_name, {})
            boosts = heur.get("boosts", {}) if isinstance(heur.get("boosts", {}), dict) else {}
            plus_two_stats = [k for k, v in boosts.items() if int(v or 0) >= 2]

            effective_gain = 0
            for stat_key, delta in boosts.items():
                current = int(stages.get(str(stat_key), 0) or 0)
                if current >= 6:
                    continue
                gain = max(0, min(6, current + int(delta or 0)) - current)
                effective_gain += gain

            setup_moves[move_name] = {
                "uses": int(uses),
                "max_uses": int(max_uses),
                "remaining_uses": int(remaining_uses),
                "plus_two_stats": plus_two_stats,
                "plus_two_count": int(len(plus_two_stats)),
                "effective_gain": int(effective_gain),
            }

            if max_uses > 0:
                total_remaining += int(remaining_uses)
                if plus_two_stats:
                    plus_two_remaining += int(remaining_uses)

        return {
            "moves": setup_moves,
            "total_remaining": int(total_remaining),
            "plus_two_remaining": int(plus_two_remaining),
        }

    def _move_hits_enemy(self, move_label: str, enemy_id: int | None) -> bool:
        move = self._normalize_move_name(move_label)
        if not move:
            return True

        enemy_key = self._enemy_battle_key(enemy_id)
        blocked = self._immune_moves_by_enemy.get(enemy_key, set())
        if move in blocked:
            return False
        return True

    @staticmethod
    def _is_switch_prompt(text: str) -> bool:
        lowered = str(text or "").lower()
        return any(token in lowered for token in (
            "select a pokemon to send out",
            "select a pokemon switch button",
            "complete baton pass",
        ))

    @staticmethod
    def _is_switch_button(button) -> bool:
        cid = str(getattr(button, "custom_id", "") or "").strip().lower()
        return cid.startswith("sw")

    @staticmethod
    def _is_forfeit_button(button) -> bool:
        cid = str(getattr(button, "custom_id", "") or "").strip().lower()
        label = str(getattr(button, "label", "") or "").strip().lower()
        return cid == "ff" or "forfeit" in label

    @staticmethod
    def _move_score(label: str, hp_ratio: float) -> int:
        normalized = str(label or "").strip().lower()
        if not normalized:
            return -100
        if any(token in normalized for token in ("recover", "roost", "synthesis", "milk drink", "soft-boiled")):
            return 90 if hp_ratio <= 0.45 else 10
        if "memento" in normalized:
            return -50
        if any(token in normalized for token in ("calm mind", "iron defense", "defense curl", "focus energy", "harden", "protect", "substitute")):
            return 20
        return 70

    @staticmethod
    def _is_recovery_move(label: str) -> bool:
        normalized = str(label or "").strip().lower()
        return any(token in normalized for token in ("recover", "roost", "synthesis", "milk drink", "soft-boiled", "slack off", "moonlight"))

    @staticmethod
    def _is_setup_move(label: str) -> bool:
        normalized = str(label or "").strip().lower()
        return any(token in normalized for token in (
            "calm mind", "iron defense", "swords dance", "nasty plot", "dragon dance", "bulk up", "quiver dance",
            "agility", "harden", "focus energy", "defense curl", "charge beam", "curse", "shift gear", "geomancy",
        ))

    @staticmethod
    def _is_support_or_sacrifice_move(label: str) -> bool:
        normalized = str(label or "").strip().lower()
        return any(token in normalized for token in (
            "memento", "tailwind", "wish", "heal bell", "aromatherapy", "encore", "helping hand", "trick room",
            "light screen", "reflect", "safeguard", "leech seed", "toxic", "thunder wave", "will-o-wisp", "baton pass",
        ))

    @staticmethod
    def _is_baton_pass_move(label: str) -> bool:
        return "baton pass" in str(label or "").strip().lower()

    @staticmethod
    def _is_damaging_move(label: str) -> bool:
        normalized = str(label or "").strip().lower()
        if not normalized:
            return False
        if AutoFight._is_recovery_move(normalized) or AutoFight._is_setup_move(normalized) or AutoFight._is_support_or_sacrifice_move(normalized):
            return False
        return True

    def _classify_support_pokemon(self, pokemon_name: str) -> bool:
        moves = self._known_moves_by_pokemon.get(str(pokemon_name or ""), set())
        if not moves:
            return False
        support_count = sum(1 for m in moves if self._is_support_or_sacrifice_move(m))
        damage_count = sum(1 for m in moves if self._is_damaging_move(m))
        return support_count >= 2 and damage_count <= 1

    def _ensure_active_from_buttons(self, move_buttons) -> None:
        labels = {str(getattr(b, "label", "") or "").strip().lower() for b in move_buttons}
        labels.discard("")
        if not labels or len(labels) < 2:
            return

        current_name = str(self._active_pokemon or "").strip()
        current_known = {str(m).strip().lower() for m in self._known_moves_by_pokemon.get(current_name, set())}
        if current_name and labels.issubset(current_known):
            return

        matches: list[str] = []
        for pokemon, known_moves in self._known_moves_by_pokemon.items():
            known = {str(m).strip().lower() for m in known_moves}
            if labels and labels.issubset(known):
                matches.append(pokemon)
        if len(matches) == 1:
            chosen = matches[0]
            if current_name.lower() != chosen.lower():
                self._log_event(
                    "active_correction_from_buttons",
                    {"from": current_name, "to": chosen, "labels": sorted(labels)[:8]},
                )
            self._active_pokemon = chosen

    async def _choose_best_switch_target(self, switch_buttons, team_status, *, incoming_type: str = "") -> str:
        enemy_info = await self._cached_get_pokemon_brief(self._enemy_active_pokemon) if self._enemy_active_pokemon else None
        enemy_types = [str(t).lower() for t in ((enemy_info or {}).get("types", []) or [])]
        enemy_speed = int((((enemy_info or {}).get("stats", {}) or {}).get("speed", 0) or 0))

        best_name = ""
        best_score = -10**9
        scored_rows: list[dict[str, object]] = []
        for button in switch_buttons:
            name = str(getattr(button, "label", "") or "").strip()
            if not name:
                continue
            if self._active_pokemon and name.lower() == self._active_pokemon.lower():
                continue

            row = team_status.get(name.lower(), {})
            if bool(row.get("fainted", False)):
                continue

            target_info = await self._cached_get_pokemon_brief(name)
            target_types = [str(t).lower() for t in ((target_info or {}).get("types", []) or [])]
            target_stats = ((target_info or {}).get("stats", {}) or {})
            target_speed = int(target_stats.get("speed", 0) or 0)

            known = {str(m).strip().lower() for m in self._known_moves_by_pokemon.get(name, set())}
            damage = sum(1 for m in known if self._is_damaging_move(m))
            setup = sum(1 for m in known if self._is_setup_move(m))
            sustain = sum(1 for m in known if self._is_recovery_move(m))
            baton = sum(1 for m in known if self._is_baton_pass_move(m))
            hp_ratio = float(row.get("hp_ratio", 1.0) or 1.0)

            # Offense pressure: prefer candidates with strong type pressure into the current enemy.
            offense_multiplier = 1.0
            if enemy_types and target_types:
                offense_multiplier = max(self._type_multiplier(t, enemy_types) for t in target_types)

            # If we know specific damaging moves for this teammate, weight by the best move profile.
            damaging_known = [m for m in known if self._is_damaging_move(m)][:6]
            if enemy_types and damaging_known:
                move_briefs = await asyncio.gather(*(self._cached_get_move_brief(m) for m in damaging_known), return_exceptions=True)
                best_move_score = 0.0
                for info in move_briefs:
                    if isinstance(info, Exception) or not info:
                        continue
                    mtype = str(info.get("type", "") or "").strip().lower()
                    power = int(info.get("power", 0) or 0)
                    if not mtype or power <= 0:
                        continue
                    m_mult = self._type_multiplier(mtype, enemy_types)
                    stab = 1.2 if mtype in target_types else 1.0
                    power_factor = max(0.35, min(1.4, float(power) / 100.0))
                    best_move_score = max(best_move_score, m_mult * stab * power_factor)
                if best_move_score > 0:
                    offense_multiplier = max(offense_multiplier, best_move_score)

            # Defense profile: prefer resistances against enemy STAB or observed incoming type.
            incoming = str(incoming_type or "").strip().lower()
            incoming_multiplier = self._type_multiplier(incoming, target_types) if incoming and target_types else 1.0
            enemy_stab_multiplier = 1.0
            if enemy_types and target_types:
                enemy_stab_multiplier = max(self._type_multiplier(et, target_types) for et in enemy_types)
            defensive_load = max(incoming_multiplier, enemy_stab_multiplier)

            # Receiver preference: matchup quality first, then known role utility and survivability.
            score = 0.0
            score += (offense_multiplier - 1.0) * 95.0
            score += (1.0 - defensive_load) * 110.0
            score += hp_ratio * 40.0
            score += damage * 4.0
            score += setup * 2.0
            score += sustain * 1.0
            score -= baton * 2.0
            if enemy_speed > 0 and target_speed > enemy_speed:
                score += 12.0

            scored_rows.append(
                {
                    "name": name[:48],
                    "score": round(float(score), 3),
                    "hp_ratio": round(hp_ratio, 3),
                    "offense_multiplier": round(float(offense_multiplier), 3),
                    "defensive_load": round(float(defensive_load), 3),
                }
            )
            if score > best_score:
                best_score = score
                best_name = name

        if scored_rows:
            self._log_event(
                "switch_target_matchup_scoring",
                {
                    "enemy": self._enemy_active_pokemon,
                    "incoming_type": str(incoming_type or "")[:24],
                    "top": sorted(scored_rows, key=lambda row: float(row.get("score", 0.0)), reverse=True)[:4],
                    "chosen": best_name[:48],
                },
            )

        return best_name

    async def _choose_level_switch_target(self, switch_buttons, team_status, *, target_index: int = 2) -> str:
        candidates: list[str] = []
        for button in switch_buttons:
            name = str(getattr(button, "label", "") or "").strip()
            if not name:
                continue
            if self._active_pokemon and name.lower() == self._active_pokemon.lower():
                continue

            row = team_status.get(name.lower(), {})
            if bool(row.get("fainted", False)):
                continue

            candidates.append(name)

        if not candidates:
            return ""

        chosen_index = min(max(int(target_index), 0), len(candidates) - 1)
        return candidates[chosen_index]

    def _choose_level_target_label(self, switch_buttons, team_status) -> str:
        locked = str(self._level_locked_target or "").strip()
        if locked:
            locked_key = locked.lower()
            row = (team_status or {}).get(locked_key, {}) or {}
            locked_available = any(
                str(getattr(button, "label", "") or "").strip().lower() == locked_key
                for button in switch_buttons
            )
            locked_active = bool(self._active_pokemon and self._active_pokemon.strip().lower() == locked_key)
            if (locked_available or locked_active) and not bool(row.get("fainted", False)):
                return locked
            self._level_locked_target = ""

        for button in switch_buttons:
            custom_id = str(getattr(button, "custom_id", "") or "").strip().lower()
            if custom_id == "sw 3":
                label = str(getattr(button, "label", "") or "").strip()
                if label:
                    self._level_locked_target = label
                return label

        candidates = [str(getattr(button, "label", "") or "").strip() for button in switch_buttons if str(getattr(button, "label", "") or "").strip()]
        if not candidates:
            return ""
        chosen_index = min(2, len(candidates) - 1)
        chosen = candidates[chosen_index]
        self._level_locked_target = chosen
        return chosen

    async def _choose_level_phase_switch_target(self, switch_buttons, team_status, *, enemy_hp_ratio: float) -> tuple[str, str]:
        level_target = self._choose_level_target_label(switch_buttons, team_status)
        offense_target = await self._choose_best_switch_target(switch_buttons, team_status)
        level_target_key = level_target.strip().lower()
        level_target_available = bool(level_target_key) and any(
            str(getattr(button, "label", "") or "").strip().lower() == level_target_key
            for button in switch_buttons
        )
        level_target_active = bool(level_target_key) and bool(self._active_pokemon and self._active_pokemon.strip().lower() == level_target_key)
        if enemy_hp_ratio <= 0.42 and level_target and (level_target_available or level_target_active):
            return level_target, level_target
        if offense_target:
            return level_target, offense_target
        return level_target, level_target

    def _enemy_hp_ratio_from_team_status(self, team_status) -> float:
        enemy_key = self._normalize_pokemon_name(self._enemy_active_pokemon)
        if not enemy_key:
            return 1.0
        row = team_status.get(enemy_key, {}) or {}
        return float(row.get("hp_ratio", 1.0) or 1.0)

    async def _has_viable_offensive_teammate(self, switch_buttons, team_status) -> bool:
        for button in switch_buttons:
            name = str(getattr(button, "label", "") or "").strip()
            if not name:
                continue
            if self._active_pokemon and name.lower() == self._active_pokemon.lower():
                continue

            row = team_status.get(name.lower(), {})
            if bool(row.get("fainted", False)):
                continue
            hp_ratio = float(row.get("hp_ratio", 1.0) or 1.0)
            if hp_ratio <= 0.2:
                continue

            known = {str(m).strip().lower() for m in self._known_moves_by_pokemon.get(name, set())}
            if any(self._is_damaging_move(m) for m in known):
                return True

            # If move info is unknown, approximate offensive viability from base stats.
            # This avoids false negatives that suppress valid Baton Pass plays early in battle.
            info = await self._cached_get_pokemon_brief(name)
            if not info:
                return True
            stats = ((info or {}).get("stats", {}) or {}) if isinstance((info or {}).get("stats", {}), dict) else {}
            atk = int(stats.get("attack", 0) or 0)
            spa = int(stats.get("special-attack", 0) or 0)
            if max(atk, spa) >= 95:
                return True
        return False

    async def _pick_button(self, message: Message, combined_text: str, enemy_id: int | None, moves_taken: int | None):
        buttons = self._enabled_buttons(message)
        if not buttons:
            return None, -1, "none"

        team_status = self._extract_team_status(combined_text)
        active_name = self._extract_active_pokemon(combined_text)
        if active_name:
            self._active_pokemon = active_name

        switch_buttons = [b for b in buttons if self._is_switch_button(b)]
        move_buttons = [b for b in buttons if not self._is_switch_button(b)]
        self._ensure_active_from_buttons(move_buttons)

        self_species = set(team_status.keys())
        combat_active, combat_enemy = self._extract_combat_actor_candidates(combined_text, self_species)
        if not self._active_pokemon and combat_active:
            self._active_pokemon = combat_active
        if not self._enemy_active_pokemon and combat_enemy:
            self._enemy_active_pokemon = combat_enemy
            asyncio.create_task(self._seed_enemy_knowledge_from_species(enemy_id, combat_enemy, source="button_parse"))

        # Fallback enemy inference from visible HP lines when parser misses at battle start.
        if not self._enemy_active_pokemon and team_status:
            own_species = {
                self._normalize_pokemon_name(self._active_pokemon),
                *{
                    self._normalize_pokemon_name(str(getattr(b, "label", "") or ""))
                    for b in switch_buttons
                },
                *{self._normalize_pokemon_name(n) for n in self._known_moves_by_pokemon.keys()},
            }
            own_species.discard("")
            for species_name, row in team_status.items():
                if species_name in own_species:
                    continue
                if bool((row or {}).get("fainted", False)):
                    continue
                self._enemy_active_pokemon = str(species_name)
                asyncio.create_task(self._seed_enemy_knowledge_from_species(enemy_id, species_name, source="team_status_fallback"))
                break

        switch_prompt = self._is_switch_prompt(combined_text)
        if switch_prompt and switch_buttons:
            preferred = ""
            level_target_snapshot: dict[str, object] | None = None
            if self._battle_strategy_mode == "ev":
                preferred = self._planned_switch_target or await self._choose_best_switch_target(
                    switch_buttons,
                    team_status,
                )
            elif self._battle_strategy_mode == "level":
                enemy_hp_ratio = self._enemy_hp_ratio_from_team_status(team_status)
                level_target, preferred = await self._choose_level_phase_switch_target(
                    switch_buttons,
                    team_status,
                    enemy_hp_ratio=enemy_hp_ratio,
                )
                switch_candidates = []
                for idx, button in enumerate(switch_buttons):
                    label = str(getattr(button, "label", "") or "").strip()
                    if not label:
                        continue
                    row = team_status.get(label.lower(), {}) or {}
                    switch_candidates.append(
                        {
                            "slot_index": idx,
                            "label": label[:80],
                            "fainted": bool(row.get("fainted", False)),
                            "hp_ratio": round(float(row.get("hp_ratio", 1.0) or 1.0), 4),
                        }
                    )
                chosen_slot_index = next((item["slot_index"] for item in switch_candidates if str(item["label"]).lower() == preferred.lower()), None)
                level_target_snapshot = {
                    "level_target": level_target[:80],
                    "phase_target": preferred[:80],
                    "target_slot_index": chosen_slot_index,
                    "switch_candidates": switch_candidates,
                }
                self._log_event("level_switch_target", level_target_snapshot)
            else:
                preferred = self._planned_switch_target or await self._choose_best_switch_target(switch_buttons, team_status)

            chosen_button = None
            if preferred:
                for idx, b in enumerate(switch_buttons):
                    if str(getattr(b, "label", "") or "").strip().lower() == preferred.strip().lower():
                        chosen_button = (b, idx)
                        break
            if not chosen_button:
                for idx, b in enumerate(switch_buttons):
                    label = str(getattr(b, "label", "") or "").strip()
                    if not label:
                        continue
                    if self._active_pokemon and label.lower() == self._active_pokemon.lower():
                        continue
                    chosen_button = (b, idx)
                    break
            if not chosen_button:
                chosen_button = (switch_buttons[0], 0)
            b, _local_idx = chosen_button
            real_idx = next((i for i, btn in enumerate(buttons) if btn is b), 0)
            self._log_event(
                "score_trace",
                {
                    "enemy": self._enemy_active_pokemon,
                    "active": self._active_pokemon,
                    "top": [{"kind": "switch", "label": str(getattr(b, "label", "") or "")[:48], "score": 999.0}],
                },
            )
            return b, real_idx, "switch"

        if self._active_pokemon:
            known = self._known_moves_by_pokemon.setdefault(self._active_pokemon, set())
            discovered = []
            for b in move_buttons:
                label = str(getattr(b, "label", "") or "").strip()
                if label and label not in known:
                    known.add(label)
                    discovered.append(label)
            if discovered:
                self._log_event("moves_discovered", {"pokemon": self._active_pokemon, "moves": discovered[:8]})

        if enemy_id is not None and enemy_id != self._battle_state.get("enemy_id", -1):
            self._battle_state = {
                "enemy_id": enemy_id,
                "moves_taken": -1,
                "last_index": -1,
                "recent_incoming_damage": 0.0,
                "recent_outgoing_damage": 0.0,
                "recent_incoming_critical": False,
                "recent_outgoing_critical": False,
            }
            self._enemy_offense_profile.clear()
            self._immune_moves_by_enemy.clear()
            self._enemy_seen_moves_by_battle.clear()

        hp_ratio = 1.0
        if self._active_pokemon:
            hp_ratio = float((team_status.get(self._active_pokemon.lower(), {}) or {}).get("hp_ratio", 1.0))
        enemy_hp_ratio = self._enemy_hp_ratio_from_team_status(team_status)

        damage_signals = self._extract_recent_damage_signals(combined_text)
        incoming_damage = float(damage_signals.get("incoming_damage", 0) or 0)
        outgoing_damage = float(damage_signals.get("outgoing_damage", 0) or 0)
        self._battle_state["recent_incoming_damage"] = incoming_damage
        self._battle_state["recent_outgoing_damage"] = outgoing_damage
        self._battle_state["recent_incoming_critical"] = bool(damage_signals.get("incoming_critical", False))
        self._battle_state["recent_outgoing_critical"] = bool(damage_signals.get("outgoing_critical", False))

        try:
            threat = await asyncio.wait_for(
                self._calculate_threat_state(self._enemy_active_pokemon, self._active_pokemon, hp_ratio),
                timeout=4.0,
            )
        except Exception as exc:
            self._log_event(
                "threat_calc_fallback",
                {
                    "enemy": self._enemy_active_pokemon,
                    "active": self._active_pokemon,
                    "error": str(exc)[:180],
                },
            )
            threat = {
                "speed_advantage": "TIE",
                "enemy_faster": False,
                "max_threat_score": 0.0,
                "highest_threat_type": "",
                "is_lethal": False,
                "enemy_types": [],
                "bot_types": [],
                "enemy_stats": {},
                "bot_stats": {},
            }
        stages = self._ensure_stat_stage_row(self._active_pokemon)
        stage_budget = sum(max(0, int(v)) for v in stages.values())
        level_target = ""
        level_phase_target = ""
        if self._battle_strategy_mode == "level":
            level_target = self._choose_level_target_label(switch_buttons, team_status)
            level_target, level_phase_target = await self._choose_level_phase_switch_target(
                switch_buttons,
                team_status,
                enemy_hp_ratio=enemy_hp_ratio,
            )
        baton_target = level_phase_target or self._planned_switch_target or await self._choose_best_switch_target(
            switch_buttons,
            team_status,
            incoming_type=str((threat.get("highest_threat_type", "") or "")),
        )
        setup_buttons = [
            b for b in move_buttons
            if self._is_setup_move(str(getattr(b, "label", "") or ""))
            and self._setup_move_is_still_useful(str(getattr(b, "label", "") or ""))
        ]
        is_support_pokemon = self._classify_support_pokemon(self._active_pokemon)
        allow_setup_first = bool(setup_buttons) and (not is_support_pokemon) and hp_ratio >= 0.55
        has_viable_offensive_teammate = await self._has_viable_offensive_teammate(switch_buttons, team_status)
        force_offense_last_resort = bool(is_support_pokemon and not has_viable_offensive_teammate)
        setup_move_turns = sum(
            self._get_move_uses(enemy_id, str(getattr(b, "label", "") or ""))
            for b in move_buttons
            if self._is_setup_move(str(getattr(b, "label", "") or ""))
        )
        # Baton/setup control should use actual setup turns, not unique setup move kinds.
        setup_moves_used = int(setup_move_turns)
        setup_progress = self._build_setup_progress(move_buttons, enemy_id, stages)
        baton_ready = any(self._is_baton_pass_move(str(getattr(b, "label", "") or "")) for b in move_buttons)
        damaging_move_buttons = [
            b for b in move_buttons
            if self._is_damaging_move(str(getattr(b, "label", "") or "")) and not self._is_forfeit_button(b)
        ]
        no_damaging_moves_available = len(damaging_move_buttons) == 0

        state = {
            "enemy_id": enemy_id,
            "moves_taken": moves_taken,
            "bot_active_name": self._active_pokemon,
            "bot_hp_ratio": hp_ratio,
            "enemy_hp_ratio": enemy_hp_ratio,
            "strategy_mode": self._battle_strategy_mode,
            "team_status": team_status,
            "strategy_mode": self._battle_strategy_mode,
            "stages": stages,
            "stage_budget": stage_budget,
            "level_target": level_target,
            "level_phase_target": level_phase_target,
            "baton_target": baton_target,
            "allow_setup_first": allow_setup_first,
            "has_viable_offensive_teammate": has_viable_offensive_teammate,
            "force_offense_last_resort": force_offense_last_resort,
            "setup_moves_used": setup_moves_used,
            "setup_move_turns": setup_move_turns,
            "setup_progress": setup_progress,
            "baton_ready": baton_ready,
            "no_damaging_moves_available": no_damaging_moves_available,
            "switch_prompt": self._is_switch_prompt(combined_text),
            "recent_incoming_damage": float(self._battle_state.get("recent_incoming_damage", 0.0) or 0.0),
            "recent_outgoing_damage": float(self._battle_state.get("recent_outgoing_damage", 0.0) or 0.0),
            "recent_incoming_critical": bool(self._battle_state.get("recent_incoming_critical", False)),
            "recent_outgoing_critical": bool(self._battle_state.get("recent_outgoing_critical", False)),
            "threat": threat,
        }

        scored: list[tuple[float, int, object]] = []
        timeout_per_move = 1.25
        scoring_deadline = time.monotonic() + 3.2
        for idx, button in enumerate(buttons):
            if time.monotonic() >= scoring_deadline:
                self._log_event("score_budget_exceeded", {"evaluated": len(scored), "total": len(buttons)})
                break
            if switch_prompt and not self._is_switch_button(button):
                continue
            try:
                # Add timeout protection to prevent infinite scoring loops
                score = await asyncio.wait_for(self._score_action(button, state), timeout=timeout_per_move)
                scored.append((float(score), idx, button))
            except asyncio.TimeoutError:
                # If scoring takes too long, use a penalty score
                label = str(getattr(button, "label", "") or "")
                self._log_event("score_timeout", {"button": label[:80], "index": idx})
                scored.append((-999.0, idx, button))
            except Exception as e:
                # Catch any scoring errors
                label = str(getattr(button, "label", "") or "")
                self._log_event("score_error", {"button": label[:80], "index": idx, "error": str(e)[:100]})
                scored.append((-999.0, idx, button))

        if not scored:
            # If no buttons passed scoring filter, use safer fallback heuristic
            # Try to select the best available button that matches expected type
            switch_prompt = state.get("switch_prompt", False)
            fallback_button = None
            fallback_idx = -1
            
            # First, try to find a button of the expected type that wasn't filtered
            for idx, button in enumerate(buttons):
                # For switch prompts, find a switch button; for move prompts, find a move button
                button_is_switch = self._is_switch_button(button)
                if switch_prompt and button_is_switch:
                    fallback_button = button
                    fallback_idx = idx
                    break
                elif not switch_prompt and not button_is_switch:
                    fallback_button = button
                    fallback_idx = idx
                    break
            
            # If no matching type found, just skip this prompt entirely
            if fallback_button is None:
                self._log_event(
                    "score_fallback_no_valid_button",
                    {"reason": "no buttons matched expected type", "switch_prompt": switch_prompt, "total_buttons": len(buttons)},
                )
                return None, -1, "none"
            
            kind = "switch" if self._is_switch_button(fallback_button) else "move"
            self._log_event(
                "score_fallback_type_match",
                {"kind": kind, "label": str(getattr(fallback_button, "label", "") or "")[:48], "switch_prompt": switch_prompt},
            )
            return fallback_button, fallback_idx, kind

        scored.sort(key=lambda item: item[0], reverse=True)
        self._log_event(
            "score_trace",
            {
                "enemy": self._enemy_active_pokemon,
                "active": self._active_pokemon,
                "buttons_total": len(buttons),
                "strategy_mode": self._battle_strategy_mode,
                "strategy_targets": {
                    "level_target": level_target,
                    "level_phase_target": level_phase_target,
                    "baton_target": baton_target,
                },
                "ev_context": {
                    "hp_ratio": round(float(state.get("bot_hp_ratio", 1.0) or 1.0), 4),
                    "enemy_hp_ratio": round(float(state.get("enemy_hp_ratio", 1.0) or 1.0), 4),
                    "recent_incoming_damage": round(float(state.get("recent_incoming_damage", 0.0) or 0.0), 2),
                    "recent_outgoing_damage": round(float(state.get("recent_outgoing_damage", 0.0) or 0.0), 2),
                    "recent_incoming_critical": bool(state.get("recent_incoming_critical", False)),
                    "stage_budget": int(state.get("stage_budget", 0) or 0),
                    "setup_remaining": int(((state.get("setup_progress", {}) or {}).get("total_remaining", 0) or 0)),
                    "setup_plus_two_remaining": int(((state.get("setup_progress", {}) or {}).get("plus_two_remaining", 0) or 0)),
                    "moves_taken": int(state.get("moves_taken", -1) or -1),
                },
                "top": [
                    {
                        "kind": "switch" if self._is_switch_button(b) else "move",
                        "label": str(getattr(b, "label", "") or "")[:48],
                        "score": round(float(s), 2),
                    }
                    for s, _, b in scored[:7]
                ],
            },
        )
        best_score, best_index, best_button = scored[0]

        if self._is_baton_pass_move(str(getattr(best_button, "label", "") or "")) and baton_target:
            self._planned_switch_target = baton_target
            self._pending_baton_stages = dict(stages)
            self._log_event(
                "strategy_baton_pass",
                {
                    "from": self._active_pokemon,
                    "mode": self._battle_strategy_mode,
                    "to": baton_target,
                    "level_target": level_target,
                    "level_phase_target": level_phase_target,
                    "stage_budget": stage_budget,
                    "score": round(best_score, 2),
                },
            )

        self._battle_state["enemy_id"] = int(enemy_id if enemy_id is not None else self._battle_state.get("enemy_id", -1))
        self._battle_state["moves_taken"] = int(moves_taken if moves_taken is not None else self._battle_state.get("moves_taken", -1))
        self._battle_state["last_index"] = int(best_index)
        kind = "switch" if self._is_switch_button(best_button) else "move"
        return best_button, best_index, kind

    @staticmethod
    def _looks_like_battle_prompt(text: str) -> bool:
        lowered = str(text or "").lower()
        return any(token in lowered for token in (
            "battle", "fight", "trainer", "npc", "attack", "move",
            "select a pokemon switch button", "complete baton pass", "enemy id:",
        ))

    async def _handle_message(self, message: Message, source: str) -> None:
        author_id = int(getattr(getattr(message, "author", None), "id", 0) or 0)
        bot_user_id = int(getattr(getattr(self.bot, "user", None), "id", 0) or 0)
        content = str(message.content or "")

        # Toggle commands are accepted only from this self account in the configured channel.
        if author_id == bot_user_id:
            run_cmd = self._parse_run_command(content)
            once_mode = self._parse_once_command(content)
            indefinite_mode = self._parse_indefinite_command(content)
            if self._is_on_command(content):
                self._log_event("toggle_on", {"raw": content[:120]})
                self.bot.autofight_active = True
                self.bot.autofight_status = "Active"
                self.bot.autofight_guard_status = ""
                self._pause_other_automation()
                self._reset_battle_knowledge()
                self._last_action_signature = ""
                self._last_clicked_by_message.clear()
                self._cancel_next_battle_task()
                self._cancel_dispatch_watchdog()
                self._run_target_battles = 0
                self._run_completed_battles = 0
                self._run_indefinite = False
                self._run_paused_state = None
                self._humanizer_next_break_after = 0
                self._humanizer_breaks_taken = 0
                self._counted_battle_end_message_ids.clear()
                self._announced_battle_prompt_message_ids.clear()
                self._battle_mode_args = ""
                self._battle_strategy_mode = "standard"
                self._run_no_response_retries = 0
                self._run_dispatch_error_retries = 0
                await self.bot.log()
                dispatched = await self._dispatch_initial_fight(message.channel, self._battle_mode_args)
                if dispatched:
                    await message.channel.send("AutoFight: ON (probe started).")
                else:
                    await message.channel.send("AutoFight: ON, but no fight command was detected.")
                return

            if run_cmd is not None:
                count, mode = run_cmd
                if count <= 0:
                    await message.channel.send("AutoFight: run count must be at least 1. Example: ;autofight run 5 npc 1 EV")
                    return

                battle_mode, strategy_mode = self._split_strategy_mode(mode)

                self._log_event("toggle_on_run", {"count": count, "mode": battle_mode[:120], "strategy": strategy_mode})
                self.bot.autofight_active = True
                self.bot.autofight_status = "Active"
                self.bot.autofight_guard_status = ""
                self._pause_other_automation()
                self._reset_battle_knowledge()
                self._last_action_signature = ""
                self._last_clicked_by_message.clear()
                self._cancel_next_battle_task()
                self._cancel_dispatch_watchdog()
                self._run_target_battles = int(count)
                self._run_completed_battles = 0
                self._run_indefinite = False
                self._run_paused_state = None
                self._arm_next_human_break()
                self._counted_battle_end_message_ids.clear()
                self._announced_battle_prompt_message_ids.clear()
                self._battle_mode_args = str(battle_mode or "user random").strip()
                self._battle_strategy_mode = strategy_mode if strategy_mode in _AUTOFIGHT_STRATEGY_MODES else "standard"
                self._run_no_response_retries = 0
                self._run_dispatch_error_retries = 0
                await self.bot.log()
                dispatched = await self._dispatch_initial_fight(message.channel, self._battle_mode_args)
                if dispatched:
                    mode_label = self._battle_strategy_mode.upper() if self._battle_strategy_mode != "standard" else "STANDARD"
                    await message.channel.send(
                        f"AutoFight: RUN mode ON ({self._run_target_battles} battles, {mode_label}). Cooldown-aware restart (60s) enabled."
                    )
                else:
                    await message.channel.send("AutoFight: RUN mode ON, but initial battle dispatch failed.")
                return

            if once_mode is not None:
                battle_mode, strategy_mode = self._split_strategy_mode(once_mode)
                self._log_event("toggle_on_once", {"mode": battle_mode[:120], "strategy": strategy_mode})
                self.bot.autofight_active = True
                self.bot.autofight_status = "Active"
                self.bot.autofight_guard_status = ""
                self._pause_other_automation()
                self._reset_battle_knowledge()
                self._last_action_signature = ""
                self._last_clicked_by_message.clear()
                self._cancel_next_battle_task()
                self._cancel_dispatch_watchdog()
                self._run_target_battles = 1
                self._run_completed_battles = 0
                self._run_indefinite = False
                self._run_paused_state = None
                self._arm_next_human_break()
                self._counted_battle_end_message_ids.clear()
                self._announced_battle_prompt_message_ids.clear()
                self._battle_mode_args = str(battle_mode or "user random").strip()
                self._battle_strategy_mode = strategy_mode if strategy_mode in _AUTOFIGHT_STRATEGY_MODES else "standard"
                self._run_no_response_retries = 0
                self._run_dispatch_error_retries = 0
                await self.bot.log()
                dispatched = await self._dispatch_initial_fight(message.channel, self._battle_mode_args)
                if dispatched:
                    mode_label = self._battle_strategy_mode.upper() if self._battle_strategy_mode != "standard" else "STANDARD"
                    await message.channel.send(f"AutoFight: ON for 1 battle ({mode_label}).")
                else:
                    await message.channel.send("AutoFight: ON for 1 battle, but initial battle dispatch failed.")
                return

            if indefinite_mode is not None:
                battle_mode, strategy_mode = self._split_strategy_mode(indefinite_mode)
                self._log_event("toggle_on_indefinite", {"mode": battle_mode[:120], "strategy": strategy_mode})
                self.bot.autofight_active = True
                self.bot.autofight_status = "Active"
                self.bot.autofight_guard_status = ""
                self._pause_other_automation()
                self._reset_battle_knowledge()
                self._last_action_signature = ""
                self._last_clicked_by_message.clear()
                self._cancel_next_battle_task()
                self._cancel_dispatch_watchdog()
                self._run_target_battles = -1
                self._run_completed_battles = 0
                self._run_indefinite = True
                self._run_paused_state = None
                self._arm_next_human_break()
                self._counted_battle_end_message_ids.clear()
                self._announced_battle_prompt_message_ids.clear()
                self._battle_mode_args = str(battle_mode or "user random").strip()
                self._battle_strategy_mode = strategy_mode if strategy_mode in _AUTOFIGHT_STRATEGY_MODES else "standard"
                self._run_no_response_retries = 0
                self._run_dispatch_error_retries = 0
                await self.bot.log()
                dispatched = await self._dispatch_initial_fight(message.channel, self._battle_mode_args)
                if dispatched:
                    mode_label = self._battle_strategy_mode.upper() if self._battle_strategy_mode != "standard" else "STANDARD"
                    await message.channel.send(f"AutoFight: INDEFINITE RUN ({mode_label}). Runs until paused.")
                else:
                    await message.channel.send("AutoFight: INDEFINITE RUN, but initial battle dispatch failed.")
                return

            if self._is_stop_command(content):
                self._log_event("toggle_stop", {"raw": content[:120]})
                self.bot.autofight_active = False
                self.bot.autofight_status = "Paused"
                self.bot.autofight_guard_status = ""
                self._reset_battle_knowledge()
                self._last_action_signature = ""
                self._last_clicked_by_message.clear()
                self._cancel_next_battle_task()
                self._cancel_dispatch_watchdog()
                self._run_target_battles = 0
                self._run_completed_battles = 0
                self._run_indefinite = False
                self._run_paused_state = None
                self._humanizer_next_break_after = 0
                self._humanizer_breaks_taken = 0
                self._counted_battle_end_message_ids.clear()
                self._announced_battle_prompt_message_ids.clear()
                self._battle_mode_args = ""
                self._battle_strategy_mode = "standard"
                self._run_no_response_retries = 0
                self._run_dispatch_error_retries = 0
                await self._restore_other_automation()
                await self.bot.log()
                await message.channel.send("AutoFight: STOPPED.")
                return

            if self._is_off_command(content):
                self._log_event("toggle_off", {"raw": content[:120]})
                self.bot.autofight_active = False
                self.bot.autofight_status = "Paused"
                self.bot.autofight_guard_status = ""
                self._reset_battle_knowledge()
                self._last_action_signature = ""
                self._last_clicked_by_message.clear()
                self._cancel_next_battle_task()
                self._cancel_dispatch_watchdog()
                self._run_target_battles = 0
                self._run_completed_battles = 0
                self._run_indefinite = False
                self._run_paused_state = None
                self._humanizer_next_break_after = 0
                self._humanizer_breaks_taken = 0
                self._counted_battle_end_message_ids.clear()
                self._announced_battle_prompt_message_ids.clear()
                self._battle_mode_args = ""
                self._battle_strategy_mode = "standard"
                self._run_no_response_retries = 0
                self._run_dispatch_error_retries = 0
                await self._restore_other_automation()
                await self.bot.log()
                await message.channel.send("AutoFight: OFF.")
                return

            if self._is_status_command(content):
                self._log_event("toggle_status", {"raw": content[:120]})
                status = str(self.bot.autofight_status or "Idle")
                completed = self._run_completed_battles
                target = self._run_target_battles
                mode = str(self._battle_strategy_mode or "standard").upper()
                
                if status.startswith("Paused") and self._run_paused_state:
                    status_msg = f"AutoFight: ⏸ PAUSED | {completed} battles completed | {mode}"
                elif status.startswith("Paused"):
                    status_msg = f"AutoFight: ⏸ PAUSED | {mode}"
                elif status == "Active" and self._run_indefinite:
                    status_msg = f"AutoFight: ∞ INDEFINITE | {completed} completed | {mode}"
                elif status == "Active" and target > 0:
                    status_msg = f"AutoFight: ▶ ACTIVE | {completed}/{target} battles | {mode}"
                elif status == "Active" and target <= 0:
                    status_msg = f"AutoFight: ▶ ACTIVE (probe mode) | {mode}"
                else:
                    status_msg = f"AutoFight: ⏹ OFF"
                guard_status = str(getattr(self.bot, "autofight_guard_status", "") or "")
                if guard_status:
                    status_msg += f" | Guard: {guard_status}"
                await message.channel.send(status_msg)
                return

            if self._is_pause_command(content):
                self._log_event("toggle_pause", {"raw": content[:120]})
                if not bool(getattr(self.bot, "autofight_active", False)):
                    await message.channel.send("AutoFight: Not currently running. Use `;af run 5` to start.")
                    return
                if self._run_paused_state is not None:
                    await message.channel.send("AutoFight: Already paused.")
                    return
                
                # Save current run state for resume
                self._run_paused_state = {
                    "target_battles": self._run_target_battles,
                    "completed_battles": self._run_completed_battles,
                    "is_indefinite": self._run_indefinite,
                    "battle_mode_args": self._battle_mode_args,
                    "strategy_mode": self._battle_strategy_mode,
                    "humanizer_next_break_after": self._humanizer_next_break_after,
                    "humanizer_breaks_taken": self._humanizer_breaks_taken,
                }
                
                self.bot.autofight_active = False
                self.bot.autofight_status = "Paused"
                self.bot.autofight_guard_status = ""
                self._cancel_next_battle_task()
                self._cancel_dispatch_watchdog()
                self._log_event("autofight_paused", {
                    "completed": self._run_completed_battles,
                    "target": self._run_target_battles,
                    "indefinite": self._run_indefinite,
                })
                await self.bot.log()
                
                if self._run_indefinite:
                    await message.channel.send(f"AutoFight: ⏸ PAUSED (∞ mode). Completed {self._run_completed_battles} battles. Use `;af resume` to continue.")
                elif self._run_target_battles > 0:
                    remaining = max(0, self._run_target_battles - self._run_completed_battles)
                    await message.channel.send(f"AutoFight: ⏸ PAUSED | {remaining} battles remaining. Use `;af resume` to continue.")
                else:
                    await message.channel.send("AutoFight: ⏸ PAUSED. Use `;af resume` to continue.")
                return

            if self._is_resume_command(content):
                self._log_event("toggle_resume", {"raw": content[:120]})
                if self._run_paused_state is None:
                    await message.channel.send("AutoFight: No paused run to resume. Use `;af run 5` to start new.")
                    return
                
                # Restore run state
                paused_state = self._run_paused_state
                self._run_target_battles = int(paused_state.get("target_battles", 0) or 0)
                self._run_completed_battles = int(paused_state.get("completed_battles", 0) or 0)
                self._run_indefinite = bool(paused_state.get("is_indefinite", False))
                self._battle_mode_args = str(paused_state.get("battle_mode_args", "") or "")
                self._battle_strategy_mode = str(paused_state.get("strategy_mode", "standard") or "standard")
                self._humanizer_next_break_after = int(paused_state.get("humanizer_next_break_after", 0) or 0)
                self._humanizer_breaks_taken = int(paused_state.get("humanizer_breaks_taken", 0) or 0)
                self._run_paused_state = None

                if self._eligible_for_human_break() and self._humanizer_next_break_after <= 0:
                    self._arm_next_human_break()
                
                self.bot.autofight_active = True
                self.bot.autofight_status = "Active"
                self._reset_battle_knowledge()
                self._last_action_signature = ""
                self._last_clicked_by_message.clear()
                self._run_no_response_retries = 0
                self._run_dispatch_error_retries = 0
                self._log_event("autofight_resumed", {
                    "completed": self._run_completed_battles,
                    "target": self._run_target_battles,
                    "indefinite": self._run_indefinite,
                })
                await self.bot.log()
                
                dispatched = await self._dispatch_initial_fight(message.channel, self._battle_mode_args)
                if dispatched:
                    if self._run_indefinite:
                        await message.channel.send(f"AutoFight: ▶ RESUMED (∞ mode) | {self._run_completed_battles} completed so far.")
                    else:
                        remaining = max(0, self._run_target_battles - self._run_completed_battles)
                        await message.channel.send(f"AutoFight: ▶ RESUMED | {remaining} battles remaining.")
                else:
                    await message.channel.send("AutoFight: RESUMED, but battle dispatch failed.")
                return

        if not bool(getattr(self.bot, "autofight_active", False)):
            return

        if author_id != POKEMEOW_APP_ID:
            return

        captcha_cog = self.bot.get_cog("Captcha")
        if captcha_cog is not None and captcha_cog.is_captcha_message(message):
            self._log_event("battle_captcha_detected", {"source": source, "message_id": int(getattr(message, "id", 0) or 0)})
            try:
                await captcha_cog.activate_captcha_mode(message)
                await captcha_cog._attempt_auto_solver(message, source=f"autofight_{source}")
                await self.bot.log()
            except Exception as exc:
                self._log_event("battle_captcha_handler_error", {"source": source, "error": str(exc)[:180]})
            return

        if bool(getattr(self.bot, "autofight_captcha_active", False)) or bool(getattr(self.bot, "captcha_active", False)):
            self._log_event("skip_captcha_active", {})
            return

        self._last_battle_activity_at = time.monotonic()
        self._run_no_response_retries = 0

        combined_text = self._combine_message_text(message)
        message_id = int(getattr(message, "id", 0) or 0)
        looks_like_battle = self._looks_like_battle_prompt(combined_text)
        if looks_like_battle and message_id and message_id < int(self._latest_battle_message_id or 0):
            self._log_event(
                "skip_stale_battle_message",
                {"source": source, "message_id": message_id, "latest_message_id": int(self._latest_battle_message_id or 0)},
            )
            return
        if looks_like_battle and message_id > int(self._latest_battle_message_id or 0):
            self._latest_battle_message_id = message_id

        self._learn_team_moves_preview(combined_text)
        lowered_text = combined_text.lower()

        enemy_id, moves_taken = self._extract_battle_progress(combined_text)
        switch_prompt = self._is_switch_prompt(combined_text)
        has_enabled_buttons = bool(self._enabled_buttons(message))
        self._sync_cloudflare_guard_status()

        cloudflare_guard_seconds = self._cloudflare_guard_remaining()
        if has_enabled_buttons and cloudflare_guard_seconds > 0:
            self._log_event(
                "skip_cloudflare_safeguard_action",
                {
                    "source": source,
                    "message_id": message_id,
                    "wait_seconds": round(cloudflare_guard_seconds, 2),
                    "status": str(getattr(self.bot, "autofight_status", "") or ""),
                    "guard_status": str(getattr(self.bot, "autofight_guard_status", "") or ""),
                },
            )
            return

        # Suppress duplicate processing of the exact same action state (message/edit pair).
        if has_enabled_buttons and enemy_id is not None and moves_taken is not None:
            state_key = f"{message_id}|{enemy_id}|{moves_taken}"
            now = time.monotonic()
            if state_key == self._last_action_state_key and (now - float(self._last_action_state_at or 0.0)) < 1.2:
                self._log_event(
                    "skip_duplicate_action_state",
                    {
                        "source": source,
                        "message_id": message_id,
                        "enemy_id": enemy_id,
                        "moves_taken": moves_taken,
                    },
                )
                return
            self._last_action_state_key = state_key
            self._last_action_state_at = now

        cloudflare_backoff_seconds = self._cloudflare_backoff_remaining()
        if has_enabled_buttons and cloudflare_backoff_seconds >= 8.0:
            self._log_event(
                "skip_cloudflare_backoff_action",
                {
                    "source": source,
                    "message_id": message_id,
                    "wait_seconds": round(cloudflare_backoff_seconds, 2),
                },
            )
            return

        active_before = self._active_pokemon
        enemy_before = self._enemy_active_pokemon
        active_name = ""
        enemy_name = ""
        if looks_like_battle:
            # Parse active/enemy from any battle-looking message, even when not actionable,
            # so opening embeds establish state before move-click messages arrive.
            active_name = self._extract_active_pokemon(combined_text)
            if active_name:
                self._active_pokemon = active_name
                asyncio.create_task(self._maybe_profile_pokemon(active_name, role="self"))
            enemy_name = self._extract_enemy_active_pokemon(combined_text)
            if enemy_name:
                self._enemy_active_pokemon = enemy_name
                asyncio.create_task(self._maybe_profile_pokemon(enemy_name, role="enemy"))
                asyncio.create_task(self._seed_enemy_knowledge_from_species(enemy_id, enemy_name, source="battle_parse"))
            self._log_parser_snapshot(
                message=message,
                source=source,
                combined_text=combined_text,
                looks_like_battle=looks_like_battle,
                enemy_id=enemy_id,
                moves_taken=moves_taken,
                switch_prompt=switch_prompt,
                has_enabled_buttons=has_enabled_buttons,
                active_candidate=active_name,
                enemy_candidate=enemy_name,
                active_before=active_before,
                enemy_before=enemy_before,
            )

        if looks_like_battle and has_enabled_buttons and message_id > 0 and message_id not in self._announced_battle_prompt_message_ids:
            self._announced_battle_prompt_message_ids.add(message_id)
            status_bits = ["▶ Battle active"]
            if self._run_indefinite:
                status_bits.append(f"∞ {self._run_completed_battles + 1}")
            elif self._run_target_battles > 0:
                status_bits.append(f"{self._run_completed_battles + 1}/{self._run_target_battles}")
            if self._battle_strategy_mode != "standard":
                status_bits.append(self._battle_strategy_mode.upper())
            if self._active_pokemon and self._enemy_active_pokemon:
                status_bits.append(f"{self._active_pokemon} vs {self._enemy_active_pokemon}")
            elif self._active_pokemon:
                status_bits.append(f"{self._active_pokemon} active")
            elif self._enemy_active_pokemon:
                status_bits.append(f"enemy {self._enemy_active_pokemon}")
            try:
                await message.channel.send(" | ".join(status_bits))
            except Exception:
                pass

        if _BATTLE_END_PATTERN.search(lowered_text):
            if message_id > 0:
                if message_id in self._counted_battle_end_message_ids:
                    self._log_event(
                        "battle_finished_duplicate_ignored",
                        {
                            "source": source,
                            "message_id": message_id,
                            "completed": self._run_completed_battles,
                            "target": self._run_target_battles,
                        },
                    )
                    return
                self._counted_battle_end_message_ids.add(message_id)

            self._run_completed_battles += 1
            self._log_event(
                "battle_finished",
                {
                    "source": source,
                    "message_id": message_id,
                    "completed": self._run_completed_battles,
                    "target": self._run_target_battles,
                    "mode": self._battle_mode_args,
                },
            )
            self._reset_battle_knowledge()
            
            # Handle indefinite mode - continue unless paused
            if self._run_indefinite or self._run_target_battles == -1:
                if bool(getattr(self.bot, "autofight_active", False)):
                    try:
                        await message.channel.send(
                            f"AutoFight: ∞ completed {self._run_completed_battles} | Next battle after cooldown."
                        )
                    except Exception:
                        pass
                    await self._schedule_next_battle_after_cooldown(message.channel)
                return
            
            if self._run_target_battles > 0:
                if self._run_completed_battles >= self._run_target_battles:
                    self.bot.autofight_active = False
                    self.bot.autofight_status = "Idle"
                    self._cancel_next_battle_task()
                    self._cancel_dispatch_watchdog()
                    await self._restore_other_automation()
                    await self.bot.log()
                    await message.channel.send(
                        f"AutoFight: completed {self._run_completed_battles}/{self._run_target_battles} battles. Stopping."
                    )
                    return

                try:
                    await message.channel.send(
                        f"AutoFight: completed {self._run_completed_battles}/{self._run_target_battles} battles. Next battle after cooldown."
                    )
                except Exception:
                    pass

                if self._next_battle_task is None or self._next_battle_task.done():
                    self._next_battle_task = asyncio.create_task(self._schedule_next_battle_after_cooldown(message.channel))
            return

        # Ignore non-actionable battle chatter to avoid corrupting active/enemy state.
        if not has_enabled_buttons and not switch_prompt and enemy_id is None and moves_taken is None:
            self._log_event("skip_non_actionable_message", {"preview": combined_text[:160]})
            return

        if not looks_like_battle:
            self._log_event("skip_not_battle_prompt", {"preview": combined_text[:160]})
            return

        if self._action_lock.locked():
            current = self._deferred_while_busy
            current_id = int(getattr(current[0], "id", 0) or 0) if current else -1
            if message_id >= current_id:
                self._deferred_while_busy = (message, source)
            self._log_event("skip_busy_action_lock", {"source": source, "message_id": message_id})
            return

        async with self._action_lock:
            if message_id in self._inflight_message_ids:
                self._deferred_messages_by_id[message_id] = (message, source)
                self._log_event("skip_inflight_message", {"source": source, "message_id": message_id})
                return
            self._inflight_message_ids.add(message_id)

            self._parse_self_stat_caps_and_drops(combined_text)
            self._learn_enemy_stat_drops_from_text(combined_text, enemy_id)
            self._learn_move_type_from_text(combined_text)
            self._learn_immunity_from_text(combined_text, enemy_id)
            self._learn_enemy_status_from_text(combined_text, enemy_id)
            self._learn_enemy_ability_from_text(combined_text, enemy_id)
            self._learn_enemy_item_from_text(combined_text, enemy_id)
            asyncio.create_task(self._learn_enemy_offense_from_text(combined_text, enemy_id))
            try:
                button, button_index, choice_kind = await self._pick_button(message, combined_text, enemy_id, moves_taken)
            except Exception as exc:
                self._log_event(
                    "pick_button_error",
                    {"source": source, "message_id": message_id, "error": str(exc)[:180]},
                )
                self._release_inflight_and_replay(message_id)
                return
            if button is None:
                self._log_event("skip_no_enabled_button", {"preview": combined_text[:160]})
                self._release_inflight_and_replay(message_id)
                return

            button_label = str(getattr(button, "label", "") or "")
            button_id = str(getattr(button, "custom_id", "") or "")
            dedupe_key = f"{button_id}|{button_label}|{button_index}"
            enemy_sig = self._normalize_pokemon_name(self._enemy_active_pokemon)
            active_sig = self._normalize_pokemon_name(self._active_pokemon)
            action_signature = f"{enemy_id}|{enemy_sig}|{active_sig}|{moves_taken}|{choice_kind}|{button_id}|{button_label}"

            # Avoid duplicate clicks on the same prompt when Discord emits rapid edits.
            if self._last_clicked_by_message.get(message_id) == dedupe_key:
                self._log_event(
                    "skip_duplicate_prompt",
                    {"source": source, "message_id": message_id, "index": button_index, "label": button_label[:80]},
                )
                self._release_inflight_and_replay(message_id)
                return
            if (
                self._last_action_signature == action_signature
                and self._last_action_signature_message_id == message_id
            ):
                self._log_event(
                    "skip_duplicate_action_signature",
                    {"source": source, "message_id": message_id, "signature": action_signature[:160]},
                )
                self._release_inflight_and_replay(message_id)
                return

            try:
                await self._click_button_with_refresh_retry(
                    message,
                    button,
                    message_id=message_id,
                    source=source,
                    button_id=button_id,
                    button_label=button_label,
                )
                if choice_kind == "switch" and button_label:
                    if self._pending_baton_stages:
                        row = self._ensure_stat_stage_row(button_label)
                        for stat_key, val in self._pending_baton_stages.items():
                            row[stat_key] = max(-6, min(6, int(val)))
                        caps = self._capped_stats_by_pokemon.setdefault(button_label.lower(), set())
                        for stat_key, val in row.items():
                            if int(val) >= 6:
                                caps.add(stat_key)
                    self._pending_baton_stages = None
                    self._planned_switch_target = ""
                    self._active_pokemon = button_label
                if choice_kind == "move" and self._is_setup_move(button_label):
                    active_key = self._normalize_pokemon_name(self._active_pokemon)
                    if active_key:
                        used = self._used_setup_moves_by_pokemon.setdefault(active_key, set())
                        used.add(self._normalize_move_name(button_label))
                if choice_kind == "move" and button_label:
                    self._record_move_use(enemy_id, button_label)
                self._last_clicked_by_message[message_id] = dedupe_key
                self._last_action_signature = action_signature
                self._last_action_signature_message_id = message_id
                self._log_event(
                    "click_success",
                    {
                        "source": source,
                        "kind": choice_kind,
                        "index": button_index,
                        "label": button_label,
                        "id": button_id,
                        "message_id": message_id,
                    },
                )
                record_anti_detect_event(
                    str(self.bot.user) if self.bot.user else "unknown",
                    "autofight_click",
                    module="autofight",
                    channel_id=self.config.autofight_channel_id,
                    details={
                        "source": source,
                        "kind": choice_kind,
                        "index": button_index,
                        "label": button_label,
                        "id": button_id,
                        "message_id": message_id,
                    },
                )
            except InvalidData:
                self._log_event("click_timeout_invaliddata", {"source": source, "message_id": message_id})
                pass
            except asyncio.TimeoutError:
                self._log_event("click_timeout", {"source": source, "message_id": message_id})
                pass
            except Exception as exc:
                if self._is_cloudflare_1015_error(str(exc)):
                    self._register_cloudflare_1015(source=source, message_id=message_id, error_text=str(exc))
                self._log_event("click_error", {"source": source, "message_id": message_id, "error": str(exc)[:180]})
                pass
            finally:
                self._release_inflight_and_replay(message_id)

        deferred_busy = self._deferred_while_busy
        self._deferred_while_busy = None
        if deferred_busy is not None:
            deferred_message, deferred_source = deferred_busy
            deferred_id = int(getattr(deferred_message, "id", 0) or 0)
            if deferred_id <= message_id:
                self._log_event(
                    "skip_stale_deferred_busy_message",
                    {"source": deferred_source, "message_id": deferred_id, "processed_message_id": message_id},
                )
                return
            self._log_event(
                "replay_deferred_busy_message",
                {"source": deferred_source, "message_id": deferred_id},
            )
            asyncio.create_task(self._handle_message(deferred_message, source=deferred_source))

    @commands.Cog.listener()
    async def on_message(self, message: Message) -> None:
        if not bool(getattr(self.config, "autofight_enabled", False)):
            return
        if not self._is_target_channel(message):
            return
        await self._handle_message(message, source="message")

    @commands.Cog.listener()
    async def on_message_edit(self, _before: Message, after: Message) -> None:
        if not bool(getattr(self.config, "autofight_enabled", False)):
            return
        if not self._is_target_channel(after):
            return
        await self._handle_message(after, source="edit")
