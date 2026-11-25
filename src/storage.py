"""JSON save/resume persistence for WarDeN CampaignState."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.models import CampaignState

DEFAULT_SAVE_DIR = Path(__file__).resolve().parent.parent / "saves"


def _sanitize_campaign_id(campaign_id: str) -> str:
    """Restrict campaign_id to safe filename characters."""
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "_", campaign_id.strip())
    if not cleaned:
        raise ValueError("campaign_id must contain at least one alphanumeric character.")
    return cleaned


def _save_path(campaign_id: str, save_dir: str | Path = DEFAULT_SAVE_DIR) -> Path:
    safe_id = _sanitize_campaign_id(campaign_id)
    return Path(save_dir) / f"{safe_id}.json"


def save_campaign(
    state: CampaignState,
    save_dir: str | Path = DEFAULT_SAVE_DIR,
) -> Path:
    """Serialize CampaignState to JSON on disk and return the saved file path."""
    directory = Path(save_dir)
    directory.mkdir(parents=True, exist_ok=True)
    target = _save_path(state.campaign_id, directory)
    target.write_text(state.model_dump_json(indent=2), encoding="utf-8")
    return target


def load_campaign(
    campaign_id: str,
    save_dir: str | Path = DEFAULT_SAVE_DIR,
) -> CampaignState:
    """Load and validate a CampaignState from JSON on disk."""
    target = _save_path(campaign_id, save_dir)
    if not target.exists():
        raise FileNotFoundError(f"No saved campaign found at '{target}'.")
    raw_json = target.read_text(encoding="utf-8")
    return CampaignState.model_validate_json(raw_json)


def list_saved_campaigns(
    save_dir: str | Path = DEFAULT_SAVE_DIR,
) -> list[dict[str, Any]]:
    """Return summary metadata for all valid saved campaigns in save_dir."""
    directory = Path(save_dir)
    if not directory.exists():
        return []

    summaries: list[dict[str, Any]] = []
    for file_path in sorted(directory.glob("*.json")):
        try:
            state = CampaignState.model_validate_json(file_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        summaries.append(
            {
                "campaign_id": state.campaign_id,
                "player_name": state.player.name,
                "character_class": state.player.character_class,
                "environment": state.environment,
                "campaign_stage": state.campaign_stage,
                "turn_count": state.turn_count,
                "max_turns": state.max_turns,
                "outcome": state.outcome,
                "is_game_over": state.is_game_over,
            }
        )
    return summaries


def delete_campaign(
    campaign_id: str,
    save_dir: str | Path = DEFAULT_SAVE_DIR,
) -> bool:
    """Delete a saved campaign JSON file. Return True if deleted, False if missing."""
    target = _save_path(campaign_id, save_dir)
    if target.exists():
        target.unlink()
        return True
    return False
