"""4-stage campaign Finite State Machine (FSM) for WarDeN."""

from __future__ import annotations

from src.models import CampaignStage, CampaignState

STAGE_ORDER: tuple[CampaignStage, ...] = (
    "Introduction",
    "Exploration",
    "Main Encounter",
    "Conclusion",
)

VALID_TRANSITIONS: dict[CampaignStage, set[CampaignStage]] = {
    "Introduction": {"Introduction", "Exploration", "Conclusion"},
    "Exploration": {"Exploration", "Main Encounter", "Conclusion"},
    "Main Encounter": {"Main Encounter", "Conclusion"},
    "Conclusion": {"Conclusion"},
}


class InvalidStageTransitionError(ValueError):
    """Raised when an invalid campaign stage transition is attempted."""


class CampaignFSM:
    """Deterministic 4-stage campaign state machine with 6-11 turn pacing."""

    @staticmethod
    def can_transition(current: CampaignStage, target: CampaignStage) -> bool:
        """Return True if transitioning from current to target stage is allowed."""
        return target in VALID_TRANSITIONS.get(current, set())

    @staticmethod
    def transition(state: CampaignState, target: CampaignStage) -> CampaignState:
        """Return a copy of state transitioned to target, or raise InvalidStageTransitionError."""
        if not CampaignFSM.can_transition(state.campaign_stage, target):
            raise InvalidStageTransitionError(
                f"Cannot transition from '{state.campaign_stage}' to '{target}'."
            )
        updated = state.model_copy(deep=True)
        updated.campaign_stage = target
        return updated

    @staticmethod
    def main_encounter_threshold(max_turns: int) -> int:
        """Return the turn number at which Exploration advances to Main Encounter."""
        # Reserve at least 2 turns for Main Encounter + Conclusion within the 6-11 turn cap.
        return max(3, max_turns - 3)

    @staticmethod
    def evaluate_next_stage(state: CampaignState) -> CampaignStage:
        """Determine the next CampaignStage from current turn count, HP, and encounter state."""
        if state.player.hp <= 0:
            return "Conclusion"

        if state.campaign_stage == "Conclusion":
            return "Conclusion"

        if state.turn_count >= state.max_turns:
            return "Conclusion"

        if state.campaign_stage == "Introduction":
            return "Exploration" if state.turn_count >= 1 else "Introduction"

        if state.campaign_stage == "Exploration":
            if state.turn_count >= CampaignFSM.main_encounter_threshold(state.max_turns):
                return "Main Encounter"
            return "Exploration"

        if state.campaign_stage == "Main Encounter":
            if state.active_enemy is None:
                return "Conclusion"
            return "Main Encounter"

        return state.campaign_stage
