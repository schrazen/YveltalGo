from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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

    def test_mega_mewtwo_y_cheese_combos_and_decider(self):
        from modules.worldboss_strategies import (
            MEW_TWO_Y_CHEESE_COMBOS,
            WorldBossActionDecider,
            get_boss_strategy,
        )

        # 1. Verify Mega Mewtwo Y combo presets
        self.assertIn("double_pass_meta", MEW_TWO_Y_CHEESE_COMBOS)
        self.assertIn("volt_absorb_electric_pass", MEW_TWO_Y_CHEESE_COMBOS)
        self.assertIn("psychic_terrain_expanding", MEW_TWO_Y_CHEESE_COMBOS)
        self.assertIn("solo_mmy_self_setup", MEW_TWO_Y_CHEESE_COMBOS)

        meta_combo = MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"]
        self.assertEqual(meta_combo.slots, ["Swoobat", "Smeargle", "Mega-Mewtwo-Y"])
        self.assertEqual(meta_combo.held_items["Mega-Mewtwo-Y"], "Twisted Spoon")

        # 2. Test Decider recognizing Mega Mewtwo Y as sweeper
        decider = WorldBossActionDecider()
        decider.update_context("Gigantamax-Pikachu", "Mega-Mewtwo-Y")

        moves = [
            DummyButton("Stored Power", "move:1"),
            DummyButton("Psychic Terrain", "move:2"),
            DummyButton("Aura Sphere", "move:3"),
            DummyButton("Recover", "move:4"),
        ]
        switches = [
            DummyButton("Swoobat", "switch:swoobat"),
            DummyButton("Smeargle", "switch:smeargle"),
        ]

        # In battle as Mega Mewtwo Y -> executes Stored Power
        btn, action, reason = decider.decide_action(moves, switches)
        self.assertIsNotNone(btn)
        self.assertEqual(btn.label, "Stored Power")
        self.assertEqual(reason, "sweeper_nuke")

        # Baton pass switch prompt -> prefers Mega Mewtwo Y even on Venusaur
        decider.update_context("Gigantamax-Venusaur", "Smeargle")
        bp_switches = [
            DummyButton("Swoobat", "switch:swoobat"),
            DummyButton("Mega-Mewtwo-Y", "switch:mmy"),
        ]
        btn_bp, action_bp, _ = decider.decide_action([], bp_switches, is_baton_pass_prompt=True)
        self.assertIsNotNone(btn_bp)
        self.assertEqual(btn_bp.label, "Mega-Mewtwo-Y")

    def test_worldboss_team_builder_and_commands(self):
        from modules.worldboss_strategies import (
            MEW_TWO_Y_CHEESE_COMBOS,
            WorldBossTeamBuilder,
        )

        # 1. Presets retrieval
        presets = WorldBossTeamBuilder.get_presets_for_boss("Gigantamax-Pikachu")
        self.assertGreaterEqual(len(presets), 1)

        # 2. Team recommendations: Full inventory
        rec_preset, reason = WorldBossTeamBuilder.recommend_team(
            "Gigantamax-Pikachu",
            owned_pokemon=["Jolteon", "Smeargle", "Mega-Mewtwo-Y"],
        )
        self.assertIn("Jolteon", rec_preset.slots)
        self.assertIn("Mega-Mewtwo-Y", rec_preset.slots)

        # 3. Hybrid recommendation: Player only has Swoobat + Mega Mewtwo Y (no Smeargle)
        hybrid_preset, hybrid_reason = WorldBossTeamBuilder.recommend_team(
            "Gigantamax-Venusaur",
            owned_pokemon=["Swoobat", "Mega-Mewtwo-Y"],
        )
        self.assertIn("Swoobat", hybrid_preset.slots)
        self.assertIn("Mega-Mewtwo-Y", hybrid_preset.slots)
        self.assertEqual(hybrid_preset.archetype, "stored_power")

        # 4. Command Generation
        cmds = WorldBossTeamBuilder.generate_pokemeow_commands(MEW_TWO_Y_CHEESE_COMBOS["double_pass_meta"])
        self.assertTrue(any(";team add" in c for c in cmds))
        self.assertIn(";team add Swoobat 1", cmds)
        self.assertTrue(any("Mega-Mewtwo-Y" in c or "mega Mewtwo Y" in c for c in cmds))
        self.assertIn(";item hold Twisted Spoon Mewtwo-Y", cmds)

        # 5. Formatted Guide text
        guide = WorldBossTeamBuilder.format_team_guide("Gigantamax-Pikachu")
        self.assertIn("World Boss Comp Guide", guide)
        self.assertIn(";team add", guide)

    def test_kingler_live_battle_scenario_with_dict_and_emojis(self):
        from modules.battle_state import _extract_active_pokemon
        from modules.worldboss_strategies import WorldBossActionDecider

        raw_embed_text = (
            "Gigantamax-Kingler Challenge\n"
            "Kingler: 10,000,000 / 10,000,000 HP\n"
            "Reward potential: [0/5]\n"
            "20,000 DMG until next threshold\n\n"
            "Kingler stares intensely at you...\n\n"
            "⚔️ Yashi's Team\n"
            "Mew 454 / 454 • 💥 DMG: 0\n"
            "Malamar 415 / 415 🥦 • 💥 DMG: 0\n"
            "Mega Mewtwo Y 407 / 407 🪨 • 💥 DMG: 0\n\n"
            "Gigantamax-Kingler\n"
            "Players in battle: 24 • Your total DMG dealt: 0\n"
            "Kingler health: 10,000,000 / 10,000,000 HP\n"
        )
        known_team = ["Mega Mewtwo Y", "Mega-Mewtwo-Y", "Mew", "Malamar", "Smeargle"]

        # 1. Verify active pokemon is extracted as Mew (NOT Mega Mewtwo Y)
        active = _extract_active_pokemon(raw_embed_text, known_team)
        self.assertEqual(active, "Mew")

        # 2. Simulate dictionary of buttons as returned by parse_battle_state
        buttons_dict = {
            "⚡ eerie impulse": DummyButton("⚡ Eerie impulse", "move:eerie"),
            "focus energy": DummyButton("Focus energy", "move:focus"),
            "roost": DummyButton("Roost", "move:roost"),
            "baton pass": DummyButton("Baton pass", "move:bp"),
            "forfeit": DummyButton("Forfeit", "util:forfeit"),
            "heal": DummyButton("Heal", "util:heal"),
        }
        switches_dict = {
            "malamar": DummyButton("Malamar", "switch:malamar"),
            "mega mewtwo y": DummyButton("Mega Mewtwo Y", "switch:mmy"),
        }

        decider = WorldBossActionDecider()
        decider.update_context("Gigantamax-Kingler", active)

        # 3. Decide action with dictionary input: should pick Eerie impulse (setup move)
        btn, action, reason = decider.decide_action(
            move_buttons=buttons_dict,
            switch_buttons=switches_dict,
            ally_hp_percent=100.0,
        )
        self.assertIsNotNone(btn)
        self.assertEqual(btn.label, "⚡ Eerie impulse")
        self.assertEqual(reason, "stat_buff_sequence")

        # 4. Low HP emergency: should pick Roost
        btn_heal, action_heal, reason_heal = decider.decide_action(
            move_buttons=buttons_dict,
            switch_buttons=switches_dict,
            ally_hp_percent=20.0,
        )
        self.assertIsNotNone(btn_heal)
        self.assertEqual(btn_heal.label, "Roost")
        self.assertEqual(reason_heal, "low_hp_emergency_heal")

        # 5. Baton pass prompt: should pick Mega Mewtwo Y
        btn_bp, action_bp, reason_bp = decider.decide_action(
            move_buttons=buttons_dict,
            switch_buttons=switches_dict,
            is_baton_pass_prompt=True,
        )
        self.assertIsNotNone(btn_bp)
        self.assertEqual(btn_bp.label, "Mega Mewtwo Y")

    def test_embed_vote_and_eternamax_and_defeat_parsing(self):
        from modules.worldboss_estimator import (
            parse_eternamax_progress,
            parse_last_defeated_seconds,
            parse_vote_progress,
        )
        from modules.battle_state import normalize

        # Real message log from user
        raw_log = """
        ❌ There is no active World Boss
        The World Boss spawns once the vote threshold has been met, or if a player activates a :boss_coin: Boss Coin from ;patreon shop.

        World Boss spawns
        📮 Spawn requirement: 201 / 250 ;votes
        :7244: Eternamax-Eternatus spawn: 6,795 / 10,000 ;votes

        World Boss Highscores & Stats
        🏆 World Boss highscores: ;worldboss highscores
        📊 View World Boss stats: ;worldboss stats

        ⚔️ A World Boss was last defeated 37 minutes ago
        :world_boss: Spawned by: :pokemeow: [STAFF] :lady: dovahluft
        👑 Previous MVP: :mystery_trainer: goatwei using :528: :235: :7123: with 💥 819,352 DMG
        📝 Register for the World Boss in our Official Discord Server•Today at 06:09
        """
        blob = normalize(raw_log)

        # 1. Normal vote progress
        votes = parse_vote_progress(blob)
        self.assertIsNotNone(votes)
        self.assertEqual(votes, (201, 250))

        # 2. Eternamax progress
        et_votes = parse_eternamax_progress(blob)
        self.assertIsNotNone(et_votes)
        self.assertEqual(et_votes, (6795, 10000))

        # 3. Last defeated seconds (37 minutes = 2220 seconds)
        last_def = parse_last_defeated_seconds(blob)
        self.assertEqual(last_def, 2220)

        # 4. Multi-format last defeated
        self.assertEqual(parse_last_defeated_seconds("last defeated 1 hour ago"), 3600)
        self.assertEqual(parse_last_defeated_seconds("last defeated 1 hour and 15 mins ago"), 4500)
        self.assertEqual(parse_last_defeated_seconds("last defeated 45 seconds ago"), 45)

    def test_collect_all_text_with_mock_embed(self):
        from unittest.mock import MagicMock
        from cogs.worldboss import WorldBoss
        from modules.battle_state import normalize
        from modules.worldboss_estimator import parse_vote_progress

        msg = MagicMock()
        msg.content = ";wb"
        embed = MagicMock()
        embed.title = "❌ There is no active World Boss"
        embed.description = "The World Boss spawns once vote threshold has been met."
        embed.author = None

        field0 = MagicMock()
        field0.name = "World Boss spawns"
        field0.value = "📮 Spawn requirement: 238 / 250 ;votes"

        footer = MagicMock()
        footer.text = "Register for the World Boss in our Official Discord Server"
        embed.footer = footer
        embed.fields = [field0]
        msg.embeds = [embed]

        collected = WorldBoss._collect_all_text(msg)
        blob = normalize(collected)

        self.assertIn("spawn requirement: 238 / 250 ;votes", blob)
        self.assertEqual(parse_vote_progress(blob), (238, 250))

    def test_presets_api_endpoint(self):
        from ui.server import app

        client = app.test_client()
        resp = client.get("/api/worldboss/presets?boss=Gigantamax-Pikachu")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("ok"))
        self.assertEqual(data.get("target_boss"), "Gigantamax-Pikachu")
        self.assertIn("recommended", data)
        self.assertIn("slots", data["recommended"])
        self.assertGreaterEqual(len(data["recommended"]["slots"]), 1)
        self.assertIn("commands", data["recommended"])
        self.assertGreaterEqual(len(data["known_bosses"]), 10)

    def test_dynamic_team_extraction_and_malamar(self):
        from modules.battle_state import extract_team_members, parse_battle_state
        from modules.worldboss_strategies import (
            MEW_TWO_Y_CHEESE_COMBOS,
            WorldBossActionDecider,
        )
        from unittest.mock import MagicMock

        # 1. Verify contrary_superpower_malamar in combos
        self.assertIn("contrary_superpower_malamar", MEW_TWO_Y_CHEESE_COMBOS)
        malamar_preset = MEW_TWO_Y_CHEESE_COMBOS["contrary_superpower_malamar"]
        self.assertIn("Malamar", malamar_preset.slots)
        self.assertIn("Superpower", malamar_preset.recommended_moves["Malamar"])

        # 2. Test dynamic extraction from real battle text
        battle_embed_text = (
            "Gigantamax-Kingler Challenge\n"
            "Kingler: 9,800,000 / 10,000,000 HP\n\n"
            "⚔️ Yashi's Team\n"
            "Mew 0 / 454 • 💥 DMG: 0\n"
            "Malamar 415 / 415 🥦 • 💥 DMG: 0\n"
            "Mega Mewtwo Y 407 / 407 🪨 • 💥 DMG: 0\n\n"
            "Gigantamax-Kingler\n"
            "Players in battle: 24\n"
        )
        team = extract_team_members(battle_embed_text)
        self.assertEqual(len(team), 3)
        self.assertEqual(team[0], ("Mew", 0, 454))
        self.assertEqual(team[1], ("Malamar", 415, 415))
        self.assertEqual(team[2], ("Mega Mewtwo Y", 407, 407))

        # 3. Test parse_battle_state with mock message
        msg = MagicMock()
        msg.content = ""
        embed = MagicMock()
        embed.title = "Gigantamax-Kingler Challenge"
        embed.description = battle_embed_text
        embed.author = None
        embed.footer = None
        embed.fields = []
        msg.embeds = [embed]
        msg.components = []

        state = parse_battle_state(msg, ["Mega Mewtwo Y", "Mew"])
        self.assertEqual(state.active_pokemon, "Malamar")
        self.assertEqual(state.ally_hp_percent, 100)

        # 4. Decider with Malamar in battle
        decider = WorldBossActionDecider()
        decider.update_context("Gigantamax-Kingler", "Malamar")
        moves = [
            DummyButton("Superpower", "move:sp"),
            DummyButton("Topsy-Turvy", "move:tt"),
            DummyButton("Baton Pass", "move:bp"),
        ]
        btn, action, reason = decider.decide_action(moves, [])
        self.assertIsNotNone(btn)
        self.assertEqual(btn.label, "Superpower")
        self.assertEqual(reason, "stat_buff_sequence")

    def test_daily_limit_notice_text_command(self):
        from unittest.mock import MagicMock
        from time import time
        from cogs.hunting import Hunting

        bot = MagicMock()
        bot.user.id = 871274613227798589
        bot.user.name = "schrazen"
        bot.last_hunt = time() - 2.0
        config = MagicMock()
        config.hunting_channel_id = 1213138761370574858
        bot.config = config

        hunting_cog = Hunting(bot)

        # Mock PokéMeow response to text command ';p'
        msg = MagicMock()
        msg.author.id = 664508672713424926
        msg.channel.id = 1213138761370574858
        msg.interaction = None
        msg.content = ""

        embed = MagicMock()
        embed.title = "🙀 Uh oh! You have reached the daily catch limit!"
        embed.description = (
            "Support our Patreon to remove this limit!\n\n"
            "**Your daily encounter limit**: 500 encounters.\n"
            "Your limit will reset on <t:1790740800:f>"
        )
        embed.footer = None
        embed.fields = []
        msg.embeds = [embed]

        is_limit = hunting_cog._is_daily_limit_notice(msg)
        self.assertTrue(is_limit)

    def test_server_guard_isolation_and_firewall(self):
        from modules.server_guard import (
            extract_guild_id,
            is_server_allowed,
            is_message_in_required_server,
            install_server_firewall,
        )

        bot = MagicMock()
        bot.required_server_id = 873791689939107861

        # Correct server message
        msg_correct = MagicMock()
        msg_correct.guild.id = 873791689939107861
        self.assertTrue(is_server_allowed(bot, msg_correct))
        self.assertTrue(is_message_in_required_server(bot, msg_correct))

        # Foreign server message
        msg_foreign = MagicMock()
        msg_foreign.guild.id = 999999999999999999
        self.assertFalse(is_server_allowed(bot, msg_foreign))
        self.assertFalse(is_message_in_required_server(bot, msg_foreign))

        # DM message (no guild)
        msg_dm = MagicMock()
        msg_dm.guild = None
        msg_dm.guild_id = None
        self.assertFalse(is_server_allowed(bot, msg_dm))

        # Test HTTP client firewall interception
        bot.http = MagicMock()
        bot.http.send_message = AsyncMock(return_value="sent")
        bot.http.interact = AsyncMock(return_value="interacted")

        # Mock channels in bot cache
        ch_foreign = MagicMock()
        ch_foreign.guild.id = 999999999999999999
        ch_authorized = MagicMock()
        ch_authorized.guild.id = 873791689939107861

        def get_channel_side_effect(cid):
            if cid == 1395794939161477230:
                return ch_foreign
            return ch_authorized

        bot.get_channel.side_effect = get_channel_side_effect

        install_server_firewall(bot)

        # Sending to foreign channel must be blocked and return None
        res_blocked = asyncio.run(bot.http.send_message(1395794939161477230, params=None))
        self.assertIsNone(res_blocked)

    def test_worldboss_ignores_foreign_server_and_no_active_boss(self):
        from cogs.worldboss import WorldBoss

        bot = MagicMock()
        bot.required_server_id = 873791689939107861
        bot.world_boss_active = False
        bot.pause_hunting = False
        bot.pause_fishing = False
        bot.log = AsyncMock()

        config = MagicMock()
        config.world_boss_channel_id = 1488006398255300658
        config.world_boss_enabled = True
        config.wb_danger_hp_percent = 40
        config.wb_dry_run = False
        config.world_boss_team_preset = "wb"
        bot.config = config

        wb_cog = WorldBoss(bot)

        # 1. Message from foreign server or wrong channel must be ignored
        foreign_msg = MagicMock()
        foreign_msg.guild.id = 1395794939161477230  # Wrong server!
        foreign_msg.channel.id = 1395794939161477230  # Wrong channel!
        foreign_msg.content = ";wb"
        foreign_msg.channel.send = AsyncMock()

        asyncio.run(wb_cog._handle_candidate_message(foreign_msg))
        foreign_msg.channel.send.assert_not_called()

        # 2. PokéMeow message: "❌ There is no active World Boss"
        auth_msg = MagicMock()
        auth_msg.guild.id = 873791689939107861  # Correct server
        auth_msg.channel.id = 1488006398255300658  # Correct channel
        auth_msg.author.id = 664508672713424926
        auth_msg.components = []
        auth_msg.content = ""
        auth_msg.channel.send = AsyncMock()

        embed = MagicMock()
        embed.title = "❌ There is no active World Boss"
        embed.description = (
            "The World Boss spawns once the vote threshold has been met.\n\n"
            "World Boss spawns\n"
            "📮 Spawn requirement: 62 / 250 ;votes\n"
            ":7244: Eternamax-Eternatus spawn: 8,406 / 10,000 ;votes\n\n"
            "⚔️ A World Boss was last defeated 13 minutes ago"
        )
        embed.footer.text = "Register for the World Boss in our Official Discord Server"
        embed.fields = []
        embed.author.name = "PokéMeow"
        auth_msg.embeds = [embed]

        asyncio.run(wb_cog._handle_candidate_message(auth_msg))

        # Votes must be accurately recorded
        self.assertEqual(wb_cog.estimator.current_votes, 62)
        self.assertEqual(wb_cog.estimator.target_votes, 250)
        # Must NOT send ;wb fight
        auth_msg.channel.send.assert_not_called()
        # World boss active must remain False
        self.assertFalse(bot.world_boss_active)


if __name__ == "__main__":
    unittest.main()

