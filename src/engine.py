"""Deterministic backend game engine for WarDeN."""

from __future__ import annotations

import json
import random
import re
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.fsm import CampaignFSM
from src.models import (
    ActionCategory,
    CampaignState,
    CharacterClass,
    CharacterSheet,
    Enemy,
    EngineResult,
    EnvironmentName,
    Item,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@lru_cache(maxsize=1)
def _load_classes_data() -> dict[str, dict[str, Any]]:
    return json.loads((DATA_DIR / "classes.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _load_enemies_data() -> list[dict[str, Any]]:
    return json.loads((DATA_DIR / "enemies.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _load_items_data() -> dict[str, dict[str, Any]]:
    items_list = json.loads((DATA_DIR / "items.json").read_text(encoding="utf-8"))
    return {item["id"]: item for item in items_list}


@lru_cache(maxsize=1)
def _load_environments_data() -> list[dict[str, Any]]:
    return json.loads((DATA_DIR / "environments.json").read_text(encoding="utf-8"))


def _effective_attack(player: CharacterSheet) -> int:
    bonus = sum(
        gear.attack_bonus
        for gear in (player.weapon, player.armor, player.accessory)
        if gear is not None
    )
    return player.attack + bonus


def _effective_defense(player: CharacterSheet) -> int:
    bonus = sum(
        gear.defense_bonus
        for gear in (player.weapon, player.armor, player.accessory)
        if gear is not None
    )
    return player.defense + bonus


def _effective_magic(player: CharacterSheet) -> int:
    bonus = sum(
        gear.magic_bonus
        for gear in (player.weapon, player.armor, player.accessory)
        if gear is not None
    )
    return player.magic + bonus


def _spawn_enemy(defeated_ids: list[str], prefer_boss: bool = False) -> Enemy:
    """Create a fresh Enemy instance from static enemies.json."""
    enemies = _load_enemies_data()
    if prefer_boss:
        for entry in enemies:
            if entry["id"] == "ashen_warden":
                return Enemy.model_validate(entry)

    candidates = [e for e in enemies if e["id"] not in defeated_ids and e["id"] != "ashen_warden"]
    if not candidates:
        candidates = [e for e in enemies if e["id"] not in defeated_ids] or enemies
    chosen = random.choice(candidates)
    return Enemy.model_validate(chosen)


def _find_consumable(player: CharacterSheet, query: str) -> Item | None:
    """Find a consumable by exact ID or case-insensitive substring match."""
    q = query.strip().lower()
    for item in player.consumables:
        if item.id.lower() == q or item.name.lower() == q:
            return item
    for item in player.consumables:
        if q in item.id.lower() or q in item.name.lower():
            return item
    return None


def _finalize_turn(
    state: CampaignState,
    enemy_just_defeated: bool = False,
) -> CampaignState:
    """Advance FSM stage, spawn Main Encounter enemy if entering, and set end flags."""
    next_stage = CampaignFSM.evaluate_next_stage(state)
    state.campaign_stage = next_stage

    if next_stage == "Main Encounter" and state.active_enemy is None:
        state.active_enemy = _spawn_enemy(state.defeated_enemies, prefer_boss=True)

    if state.player.hp <= 0:
        state.campaign_stage = "Conclusion"
        state.is_game_over = True
        state.outcome = "defeat"
    elif state.campaign_stage == "Conclusion":
        state.is_game_over = True
        if state.active_enemy is None and (enemy_just_defeated or len(state.defeated_enemies) > 0):
            state.outcome = "victory"
        elif state.active_enemy is not None:
            state.outcome = "defeat"
        else:
            state.outcome = "victory"

    return state


def start_campaign(
    player_name: str,
    character_class: CharacterClass,
    environment: EnvironmentName,
    max_turns: int = 8,
) -> CampaignState:
    """Initialize a new CampaignState from static class and environment presets."""
    clean_name = player_name.strip()
    if not clean_name:
        raise ValueError("player_name must not be empty.")
    if not (6 <= max_turns <= 11):
        raise ValueError("max_turns must be between 6 and 11.")

    classes = _load_classes_data()
    if character_class not in classes:
        raise ValueError(f"Unknown character_class: {character_class}")

    valid_envs = {env["name"] for env in _load_environments_data()}
    if environment not in valid_envs:
        raise ValueError(f"Unknown environment: {environment}")

    preset = dict(classes[character_class])
    player = CharacterSheet.model_validate({"name": clean_name, **preset})

    slug = re.sub(r"[^a-z0-9]+", "-", clean_name.lower()).strip("-") or "hero"
    campaign_id = f"{slug}-{uuid4().hex[:8]}"

    return CampaignState(
        campaign_id=campaign_id,
        player=player,
        environment=environment,
        campaign_stage="Introduction",
        turn_count=0,
        max_turns=max_turns,
    )


def roll_d20(modifier: int = 0) -> tuple[int, int]:
    """Roll a 20-sided die and return (raw_roll, raw_roll + modifier)."""
    raw_roll = random.randint(1, 20)
    return raw_roll, raw_roll + modifier


def use_consumable(
    state: CampaignState,
    item_id: str,
) -> tuple[CampaignState, EngineResult]:
    """Consume an item from the player's consumables list and return updated state and result."""
    if is_campaign_over(state):
        raise ValueError("Cannot use consumable: campaign is already over.")

    updated = state.model_copy(deep=True)
    updated.turn_count += 1
    turn_num = updated.turn_count

    item = _find_consumable(updated.player, item_id)
    if item is None:
        updated = _finalize_turn(updated)
        result = EngineResult(
            turn_number=turn_num,
            action_category="Item",
            interpreted_action=f"Attempted to use {item_id}",
            success=False,
            campaign_stage=updated.campaign_stage,
            summary=f"No consumable matching '{item_id}' was found in inventory.",
        )
        updated.engine_log.append(result)
        return updated, result

    healing_done = 0
    damage_dealt = 0
    enemy_just_defeated = False
    summary_parts: list[str] = []

    if item.heal_amount > 0:
        old_hp = updated.player.hp
        updated.player.hp = min(updated.player.max_hp, updated.player.hp + item.heal_amount)
        healing_done = updated.player.hp - old_hp
        summary_parts.append(
            f"Used {item.name}, restoring {healing_done} HP ({updated.player.hp}/{updated.player.max_hp})."
        )

    if item.attack_bonus > 0 and updated.active_enemy is not None:
        damage_dealt = item.attack_bonus + random.randint(1, 6)
        updated.active_enemy.hp = max(0, updated.active_enemy.hp - damage_dealt)
        summary_parts.append(
            f"Threw {item.name} at {updated.active_enemy.name} for {damage_dealt} damage "
            f"(Enemy HP: {updated.active_enemy.hp}/{updated.active_enemy.max_hp})."
        )
        if updated.active_enemy.hp == 0:
            updated.defeated_enemies.append(updated.active_enemy.id)
            updated.active_enemy = None
            enemy_just_defeated = True
            summary_parts.append("The enemy was defeated!")
    elif item.attack_bonus > 0 and updated.active_enemy is None and item.heal_amount == 0:
        summary_parts.append(f"Uncorked {item.name}, though no enemy is currently engaged.")

    if item.quantity > 1:
        item.quantity -= 1
    else:
        updated.player.consumables = [
            c for c in updated.player.consumables if c.id != item.id
        ]

    updated = _finalize_turn(updated, enemy_just_defeated=enemy_just_defeated)
    result = EngineResult(
        turn_number=turn_num,
        action_category="Item",
        interpreted_action=f"Use {item.name}",
        success=True,
        damage_dealt=damage_dealt,
        healing_done=healing_done,
        items_used=[item.id],
        campaign_stage=updated.campaign_stage,
        summary=" ".join(summary_parts) or f"Used {item.name}.",
    )
    updated.engine_log.append(result)
    return updated, result


def process_turn(
    state: CampaignState,
    action_text: str,
    action_category: ActionCategory,
) -> tuple[CampaignState, EngineResult]:
    """Resolve one player turn deterministically and return updated state and EngineResult."""
    if is_campaign_over(state):
        raise ValueError("Cannot process turn: campaign is already over.")

    clean_action = action_text.strip() or f"{action_category} action"

    if action_category == "Item":
        return use_consumable(state, clean_action)

    updated = state.model_copy(deep=True)
    updated.turn_count += 1
    turn_num = updated.turn_count

    player_roll: int | None = None
    enemy_roll: int | None = None
    damage_dealt = 0
    damage_taken = 0
    items_gained: list[str] = []
    success = True
    enemy_just_defeated = False
    summary_parts: list[str] = []

    if action_category == "Combat":
        if updated.active_enemy is None:
            prefer_boss = (
                updated.campaign_stage == "Main Encounter"
                or updated.turn_count >= CampaignFSM.main_encounter_threshold(updated.max_turns)
            )
            updated.active_enemy = _spawn_enemy(updated.defeated_enemies, prefer_boss=prefer_boss)
            summary_parts.append(f"{updated.active_enemy.name} engages in combat!")

        enemy = updated.active_enemy
        atk_mod = max(_effective_attack(updated.player), _effective_magic(updated.player))
        raw, total = roll_d20(atk_mod)
        player_roll = raw

        if raw == 20 or (raw != 1 and total >= enemy.defense):
            dmg = random.randint(2, 6) + max(1, atk_mod // 2)
            if raw == 20:
                dmg *= 2
            damage_dealt = dmg
            enemy.hp = max(0, enemy.hp - dmg)
            summary_parts.append(
                f"Rolled {raw} (total {total} vs DC {enemy.defense}) and hit {enemy.name} "
                f"for {dmg} damage (Enemy HP: {enemy.hp}/{enemy.max_hp})."
            )
        else:
            success = False
            summary_parts.append(
                f"Rolled {raw} (total {total} vs DC {enemy.defense}) and missed {enemy.name}."
            )

        if enemy.hp == 0:
            updated.defeated_enemies.append(enemy.id)
            updated.active_enemy = None
            enemy_just_defeated = True
            summary_parts.append(f"{enemy.name} is defeated!")
        else:
            e_raw, e_total = roll_d20(enemy.attack)
            enemy_roll = e_raw
            player_ac = 10 + _effective_defense(updated.player)
            if e_raw == 20 or (e_raw != 1 and e_total >= player_ac):
                edmg = random.randint(1, 5) + max(1, enemy.attack // 2)
                if e_raw == 20:
                    edmg *= 2
                damage_taken = edmg
                updated.player.hp = max(0, updated.player.hp - edmg)
                summary_parts.append(
                    f"{enemy.name} rolled {e_raw} and struck back for {edmg} damage "
                    f"(Player HP: {updated.player.hp}/{updated.player.max_hp})."
                )
            else:
                summary_parts.append(f"{enemy.name} rolled {e_raw} and missed.")

    elif action_category == "Exploration":
        skill_mod = (_effective_attack(updated.player) + _effective_magic(updated.player)) // 2
        raw, total = roll_d20(skill_mod)
        player_roll = raw
        dc = 11

        if raw == 20 or (raw != 1 and total >= dc):
            summary_parts.append(
                f"Exploration check succeeded (rolled {raw}, total {total} vs DC {dc})."
            )
            if raw >= 15 and len(updated.player.consumables) < 4:
                items_db = _load_items_data()
                if "healing_potion" in items_db:
                    found = Item.model_validate(items_db["healing_potion"])
                    existing = _find_consumable(updated.player, found.id)
                    if existing is not None:
                        existing.quantity += 1
                    else:
                        updated.player.consumables.append(found)
                    items_gained.append(found.id)
                    summary_parts.append(f"Discovered a {found.name}!")
        else:
            success = False
            summary_parts.append(
                f"Exploration check faltered (rolled {raw}, total {total} vs DC {dc})."
            )
            if updated.active_enemy is not None:
                e_raw, e_total = roll_d20(updated.active_enemy.attack)
                enemy_roll = e_raw
                player_ac = 10 + _effective_defense(updated.player)
                if e_raw == 20 or (e_raw != 1 and e_total >= player_ac):
                    edmg = random.randint(1, 4) + 1
                    damage_taken = edmg
                    updated.player.hp = max(0, updated.player.hp - edmg)
                    summary_parts.append(
                        f"{updated.active_enemy.name} exploited the opening for {edmg} damage!"
                    )

    elif action_category == "Dialogue":
        cha_mod = max(1, _effective_magic(updated.player) // 2)
        raw, total = roll_d20(cha_mod)
        player_roll = raw
        dc = 10

        if raw == 20 or (raw != 1 and total >= dc):
            summary_parts.append(
                f"Dialogue check succeeded (rolled {raw}, total {total} vs DC {dc})."
            )
        else:
            success = False
            summary_parts.append(
                f"Dialogue check fell flat (rolled {raw}, total {total} vs DC {dc})."
            )

    else:  # "Invalid"
        success = False
        summary_parts.append("Action was invalid or outside supported game rules.")

    updated = _finalize_turn(updated, enemy_just_defeated=enemy_just_defeated)
    result = EngineResult(
        turn_number=turn_num,
        action_category=action_category,
        interpreted_action=clean_action[:200],
        success=success,
        player_roll=player_roll,
        enemy_roll=enemy_roll,
        damage_dealt=damage_dealt,
        damage_taken=damage_taken,
        items_gained=items_gained,
        campaign_stage=updated.campaign_stage,
        summary=" ".join(summary_parts)[:500],
    )
    updated.engine_log.append(result)
    return updated, result


def is_campaign_over(state: CampaignState) -> bool:
    """Return True if the player is defeated, the campaign concluded, or max_turns is reached."""
    return (
        state.is_game_over
        or state.player.hp <= 0
        or state.campaign_stage == "Conclusion"
        or state.turn_count >= state.max_turns
    )
