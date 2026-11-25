"""Pydantic v2 domain models and strict schemas for WarDeN."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CampaignStage = Literal[
    "Introduction",
    "Exploration",
    "Main Encounter",
    "Conclusion",
]

CharacterClass = Literal["Warrior", "Archer", "Mage"]

ActionCategory = Literal[
    "Combat",
    "Exploration",
    "Dialogue",
    "Item",
    "Invalid",
]

EquipmentSlot = Literal["weapon", "armor", "accessory", "consumable"]

EnvironmentName = Literal[
    "Forest",
    "Mountains",
    "Coast",
    "Swamp",
    "Cave",
    "Desert",
    "Plains",
    "Snowfields",
]

CampaignOutcome = Literal["ongoing", "victory", "defeat"]


class Ability(BaseModel):
    """Special skill available to a character class or enemy."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=60)
    description: str = Field(..., min_length=1, max_length=300)
    power: int = Field(default=0, ge=0)
    magic_cost: int = Field(default=0, ge=0)
    cooldown_turns: int = Field(default=0, ge=0)


class Item(BaseModel):
    """Equipable gear or consumable fantasy item."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1, max_length=60)
    name: str = Field(..., min_length=1, max_length=80)
    slot: EquipmentSlot
    description: str = Field(default="", max_length=300)
    attack_bonus: int = Field(default=0, ge=0)
    defense_bonus: int = Field(default=0, ge=0)
    magic_bonus: int = Field(default=0, ge=0)
    heal_amount: int = Field(default=0, ge=0)
    quantity: int = Field(default=1, ge=1)


class CharacterSheet(BaseModel):
    """Player character state, stats, equipment slots, and abilities."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=50)
    character_class: CharacterClass
    hp: int = Field(..., ge=0)
    max_hp: int = Field(..., ge=1)
    attack: int = Field(..., ge=0)
    defense: int = Field(..., ge=0)
    magic: int = Field(..., ge=0)
    weapon: Item | None = None
    armor: Item | None = None
    accessory: Item | None = None
    consumables: list[Item] = Field(default_factory=list)
    abilities: list[Ability] = Field(default_factory=list, max_length=2)

    @model_validator(mode="after")
    def validate_hp_within_max(self) -> CharacterSheet:
        if self.hp > self.max_hp:
            raise ValueError(f"hp ({self.hp}) cannot exceed max_hp ({self.max_hp})")
        return self


class Enemy(BaseModel):
    """Predefined fantasy enemy with combat stats and behavior."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1, max_length=60)
    name: str = Field(..., min_length=1, max_length=80)
    description: str = Field(default="", max_length=300)
    hp: int = Field(..., ge=0)
    max_hp: int = Field(..., ge=1)
    attack: int = Field(..., ge=0)
    defense: int = Field(..., ge=0)
    abilities: list[Ability] = Field(default_factory=list)
    behavior: str = Field(default="aggressive", min_length=1, max_length=120)

    @model_validator(mode="after")
    def validate_hp_within_max(self) -> Enemy:
        if self.hp > self.max_hp:
            raise ValueError(f"hp ({self.hp}) cannot exceed max_hp ({self.max_hp})")
        return self


class EngineResult(BaseModel):
    """Deterministic turn outcome produced by the backend engine."""

    model_config = ConfigDict(extra="forbid")

    turn_number: int = Field(..., ge=1, le=11)
    action_category: ActionCategory
    interpreted_action: str = Field(..., min_length=1, max_length=200)
    success: bool = True
    player_roll: int | None = Field(default=None, ge=1, le=20)
    enemy_roll: int | None = Field(default=None, ge=1, le=20)
    damage_dealt: int = Field(default=0, ge=0)
    damage_taken: int = Field(default=0, ge=0)
    healing_done: int = Field(default=0, ge=0)
    items_used: list[str] = Field(default_factory=list)
    items_gained: list[str] = Field(default_factory=list)
    campaign_stage: CampaignStage
    summary: str = Field(..., min_length=1, max_length=500)


class CampaignState(BaseModel):
    """Full authoritative campaign state persisted between turns."""

    model_config = ConfigDict(extra="forbid")

    campaign_id: str = Field(..., min_length=1, max_length=80)
    player: CharacterSheet
    environment: EnvironmentName
    campaign_stage: CampaignStage = "Introduction"
    turn_count: int = Field(default=0, ge=0, le=11)
    max_turns: int = Field(default=8, ge=6, le=11)
    active_enemy: Enemy | None = None
    defeated_enemies: list[str] = Field(default_factory=list)
    history: list[dict[str, str]] = Field(default_factory=list)
    engine_log: list[EngineResult] = Field(default_factory=list)
    is_game_over: bool = False
    outcome: CampaignOutcome = "ongoing"

    @model_validator(mode="after")
    def validate_turn_bounds(self) -> CampaignState:
        if self.turn_count > self.max_turns:
            raise ValueError(
                f"turn_count ({self.turn_count}) cannot exceed max_turns ({self.max_turns})"
            )
        return self


class DMResponse(BaseModel):
    """Structured JSON response expected from the Luna 6 Dungeon Master."""

    model_config = ConfigDict(extra="forbid")

    narration: str = Field(..., min_length=1)
    action_category: ActionCategory
    interpreted_action: str = Field(..., min_length=1)
    npc_speaker: str | None = None
    campaign_stage: CampaignStage
    suggested_options: list[str] = Field(default_factory=list, max_length=4)
