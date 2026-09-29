from __future__ import annotations

import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from modules.worldboss_strategies import (
    WORLD_BOSS_STRATEGIES,
    WorldBossActionDecider,
    get_boss_strategy,
)


class DummyButton:
    def __init__(self, label: str, custom_id: str, disabled: bool = False):
        self.label = label
        self.custom_id = custom_id
        self.disabled = disabled


class TestWorldBoss(unittest.TestCase):
    def test_catalog_and_lookup(self):
        self.assertGreaterEqual(len(WORLD_BOSS_STRATEGIES), 30)
        strat = get_boss_strategy("Gigantamax-Venusaur")
        self.assertIsNotNone(strat)
        self.assertEqual(strat.archetype, "stored_power")
        self.assertEqual(strat.sweeper, "Mega Gardevoir")

        shuckle_strat = get_boss_strategy("Gigantamax-Charizard")
        self.assertIsNotNone(shuckle_strat)
        self.assertEqual(shuckle_strat.archetype, "shuckle_rollout")

    def test_stored_power_decider_flow(self):
        decider = WorldBossActionDecider()
        decider.update_context("Gigantamax-Venusaur", "Smeargle")

        moves = [
            DummyButton("Eerie Impulse", "move:1"),
            DummyButton("Geomancy", "move:2"),
            DummyButton("Octolock", "move:3"),
            DummyButton("Baton Pass", "move:4"),
        ]
        switches = [
            DummyButton("Mega Gardevoir", "switch:gardevoir"),
            DummyButton("Swoobat", "switch:swoobat"),
        ]

        btn, action, reason = decider.decide_action(moves, switches, ally_hp_percent=100.0)
        self.assertIsNotNone(btn)
        self.assertIn("Eerie Impulse", action)

        milk_drink_moves = [
            DummyButton("Milk Drink", "move:heal"),
            DummyButton("Shift Gear", "move:1"),
        ]
        btn_heal, action_heal, _ = decider.decide_action(milk_drink_moves, switches, ally_hp_percent=25.0)
        self.assertIsNotNone(btn_heal)
        self.assertEqual(btn_heal.label, "Milk Drink")

    def test_baton_pass_prompt_selection(self):
        decider = WorldBossActionDecider()
        decider.update_context("Gigantamax-Venusaur", "Smeargle")

        switches = [
            DummyButton("Mega Gardevoir", "switch:gardevoir"),
            DummyButton("Swoobat", "switch:swoobat"),
        ]
        btn, action, _ = decider.decide_action([], switches, is_baton_pass_prompt=True)
        self.assertIsNotNone(btn)
        self.assertEqual(btn.label, "Mega Gardevoir")

    def test_decider_danger_hp_and_reset(self):
        # Verify WorldBossActionDecider accepts danger_hp_percent keyword
        decider = WorldBossActionDecider(danger_hp_percent=50.0)
        self.assertEqual(decider.danger_hp_percent, 50.0)

        decider.update_context("Gigantamax-Venusaur", "Smeargle")
        self.assertEqual(decider.current_boss_name, "Gigantamax-Venusaur")

        # Test reset
        decider.reset()
        self.assertEqual(decider.current_boss_name, "")
        self.assertEqual(decider.active_pokemon_name, "")


if __name__ == "__main__":
    unittest.main()
