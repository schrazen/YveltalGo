from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class TeamPreset:
    name: str
    archetype: str  # 'stored_power', 'shuckle_rollout', 'power_trip', 'echoed_voice'
    slots: list[str]
    tier: str = "S+"  # "S+", "S", "A", "Budget"
    held_items: dict[str, str] = field(default_factory=dict)
    description: str = ""
    recommended_moves: dict[str, list[str]] = field(default_factory=dict)


# ==============================================================================
# Canonical PokéMeow World Boss Cheese Archetypes & Mega Mewtwo Y Combos
# (Aligned with Dovahluft's WB Excel Guide and Top MVP Leaderboards)
# ==============================================================================

MEW_TWO_Y_CHEESE_COMBOS: dict[str, TeamPreset] = {
    "double_pass_meta": TeamPreset(
        name="Swoobat + Smeargle + Mega-Mewtwo-Y (Goatwei 800k+ Meta MVP)",
        archetype="stored_power",
        slots=["Swoobat", "Smeargle", "Mega-Mewtwo-Y"],
        tier="S+",
        held_items={
            "Mega-Mewtwo-Y": "Twisted Spoon",
            "Smeargle": "Leftovers",
            "Swoobat": "Focus Sash",
        },
        description=(
            "Slot 1 Swoobat uses Simple ability: Calm Mind (+2 SpAtk, +2 SpDef) and Amnesia (+4 SpDef), "
            "then Baton Passes to Smeargle. Smeargle applies Geomancy (+2 SpAtk/SpDef/Speed), Cotton Guard (+3 Def), "
            "and Octolock (strips boss Def/SpDef each turn), then Baton Passes to Mega Mewtwo Y. "
            "Mega Mewtwo Y (194 SpAtk + Insomnia sleep immunity) fires Stored Power with 20+ stat boosts for 800k+ DMG."
        ),
        recommended_moves={
            "Swoobat": ["Calm Mind", "Amnesia", "Agility", "Baton Pass"],
            "Smeargle": ["Geomancy", "Cotton Guard", "Octolock", "Baton Pass"],
            "Mega-Mewtwo-Y": ["Stored Power", "Psychic Terrain", "Aura Sphere", "Recover"],
        },
    ),
    "volt_absorb_electric_pass": TeamPreset(
        name="Jolteon/Lanturn + Smeargle + Mega-Mewtwo-Y (Pikachu Electric Immunity)",
        archetype="stored_power",
        slots=["Jolteon", "Smeargle", "Mega-Mewtwo-Y"],
        tier="S",
        held_items={
            "Mega-Mewtwo-Y": "Twisted Spoon",
            "Smeargle": "Leftovers",
            "Jolteon": "Focus Sash",
        },
        description=(
            "Electric immunity pivot for Gmax Pikachu. Jolteon absorbs Electric attacks via Volt Absorb, "
            "debuffs the boss with Captivate/Fake Tears, and passes to Smeargle to complete stat accumulation "
            "before passing into Mega Mewtwo Y."
        ),
        recommended_moves={
            "Jolteon": ["Captivate", "Fake Tears", "Focus Energy", "Baton Pass"],
            "Smeargle": ["Geomancy", "Cotton Guard", "Baton Pass"],
            "Mega-Mewtwo-Y": ["Stored Power", "Psychic Terrain", "Recover"],
        },
    ),
    "psychic_terrain_expanding": TeamPreset(
        name="Tapu Lele / Smeargle + Mega-Mewtwo-Y (Psychic Terrain Expanding Force)",
        archetype="stored_power",
        slots=["Tapu Lele", "Smeargle", "Mega-Mewtwo-Y"],
        tier="S",
        held_items={
            "Mega-Mewtwo-Y": "Twisted Spoon",
            "Smeargle": "Leftovers",
        },
        description=(
            "Psychic Terrain grants a 1.3x boost to all Psychic moves and completely prevents enemy priority "
            "attacks (Sucker Punch, Extreme Speed). Mega Mewtwo Y utilizes Expanding Force or Stored Power to wipe the boss."
        ),
        recommended_moves={
            "Smeargle": ["Geomancy", "Cotton Guard", "Psychic Terrain", "Baton Pass"],
            "Mega-Mewtwo-Y": ["Stored Power", "Expanding Force", "Psystrike", "Recover"],
        },
    ),
    "debuff_stall_pass": TeamPreset(
        name="Smeargle (Octolock) + Swoobat + Mega-Mewtwo-Y (Boss Debuff Breaker)",
        archetype="stored_power",
        slots=["Smeargle", "Swoobat", "Mega-Mewtwo-Y"],
        tier="S",
        held_items={
            "Mega-Mewtwo-Y": "Twisted Spoon",
            "Smeargle": "Focus Sash",
        },
        description=(
            "Smeargle leads with Eerie Impulse (-2 SpAtk) and Octolock (permanently drops boss Def & SpDef each turn), "
            "neutralizing heavy-hitting bosses before Swoobat and Mega Mewtwo Y enter the field."
        ),
        recommended_moves={
            "Smeargle": ["Eerie Impulse", "Octolock", "Geomancy", "Baton Pass"],
            "Swoobat": ["Calm Mind", "Amnesia", "Baton Pass"],
            "Mega-Mewtwo-Y": ["Stored Power", "Aura Sphere", "Recover"],
        },
    ),
    "contrary_superpower_malamar": TeamPreset(
        name="Mew + Malamar + Mega-Mewtwo-Y (Contrary Superpower & Eerie Pass)",
        archetype="stored_power",
        slots=["Mew", "Malamar", "Mega-Mewtwo-Y"],
        tier="S+",
        held_items={
            "Mega-Mewtwo-Y": "Twisted Spoon",
            "Malamar": "Leftovers",
            "Mew": "Focus Sash",
        },
        description=(
            "Mew leads with Eerie Impulse (-2 SpAtk) and Focus Energy/Roost, passing into Contrary Malamar. "
            "Malamar uses Superpower to invert stat drops into +1 Atk and +1 Def each turn while inverting boss stats with Topsy-Turvy, "
            "then Baton Passes massive accumulated stats into Mega Mewtwo Y for a catastrophic Stored Power nuke."
        ),
        recommended_moves={
            "Mew": ["Eerie Impulse", "Focus Energy", "Roost", "Baton Pass"],
            "Malamar": ["Superpower", "Topsy-Turvy", "Foul Play", "Baton Pass"],
            "Mega-Mewtwo-Y": ["Stored Power", "Aura Sphere", "Psystrike", "Recover"],
        },
    ),
    "solo_mmy_self_setup": TeamPreset(
        name="Solo / Duo Mega-Mewtwo-Y Self-Sufficient Setup (No Passers Required)",
        archetype="stored_power",
        slots=["Mega-Mewtwo-Y"],
        tier="A",
        held_items={"Mega-Mewtwo-Y": "Twisted Spoon"},
        description=(
            "Self-contained setup when player does not own Baton Passers. MMY sets up Calm Mind / Nasty Plot, "
            "heals with Recover when taking damage, and sweeps with Stored Power and Aura Sphere."
        ),
        recommended_moves={
            "Mega-Mewtwo-Y": ["Calm Mind", "Recover", "Stored Power", "Aura Sphere"],
        },
    ),
}

