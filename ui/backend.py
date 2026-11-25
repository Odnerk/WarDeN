"""Backend adapter bridging the Streamlit UI to src.engine, src.dm_client, and src.security."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import streamlit as st

from src.dm_client import (
    classify_free_text,
    generate_campaign_intro,
    generate_narration,
)
from src.engine import is_campaign_over, process_turn, start_campaign, use_consumable
from src.models import (
    ActionCategory,
    CampaignState as BackendCampaignState,
    CharacterClass,
    Enemy,
    EngineResult,
    EnvironmentName,
)
from src.security import get_fallback_response, sanitize_input

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

DIFFICULTY_OPTIONS: tuple[str, ...] = (
    "Standard",
    "Story (Relaxed)",
    "Hardcore",
)
MAX_TURNS = 11
MAX_INPUT_CHARS = 280
MAX_SAVE_FILE_BYTES = 512 * 1024

_CLASS_SPEED_FALLBACK: dict[str, int] = {
    "Warrior": 4,
    "Archer": 7,
    "Mage": 5,
}


@dataclass
class Ability:
    name: str
    description: str
    stat: str = "attack"
    bonus: int = 2


@dataclass
class ConsumableItem:
    name: str
    description: str
    effect_type: str
    value: int
    quantity: int = 1
    id: str = ""


@dataclass
class EquipmentSlots:
    weapon: str
    armor: str
    accessory: str = "Empty"


@dataclass
class CharacterState:
    name: str
    char_class: str
    current_hp: int
    max_hp: int
    attack: int
    defense: int
    magic: int
    speed: int
    equipment: EquipmentSlots
    abilities: list[Ability] = field(default_factory=list)
    consumables: list[ConsumableItem] = field(default_factory=list)
    temp_attack_bonus: int = 0
    temp_defense_bonus: int = 0


@dataclass
class EnemyState:
    name: str
    title: str
    current_hp: int
    max_hp: int
    defense: int
    attack_bonus: int
    damage_min: int = 1
    damage_max: int = 6


@dataclass
class DiceRollResult:
    action_label: str
    d20_roll: int
    modifier: int
    total: int
    target_dc: int
    outcome: str
    damage: int
    enemy_roll_total: int = 0
    player_dc: int = 12
    enemy_hit: bool = False
    enemy_damage: int = 0


@dataclass
class ChatMessage:
    role: str
    content: str
    turn: int = 1
    npc_speaker: str | None = None
    roll_detail: dict[str, Any] | None = None
    is_combat: bool = False


@dataclass
class CampaignState:
    character: CharacterState
    environment: str
    premise: str = ""
    adventure_direction: str = ""
    difficulty: str = "Standard"
    custom_instructions: str = ""
    campaign_title: str = "WarDeN Chronicle"
    chapter_title: str = "CHAPTER 01 · THE ADVENTURE BEGINS"
    campaign_stage: str = "Introduction"
    current_turn: int = 1
    max_turns: int = 8
    combat_round: int = 0
    active_enemy: EnemyState | None = None
    last_roll: DiceRollResult | None = None
    history: list[ChatMessage] = field(default_factory=list)
    suggested_options: list[str] = field(default_factory=list)
    key_decisions: list[str] = field(default_factory=list)
    outcome: str | None = None
    enemy_defeated: bool = False
    backend_state: BackendCampaignState | None = None


@st.cache_data
def load_classes_data() -> dict[str, dict[str, Any]]:
    """Load class presets from data/classes.json formatted for setup cards."""
    raw = json.loads((DATA_DIR / "classes.json").read_text(encoding="utf-8"))
    formatted: dict[str, dict[str, Any]] = {}
    for cls_name, cls_data in raw.items():
        entry = dict(cls_data)
        entry.setdefault("name", cls_name)
        entry.setdefault("speed", _CLASS_SPEED_FALLBACK.get(cls_name, 5))
        formatted[cls_name] = entry
    return formatted


@st.cache_data
def load_environments_data() -> list[dict[str, Any]]:
    """Load fantasy environments from data/environments.json."""
    return json.loads((DATA_DIR / "environments.json").read_text(encoding="utf-8"))


def _sync_character(backend: BackendCampaignState) -> CharacterState:
    player = backend.player
    return CharacterState(
        name=player.name,
        char_class=player.character_class,
        current_hp=player.hp,
        max_hp=player.max_hp,
        attack=player.attack,
        defense=player.defense,
        magic=player.magic,
        speed=_CLASS_SPEED_FALLBACK.get(player.character_class, 5),
        equipment=EquipmentSlots(
            weapon=player.weapon.name if player.weapon else "Unarmed",
            armor=player.armor.name if player.armor else "None",
            accessory=player.accessory.name if player.accessory else "Empty",
        ),
        abilities=[
            Ability(
                name=ab.name,
                description=ab.description,
                stat="magic" if ab.magic_cost > 0 else "attack",
                bonus=ab.power,
            )
            for ab in player.abilities
        ],
        consumables=[
            ConsumableItem(
                id=item.id,
                name=item.name,
                description=item.description,
                effect_type="heal" if item.heal_amount > 0 else "buff_magic",
                value=item.heal_amount or item.magic_bonus,
                quantity=item.quantity,
            )
            for item in player.consumables
        ],
    )


def _sync_enemy(enemy: Enemy | None) -> EnemyState | None:
    if enemy is None:
        return None
    return EnemyState(
        name=enemy.name,
        title=enemy.behavior.replace("_", " ").title(),
        current_hp=enemy.hp,
        max_hp=enemy.max_hp,
        defense=enemy.defense,
        attack_bonus=enemy.attack,
    )


def _map_outcome(backend_outcome: str) -> str | None:
    if backend_outcome == "victory":
        return "Victory"
    if backend_outcome == "defeat":
        return "Defeat"
    return None


def _build_roll_detail(
    backend: BackendCampaignState,
    engine_result: EngineResult,
) -> DiceRollResult | None:
    if engine_result.player_roll is None:
        return None
    player = backend.player
    atk_mod = max(player.attack, player.magic)
    target_dc = backend.active_enemy.defense if backend.active_enemy else 11
    raw = engine_result.player_roll
    outcome = "Hit" if engine_result.success else "Miss"
    if raw == 20:
        outcome = "Critical Hit"
    elif raw == 1:
        outcome = "Critical Miss"

    return DiceRollResult(
        action_label=engine_result.interpreted_action[:40],
        d20_roll=raw,
        modifier=atk_mod,
        total=raw + atk_mod,
        target_dc=target_dc,
        outcome=outcome,
        damage=engine_result.damage_dealt,
        enemy_roll_total=engine_result.enemy_roll or 0,
        player_dc=10 + player.defense,
        enemy_hit=engine_result.damage_taken > 0,
        enemy_damage=engine_result.damage_taken,
    )


def _sync_ui_state(
    backend: BackendCampaignState,
    *,
    previous: CampaignState | None = None,
    history: list[ChatMessage] | None = None,
    suggested_options: list[str] | None = None,
    last_roll: DiceRollResult | None = None,
    combat_round: int | None = None,
    key_decisions: list[str] | None = None,
) -> CampaignState:
    chapter_map = {
        "Introduction": f"CHAPTER 01 · THE {backend.environment.upper()}",
        "Exploration": f"CHAPTER 02 · DEEPER INTO THE {backend.environment.upper()}",
        "Main Encounter": f"CHAPTER 03 · THE {backend.environment.upper()} CLIMAX",
        "Conclusion": "EPILOGUE · CHRONICLE COMPLETE",
    }
    return CampaignState(
        character=_sync_character(backend),
        environment=backend.environment,
        premise=previous.premise if previous else "",
        adventure_direction=previous.adventure_direction if previous else "",
        difficulty=previous.difficulty if previous else "Standard",
        custom_instructions=previous.custom_instructions if previous else "",
        campaign_title=previous.campaign_title if previous else f"Shadows of the {backend.environment}",
        chapter_title=chapter_map.get(backend.campaign_stage, "CHAPTER 01"),
        campaign_stage=backend.campaign_stage,
        current_turn=max(1, backend.turn_count),
        max_turns=backend.max_turns,
        combat_round=combat_round if combat_round is not None else (previous.combat_round if previous else 0),
        active_enemy=_sync_enemy(backend.active_enemy),
        last_roll=last_roll if last_roll is not None else (previous.last_roll if previous else None),
        history=history if history is not None else (list(previous.history) if previous else []),
        suggested_options=(
            suggested_options
            if suggested_options is not None
            else (list(previous.suggested_options) if previous else [])
        ),
        key_decisions=(
            key_decisions
            if key_decisions is not None
            else (list(previous.key_decisions) if previous else [])
        ),
        outcome=_map_outcome(backend.outcome),
        enemy_defeated=bool(backend.defeated_enemies),
        backend_state=backend,
    )


def create_new_campaign(
    character_name: str,
    char_class: str,
    environment: str,
    premise: str = "",
    adventure_direction: str = "",
    difficulty: str = "Standard",
    custom_instructions: str = "",
) -> CampaignState:
    """Initialize BackendCampaignState via src.engine and generate Luna 6 opening narration."""
    max_turns = 8 if difficulty == "Story (Relaxed)" else (10 if difficulty == "Hardcore" else 8)
    backend = start_campaign(
        player_name=character_name,
        character_class=char_class,  # type: ignore[arg-type]
        environment=environment,  # type: ignore[arg-type]
        max_turns=max_turns,
    )
    config = {
        "premise": premise,
        "adventure_direction": adventure_direction,
        "difficulty": difficulty,
        "custom_instructions": custom_instructions,
    }
    intro = generate_campaign_intro(backend, campaign_config=config)
    backend.history.append({"role": "assistant", "content": intro.narration})

    ui_history = [
        ChatMessage(
            role="assistant",
            content=intro.narration,
            turn=1,
            npc_speaker=intro.npc_speaker,
            is_combat=False,
        )
    ]
    base = CampaignState(
        character=_sync_character(backend),
        environment=backend.environment,
        premise=premise,
        adventure_direction=adventure_direction,
        difficulty=difficulty,
        custom_instructions=custom_instructions,
        campaign_title=(premise.strip()[:55] if premise.strip() else f"Shadows of the {environment}"),
    )
    return _sync_ui_state(
        backend,
        previous=base,
        history=ui_history,
        suggested_options=intro.suggested_options,
    )


def _resolve_action_category(
    action_type: str,
    cleaned_text: str,
    stage: str,
) -> ActionCategory:
    mapping: dict[str, ActionCategory] = {
        "Combat": "Combat",
        "Attack": "Combat",
        "Use Ability": "Combat",
        "Defend": "Combat",
        "Exploration": "Exploration",
        "Dialogue": "Dialogue",
        "Item": "Item",
    }
    if action_type in mapping:
        return mapping[action_type]
    classification = classify_free_text(cleaned_text, stage)  # type: ignore[arg-type]
    return classification.action_category


def process_player_turn(
    state: CampaignState,
    action_text: str,
    action_type: str,
) -> CampaignState:
    """Run Layer 1 sanitization, deterministic engine resolution, and Luna 6 narration."""
    backend = state.backend_state
    if backend is None or is_campaign_over(backend):
        return state

    sanitized = sanitize_input(action_text)
    if sanitized.is_blocked:
        fallback = get_fallback_response(backend.campaign_stage, reason=sanitized.reason)
        new_history = list(state.history)
        if sanitized.cleaned_text:
            new_history.append(
                ChatMessage(role="user", content=sanitized.cleaned_text, turn=state.current_turn)
            )
        new_history.append(
            ChatMessage(
                role="assistant",
                content=fallback.narration,
                turn=state.current_turn,
                npc_speaker=fallback.npc_speaker,
                is_combat=backend.campaign_stage == "Main Encounter",
            )
        )
        return _sync_ui_state(
            backend,
            previous=state,
            history=new_history,
            suggested_options=fallback.suggested_options,
        )

    action_category = _resolve_action_category(
        action_type=action_type,
        cleaned_text=sanitized.cleaned_text,
        stage=backend.campaign_stage,
    )

    if action_category == "Invalid":
        fallback = get_fallback_response(backend.campaign_stage)
        new_history = list(state.history) + [
            ChatMessage(role="user", content=sanitized.cleaned_text, turn=state.current_turn),
            ChatMessage(
                role="assistant",
                content=fallback.narration,
                turn=state.current_turn,
                is_combat=backend.campaign_stage == "Main Encounter",
            ),
        ]
        return _sync_ui_state(
            backend,
            previous=state,
            history=new_history,
            suggested_options=fallback.suggested_options,
        )

    updated_backend, engine_result = process_turn(
        backend,
        sanitized.cleaned_text,
        action_category,
    )
    dm_resp = generate_narration(
        state=updated_backend,
        engine_result=engine_result,
        player_input=sanitized.cleaned_text,
        recent_history=updated_backend.history,
    )

    updated_backend.history.append({"role": "user", "content": sanitized.cleaned_text})
    updated_backend.history.append({"role": "assistant", "content": dm_resp.narration})

    roll_detail = _build_roll_detail(updated_backend, engine_result)
    is_combat = (
        action_category == "Combat"
        or updated_backend.campaign_stage == "Main Encounter"
        or state.campaign_stage == "Main Encounter"
    )
    combat_round = (state.combat_round + 1) if is_combat else state.combat_round

    new_history = list(state.history) + [
        ChatMessage(
            role="user",
            content=sanitized.cleaned_text,
            turn=engine_result.turn_number,
            is_combat=is_combat,
        ),
        ChatMessage(
            role="assistant",
            content=dm_resp.narration,
            turn=engine_result.turn_number,
            npc_speaker=dm_resp.npc_speaker,
            roll_detail=vars(roll_detail) if roll_detail else None,
            is_combat=is_combat,
        ),
    ]
    decisions = list(state.key_decisions)
    decisions.append(f"{engine_result.action_category}: {engine_result.interpreted_action}")

    return _sync_ui_state(
        updated_backend,
        previous=state,
        history=new_history,
        suggested_options=dm_resp.suggested_options,
        last_roll=roll_detail,
        combat_round=combat_round,
        key_decisions=decisions,
    )


def use_consumable_item(
    state: CampaignState,
    item_name: str,
) -> tuple[CampaignState, str]:
    """Use a consumable via src.engine.use_consumable and sync UI state."""
    backend = state.backend_state
    if backend is None:
        return state, "No active campaign."

    target_id = item_name
    for item in backend.player.consumables:
        if item.name.lower() == item_name.lower() or item.id.lower() == item_name.lower():
            target_id = item.id
            break

    try:
        updated_backend, engine_result = use_consumable(backend, target_id)
    except ValueError as exc:
        return state, str(exc)

    synced = _sync_ui_state(updated_backend, previous=state)
    return synced, engine_result.summary


def campaign_to_json(state: CampaignState) -> str:
    """Serialize authoritative BackendCampaignState to JSON."""
    if state.backend_state is not None:
        return state.backend_state.model_dump_json(indent=2)
    raise ValueError("Cannot save campaign without backend_state.")


def campaign_from_json(raw_bytes: bytes | str) -> CampaignState:
    """Load and validate a saved BackendCampaignState JSON file."""
    if isinstance(raw_bytes, bytes):
        if len(raw_bytes) > MAX_SAVE_FILE_BYTES:
            raise ValueError("Save file exceeds maximum allowed size (512 KB).")
        raw_text = raw_bytes.decode("utf-8")
    else:
        raw_text = raw_bytes

    try:
        backend = BackendCampaignState.model_validate_json(raw_text)
    except Exception as exc:
        raise ValueError(f"Invalid WarDeN save file: {exc}") from exc

    ui_history: list[ChatMessage] = []
    for idx, entry in enumerate(backend.history, start=1):
        role = entry.get("role", "assistant")
        if role in {"assistant", "user"}:
            ui_history.append(
                ChatMessage(
                    role=role,
                    content=entry.get("content", ""),
                    turn=min(backend.max_turns, max(1, (idx + 1) // 2)),
                )
            )

    decisions = [
        f"{res.action_category}: {res.interpreted_action}"
        for res in backend.engine_log
    ]
    return _sync_ui_state(
        backend,
        history=ui_history,
        key_decisions=decisions,
    )
