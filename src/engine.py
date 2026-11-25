"""Deterministic backend game engine stubs for WarDeN."""

from __future__ import annotations

from src.models import (
    ActionCategory,
    CampaignState,
    CharacterClass,
    EngineResult,
    EnvironmentName,
)


def start_campaign(
    player_name: str,
    character_class: CharacterClass,
    environment: EnvironmentName,
    max_turns: int = 8,
) -> CampaignState:
    """Initialize a new CampaignState from static class and environment presets."""
    raise NotImplementedError("Owned by teammate")


def roll_d20(modifier: int = 0) -> tuple[int, int]:
    """Roll a 20-sided die and return (raw_roll, raw_roll + modifier)."""
    raise NotImplementedError("Owned by teammate")


def use_consumable(
    state: CampaignState,
    item_id: str,
) -> tuple[CampaignState, EngineResult]:
    """Consume an item from the player's consumables list and return updated state and result."""
    raise NotImplementedError("Owned by teammate")


def process_turn(
    state: CampaignState,
    action_text: str,
    action_category: ActionCategory,
) -> tuple[CampaignState, EngineResult]:
    """Resolve one player turn deterministically and return updated state and EngineResult."""
    raise NotImplementedError("Owned by teammate")


def is_campaign_over(state: CampaignState) -> bool:
    """Return True if the player is defeated, the campaign concluded, or max_turns is reached."""
    raise NotImplementedError("Owned by teammate")