GENERAL_CHEESE_PRESETS: dict[str, TeamPreset] = {
    "gardevoir_stored_power": TeamPreset(
        name="Smeargle + Swoobat + Mega-Gardevoir (Fairy/Psychic Draining Kiss)",
        archetype="stored_power",
        slots=["Smeargle", "Swoobat", "Mega-Gardevoir"],
        tier="S+",
        held_items={
            "Mega-Gardevoir": "Twisted Spoon",
            "Smeargle": "Leftovers",
        },
        description=(
            "Pixilate Fairy/Psychic sweeper. Draining Kiss heals Gardevoir back to 100% HP on every single turn "
            "while Stored Power shreds Dragon, Dark, and Fighting bosses (Gmax Urshifu, Machamp, Eternatus)."
        ),
        recommended_moves={
            "Smeargle": ["Geomancy", "Cotton Guard", "Octolock", "Baton Pass"],
            "Mega-Gardevoir": ["Stored Power", "Draining Kiss", "Moonblast", "Calm Mind"],
        },
    ),
    "shuckle_rollout_nuke": TeamPreset(
        name="Poliwrath + Mew + Shuckle (The Rollout Titan)",
        archetype="shuckle_rollout",
        slots=["Poliwrath", "Mew", "Shuckle"],
        tier="S+",
        held_items={
            "Shuckle": "Hard Stone",
            "Poliwrath": "Sitrus Berry",
            "Mew": "Leftovers",
        },
        description=(
            "Poliwrath uses Belly Drum (+6 Atk) and passes to Mew (Amnesia/Screech/Pass) into Shuckle. "
            "Shuckle uses Defense Curl (doubles Rollout power) + Power Trick (swaps base 10 Atk with 230 Def) "
            "then unleashes exponential Rollout against Fire, Flying, Bug, and Ice bosses."
        ),
        recommended_moves={
            "Poliwrath": ["Belly Drum", "Baton Pass"],
            "Mew": ["Amnesia", "Screech", "Baton Pass"],
            "Shuckle": ["Defense Curl", "Power Trick", "Rollout"],
        },
    ),
    "krookodile_power_trip": TeamPreset(
        name="Smeargle + Blaziken + Krookodile (Physical Power Trip)",
        archetype="power_trip",
        slots=["Smeargle", "Blaziken", "Krookodile"],
        tier="S+",
        held_items={
            "Krookodile": "Black Glasses",
            "Smeargle": "Focus Sash",
        },
        description=(
            "Physical counterpart of Stored Power (+20 BP per positive stat stage). "
            "Krookodile (Moxie / Anger Point) receives Shift Gear, Coil, and Cotton Guard buffs to obliterate "
            "Ghost and Psychic bosses (Gengar, Orbeetle, Hatterene, Alcremie)."
        ),
        recommended_moves={
            "Smeargle": ["Shift Gear", "Coil", "Cotton Guard", "Baton Pass"],
            "Krookodile": ["Power Trip", "Crunch", "Earthquake"],
        },
    ),
    "sylveon_echoed_voice": TeamPreset(
        name="Smeargle + Sylveon (Pixilate Echoed Voice)",
        archetype="echoed_voice",
        slots=["Smeargle", "Sylveon"],
        tier="A",
        held_items={"Sylveon": "Pixie Plate"},
        description="Echoed Voice gains power with consecutive uses, boosted by Pixilate and Fairy Plate.",
        recommended_moves={
            "Smeargle": ["Geomancy", "Shift Gear", "Baton Pass"],
            "Sylveon": ["Echoed Voice", "Hyper Voice", "Calm Mind"],
        },
    ),
}


@dataclass
class WorldBossStrategy:
    boss_name: str
    archetype: str  # 'stored_power', 'shuckle_rollout', 'power_trip', 'echoed_voice'
    sweeper: str
    sweepers: list[str] = field(default_factory=list)
    passers: list[str] = field(default_factory=list)
    setup_moves: list[str] = field(default_factory=list)
    attack_moves: list[str] = field(default_factory=list)
    emergency_moves: list[str] = field(default_factory=list)
    recommended_items: dict[str, str] = field(default_factory=dict)
    team_presets: list[TeamPreset] = field(default_factory=list)
    notes: str = ""

    def get_all_sweepers(self) -> list[str]:
        """Return all valid sweeper candidates in priority order."""
        res: list[str] = []
        if self.sweepers:
            for s in self.sweepers:
                if s and s not in res:
                    res.append(s)
        if self.sweeper and self.sweeper not in res:
            res.append(self.sweeper)
        return res


