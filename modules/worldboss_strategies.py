from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class WorldBossStrategy:
    boss_name: str
    archetype: str  # 'stored_power', 'shuckle_rollout', 'power_trip', 'echoed_voice'
    sweeper: str
    passers: list[str] = field(default_factory=list)
    setup_moves: list[str] = field(default_factory=list)
    attack_moves: list[str] = field(default_factory=list)
    emergency_moves: list[str] = field(default_factory=list)
    recommended_items: dict[str, str] = field(default_factory=dict)
    notes: str = ""


# Master strategy dictionary covering all 34 Gigantamax World Bosses
WORLD_BOSS_STRATEGIES: dict[str, WorldBossStrategy] = {
    # Stored Power Cheese
    "venusaur": WorldBossStrategy(
        boss_name="Gigantamax-Venusaur",
        archetype="stored_power",
        sweeper="Mega Gardevoir",
        passers=["Smeargle", "Shiny Smeargle"],
        setup_moves=["Eerie Impulse", "Geomancy", "Focus Energy", "Octolock", "Coil", "Acupressure", "Baton Pass"],
        attack_moves=["Stored Power", "Draining Kiss"],
        emergency_moves=["Draining Kiss", "Milk Drink", "Recover"],
    ),
    "charizard": WorldBossStrategy(
        boss_name="Gigantamax-Charizard",
        archetype="shuckle_rollout",
        sweeper="Shuckle",
        passers=["Poliwrath", "Mew", "Vaporeon", "Gliscor"],
        setup_moves=["Captivate", "Amnesia", "Belly Drum", "Hone Claws", "Focus Energy", "Screech", "Defense Curl", "Power Trick", "Baton Pass"],
        attack_moves=["Rollout"],
        emergency_moves=["Milk Drink", "Recover"],
    ),
    "blastoise": WorldBossStrategy(
        boss_name="Gigantamax-Blastoise",
        archetype="stored_power",
        sweeper="Mega Gardevoir",
        passers=["Smeargle", "Shiny Smeargle"],
        setup_moves=["Eerie Impulse", "Geomancy", "Focus Energy", "Octolock", "Coil", "Acupressure", "Baton Pass"],
        attack_moves=["Stored Power", "Draining Kiss"],
        emergency_moves=["Draining Kiss"],
    ),
    "butterfree": WorldBossStrategy(
        boss_name="Gigantamax-Butterfree",
        archetype="shuckle_rollout",
        sweeper="Shuckle",
        passers=["Poliwrath", "Mew", "Vaporeon", "Gliscor"],
        setup_moves=["Captivate", "Amnesia", "Belly Drum", "Hone Claws", "Focus Energy", "Screech", "Defense Curl", "Power Trick", "Baton Pass"],
        attack_moves=["Rollout"],
        emergency_moves=[],
    ),
    "pikachu": WorldBossStrategy(
        boss_name="Gigantamax-Pikachu",
        archetype="stored_power",
        sweeper="Mega-Mewtwo-Y",
        passers=["Remoraid", "Jolteon", "Smeargle"],
        setup_moves=["Entrainment", "Captivate", "Fake Tears", "Focus Energy", "Substitute", "Role Play", "Baton Pass"],
        attack_moves=["Stored Power", "Psychic Terrain"],
        emergency_moves=[],
    ),
    "meowth": WorldBossStrategy(
        boss_name="Gigantamax-Meowth",
        archetype="stored_power",
        sweeper="Mega-Gardevoir",
        passers=["Smeargle", "Shiny Smeargle"],
        setup_moves=["Eerie Impulse", "Geomancy", "Octolock", "Coil", "Focus Energy", "Baton Pass"],
        attack_moves=["Stored Power", "Draining Kiss"],
        emergency_moves=["Draining Kiss"],
    ),
    "machamp": WorldBossStrategy(
        boss_name="Gigantamax-Machamp",
        archetype="stored_power",
        sweeper="Mega-Gardevoir",
        passers=["Smeargle", "Shiny Smeargle"],
        setup_moves=["Eerie Impulse", "Geomancy", "Octolock", "Coil", "Focus Energy", "Baton Pass"],
        attack_moves=["Stored Power", "Draining Kiss"],
        emergency_moves=["Draining Kiss"],
    ),
    "gengar": WorldBossStrategy(
        boss_name="Gigantamax-Gengar",
        archetype="power_trip",
        sweeper="Krookodile",
        passers=["Smeargle", "Shiny Smeargle"],
        setup_moves=["Shift Gear", "Coil", "Ingrain", "Amnesia", "Baton Pass"],
        attack_moves=["Power Trip", "Crunch", "Earthquake"],
        emergency_moves=[],
    ),
    "kingler": WorldBossStrategy(
        boss_name="Gigantamax-Kingler",
        archetype="stored_power",
        sweeper="Mega-Gardevoir",
        passers=["Smeargle", "Shiny Smeargle"],
        setup_moves=["Eerie Impulse", "Geomancy", "Octolock", "Coil", "Baton Pass"],
        attack_moves=["Stored Power", "Draining Kiss"],
        emergency_moves=["Draining Kiss"],
    ),
    "lapras": WorldBossStrategy(
        boss_name="Gigantamax-Lapras",
        archetype="shuckle_rollout",
        sweeper="Shuckle",
        passers=["Poliwrath", "Mew"],
        setup_moves=["Captivate", "Amnesia", "Belly Drum", "Defense Curl", "Power Trick", "Baton Pass"],
        attack_moves=["Rollout"],
        emergency_moves=[],
    ),
    "eevee": WorldBossStrategy(
        boss_name="Gigantamax-Eevee",
        archetype="stored_power",
        sweeper="Mega-Gardevoir",
        passers=["Smeargle", "Shiny Smeargle"],
        setup_moves=["Eerie Impulse", "Geomancy", "Octolock", "Coil", "Baton Pass"],
        attack_moves=["Stored Power", "Draining Kiss"],
        emergency_moves=["Draining Kiss"],
    ),
    "snorlax": WorldBossStrategy(
        boss_name="Gigantamax-Snorlax",
        archetype="shuckle_rollout",
        sweeper="Shuckle",
        passers=["Poliwrath", "Mew"],
        setup_moves=["Captivate", "Amnesia", "Belly Drum", "Defense Curl", "Power Trick", "Baton Pass"],
        attack_moves=["Rollout"],
        emergency_moves=[],
    ),
    "garbodor": WorldBossStrategy(
        boss_name="Gigantamax-Garbodor",
        archetype="stored_power",
        sweeper="Mega-Gardevoir",
        passers=["Smeargle", "Shiny Smeargle"],
        setup_moves=["Eerie Impulse", "Geomancy", "Octolock", "Coil", "Baton Pass"],
        attack_moves=["Stored Power", "Draining Kiss"],
        emergency_moves=["Draining Kiss"],
    ),
    "melmetal": WorldBossStrategy(
        boss_name="Gigantamax-Melmetal",
        archetype="stored_power",
        sweeper="Mega-Charizard-Y",
        passers=["Smeargle", "Shiny Smeargle"],
        setup_moves=["Geomancy", "Coil", "Baton Pass"],
        attack_moves=["Flamethrower", "Fire Blast", "Overheat"],
        emergency_moves=[],
    ),
    "corviknight": WorldBossStrategy(
        boss_name="Gigantamax-Corviknight",
        archetype="echoed_voice",
        sweeper="Sylveon",
        passers=["Smeargle", "Shiny Smeargle"],
        setup_moves=["Geomancy", "Shift Gear", "Baton Pass"],
        attack_moves=["Echoed Voice", "Hyper Voice"],
        emergency_moves=[],
    ),
    "orbeetle": WorldBossStrategy(
        boss_name="Gigantamax-Orbeetle",
        archetype="power_trip",
        sweeper="Krookodile",
        passers=["Smeargle", "Shiny Smeargle"],
        setup_moves=["Shift Gear", "Coil", "Baton Pass"],
        attack_moves=["Power Trip"],
        emergency_moves=[],
    ),
    "drednaw": WorldBossStrategy(
        boss_name="Gigantamax-Drednaw",
        archetype="stored_power",
        sweeper="Mega-Gardevoir",
        passers=["Smeargle", "Shiny Smeargle"],
        setup_moves=["Eerie Impulse", "Geomancy", "Octolock", "Coil", "Baton Pass"],
        attack_moves=["Stored Power", "Energy Ball"],
        emergency_moves=[],
    ),
    "coalossal": WorldBossStrategy(
        boss_name="Gigantamax-Coalossal",
        archetype="stored_power",
        sweeper="Mega-Blastoise",
        passers=["Smeargle", "Shiny Smeargle"],
        setup_moves=["Geomancy", "Octolock", "Coil", "Baton Pass"],
        attack_moves=["Water Pulse", "Hydro Cannon", "Stored Power"],
        emergency_moves=[],
    ),
    "flapple": WorldBossStrategy(
        boss_name="Gigantamax-Flapple",
        archetype="stored_power",
        sweeper="Mega-Gardevoir",
        passers=["Smeargle", "Shiny Smeargle"],
        setup_moves=["Eerie Impulse", "Geomancy", "Octolock", "Coil", "Baton Pass"],
        attack_moves=["Stored Power", "Moonblast", "Draining Kiss"],
        emergency_moves=["Draining Kiss"],
    ),
    "appletun": WorldBossStrategy(
        boss_name="Gigantamax-Appletun",
        archetype="stored_power",
        sweeper="Mega-Gardevoir",
        passers=["Smeargle", "Shiny Smeargle"],
        setup_moves=["Eerie Impulse", "Geomancy", "Octolock", "Coil", "Baton Pass"],
        attack_moves=["Stored Power", "Moonblast", "Draining Kiss"],
        emergency_moves=["Draining Kiss"],
    ),
    "sandaconda": WorldBossStrategy(
        boss_name="Gigantamax-Sandaconda",
        archetype="stored_power",
        sweeper="Mega-Gardevoir",
        passers=["Smeargle", "Shiny Smeargle"],
        setup_moves=["Eerie Impulse", "Geomancy", "Octolock", "Coil", "Baton Pass"],
        attack_moves=["Stored Power", "Energy Ball"],
        emergency_moves=[],
    ),
    "toxtricity": WorldBossStrategy(
        boss_name="Gigantamax-Toxtricity",
        archetype="stored_power",
        sweeper="Mega-Gardevoir",
        passers=["Smeargle", "Shiny Smeargle"],
        setup_moves=["Eerie Impulse", "Geomancy", "Octolock", "Coil", "Baton Pass"],
        attack_moves=["Stored Power", "Psychic"],
        emergency_moves=[],
    ),
    "centiskorch": WorldBossStrategy(
        boss_name="Gigantamax-Centiskorch",
        archetype="shuckle_rollout",
        sweeper="Shuckle",
        passers=["Poliwrath", "Mew"],
        setup_moves=["Captivate", "Amnesia", "Belly Drum", "Defense Curl", "Power Trick", "Baton Pass"],
        attack_moves=["Rollout"],
        emergency_moves=[],
    ),
    "hatterene": WorldBossStrategy(
        boss_name="Gigantamax-Hatterene",
        archetype="power_trip",
        sweeper="Krookodile",
        passers=["Smeargle", "Shiny Smeargle"],
        setup_moves=["Shift Gear", "Coil", "Baton Pass"],
        attack_moves=["Power Trip", "Crunch"],
        emergency_moves=[],
    ),
    "grimmsnarl": WorldBossStrategy(
        boss_name="Gigantamax-Grimmsnarl",
        archetype="stored_power",
        sweeper="Mega-Gardevoir",
        passers=["Smeargle", "Shiny Smeargle"],
        setup_moves=["Eerie Impulse", "Geomancy", "Octolock", "Coil", "Baton Pass"],
        attack_moves=["Stored Power", "Moonblast", "Draining Kiss"],
        emergency_moves=["Draining Kiss"],
    ),
    "alcremie": WorldBossStrategy(
        boss_name="Gigantamax-Alcremie",
        archetype="power_trip",
        sweeper="Krookodile",
        passers=["Smeargle", "Shiny Smeargle"],
        setup_moves=["Shift Gear", "Coil", "Baton Pass"],
        attack_moves=["Power Trip"],
        emergency_moves=[],
    ),
    "copperajah": WorldBossStrategy(
        boss_name="Gigantamax-Copperajah",
        archetype="stored_power",
        sweeper="Mega-Charizard-Y",
        passers=["Smeargle", "Shiny Smeargle"],
        setup_moves=["Geomancy", "Coil", "Baton Pass"],
        attack_moves=["Flamethrower", "Fire Blast"],
        emergency_moves=[],
    ),
    "duraludon": WorldBossStrategy(
        boss_name="Gigantamax-Duraludon",
        archetype="stored_power",
        sweeper="Mega-Charizard-Y",
        passers=["Smeargle", "Shiny Smeargle"],
        setup_moves=["Geomancy", "Coil", "Baton Pass"],
        attack_moves=["Flamethrower", "Earth Power"],
        emergency_moves=[],
    ),
    "eternatus": WorldBossStrategy(
        boss_name="Eternamax-Eternatus",
        archetype="stored_power",
        sweeper="Mega-Gardevoir",
        passers=["Smeargle", "Shiny Smeargle"],
        setup_moves=["Eerie Impulse", "Geomancy", "Octolock", "Coil", "Baton Pass"],
        attack_moves=["Stored Power", "Psychic"],
        emergency_moves=["Draining Kiss"],
    ),
    "urshifu single": WorldBossStrategy(
        boss_name="Gigantamax-Urshifu-Single",
        archetype="stored_power",
        sweeper="Mega-Gardevoir",
        passers=["Smeargle", "Shiny Smeargle"],
        setup_moves=["Eerie Impulse", "Geomancy", "Octolock", "Coil", "Baton Pass"],
        attack_moves=["Stored Power", "Moonblast"],
        emergency_moves=["Draining Kiss"],
    ),
    "urshifu rapid": WorldBossStrategy(
        boss_name="Gigantamax-Urshifu-Rapid",
        archetype="stored_power",
        sweeper="Mega-Gardevoir",
        passers=["Smeargle", "Shiny Smeargle"],
        setup_moves=["Eerie Impulse", "Geomancy", "Octolock", "Coil", "Baton Pass"],
        attack_moves=["Stored Power", "Moonblast", "Energy Ball"],
        emergency_moves=["Draining Kiss"],
    ),
}

