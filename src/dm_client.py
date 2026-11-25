"""Luna 6 Dungeon Master LLM client stubs for WarDeN."""

from __future__ import annotations

from src.models import CampaignState, DMResponse, EngineResult


def generate_intro(state: CampaignState) -> DMResponse:
    """Generate the opening Introduction narration and initial suggested options."""
    raise NotImplementedError("Owned by teammate")


def generate_dm_response(
    state: CampaignState,
    player_input: str,
    engine_result: EngineResult | None = None,
) -> DMResponse:
    """Generate a structured DMResponse for a turn using state, engine facts, and sanitized input."""
    raise NotImplementedError("Owned by teammate")