# Master strategy dictionary covering all 34 Gigantamax World Bosses
WORLD_BOSS_STRATEGIES: dict[str, WorldBossStrategy] = {
    # Stored Power Cheese Bosses
    "venusaur": WorldBossStrategy(
        boss_name="Gigantamax-Venusaur",
        archetype="stored_power",
        sweeper="Mega Gardevoir",
        sweepers=["Mega-Mewtwo-Y", "Mega Gardevoir", "Mega-Gardevoir", "Necrozma-Ultra"],
        passers=["Swoobat", "Smeargle", "Shiny Smeargle", "Mew"],
        setup_moves=["Eerie Impulse", "Geomancy", "Calm Mind", "Amnesia", "Focus Energy", "Octolock", "Coil", "Acupressure", "Baton Pass"],
        attack_moves=["Stored Power", "Psychic", "Expanding Force", "Draining Kiss"],
        emergency_moves=["Draining Kiss", "Milk Drink", "Recover"],
        team_presets=[
            MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"],
            GENERAL_CHEESE_PRESETS["gardevoir_stored_power"],
            MEW_TWO_Y_CHEESE_COMBOS["solo_mmy_self_setup"],
        ],
    ),
    "charizard": WorldBossStrategy(
        boss_name="Gigantamax-Charizard",
        archetype="shuckle_rollout",
        sweeper="Shuckle",
        sweepers=["Shuckle", "Mega-Mewtwo-Y", "Mega-Gardevoir"],
        passers=["Poliwrath", "Mew", "Vaporeon", "Gliscor", "Smeargle"],
        setup_moves=["Captivate", "Amnesia", "Belly Drum", "Hone Claws", "Focus Energy", "Screech", "Defense Curl", "Power Trick", "Baton Pass"],
        attack_moves=["Rollout", "Stored Power"],
        emergency_moves=["Milk Drink", "Recover"],
        team_presets=[
            GENERAL_CHEESE_PRESETS["shuckle_rollout_nuke"],
            MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"],
        ],
    ),
    "blastoise": WorldBossStrategy(
        boss_name="Gigantamax-Blastoise",
        archetype="stored_power",
        sweeper="Mega Gardevoir",
        sweepers=["Mega-Mewtwo-Y", "Mega Gardevoir", "Mega-Gardevoir"],
        passers=["Swoobat", "Smeargle", "Shiny Smeargle"],
        setup_moves=["Eerie Impulse", "Geomancy", "Calm Mind", "Amnesia", "Focus Energy", "Octolock", "Coil", "Acupressure", "Baton Pass"],
        attack_moves=["Stored Power", "Expanding Force", "Draining Kiss"],
        emergency_moves=["Draining Kiss", "Recover"],
        team_presets=[
            MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"],
            GENERAL_CHEESE_PRESETS["gardevoir_stored_power"],
        ],
    ),
    "butterfree": WorldBossStrategy(
        boss_name="Gigantamax-Butterfree",
        archetype="shuckle_rollout",
        sweeper="Shuckle",
        sweepers=["Shuckle", "Mega-Mewtwo-Y", "Mega-Gardevoir"],
        passers=["Poliwrath", "Mew", "Vaporeon", "Gliscor", "Smeargle"],
        setup_moves=["Captivate", "Amnesia", "Belly Drum", "Hone Claws", "Focus Energy", "Screech", "Defense Curl", "Power Trick", "Baton Pass"],
        attack_moves=["Rollout", "Stored Power"],
        emergency_moves=["Recover"],
        team_presets=[
            GENERAL_CHEESE_PRESETS["shuckle_rollout_nuke"],
            MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"],
        ],
    ),
    "pikachu": WorldBossStrategy(
        boss_name="Gigantamax-Pikachu",
        archetype="stored_power",
        sweeper="Mega-Mewtwo-Y",
        sweepers=["Mega-Mewtwo-Y", "Mega Gardevoir", "Mega-Gardevoir"],
        passers=["Jolteon", "Remoraid", "Smeargle", "Swoobat"],
        setup_moves=["Entrainment", "Captivate", "Fake Tears", "Focus Energy", "Geomancy", "Cotton Guard", "Substitute", "Role Play", "Baton Pass"],
        attack_moves=["Stored Power", "Expanding Force", "Psychic Terrain", "Psystrike"],
        emergency_moves=["Recover"],
        team_presets=[
            MEW_TWO_Y_CHEESE_COMBOS["volt_absorb_electric_pass"],
            MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"],
            MEW_TWO_Y_CHEESE_COMBOS["solo_mmy_self_setup"],
        ],
    ),
    "meowth": WorldBossStrategy(
        boss_name="Gigantamax-Meowth",
        archetype="stored_power",
        sweeper="Mega-Gardevoir",
        sweepers=["Mega-Mewtwo-Y", "Mega-Gardevoir", "Mega Gardevoir"],
        passers=["Swoobat", "Smeargle", "Shiny Smeargle"],
        setup_moves=["Eerie Impulse", "Geomancy", "Calm Mind", "Amnesia", "Octolock", "Coil", "Focus Energy", "Baton Pass"],
        attack_moves=["Stored Power", "Expanding Force", "Draining Kiss"],
        emergency_moves=["Draining Kiss", "Recover"],
        team_presets=[
            MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"],
            GENERAL_CHEESE_PRESETS["gardevoir_stored_power"],
        ],
    ),
    "machamp": WorldBossStrategy(
        boss_name="Gigantamax-Machamp",
        archetype="stored_power",
        sweeper="Mega-Gardevoir",
        sweepers=["Mega-Mewtwo-Y", "Mega-Gardevoir", "Mega Gardevoir"],
        passers=["Swoobat", "Smeargle", "Shiny Smeargle"],
        setup_moves=["Eerie Impulse", "Geomancy", "Calm Mind", "Amnesia", "Octolock", "Coil", "Focus Energy", "Baton Pass"],
        attack_moves=["Stored Power", "Expanding Force", "Psychic", "Draining Kiss"],
        emergency_moves=["Draining Kiss", "Recover"],
        team_presets=[
            MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"],
            GENERAL_CHEESE_PRESETS["gardevoir_stored_power"],
        ],
    ),
    "gengar": WorldBossStrategy(
        boss_name="Gigantamax-Gengar",
        archetype="power_trip",
        sweeper="Krookodile",
        sweepers=["Krookodile", "Mega-Mewtwo-Y"],
        passers=["Smeargle", "Blaziken", "Scolipede"],
        setup_moves=["Shift Gear", "Coil", "Cotton Guard", "Ingrain", "Amnesia", "Swords Dance", "Baton Pass"],
        attack_moves=["Power Trip", "Crunch", "Earthquake"],
        emergency_moves=["Recover"],
        team_presets=[
            GENERAL_CHEESE_PRESETS["krookodile_power_trip"],
            MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"],
        ],
    ),
    "kingler": WorldBossStrategy(
        boss_name="Gigantamax-Kingler",
        archetype="stored_power",
        sweeper="Mega-Gardevoir",
        sweepers=["Mega-Mewtwo-Y", "Mega-Gardevoir", "Mega Gardevoir"],
        passers=["Swoobat", "Smeargle"],
        setup_moves=["Eerie Impulse", "Geomancy", "Calm Mind", "Amnesia", "Octolock", "Coil", "Baton Pass"],
        attack_moves=["Stored Power", "Expanding Force", "Draining Kiss"],
        emergency_moves=["Draining Kiss", "Recover"],
        team_presets=[
            MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"],
            GENERAL_CHEESE_PRESETS["gardevoir_stored_power"],
        ],
    ),
    "lapras": WorldBossStrategy(
        boss_name="Gigantamax-Lapras",
        archetype="shuckle_rollout",
        sweeper="Shuckle",
        sweepers=["Shuckle", "Mega-Mewtwo-Y"],
        passers=["Poliwrath", "Mew", "Smeargle"],
        setup_moves=["Captivate", "Amnesia", "Belly Drum", "Defense Curl", "Power Trick", "Baton Pass"],
        attack_moves=["Rollout", "Stored Power"],
        emergency_moves=["Recover"],
        team_presets=[
            GENERAL_CHEESE_PRESETS["shuckle_rollout_nuke"],
            MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"],
        ],
    ),
    "eevee": WorldBossStrategy(
        boss_name="Gigantamax-Eevee",
        archetype="stored_power",
        sweeper="Mega-Gardevoir",
        sweepers=["Mega-Mewtwo-Y", "Mega-Gardevoir", "Mega Gardevoir"],
        passers=["Swoobat", "Smeargle"],
        setup_moves=["Eerie Impulse", "Geomancy", "Calm Mind", "Amnesia", "Octolock", "Coil", "Baton Pass"],
        attack_moves=["Stored Power", "Expanding Force", "Draining Kiss"],
        emergency_moves=["Draining Kiss", "Recover"],
        team_presets=[
            MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"],
            GENERAL_CHEESE_PRESETS["gardevoir_stored_power"],
        ],
    ),
    "snorlax": WorldBossStrategy(
        boss_name="Gigantamax-Snorlax",
        archetype="shuckle_rollout",
        sweeper="Shuckle",
        sweepers=["Shuckle", "Mega-Mewtwo-Y"],
        passers=["Poliwrath", "Mew", "Smeargle"],
        setup_moves=["Captivate", "Amnesia", "Belly Drum", "Defense Curl", "Power Trick", "Baton Pass"],
        attack_moves=["Rollout", "Stored Power", "Aura Sphere"],
        emergency_moves=["Recover"],
        team_presets=[
            GENERAL_CHEESE_PRESETS["shuckle_rollout_nuke"],
            MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"],
        ],
    ),
    "garbodor": WorldBossStrategy(
        boss_name="Gigantamax-Garbodor",
        archetype="stored_power",
        sweeper="Mega-Gardevoir",
        sweepers=["Mega-Mewtwo-Y", "Mega-Gardevoir", "Mega Gardevoir"],
        passers=["Swoobat", "Smeargle"],
        setup_moves=["Eerie Impulse", "Geomancy", "Calm Mind", "Amnesia", "Octolock", "Coil", "Baton Pass"],
        attack_moves=["Stored Power", "Psychic", "Expanding Force"],
        emergency_moves=["Draining Kiss", "Recover"],
        team_presets=[
            MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"],
            GENERAL_CHEESE_PRESETS["gardevoir_stored_power"],
        ],
    ),
    "melmetal": WorldBossStrategy(
        boss_name="Gigantamax-Melmetal",
        archetype="stored_power",
        sweeper="Mega-Charizard-Y",
        sweepers=["Mega-Mewtwo-Y", "Mega-Charizard-Y"],
        passers=["Smeargle", "Swoobat"],
        setup_moves=["Geomancy", "Calm Mind", "Coil", "Baton Pass"],
        attack_moves=["Flamethrower", "Fire Blast", "Stored Power", "Aura Sphere"],
        emergency_moves=["Recover"],
        team_presets=[
            MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"],
            MEW_TWO_Y_CHEESE_COMBOS["solo_mmy_self_setup"],
        ],
    ),
    "corviknight": WorldBossStrategy(
        boss_name="Gigantamax-Corviknight",
        archetype="echoed_voice",
        sweeper="Sylveon",
        sweepers=["Sylveon", "Mega-Mewtwo-Y"],
        passers=["Smeargle", "Swoobat"],
        setup_moves=["Geomancy", "Shift Gear", "Calm Mind", "Baton Pass"],
        attack_moves=["Echoed Voice", "Hyper Voice", "Stored Power"],
        emergency_moves=["Recover"],
        team_presets=[
            GENERAL_CHEESE_PRESETS["sylveon_echoed_voice"],
            MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"],
        ],
    ),
    "orbeetle": WorldBossStrategy(
        boss_name="Gigantamax-Orbeetle",
        archetype="power_trip",
        sweeper="Krookodile",
        sweepers=["Krookodile", "Mega-Mewtwo-Y"],
        passers=["Smeargle", "Blaziken"],
        setup_moves=["Shift Gear", "Coil", "Cotton Guard", "Baton Pass"],
        attack_moves=["Power Trip", "Crunch"],
        emergency_moves=["Recover"],
        team_presets=[
            GENERAL_CHEESE_PRESETS["krookodile_power_trip"],
            MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"],
        ],
    ),
    "drednaw": WorldBossStrategy(
        boss_name="Gigantamax-Drednaw",
        archetype="stored_power",
        sweeper="Mega-Gardevoir",
        sweepers=["Mega-Mewtwo-Y", "Mega-Gardevoir", "Mega Gardevoir"],
        passers=["Swoobat", "Smeargle"],
        setup_moves=["Eerie Impulse", "Geomancy", "Calm Mind", "Amnesia", "Octolock", "Coil", "Baton Pass"],
        attack_moves=["Stored Power", "Energy Ball", "Expanding Force"],
        emergency_moves=["Recover"],
        team_presets=[
            MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"],
            GENERAL_CHEESE_PRESETS["gardevoir_stored_power"],
        ],
    ),
    "coalossal": WorldBossStrategy(
        boss_name="Gigantamax-Coalossal",
        archetype="stored_power",
        sweeper="Mega-Blastoise",
        sweepers=["Mega-Mewtwo-Y", "Mega-Blastoise"],
        passers=["Smeargle", "Swoobat"],
        setup_moves=["Geomancy", "Calm Mind", "Octolock", "Coil", "Baton Pass"],
        attack_moves=["Water Pulse", "Hydro Cannon", "Stored Power"],
        emergency_moves=["Recover"],
        team_presets=[
            MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"],
            MEW_TWO_Y_CHEESE_COMBOS["solo_mmy_self_setup"],
        ],
    ),
    "flapple": WorldBossStrategy(
        boss_name="Gigantamax-Flapple",
        archetype="stored_power",
        sweeper="Mega-Gardevoir",
        sweepers=["Mega-Mewtwo-Y", "Mega-Gardevoir", "Mega Gardevoir"],
        passers=["Swoobat", "Smeargle"],
        setup_moves=["Eerie Impulse", "Geomancy", "Calm Mind", "Amnesia", "Octolock", "Coil", "Baton Pass"],
        attack_moves=["Stored Power", "Moonblast", "Draining Kiss", "Expanding Force"],
        emergency_moves=["Draining Kiss", "Recover"],
        team_presets=[
            MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"],
            GENERAL_CHEESE_PRESETS["gardevoir_stored_power"],
        ],
    ),
    "appletun": WorldBossStrategy(
        boss_name="Gigantamax-Appletun",
        archetype="stored_power",
        sweeper="Mega-Gardevoir",
        sweepers=["Mega-Mewtwo-Y", "Mega-Gardevoir", "Mega Gardevoir"],
        passers=["Swoobat", "Smeargle"],
        setup_moves=["Eerie Impulse", "Geomancy", "Calm Mind", "Amnesia", "Octolock", "Coil", "Baton Pass"],
        attack_moves=["Stored Power", "Moonblast", "Draining Kiss", "Expanding Force"],
        emergency_moves=["Draining Kiss", "Recover"],
        team_presets=[
            MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"],
            GENERAL_CHEESE_PRESETS["gardevoir_stored_power"],
        ],
    ),
    "sandaconda": WorldBossStrategy(
        boss_name="Gigantamax-Sandaconda",
        archetype="stored_power",
        sweeper="Mega-Gardevoir",
        sweepers=["Mega-Mewtwo-Y", "Mega-Gardevoir", "Mega Gardevoir"],
        passers=["Swoobat", "Smeargle"],
        setup_moves=["Eerie Impulse", "Geomancy", "Calm Mind", "Amnesia", "Octolock", "Coil", "Baton Pass"],
        attack_moves=["Stored Power", "Energy Ball", "Expanding Force"],
        emergency_moves=["Recover"],
        team_presets=[
            MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"],
            GENERAL_CHEESE_PRESETS["gardevoir_stored_power"],
        ],
    ),
    "toxtricity": WorldBossStrategy(
        boss_name="Gigantamax-Toxtricity",
        archetype="stored_power",
        sweeper="Mega-Gardevoir",
        sweepers=["Mega-Mewtwo-Y", "Mega-Gardevoir", "Mega Gardevoir"],
        passers=["Swoobat", "Smeargle"],
        setup_moves=["Eerie Impulse", "Geomancy", "Calm Mind", "Amnesia", "Octolock", "Coil", "Baton Pass"],
        attack_moves=["Stored Power", "Psychic", "Expanding Force"],
        emergency_moves=["Recover"],
        team_presets=[
            MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"],
            GENERAL_CHEESE_PRESETS["gardevoir_stored_power"],
        ],
    ),
    "centiskorch": WorldBossStrategy(
        boss_name="Gigantamax-Centiskorch",
        archetype="shuckle_rollout",
        sweeper="Shuckle",
        sweepers=["Shuckle", "Mega-Mewtwo-Y"],
        passers=["Poliwrath", "Mew", "Smeargle"],
        setup_moves=["Captivate", "Amnesia", "Belly Drum", "Defense Curl", "Power Trick", "Baton Pass"],
        attack_moves=["Rollout", "Stored Power"],
        emergency_moves=["Recover"],
        team_presets=[
            GENERAL_CHEESE_PRESETS["shuckle_rollout_nuke"],
            MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"],
        ],
    ),
    "hatterene": WorldBossStrategy(
        boss_name="Gigantamax-Hatterene",
        archetype="power_trip",
        sweeper="Krookodile",
        sweepers=["Krookodile", "Mega-Mewtwo-Y"],
        passers=["Smeargle", "Blaziken"],
        setup_moves=["Shift Gear", "Coil", "Cotton Guard", "Baton Pass"],
        attack_moves=["Power Trip", "Crunch"],
        emergency_moves=["Recover"],
        team_presets=[
            GENERAL_CHEESE_PRESETS["krookodile_power_trip"],
            MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"],
        ],
    ),
    "grimmsnarl": WorldBossStrategy(
        boss_name="Gigantamax-Grimmsnarl",
        archetype="stored_power",
        sweeper="Mega-Gardevoir",
        sweepers=["Mega-Gardevoir", "Mega Gardevoir", "Mega-Mewtwo-Y"],
        passers=["Swoobat", "Smeargle"],
        setup_moves=["Eerie Impulse", "Geomancy", "Calm Mind", "Amnesia", "Octolock", "Coil", "Baton Pass"],
        attack_moves=["Stored Power", "Moonblast", "Draining Kiss"],
        emergency_moves=["Draining Kiss", "Recover"],
        team_presets=[
            GENERAL_CHEESE_PRESETS["gardevoir_stored_power"],
            MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"],
        ],
    ),
    "alcremie": WorldBossStrategy(
        boss_name="Gigantamax-Alcremie",
        archetype="power_trip",
        sweeper="Krookodile",
        sweepers=["Krookodile", "Mega-Mewtwo-Y"],
        passers=["Smeargle", "Blaziken"],
        setup_moves=["Shift Gear", "Coil", "Cotton Guard", "Baton Pass"],
        attack_moves=["Power Trip", "Crunch"],
        emergency_moves=["Recover"],
        team_presets=[
            GENERAL_CHEESE_PRESETS["krookodile_power_trip"],
            MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"],
        ],
    ),
    "copperajah": WorldBossStrategy(
        boss_name="Gigantamax-Copperajah",
        archetype="stored_power",
        sweeper="Mega-Charizard-Y",
        sweepers=["Mega-Mewtwo-Y", "Mega-Charizard-Y"],
        passers=["Smeargle", "Swoobat"],
        setup_moves=["Geomancy", "Calm Mind", "Coil", "Baton Pass"],
        attack_moves=["Flamethrower", "Fire Blast", "Stored Power", "Aura Sphere"],
        emergency_moves=["Recover"],
        team_presets=[
            MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"],
            MEW_TWO_Y_CHEESE_COMBOS["solo_mmy_self_setup"],
        ],
    ),
    "duraludon": WorldBossStrategy(
        boss_name="Gigantamax-Duraludon",
        archetype="stored_power",
        sweeper="Mega-Charizard-Y",
        sweepers=["Mega-Mewtwo-Y", "Mega-Charizard-Y"],
        passers=["Smeargle", "Swoobat"],
        setup_moves=["Geomancy", "Calm Mind", "Coil", "Baton Pass"],
        attack_moves=["Flamethrower", "Earth Power", "Stored Power", "Aura Sphere"],
        emergency_moves=["Recover"],
        team_presets=[
            MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"],
            MEW_TWO_Y_CHEESE_COMBOS["solo_mmy_self_setup"],
        ],
    ),
    "eternatus": WorldBossStrategy(
        boss_name="Eternamax-Eternatus",
        archetype="stored_power",
        sweeper="Mega-Gardevoir",
        sweepers=["Mega-Mewtwo-Y", "Mega-Gardevoir", "Mega Gardevoir"],
        passers=["Swoobat", "Smeargle"],
        setup_moves=["Eerie Impulse", "Geomancy", "Calm Mind", "Amnesia", "Octolock", "Coil", "Baton Pass"],
        attack_moves=["Stored Power", "Psychic", "Expanding Force", "Draining Kiss"],
        emergency_moves=["Draining Kiss", "Recover"],
        team_presets=[
            MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"],
            GENERAL_CHEESE_PRESETS["gardevoir_stored_power"],
        ],
    ),
    "urshifu single": WorldBossStrategy(
        boss_name="Gigantamax-Urshifu-Single",
        archetype="stored_power",
        sweeper="Mega-Gardevoir",
        sweepers=["Mega-Gardevoir", "Mega Gardevoir", "Mega-Mewtwo-Y"],
        passers=["Swoobat", "Smeargle"],
        setup_moves=["Eerie Impulse", "Geomancy", "Calm Mind", "Amnesia", "Octolock", "Coil", "Baton Pass"],
        attack_moves=["Stored Power", "Moonblast", "Draining Kiss"],
        emergency_moves=["Draining Kiss", "Recover"],
        team_presets=[
            GENERAL_CHEESE_PRESETS["gardevoir_stored_power"],
            MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"],
        ],
    ),
    "urshifu rapid": WorldBossStrategy(
        boss_name="Gigantamax-Urshifu-Rapid",
        archetype="stored_power",
        sweeper="Mega-Gardevoir",
        sweepers=["Mega-Mewtwo-Y", "Mega-Gardevoir", "Mega Gardevoir"],
        passers=["Swoobat", "Smeargle"],
        setup_moves=["Eerie Impulse", "Geomancy", "Calm Mind", "Amnesia", "Octolock", "Coil", "Baton Pass"],
        attack_moves=["Stored Power", "Moonblast", "Energy Ball", "Expanding Force"],
        emergency_moves=["Draining Kiss", "Recover"],
        team_presets=[
            MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"],
            GENERAL_CHEESE_PRESETS["gardevoir_stored_power"],
        ],
    ),
}

