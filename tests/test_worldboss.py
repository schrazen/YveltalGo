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

    def test_estimator_adaptive_intervals_and_probing(self):
        import time
        from modules.worldboss_estimator import WorldBossEstimator, parse_future_boss_seconds

        # 1. Test future countdown parser
        self.assertEqual(parse_future_boss_seconds("Next world boss in approx. 1 hour and 30 minutes"), 5400)
        self.assertEqual(parse_future_boss_seconds("Next world boss appears in: 45m 10s"), 2710)
        self.assertIsNone(parse_future_boss_seconds("Registration is open for World Boss"))

        # 2. Test estimator intervals and stages with in-memory temp file
        temp_history = BASE_DIR / "data" / "test_wb_history_temp.json"
        if temp_history.exists():
            temp_history.unlink()

        try:
            est = WorldBossEstimator(history_file=temp_history)
            now = time.time()

            # Initial stage without data
            should_init, reason_init = est.should_probe(now)
            self.assertTrue(should_init)
            self.assertIn("Initial discovery", reason_init)

            # Record two past spawns spaced 2 hours (7200s) apart
            est.spawn_timestamps = [now - 14400.0, now - 7200.0]
            est.last_spawn_time = now - 7200.0
            est._recalculate_interval()
            self.assertAlmostEqual(est.learned_interval, 7200.0, delta=10.0)

            # 3. Test Cooldown Stage (just after spawn/fight)
            # T = now - 6000 (1200s elapsed < 4320s cooldown period)
            should_cooldown, reason_cooldown = est.should_probe(now - 6000.0)
            self.assertFalse(should_cooldown)
            self.assertIn("cooldown", reason_cooldown.lower())

            # 4. Test Vigilance Stage (near expected spawn)
            # T = now (7200s elapsed)
            est.last_probe_time = now - 700.0  # Probe was > 10m ago
            should_vig, reason_vig = est.should_probe(now)
            self.assertTrue(should_vig)
            self.assertIn("Vigilance", reason_vig)

            # 5. Test Rate-limit Cooldown (just probed 60s ago)
            est.last_probe_time = now - 60.0
            should_rate, reason_rate = est.should_probe(now)
            self.assertFalse(should_rate)
            self.assertIn("Rate-limit", reason_rate)

            # 6. Test Explicit Target Countdown
            est.record_explicit_countdown(600)  # 10 minutes away
            should_wait, _ = est.should_probe(now + 100)
            self.assertFalse(should_wait)

            # Reached target (within 45s of target)
            should_target, reason_target = est.should_probe(now + 560)
            self.assertTrue(should_target)
            self.assertIn("Explicit target", reason_target)

            # 7. Test Status Summary
            summary = est.get_status_summary(now)
            self.assertIn("Stage:", summary)
            self.assertIn("Interval:", summary)
        finally:
            if temp_history.exists():
                temp_history.unlink()

    def test_estimator_vote_parsing_and_pacing(self):
        import time
        from modules.worldboss_estimator import (
            WorldBossEstimator,
            parse_last_defeated_seconds,
            parse_vote_progress,
        )

        sample_wb_response = (
            "❌ There is no active World Boss\n"
            "The World Boss spawns once the vote threshold has been met, or if a player activates a :boss_coin: Boss Coin from ;patreon shop.\n\n"
            "World Boss spawns\n"
            "📮 Spawn requirement: 232 / 250 ;votes\n"
            ":7244: Eternamax-Eternatus spawn: 6,826 / 10,000 ;votes\n\n"
            "World Boss Highscores & Stats\n"
            "🏆 World Boss highscores: ;worldboss highscores\n"
            "📊 View World Boss stats: ;worldboss stats\n\n"
            "⚔️ A World Boss was last defeated 38 minutes ago\n"
            ":world_boss: Spawned by: :pokemeow: [STAFF] :lady: dovahluft\n"
            "👑 Previous MVP: :mystery_trainer: goatwei using :528: :235: :7123: with 💥 819,352 DMG\n"
            "📝 Register for the World Boss in our Official Discord Server•Today at 06:15"
        )

        # 1. Parse vote progress
        votes = parse_vote_progress(sample_wb_response)
        self.assertIsNotNone(votes)
        self.assertEqual(votes, (232, 250))

        # Test another format / commas
        self.assertEqual(parse_vote_progress("Spawn requirement: 1,200 / 2,500 ;votes"), (1200, 2500))
        self.assertIsNone(parse_vote_progress("No votes mentioned here"))

        # 2. Parse last defeated time
        last_def = parse_last_defeated_seconds(sample_wb_response)
        self.assertEqual(last_def, 38 * 60)
        self.assertEqual(parse_last_defeated_seconds("A World Boss was last defeated 2 hours ago"), 7200)
        self.assertIsNone(parse_last_defeated_seconds("No defeat info"))

        # 3. Test Estimator vote pacing logic
        temp_history = BASE_DIR / "data" / "test_wb_votes_temp.json"
        if temp_history.exists():
            temp_history.unlink()

        try:
            est = WorldBossEstimator(history_file=temp_history)
            now = time.time()

            # Record sample 1: 201 votes at T-180s (3 mins ago)
            est.record_vote_status(201, 250)
            est.vote_samples = [(now - 180.0, 201)]

            # Record sample 2: 224 votes at T (now) -> 23 votes in 3 mins = 7.67 votes/min
            est.record_vote_status(224, 250)
            self.assertGreater(est.vote_velocity_per_min, 5.0)

            # Check ETA calculation: remaining votes = 26, velocity ~7.67 v/m -> ETA ~3.4 mins
            eta = est.get_estimated_minutes_to_spawn()
            self.assertLess(eta, 6.0)
            self.assertGreater(eta, 1.0)

            # Check dynamic stages:
            # When votes = 224 / 250 (26 needed <= 35) -> "Approaching"
            est.last_probe_time = now - 200.0  # Probed > 2.5m ago
            should_p, reason_p = est.should_probe(now)
            self.assertTrue(should_p)
            self.assertIn("Approaching spawn probe", reason_p)

            # When votes = 245 / 250 (5 needed <= 12) -> "Imminent"
            est.record_vote_status(245, 250)
            est.last_probe_time = now - 70.0  # Probed 70s ago
            should_imm, reason_imm = est.should_probe(now)
            self.assertTrue(should_imm)
            self.assertIn("Imminent spawn probe", reason_imm)
        finally:
            if temp_history.exists():
                temp_history.unlink()


if __name__ == "__main__":
    unittest.main()