DEFAULT_FALLBACK_STRATEGY = WorldBossStrategy(
    boss_name="Default-WorldBoss",
    archetype="stored_power",
    sweeper="Mega-Gardevoir",
    passers=["Smeargle", "Shiny Smeargle"],
    setup_moves=["Geomancy", "Shift Gear", "Coil", "Baton Pass"],
    attack_moves=["Stored Power", "Draining Kiss"],
    emergency_moves=["Draining Kiss", "Milk Drink", "Recover"],
)


def get_boss_strategy(boss_name: str) -> WorldBossStrategy:
    """Lookup World Boss strategy by loose or normalized name."""
    clean = re.sub(r"[^\w\s]", " ", (boss_name or "").lower()).strip()
    clean = re.sub(r"\b(gigantamax|gmax|eternamax)\b", "", clean).strip()

    for key, strat in WORLD_BOSS_STRATEGIES.items():
        if key in clean or clean in key:
            return strat

    return DEFAULT_FALLBACK_STRATEGY


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
        move_buttons: list[Any],
        switch_buttons: list[Any],
        ally_hp_percent: float = 100.0,
        is_baton_pass_prompt: bool = False,
    ) -> tuple[Any | None, str, str]:
        """Decide the single best action given current combat buttons and state.
        
        Returns: (button, action_name, reason)
        """
        # 1. Baton Pass switch prompt
        if is_baton_pass_prompt and switch_buttons:
            # Prefer designated sweeper first
            sweeper_clean = self.strategy.sweeper.lower().replace("-", " ")
            for btn in switch_buttons:
                label = str(getattr(btn, "label", "") or "").lower().replace("-", " ")
                if sweeper_clean in label or label in sweeper_clean:
                    return btn, f"Switch:{getattr(btn, 'label', '')}", "baton_pass_sweeper_switch"

            # Fallback to any available non-fainted switch
            return switch_buttons[0], f"Switch:{getattr(switch_buttons[0], 'label', '')}", "baton_pass_fallback_switch"

        # 2. Emergency Healing if HP drops dangerously low
        if ally_hp_percent < self.danger_hp_percent and move_buttons:
            for em_name in self.strategy.emergency_moves:
                em_clean = em_name.lower().replace("-", " ")
                for btn in move_buttons:
                    label = str(getattr(btn, "label", "") or "").lower().replace("-", " ")
                    if em_clean in label or label in em_clean:
                        return btn, f"Emergency:{getattr(btn, 'label', '')}", "low_hp_emergency_heal"

        # 3. Sweeper in battle: Attack!
        sweeper_clean = self.strategy.sweeper.lower().replace("-", " ")
        active_clean = self.active_pokemon_name.lower().replace("-", " ")
        if sweeper_clean in active_clean or active_clean in sweeper_clean:
            for atk_name in self.strategy.attack_moves:
                atk_clean = atk_name.lower().replace("-", " ")
                for btn in move_buttons:
                    label = str(getattr(btn, "label", "") or "").lower().replace("-", " ")
                    if atk_clean in label or label in atk_clean:
                        return btn, f"Attack:{getattr(btn, 'label', '')}", "sweeper_nuke"

            # If preferred attack not matched, use first available move
            if move_buttons:
                return move_buttons[0], f"Move:{getattr(move_buttons[0], 'label', '')}", "sweeper_fallback_move"

        # 4. Passer / Buffer in battle: Setup & Pass
        # Priority order: Setup moves in order
        for setup_move in self.strategy.setup_moves:
            s_clean = setup_move.lower().replace("-", " ")
            for btn in move_buttons:
                label = str(getattr(btn, "label", "") or "").lower().replace("-", " ")
                if s_clean in label or label in s_clean:
                    self.turn_count += 1
                    return btn, f"Setup:{getattr(btn, 'label', '')}", "stat_buff_sequence"

        # 5. Fallback move or switch if setup moves exhausted
        if move_buttons:
            return move_buttons[0], f"Move:{getattr(move_buttons[0], 'label', '')}", "first_available_move"

        if switch_buttons:
            return switch_buttons[0], f"Switch:{getattr(switch_buttons[0], 'label', '')}", "first_available_switch"

        return None, "no_action", "no_viable_buttons"