DEFAULT_FALLBACK_STRATEGY = WorldBossStrategy(
    boss_name="Default-WorldBoss",
    archetype="stored_power",
    sweeper="Mega-Gardevoir",
    sweepers=["Mega-Mewtwo-Y", "Mega Mewtwo Y", "Mega-Gardevoir", "Mega Gardevoir", "Necrozma-Ultra", "Swoobat"],
    passers=["Swoobat", "Smeargle", "Shiny Smeargle", "Mew", "Malamar", "Poliwrath"],
    setup_moves=[
        "Superpower", "Topsy-Turvy", "Eerie Impulse", "Geomancy", "Calm Mind", "Amnesia", "Agility",
        "Cotton Guard", "Iron Defense", "Octolock", "Shift Gear", "Coil",
        "Acupressure", "Focus Energy", "Captivate", "Fake Tears", "Roost",
        "Psychic Terrain", "Belly Drum", "Defense Curl", "Power Trick", "Baton Pass"
    ],
    attack_moves=[
        "Stored Power", "Expanding Force", "Psystrike", "Psychic",
        "Draining Kiss", "Moonblast", "Aura Sphere", "Focus Blast",
        "Superpower", "Psycho Cut", "Night Slash", "Foul Play",
        "Rollout", "Power Trip", "Crunch", "Earthquake", "Flamethrower", "Echoed Voice"
    ],
    emergency_moves=["Draining Kiss", "Roost", "Milk Drink", "Recover", "Wish", "Rest"],
    team_presets=[
        MEW_TWO_Y_CHEESE_COMBOS["contrary_superpower_malamar"],
        MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"],
        GENERAL_CHEESE_PRESETS["gardevoir_stored_power"],
        MEW_TWO_Y_CHEESE_COMBOS["solo_mmy_self_setup"],
    ],
)


