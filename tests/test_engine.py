"""Unit tests for WarDeN engine, FSM, and storage (Member 1 deliverables)."""

from __future__ import annotations

import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.engine import (
    is_campaign_over,
    process_turn,
    roll_d20,
    start_campaign,
    use_consumable,
)
from src.fsm import CampaignFSM, InvalidStageTransitionError
from src.storage import (
    delete_campaign,
    list_saved_campaigns,
    load_campaign,
    save_campaign,
)


class TestStartCampaign(unittest.TestCase):
    def test_start_campaign_all_classes(self) -> None:
        for cls in ("Warrior", "Archer", "Mage"):
            state = start_campaign("Aria", cls, "Forest", max_turns=8)
            self.assertEqual(state.player.name, "Aria")
            self.assertEqual(state.player.character_class, cls)
            self.assertEqual(state.environment, "Forest")
            self.assertEqual(state.campaign_stage, "Introduction")
            self.assertEqual(state.turn_count, 0)
            self.assertEqual(state.max_turns, 8)
            self.assertFalse(state.is_game_over)
            self.assertEqual(state.outcome, "ongoing")

    def test_start_campaign_validates_bounds(self) -> None:
        with self.assertRaises(ValueError):
            start_campaign("   ", "Warrior", "Forest")
        with self.assertRaises(ValueError):
            start_campaign("Kael", "Warrior", "Forest", max_turns=5)
        with self.assertRaises(ValueError):
            start_campaign("Kael", "Warrior", "Forest", max_turns=12)


class TestDiceAndCombat(unittest.TestCase):
    def test_roll_d20_range_and_modifier(self) -> None:
        random.seed(42)
        for _ in range(50):
            raw, total = roll_d20(5)
            self.assertGreaterEqual(raw, 1)
            self.assertLessEqual(raw, 20)
            self.assertEqual(total, raw + 5)

    def test_combat_hit_and_defeat_advances_state(self) -> None:
        state = start_campaign("Garrick", "Warrior", "Mountains", max_turns=8)
        # Advance past Introduction
        state, _ = process_turn(state, "Survey the pass", "Exploration")
        self.assertEqual(state.campaign_stage, "Exploration")

        # Force natural 20 hits so player defeats enemy deterministically
        with patch("src.engine.random.randint", side_effect=[20, 6, 20, 6, 20, 6, 20, 6]):
            state, res1 = process_turn(state, "Strike the foe", "Combat")
            self.assertEqual(res1.action_category, "Combat")
            self.assertTrue(res1.success)
            self.assertGreater(res1.damage_dealt, 0)

            while state.active_enemy is not None and not is_campaign_over(state):
                state, _ = process_turn(state, "Finish it", "Combat")

        self.assertGreaterEqual(len(state.defeated_enemies), 1)
        self.assertIsNone(state.active_enemy)

    def test_player_defeat_ends_campaign(self) -> None:
        state = start_campaign("Lyra", "Mage", "Cave", max_turns=8)
        state.player.hp = 1
        # Player misses (roll=1), enemy rolls 20 and hits
        with patch("src.engine.random.randint", side_effect=[1, 20, 5]):
            state, res = process_turn(state, "Attack recklessly", "Combat")

        self.assertFalse(res.success)
        self.assertEqual(state.player.hp, 0)
        self.assertTrue(is_campaign_over(state))
        self.assertEqual(state.campaign_stage, "Conclusion")
        self.assertEqual(state.outcome, "defeat")


class TestConsumables(unittest.TestCase):
    def test_use_healing_potion_restores_hp_and_decrements_qty(self) -> None:
        state = start_campaign("Talia", "Warrior", "Forest", max_turns=8)
        state.player.hp = 15
        initial_qty = state.player.consumables[0].quantity

        state, res = use_consumable(state, "healing_potion")
        self.assertTrue(res.success)
        self.assertEqual(res.healing_done, 10)
        self.assertEqual(state.player.hp, 25)
        self.assertEqual(res.items_used, ["healing_potion"])
        self.assertEqual(state.player.consumables[0].quantity, initial_qty - 1)

    def test_use_missing_consumable_returns_failure(self) -> None:
        state = start_campaign("Talia", "Warrior", "Forest", max_turns=8)
        state, res = use_consumable(state, "nonexistent_elixir")
        self.assertFalse(res.success)
        self.assertEqual(res.healing_done, 0)


class TestFSMAndPacing(unittest.TestCase):
    def test_invalid_transition_raises(self) -> None:
        state = start_campaign("Rowan", "Archer", "Swamp", max_turns=6)
        with self.assertRaises(InvalidStageTransitionError):
            CampaignFSM.transition(state, "Main Encounter")

    def test_four_stage_progression_within_turn_cap(self) -> None:
        state = start_campaign("Rowan", "Archer", "Swamp", max_turns=6)
        stages_seen = [state.campaign_stage]

        with patch("src.engine.random.randint", return_value=15):
            while not is_campaign_over(state):
                if state.campaign_stage == "Main Encounter":
                    state, _ = process_turn(state, "Shoot the warden", "Combat")
                else:
                    state, _ = process_turn(state, "Move carefully", "Exploration")
                stages_seen.append(state.campaign_stage)

        self.assertIn("Introduction", stages_seen)
        self.assertIn("Exploration", stages_seen)
        self.assertIn("Main Encounter", stages_seen)
        self.assertEqual(stages_seen[-1], "Conclusion")
        self.assertLessEqual(state.turn_count, 6)
        self.assertTrue(is_campaign_over(state))


class TestStorage(unittest.TestCase):
    def test_save_load_list_and_delete(self) -> None:
        state = start_campaign("Bram", "Warrior", "Desert", max_turns=8)
        state, _ = process_turn(state, "Search the ruins", "Dialogue")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            saved_path = save_campaign(state, save_dir=tmp_dir)
            self.assertTrue(saved_path.exists())

            loaded = load_campaign(state.campaign_id, save_dir=tmp_dir)
            self.assertEqual(loaded, state)

            listings = list_saved_campaigns(save_dir=tmp_dir)
            self.assertEqual(len(listings), 1)
            self.assertEqual(listings[0]["campaign_id"], state.campaign_id)
            self.assertEqual(listings[0]["player_name"], "Bram")

            self.assertTrue(delete_campaign(state.campaign_id, save_dir=tmp_dir))
            self.assertFalse(delete_campaign(state.campaign_id, save_dir=tmp_dir))
            self.assertEqual(list_saved_campaigns(save_dir=tmp_dir), [])


if __name__ == "__main__":
    unittest.main()