def get_boss_strategy(boss_name: str) -> WorldBossStrategy:
    """Lookup World Boss strategy by loose or normalized name."""
    clean = re.sub(r"[^\w\s]", " ", (boss_name or "").lower()).strip()
    clean = re.sub(r"\b(gigantamax|gmax|eternamax)\b", "", clean).strip()

    for key, strat in WORLD_BOSS_STRATEGIES.items():
        if key in clean or clean in key:
            return strat

    return DEFAULT_FALLBACK_STRATEGY


# ==============================================================================
# WorldBossTeamBuilder (Meta Cheese Team Formation & Equipment Automation)
# ==============================================================================

class WorldBossTeamBuilder:
    """Intelligent team composition and equipment engine for PokéMeow World Boss battles."""

    @staticmethod
    def get_presets_for_boss(boss_name: str) -> list[TeamPreset]:
        strategy = get_boss_strategy(boss_name)
        if strategy.team_presets:
            return strategy.team_presets
        return [
            MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"],
            GENERAL_CHEESE_PRESETS["gardevoir_stored_power"],
            MEW_TWO_Y_CHEESE_COMBOS["solo_mmy_self_setup"],
        ]

    @staticmethod
    def recommend_team(
        boss_name: str,
        owned_pokemon: Optional[list[str]] = None,
    ) -> tuple[TeamPreset, str]:
        """Recommend the optimal team preset based on boss and owned Pokémon.
        
        If owned_pokemon is provided, evaluates which presets can be fully formed.
        If no preset is 100% matched, adapts and constructs the best viable hybrid team.
        """
        presets = WorldBossTeamBuilder.get_presets_for_boss(boss_name)
        if not owned_pokemon:
            return presets[0], "Recommended #1 Meta Preset"

        cleaned_owned = [p.lower().replace("-", " ").strip() for p in owned_pokemon]

        # 1. Check exact preset matches (prioritizing multi-slot teams)
        matched_presets: list[tuple[TeamPreset, int]] = []
        for preset in presets:
            all_present = True
            for slot_pkmn in preset.slots:
                c_slot = slot_pkmn.lower().replace("-", " ").strip()
                if not any(c_slot in o or o in c_slot for o in cleaned_owned):
                    all_present = False
                    break
            if all_present:
                matched_presets.append((preset, len(preset.slots)))

        multi_slot = [p for p, count in matched_presets if count >= 2]
        if multi_slot:
            return multi_slot[0], f"Matched complete preset '{multi_slot[0].name}'"

        # 2. Hybrid adaptation using Pokémon meta knowledge
        has_mmy = any("mewtwo" in o for o in cleaned_owned)
        has_gard = any("gardevoir" in o for o in cleaned_owned)
        has_shuckle = any("shuckle" in o for o in cleaned_owned)
        has_krook = any("krookodile" in o for o in cleaned_owned)

        has_smeargle = any("smeargle" in o for o in cleaned_owned)
        has_swoobat = any("swoobat" in o for o in cleaned_owned)
        has_mew = any("mew" in o and "mewtwo" not in o for o in cleaned_owned)
        has_poliwrath = any("poliwrath" in o for o in cleaned_owned)

        # If player owns passers and sweepers, construct an adaptive hybrid team
        if has_swoobat or has_smeargle or has_mew or (has_poliwrath and has_shuckle):
            boss_lowered = boss_name.lower()
            if has_shuckle and any(x in boss_lowered for x in ["charizard", "centiskorch", "butterfree", "lapras", "snorlax"]):
                chosen_sweeper = "Shuckle"
            elif has_krook and any(x in boss_lowered for x in ["gengar", "orbeetle", "hatterene", "alcremie"]):
                chosen_sweeper = "Krookodile"
            elif has_gard and any(x in boss_lowered for x in ["urshifu", "machamp", "grimmsnarl", "eternatus"]):
                chosen_sweeper = "Mega-Gardevoir"
            elif has_mmy:
                chosen_sweeper = "Mega-Mewtwo-Y"
            elif has_gard:
                chosen_sweeper = "Mega-Gardevoir"
            elif has_shuckle:
                chosen_sweeper = "Shuckle"
            else:
                chosen_sweeper = "Mega-Mewtwo-Y"

            chosen_passers: list[str] = []
            if has_swoobat:
                chosen_passers.append("Swoobat")
            if has_smeargle:
                chosen_passers.append("Smeargle")
            elif has_mew:
                chosen_passers.append("Mew")
            elif has_poliwrath and chosen_sweeper == "Shuckle":
                chosen_passers.append("Poliwrath")

            hybrid_slots = chosen_passers + [chosen_sweeper]
            held_items = {}
            if "Mewtwo" in chosen_sweeper or "Gardevoir" in chosen_sweeper:
                held_items[chosen_sweeper] = "Twisted Spoon"
            elif "Shuckle" in chosen_sweeper:
                held_items[chosen_sweeper] = "Hard Stone"
            elif "Krookodile" in chosen_sweeper:
                held_items[chosen_sweeper] = "Black Glasses"

            hybrid_preset = TeamPreset(
                name=f"Adapted Hybrid ({' + '.join(hybrid_slots[:3])})",
                archetype="stored_power" if "Shuckle" not in chosen_sweeper else "shuckle_rollout",
                slots=hybrid_slots[:3],
                held_items=held_items,
                description="Auto-constructed hybrid based on available account Pokémon and PokéMeow meta cheese.",
                tier="A+",
            )
            return hybrid_preset, "Constructed adaptive hybrid team"

        # 3. Fallback to matched single-slot preset (e.g. solo MMY)
        if matched_presets:
            return matched_presets[0][0], f"Matched preset '{matched_presets[0][0].name}'"

        return presets[0], "Fallback to default meta preset"

    @staticmethod
    def generate_pokemeow_commands(preset: TeamPreset, favorite_team_name: Optional[str] = None) -> list[str]:
        """Generate the exact PokéMeow commands to configure this team."""
        commands: list[str] = []
        if not preset.slots:
            return commands

        # If user has a favorite team name (or matches known preset), load via ;team use <name>
        if favorite_team_name:
            commands.append(f";team use {favorite_team_name}")
        elif preset.name.lower() in {"wb", "wb2", "wb3", "mgarde", "mewft", "farm"}:
            commands.append(f";team use {preset.name.lower()}")

        # Slot-by-slot setting using valid PokéMeow syntax: ;team add {pokemon} {slot 1-3}
        for idx, pkmn in enumerate(preset.slots, start=1):
            clean_name = pkmn.replace("Mega-", "mega ").replace("Shiny-", "shiny ").replace("Golden-", "golden ")
            if "mega " in clean_name.lower():
                clean_name = clean_name.replace("-", " ")
            clean_name = clean_name.strip()
            commands.append(f";team add {clean_name} {idx}")

        # Held item assignment
        for pkmn, item in preset.held_items.items():
            clean_pkmn = pkmn.replace("Mega-", "").replace("Shiny-", "").strip()
            commands.append(f";item hold {item} {clean_pkmn}")

        return commands

    @staticmethod
    def format_team_guide(boss_name: str, owned_pokemon: Optional[list[str]] = None) -> str:
        """Format an extensive human-readable team comp guide for Discord."""
        preset, match_reason = WorldBossTeamBuilder.recommend_team(boss_name, owned_pokemon)
        commands = WorldBossTeamBuilder.generate_pokemeow_commands(preset)

        lines = [
            f"**⚔️ World Boss Comp Guide for {boss_name}**",
            f"**Meta Preset:** {preset.name} [{preset.tier}] ({match_reason})",
            f"**Archetype:** `{preset.archetype}`",
            f"**Team Slots:** " + " ➔ ".join(f"**[{i+1}] {s}**" for i, s in enumerate(preset.slots)),
        ]
        if preset.held_items:
            items_str = ", ".join(f"{p}: `{item}`" for p, item in preset.held_items.items())
            lines.append(f"**Held Items:** {items_str}")
        if preset.description:
            lines.append(f"**Tactics:** {preset.description}")

        lines.append("\n**PokéMeow Setup Commands:**")
        lines.append(f"`{commands[0]}`")
        for cmd in commands:
            if "item hold" in cmd:
                lines.append(f"`{cmd}`")

        return "\n".join(lines)


# ==============================================================================
# WorldBossActionDecider (Deterministic Battle Engine)
# ==============================================================================

class WorldBossActionDecider:
    """Deterministic combat decision engine for PokéMeow World Boss battles."""

    def __init__(self, danger_hp_percent: float = 40.0) -> None:
        self.danger_hp_percent: float = float(danger_hp_percent)
        self.current_boss_name: str = ""
        self.active_pokemon_name: str = ""
        self.strategy: WorldBossStrategy = DEFAULT_FALLBACK_STRATEGY
        self.turn_count: int = 0
        self.setup_complete: bool = False

    def reset(self) -> None:
        """Reset combat state between battles."""
        self.current_boss_name = ""
        self.active_pokemon_name = ""
        self.strategy = DEFAULT_FALLBACK_STRATEGY
        self.turn_count = 0
        self.setup_complete = False

    def update_context(self, boss_name: str, active_pokemon: str) -> None:
        if boss_name and boss_name != self.current_boss_name:
            self.current_boss_name = boss_name
            self.strategy = get_boss_strategy(boss_name)
            self.turn_count = 0
            self.setup_complete = False

        if active_pokemon:
            clean_active = active_pokemon.strip()
            if clean_active != self.active_pokemon_name:
                self.active_pokemon_name = clean_active
                self.turn_count = 0

    def decide_action(
        self,
        move_buttons: list[Any] | dict[str, Any],
        switch_buttons: list[Any] | dict[str, Any],
        ally_hp_percent: float | None = 100.0,
        is_baton_pass_prompt: bool = False,
    ) -> tuple[Any | None, str, str]:
        """Decide the single best action given current combat buttons and state.
        
        Returns: (button, action_name, reason)
        """
        # Sanitize ally HP percent to prevent NoneType comparison crashes
        if ally_hp_percent is None:
            safe_ally_hp = 100.0
        else:
            try:
                safe_ally_hp = float(ally_hp_percent)
            except (ValueError, TypeError):
                safe_ally_hp = 100.0

        danger_threshold = float(getattr(self, "danger_hp_percent", 40.0) or 40.0)

        # Ensure we are working with concrete lists of Button objects
        if isinstance(move_buttons, dict):
            move_buttons = list(move_buttons.values())
        else:
            move_buttons = list(move_buttons or [])

        if isinstance(switch_buttons, dict):
            switch_buttons = list(switch_buttons.values())
        else:
            switch_buttons = list(switch_buttons or [])

        # Filter out forfeit / cancel buttons completely so bot NEVER surrenders
        move_buttons = [
            b for b in move_buttons
            if not any(
                token in (str(getattr(b, "label", "") or "") + " " + str(getattr(b, "custom_id", "") or "")).lower()
                for token in ["forfeit", "cancel", "run", "surrender"]
            )
        ]

        def _matches(btn: Any, target_name: str) -> bool:
            lbl = str(getattr(btn, "label", "") or "").lower().replace("-", " ")
            cid = str(getattr(btn, "custom_id", "") or "").lower().replace("-", " ")
            tgt = str(target_name or "").lower().replace("-", " ").strip()
            if not tgt:
                return False
            clean_lbl = re.sub(r"[^\w\s]", " ", lbl).strip()
            clean_lbl = re.sub(r"\s+", " ", clean_lbl)
            if tgt in lbl or tgt in cid or tgt in clean_lbl:
                return True
            if len(clean_lbl) >= 4 and clean_lbl in tgt:
                return True
            return False

        # 1. Baton Pass switch prompt
        if is_baton_pass_prompt and switch_buttons:
            for sweeper_candidate in self.strategy.get_all_sweepers():
                for btn in switch_buttons:
                    if _matches(btn, sweeper_candidate):
                        return btn, f"Switch:{getattr(btn, 'label', '')}", f"baton_pass_sweeper_switch_{sweeper_candidate}"

            return switch_buttons[0], f"Switch:{getattr(switch_buttons[0], 'label', '')}", "baton_pass_fallback_switch"

        # 2. Emergency Healing if HP drops dangerously low
        if safe_ally_hp < danger_threshold and move_buttons:
            for em_name in (self.strategy.emergency_moves + ["Recover", "Roost", "Milk Drink", "Wish", "Draining Kiss"]):
                for btn in move_buttons:
                    if _matches(btn, em_name):
                        return btn, f"Emergency:{getattr(btn, 'label', '')}", "low_hp_emergency_heal"

        # 3. Sweeper in battle: Attack!
        all_sweepers = self.strategy.get_all_sweepers()
        active_clean = self.active_pokemon_name.lower().replace("-", " ")
        is_active_sweeper = any(
            (sw.lower().replace("-", " ") in active_clean or active_clean in sw.lower().replace("-", " "))
            for sw in all_sweepers
        )
        if is_active_sweeper:
            for atk_name in self.strategy.attack_moves:
                for btn in move_buttons:
                    if _matches(btn, atk_name):
                        return btn, f"Attack:{getattr(btn, 'label', '')}", "sweeper_nuke"

        # 4. Passer / Buffer in battle: Setup & Pass
        # Prioritize stat buffs over Baton Pass so passer actually buffs stats before passing!
        buff_moves = [m for m in self.strategy.setup_moves if m.lower() != "baton pass"]
        universal_setup = [
            "Superpower", "Topsy-Turvy", "Eerie Impulse", "Geomancy", "Calm Mind",
            "Cotton Guard", "Iron Defense", "Octolock", "Focus Energy", "Belly Drum",
            "Defense Curl", "Power Trick", "Coil", "Shift Gear", "Amnesia", "Agility"
        ]
        for u in universal_setup:
            if u not in buff_moves:
                buff_moves.append(u)

        for setup_move in buff_moves:
            for btn in move_buttons:
                if _matches(btn, setup_move):
                    self.turn_count += 1
                    return btn, f"Setup:{getattr(btn, 'label', '')}", "stat_buff_sequence"

        # Baton pass when stat buffs are finished (or if no other setup move is present)
        for btn in move_buttons:
            if _matches(btn, "Baton Pass"):
                self.turn_count += 1
                return btn, f"Setup:{getattr(btn, 'label', '')}", "baton_pass_transfer"

        # 5. Attack moves fallback (if setup moves exhausted or non-sweeper has attack)
        for atk_name in self.strategy.attack_moves:
            for btn in move_buttons:
                if _matches(btn, atk_name):
                    return btn, f"Attack:{getattr(btn, 'label', '')}", "fallback_attack"

        # 6. Fallback move (first valid non-forfeit move)
        if move_buttons:
            return move_buttons[0], f"Move:{getattr(move_buttons[0], 'label', '')}", "first_available_move"

        # 7. Fallback switch if no moves available
        if switch_buttons:
            return switch_buttons[0], f"Switch:{getattr(switch_buttons[0], 'label', '')}", "first_available_switch"

        return None, "no_action", "no_viable_buttons"
