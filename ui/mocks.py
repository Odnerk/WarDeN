"""Standalone mock models, static data loaders, deterministic engine, and DM client.

Aligned with the WarDeN proposal document & wireframes (Pages 3, 4, 6-10):
- 3 playable classes with exact wireframe stats:
  - Warrior: 18 HP, Attack 8, Defense 7, Magic 2, Speed 4 (Power Strike, Guard)
  - Archer:  13 HP, Attack 7, Defense 5, Magic 3, Speed 7 (Aimed Shot, Quick Step)
  - Mage:    10 HP, Attack 3, Defense 3, Magic 9, Speed 5 (Arcane Bolt, Ward)
- 8 fantasy environments (Forest, Mountains, Coast, Swamp, Cave, Desert, Plains, Snowfield)
- Predefined enemies including Hollow Guard (20 HP)
- Structured campaign setup fields (premise, adventure_direction, difficulty,
  environment, custom_instructions)
- ``@st.cache_data`` loaders for ``data/*.json`` and ``@st.cache_resource`` DM client.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import streamlit as st

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

VALID_STAGES: tuple[str, ...] = (
    "Introduction",
    "Exploration",
    "Main Encounter",
    "Conclusion",
)
DIFFICULTY_OPTIONS: tuple[str, ...] = (
    "Standard",
    "Story (Relaxed)",
    "Hardcore",
)
MAX_TURNS = 11
MAX_INPUT_CHARS = 280
MAX_SAVE_FILE_BYTES = 512 * 1024


# ---------------------------------------------------------------------------
# Dataclass Schemas
# ---------------------------------------------------------------------------


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
    effect_type: str  # "heal" | "buff_attack" | "buff_defense"
    value: int
    quantity: int = 1


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
    damage_min: int
    damage_max: int


@dataclass
class DiceRollResult:
    action_label: str
    d20_roll: int
    modifier: int
    total: int
    target_dc: int
    outcome: str  # "Critical Hit" | "Hit" | "Miss" | "Critical Miss"
    damage: int
    enemy_roll_total: int = 0
    player_dc: int = 12
    enemy_hit: bool = False
    enemy_damage: int = 0

    def format_player_check(self) -> tuple[str, str, str]:
        detail = f"D20 {self.d20_roll} (+{self.modifier} = {self.total}) vs. Defense {self.target_dc}"
        if self.damage > 0:
            outcome = f"{self.outcome} (-{self.damage} HP)"
        else:
            outcome = self.outcome
        return self.action_label, detail, outcome

    def format_enemy_check(self) -> tuple[str, str, str]:
        detail = f"{self.enemy_roll_total} vs. Defense {self.player_dc}"
        outcome = f"Hit (-{self.enemy_damage} HP)" if self.enemy_hit else "Miss"
        return "Enemy attack", detail, outcome

    def format_summary(self) -> str:
        base = f"D20 Roll: {self.d20_roll} (+{self.modifier} = {self.total}) | {self.outcome} | Damage: {self.damage}"
        if self.enemy_damage > 0:
            base += f" | Enemy Counter: -{self.enemy_damage} HP"
        return base


@dataclass
class ChatMessage:
    role: str  # "assistant" | "user"
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
    campaign_title: str = "The Watcher in the Pines"
    chapter_title: str = "CHAPTER 01 · THE OLD ROAD"
    campaign_stage: str = "Introduction"
    current_turn: int = 1
    max_turns: int = MAX_TURNS
    combat_round: int = 0
    active_enemy: EnemyState | None = None
    last_roll: DiceRollResult | None = None
    history: list[ChatMessage] = field(default_factory=list)
    suggested_options: list[str] = field(default_factory=list)
    key_decisions: list[str] = field(default_factory=list)
    outcome: str | None = None  # "Victory" | "Defeat" | None
    enemy_defeated: bool = False


# ---------------------------------------------------------------------------
# Static Fallback Data (exact wireframe stats + 8 proposal environments)
# ---------------------------------------------------------------------------

DEFAULT_CLASSES: dict[str, dict[str, Any]] = {
    "Warrior": {
        "name": "Warrior",
        "max_hp": 18,
        "attack": 8,
        "defense": 7,
        "magic": 2,
        "speed": 4,
        "equipment": {
            "weapon": "Iron Longsword",
            "armor": "Chainmail",
            "accessory": "Empty",
        },
        "abilities": [
            {
                "name": "Power Strike",
                "description": "Heavy cleave (+3 Attack on D20 check).",
                "stat": "attack",
                "bonus": 3,
            },
            {
                "name": "Guard",
                "description": "Brace shield (+3 Defense this round).",
                "stat": "defense",
                "bonus": 3,
            },
        ],
        "consumables": [
            {
                "name": "Health Potion",
                "description": "Restores 6 HP immediately.",
                "effect_type": "heal",
                "value": 6,
                "quantity": 2,
            },
            {
                "name": "Rations",
                "description": "Restores 3 HP and steadies stamina.",
                "effect_type": "heal",
                "value": 3,
                "quantity": 3,
            },
        ],
    },
    "Archer": {
        "name": "Archer",
        "max_hp": 13,
        "attack": 7,
        "defense": 5,
        "magic": 3,
        "speed": 7,
        "equipment": {
            "weapon": "Yew Longbow",
            "armor": "Ranger Leather",
            "accessory": "Hawkfeather Charm",
        },
        "abilities": [
            {
                "name": "Aimed Shot",
                "description": "Precision strike (+3 Attack on D20 check).",
                "stat": "attack",
                "bonus": 3,
            },
            {
                "name": "Quick Step",
                "description": "Evade incoming blows (+3 Defense this round).",
                "stat": "defense",
                "bonus": 3,
            },
        ],
        "consumables": [
            {
                "name": "Health Potion",
                "description": "Restores 6 HP immediately.",
                "effect_type": "heal",
                "value": 6,
                "quantity": 2,
            },
            {
                "name": "Rations",
                "description": "Restores 3 HP on the road.",
                "effect_type": "heal",
                "value": 3,
                "quantity": 3,
            },
        ],
    },
    "Mage": {
        "name": "Mage",
        "max_hp": 10,
        "attack": 3,
        "defense": 3,
        "magic": 9,
        "speed": 5,
        "equipment": {
            "weapon": "Runed Ash Staff",
            "armor": "Apprentice Robe",
            "accessory": "Mana Focus",
        },
        "abilities": [
            {
                "name": "Arcane Bolt",
                "description": "Focused arcane lance using Magic (+2 bonus).",
                "stat": "magic",
                "bonus": 2,
            },
            {
                "name": "Ward",
                "description": "Conjure protective barrier (+4 Defense this round).",
                "stat": "defense",
                "bonus": 4,
            },
        ],
        "consumables": [
            {
                "name": "Health Potion",
                "description": "Restores 6 HP immediately.",
                "effect_type": "heal",
                "value": 6,
                "quantity": 2,
            },
            {
                "name": "Aether Tonic",
                "description": "Grants +3 Magic/Attack on your next check.",
                "effect_type": "buff_attack",
                "value": 3,
                "quantity": 2,
            },
        ],
    },
}

DEFAULT_ENVIRONMENTS: list[dict[str, Any]] = [
    {
        "name": "Forest",
        "tagline": "Ancient pines, mist-draped roads, and abandoned watchtowers.",
        "chapter": "CHAPTER 01 · THE OLD ROAD",
        "title": "The Watcher in the Pines",
        "npc": "Scout Mirel",
        "default_enemy": "Hollow Guard",
    },
    {
        "name": "Mountains",
        "tagline": "Wind-carved passes and ruined beacon keeps.",
        "chapter": "CHAPTER 01 · THE HIGH PASS",
        "title": "The Bell of Frostspire",
        "npc": "Warden Torin",
        "default_enemy": "Ironbound Marauder",
    },
    {
        "name": "Coast",
        "tagline": "Fog-wrapped sea cliffs and silent black-stone piers.",
        "chapter": "CHAPTER 01 · THE SALT TIDE",
        "title": "Lanterns of the Drowned Quay",
        "npc": "Harbormaster Kael",
        "default_enemy": "Hollow Guard",
    },
    {
        "name": "Swamp",
        "tagline": "Sinking boardwalks and pale bog-lights.",
        "chapter": "CHAPTER 01 · THE MIRE CAUSEWAY",
        "title": "The Sunken Reliquary",
        "npc": "Herbalist Soren",
        "default_enemy": "Blight Wraith",
    },
    {
        "name": "Cave",
        "tagline": "Echoing limestone vaults and forgotten shrines.",
        "chapter": "CHAPTER 01 · THE DEEP ARCH",
        "title": "Echoes Under Stone",
        "npc": "Lantern-Keeper Orin",
        "default_enemy": "Hollow Guard",
    },
    {
        "name": "Desert",
        "tagline": "Red dunes hiding glass-fused obelisks.",
        "chapter": "CHAPTER 01 · THE SUNKEN CARAVAN",
        "title": "Crown of the Glass Dunes",
        "npc": "Caravaner Tariq",
        "default_enemy": "Cinder Stalker",
    },
    {
        "name": "Plains",
        "tagline": "Wind-swept barrows and standing boundary stones.",
        "chapter": "CHAPTER 01 · THE BARROW MARCH",
        "title": "Oath of the Grey Heath",
        "npc": "Outrider Freya",
        "default_enemy": "Ironbound Marauder",
    },
    {
        "name": "Snowfield",
        "tagline": "Silent white expanses and buried watchposts.",
        "chapter": "CHAPTER 01 · THE WHITE EXPANSE",
        "title": "Ashes in the Frost",
        "npc": "Tracker Vael",
        "default_enemy": "Cinder Stalker",
    },
]

DEFAULT_ENEMIES: dict[str, dict[str, Any]] = {
    "Hollow Guard": {
        "name": "Hollow Guard",
        "title": "Oathbound Sentinel",
        "max_hp": 20,
        "defense": 13,
        "attack_bonus": 3,
        "damage_min": 2,
        "damage_max": 4,
    },
    "Cinder Stalker": {
        "name": "Cinder Stalker",
        "title": "Ash-Born Prowler",
        "max_hp": 16,
        "defense": 13,
        "attack_bonus": 4,
        "damage_min": 2,
        "damage_max": 5,
    },
    "Blight Wraith": {
        "name": "Blight Wraith",
        "title": "Mire-Touched Shade",
        "max_hp": 15,
        "defense": 14,
        "attack_bonus": 3,
        "damage_min": 2,
        "damage_max": 5,
    },
    "Ironbound Marauder": {
        "name": "Ironbound Marauder",
        "title": "Rusted Vanguard",
        "max_hp": 18,
        "defense": 12,
        "attack_bonus": 3,
        "damage_min": 2,
        "damage_max": 4,
    },
}

DEFAULT_ITEMS: dict[str, Any] = {
    "consumables": [
        {"name": "Health Potion", "description": "Restores 6 HP immediately.", "effect_type": "heal", "value": 6},
        {"name": "Rations", "description": "Restores 3 HP on the road.", "effect_type": "heal", "value": 3},
        {"name": "Aether Tonic", "description": "Grants +3 Magic/Attack next check.", "effect_type": "buff_attack", "value": 3},
    ]
}


# ---------------------------------------------------------------------------
# Cached Static Data Loaders (@st.cache_data)
# ---------------------------------------------------------------------------


def _read_json_if_exists(filename: str) -> Any | None:
    path = DATA_DIR / filename
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _normalize_class_entry(cls_key: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize either Member 4's data/classes.json schema or built-in fallback schema."""
    fallback = DEFAULT_CLASSES.get(cls_key, DEFAULT_CLASSES["Warrior"])
    name = str(raw.get("name") or raw.get("character_class") or cls_key)

    if isinstance(raw.get("equipment"), dict):
        equip = raw["equipment"]
    else:
        def _slot_name(val: Any, default: str) -> str:
            if isinstance(val, dict):
                return str(val.get("name", default))
            return str(val) if val else default

        equip = {
            "weapon": _slot_name(raw.get("weapon"), fallback["equipment"]["weapon"]),
            "armor": _slot_name(raw.get("armor"), fallback["equipment"]["armor"]),
            "accessory": _slot_name(raw.get("accessory"), fallback["equipment"]["accessory"]),
        }

    abilities: list[dict[str, Any]] = []
    for idx, ab in enumerate(raw.get("abilities", fallback["abilities"])):
        if isinstance(ab, dict):
            stat_default = "magic" if name == "Mage" and idx == 0 else ("defense" if idx > 0 else "attack")
            abilities.append(
                {
                    "name": str(ab.get("name", "Strike")),
                    "description": str(ab.get("description", "")),
                    "stat": str(ab.get("stat", stat_default)),
                    "bonus": int(ab.get("bonus", ab.get("power", 2))),
                }
            )

    consumables: list[dict[str, Any]] = []
    for item in raw.get("consumables", fallback["consumables"]):
        if isinstance(item, dict):
            heal_amt = int(item.get("heal_amount", 0))
            atk_amt = int(item.get("attack_bonus", 0))
            def_amt = int(item.get("defense_bonus", 0))
            if "effect_type" in item and "value" in item:
                eff_type = str(item["effect_type"])
                eff_val = int(item["value"])
            elif heal_amt > 0:
                eff_type, eff_val = "heal", heal_amt
            elif atk_amt > 0:
                eff_type, eff_val = "buff_attack", atk_amt
            elif def_amt > 0:
                eff_type, eff_val = "buff_defense", def_amt
            else:
                eff_type, eff_val = "heal", 6

            consumables.append(
                {
                    "name": str(item.get("name", "Healing Potion")),
                    "description": str(item.get("description", "Restores HP.")),
                    "effect_type": eff_type,
                    "value": eff_val,
                    "quantity": int(item.get("quantity", 1)),
                }
            )

    return {
        "name": name,
        "max_hp": int(raw.get("max_hp", raw.get("hp", fallback["max_hp"]))),
        "attack": int(raw.get("attack", fallback["attack"])),
        "defense": int(raw.get("defense", fallback["defense"])),
        "magic": int(raw.get("magic", fallback["magic"])),
        "speed": int(raw.get("speed", fallback["speed"])),
        "equipment": equip,
        "abilities": abilities,
        "consumables": consumables,
    }


@st.cache_data(show_spinner=False)
def load_classes_data() -> dict[str, dict[str, Any]]:
    loaded = _read_json_if_exists("classes.json")
    if isinstance(loaded, dict) and loaded:
        return {
            key: _normalize_class_entry(key, val)
            for key, val in loaded.items()
            if isinstance(val, dict)
        }
    if isinstance(loaded, list) and loaded:
        out: dict[str, dict[str, Any]] = {}
        for entry in loaded:
            if isinstance(entry, dict):
                key = str(entry.get("name") or entry.get("character_class") or "")
                if key:
                    out[key] = _normalize_class_entry(key, entry)
        if out:
            return out
    return DEFAULT_CLASSES


@st.cache_data(show_spinner=False)
def load_environments_data() -> list[dict[str, Any]]:
    loaded = _read_json_if_exists("environments.json")
    fallback_by_name = {e["name"].lower(): e for e in DEFAULT_ENVIRONMENTS}
    if isinstance(loaded, list) and loaded:
        normalized: list[dict[str, Any]] = []
        for entry in loaded:
            if isinstance(entry, str):
                fb = fallback_by_name.get(entry.lower(), {})
                normalized.append(
                    {
                        "name": entry,
                        "tagline": fb.get("tagline", ""),
                        "chapter": fb.get("chapter", f"CHAPTER 01 · {entry.upper()}"),
                        "title": fb.get("title", f"Chronicle of the {entry}"),
                        "npc": fb.get("npc", "Scout Mirel"),
                        "default_enemy": fb.get("default_enemy", "Hollow Guard"),
                    }
                )
            elif isinstance(entry, dict) and entry.get("name"):
                ename = str(entry["name"])
                fb = fallback_by_name.get(ename.lower()) or fallback_by_name.get(ename.lower().rstrip("s"), {})
                normalized.append(
                    {
                        "name": ename,
                        "tagline": str(entry.get("tagline") or entry.get("atmosphere") or fb.get("tagline", "")),
                        "chapter": str(entry.get("chapter") or fb.get("chapter", f"CHAPTER 01 · {ename.upper()}")),
                        "title": str(entry.get("title") or fb.get("title", f"Chronicle of the {ename}")),
                        "npc": str(entry.get("npc") or fb.get("npc", "Scout Mirel")),
                        "default_enemy": str(entry.get("default_enemy") or fb.get("default_enemy", "Hollow Guard")),
                    }
                )
        if normalized:
            return normalized
    return DEFAULT_ENVIRONMENTS


def _normalize_enemy_entry(raw: dict[str, Any]) -> dict[str, Any]:
    name = str(raw.get("name", "Hollow Guard"))
    atk = int(raw.get("attack_bonus", raw.get("attack", 3)))
    return {
        "name": name,
        "title": str(raw.get("title") or raw.get("behavior", "Guardian").replace("_", " ").title()),
        "max_hp": int(raw.get("max_hp", raw.get("hp", 20))),
        "defense": int(raw.get("defense", 13)),
        "attack_bonus": atk,
        "damage_min": int(raw.get("damage_min", max(2, atk // 2))),
        "damage_max": int(raw.get("damage_max", max(4, atk))),
    }


@st.cache_data(show_spinner=False)
def load_enemies_data() -> dict[str, dict[str, Any]]:
    loaded = _read_json_if_exists("enemies.json")
    if isinstance(loaded, dict) and loaded:
        return {
            str(entry.get("name", key)): _normalize_enemy_entry(entry)
            for key, entry in loaded.items()
            if isinstance(entry, dict)
        }
    if isinstance(loaded, list) and loaded:
        return {
            str(entry["name"]): _normalize_enemy_entry(entry)
            for entry in loaded
            if isinstance(entry, dict) and "name" in entry
        }
    return DEFAULT_ENEMIES


@st.cache_data(show_spinner=False)
def load_items_data() -> dict[str, Any]:
    loaded = _read_json_if_exists("items.json")
    if isinstance(loaded, dict) and loaded:
        return loaded
    return DEFAULT_ITEMS


# ---------------------------------------------------------------------------
# Mock AI Dungeon Master Client (@st.cache_resource)
# ---------------------------------------------------------------------------


class MockDMClient:
    """Read-only narration generator standing in for Luna 6 until Member 2 merges."""

    def narrate(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        stage = snapshot.get("campaign_stage", "Introduction")
        env = snapshot.get("environment", "Forest")
        char_name = snapshot.get("character_name", "Rowan")
        action_type = snapshot.get("action_type", "Free Action")
        action_summary = snapshot.get("action_summary", "")
        premise = snapshot.get("premise", "")
        npc_name = snapshot.get("npc_name", "Scout Mirel")
        enemy = snapshot.get("active_enemy")
        last_roll = snapshot.get("last_roll")
        outcome = snapshot.get("outcome")

        if stage == "Introduction" and not action_summary:
            premise_note = f" {premise}" if premise else ""
            return {
                "narration": (
                    f"The road narrows as the {env.lower()} closes around you. Ahead, an abandoned watchtower rises above the boundary stones, "
                    f"its upper windows dark.{premise_note} Near the weathered gate, {npc_name} lowers a hood and watches the threshold in silence."
                ),
                "npc_speaker": None,
                "suggested_options": [
                    "Leave the road and approach quietly",
                    "Inspect the tracks near the entrance",
                    f"Speak with {npc_name} before advancing",
                ],
            }

        if stage == "Conclusion":
            if outcome == "Victory":
                return {
                    "narration": (
                        f"With the threat defeated, the {env.lower()} falls silent. At the summit of the crossing, {char_name} relights the old beacon "
                        "and watches its signal travel from ridge to distant ridge.\n\n"
                        "By dawn, the lost patrol returns to the road. The land remains deep and unknowable, but the path is safe once more—"
                        "and your name will be remembered by those who travel it."
                    ),
                    "npc_speaker": None,
                    "suggested_options": [],
                }
            return {
                "narration": (
                    f"Your lantern gutters out against the cold stone as exhaustion claims {char_name} beneath the shadow of the {env.lower()}.\n\n"
                    f"Though the expedition falls short of the summit, {npc_name} recovers your journal before dawn so the next Warden "
                    "will know what waits beyond the gate."
                ),
                "npc_speaker": None,
                "suggested_options": [],
            }

        if enemy is not None:
            enemy_name = enemy["name"]
            enemy_hp = enemy["current_hp"]
            if last_roll is None:
                return {
                    "narration": (
                        f"Iron scrapes across wet stone. A {enemy_name} steps out of the archway, dragging a rusted blade as its hollow helm turns toward {char_name}. "
                        "There is no turning back without crossing its guard."
                    ),
                    "npc_speaker": None,
                    "suggested_options": [
                        f"Press the {enemy_name}'s open flank",
                        "Channel your signature ability",
                        "Hold stance and read its next swing",
                    ],
                }

            roll_outcome = last_roll["outcome"]
            dmg = last_roll["damage"]
            edmg = last_roll["enemy_damage"]
            if roll_outcome == "Critical Hit":
                first = f"Your strike breaks straight through the {enemy_name}'s guard for {dmg} damage, staggering it backward."
            elif roll_outcome == "Hit":
                first = f"You catch the {enemy_name} mid-stride and land a solid blow for {dmg} damage."
            else:
                first = f"The {enemy_name} turns your strike aside with a ringing clash of rusted iron."

            if enemy_hp <= 0:
                second = f" Its frame gives way, collapsing across the threshold in silence."
            elif edmg > 0:
                second = f" It lunges back before you can reset, grazing you for {edmg} damage."
            else:
                second = " Its counterattack goes wide, leaving a brief opening before it recovers its stance."

            return {
                "narration": first + second,
                "npc_speaker": None,
                "suggested_options": [
                    f"Strike while the {enemy_name} is open",
                    "Use your class ability",
                    "Guard and recover footing",
                ],
            }

        if action_type == "Dialogue":
            return {
                "narration": (
                    f"\"Two patrols entered before dusk,\" {npc_name} whispers, eyes fixed on the dark doorway. "
                    "\"None came back out. Listen for the drag of iron before you cross the inner hall.\""
                ),
                "npc_speaker": npc_name,
                "suggested_options": [
                    "Ask about the guardian inside",
                    "Inspect the tracks along the stone",
                    "Advance toward the inner chamber",
                ],
            }

        return {
            "narration": (
                "Wet ground softens your steps. Near the lower entrance, you notice fresh tracks pressed into the mud "
                "and hear a faint metallic scraping echoing from within."
            ),
            "npc_speaker": None,
            "suggested_options": [
                "Inspect the tracks before entering",
                f"Warn {npc_name} about what you heard",
                "Step through the archway with weapon ready",
            ],
        }


@st.cache_resource(show_spinner=False)
def get_dm_client() -> Any:
    try:
        from src import dm_client as real_dm_client  # type: ignore[import-not-found]

        if hasattr(real_dm_client, "get_dm_client"):
            return real_dm_client.get_dm_client()
        if hasattr(real_dm_client, "DMClient"):
            return real_dm_client.DMClient()
    except Exception:
        pass
    return MockDMClient()


# ---------------------------------------------------------------------------
# Sanitization & Deterministic Engine Logic
# ---------------------------------------------------------------------------


def sanitize_player_input(raw_text: str, max_chars: int = MAX_INPUT_CHARS) -> str:
    cleaned = str(raw_text or "")
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", cleaned)
    cleaned = cleaned.replace("<", "").replace(">", "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_chars]


def _lookup_env_meta(environment_name: str) -> dict[str, Any]:
    for env in load_environments_data():
        if env.get("name") == environment_name:
            return env
    return DEFAULT_ENVIRONMENTS[0]


def _build_read_only_snapshot(
    state: CampaignState,
    action_type: str = "Free Action",
    action_summary: str = "",
) -> dict[str, Any]:
    env_meta = _lookup_env_meta(state.environment)
    return {
        "campaign_stage": state.campaign_stage,
        "current_turn": state.current_turn,
        "max_turns": state.max_turns,
        "environment": state.environment,
        "premise": state.premise,
        "adventure_direction": state.adventure_direction,
        "difficulty": state.difficulty,
        "character_name": state.character.name,
        "char_class": state.character.char_class,
        "character_hp": state.character.current_hp,
        "character_max_hp": state.character.max_hp,
        "npc_name": env_meta.get("npc", "Scout Mirel"),
        "action_type": action_type,
        "action_summary": action_summary,
        "active_enemy": asdict(state.active_enemy) if state.active_enemy else None,
        "last_roll": asdict(state.last_roll) if state.last_roll else None,
        "outcome": state.outcome,
    }


def _spawn_environment_enemy(environment_name: str, difficulty: str = "Standard") -> EnemyState:
    env_meta = _lookup_env_meta(environment_name)
    enemies = load_enemies_data()
    enemy_key = env_meta.get("default_enemy", "Hollow Guard")
    template = enemies.get(enemy_key) or next(iter(enemies.values()))

    hp_delta = -3 if "Story" in difficulty else (3 if difficulty == "Hardcore" else 0)
    max_hp = max(8, int(template.get("max_hp", 20)) + hp_delta)

    return EnemyState(
        name=str(template.get("name", "Hollow Guard")),
        title=str(template.get("title", "Guardian")),
        current_hp=max_hp,
        max_hp=max_hp,
        defense=int(template.get("defense", 13)),
        attack_bonus=int(template.get("attack_bonus", 3)),
        damage_min=int(template.get("damage_min", 2)),
        damage_max=int(template.get("damage_max", 4)),
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
    classes = load_classes_data()
    cls_data = classes.get(char_class) or DEFAULT_CLASSES["Warrior"]
    env_meta = _lookup_env_meta(environment)

    safe_name = sanitize_player_input(character_name, max_chars=40) or "Rowan"
    safe_premise = sanitize_player_input(premise, max_chars=MAX_INPUT_CHARS)
    safe_direction = sanitize_player_input(adventure_direction, max_chars=MAX_INPUT_CHARS)
    safe_custom = sanitize_player_input(custom_instructions, max_chars=MAX_INPUT_CHARS)

    equip_raw = cls_data.get("equipment", {})
    equipment = EquipmentSlots(
        weapon=str(equip_raw.get("weapon", "Iron Longsword")),
        armor=str(equip_raw.get("armor", "Chainmail")),
        accessory=str(equip_raw.get("accessory", "Empty")),
    )

    abilities = [
        Ability(
            name=str(ab.get("name", "Strike")),
            description=str(ab.get("description", "")),
            stat=str(ab.get("stat", "attack")),
            bonus=int(ab.get("bonus", 2)),
        )
        for ab in cls_data.get("abilities", [])
        if isinstance(ab, dict)
    ]

    consumables = [
        ConsumableItem(
            name=str(item.get("name", "Health Potion")),
            description=str(item.get("description", "Restores HP.")),
            effect_type=str(item.get("effect_type", "heal")),
            value=int(item.get("value", 6)),
            quantity=int(item.get("quantity", 1)),
        )
        for item in cls_data.get("consumables", [])
        if isinstance(item, dict)
    ]

    max_hp = int(cls_data.get("max_hp", 18))
    character = CharacterState(
        name=safe_name,
        char_class=str(cls_data.get("name", char_class)),
        current_hp=max_hp,
        max_hp=max_hp,
        attack=int(cls_data.get("attack", 6)),
        defense=int(cls_data.get("defense", 5)),
        magic=int(cls_data.get("magic", 2)),
        speed=int(cls_data.get("speed", 4)),
        equipment=equipment,
        abilities=abilities,
        consumables=consumables,
    )

    state = CampaignState(
        character=character,
        environment=environment,
        premise=safe_premise,
        adventure_direction=safe_direction,
        difficulty=difficulty if difficulty in DIFFICULTY_OPTIONS else "Standard",
        custom_instructions=safe_custom,
        campaign_title=str(env_meta.get("title", "The Watcher in the Pines")),
        chapter_title=str(env_meta.get("chapter", "CHAPTER 01 · THE OLD ROAD")),
        campaign_stage="Introduction",
        current_turn=1,
        max_turns=MAX_TURNS,
    )

    dm = get_dm_client()
    dm_resp = dm.narrate(_build_read_only_snapshot(state, action_type="Introduction"))
    state.history.append(
        ChatMessage(
            role="assistant",
            content=str(dm_resp.get("narration", "Your journey begins.")),
            turn=1,
            npc_speaker=dm_resp.get("npc_speaker"),
        )
    )
    state.suggested_options = [str(opt) for opt in dm_resp.get("suggested_options", [])[:3]]
    return state


def use_consumable_item(state: CampaignState, item_name: str) -> tuple[CampaignState, str]:
    if state.campaign_stage == "Conclusion":
        return state, "The campaign has concluded."
    if state.character.current_hp <= 0:
        return state, "Cannot use items while defeated."

    for item in state.character.consumables:
        if item.name == item_name:
            if item.quantity <= 0:
                return state, f"No {item.name} remaining."
            item.quantity -= 1
            if item.effect_type == "heal":
                before = state.character.current_hp
                state.character.current_hp = min(
                    state.character.max_hp,
                    state.character.current_hp + item.value,
                )
                healed = state.character.current_hp - before
                return state, f"Used {item.name}: restored {healed} HP."
            if item.effect_type == "buff_attack":
                state.character.temp_attack_bonus += item.value
                return state, f"Used {item.name}: +{item.value} Attack on your next check."
            if item.effect_type == "buff_defense":
                state.character.temp_defense_bonus += item.value
                return state, f"Used {item.name}: +{item.value} Defense for this clash."
            return state, f"Used {item.name}."

    return state, f"Item '{item_name}' not found."


def _resolve_combat_exchange(state: CampaignState, action_type: str) -> DiceRollResult:
    assert state.active_enemy is not None
    char = state.character
    enemy = state.active_enemy

    use_ability = action_type == "Use Ability"
    primary_stat = max(char.attack, char.magic) if char.char_class == "Mage" else char.attack
    ability_bonus = 0
    action_label = "Player attack"

    if use_ability and char.abilities:
        off_ab = char.abilities[0]
        action_label = off_ab.name
        ability_bonus = off_ab.bonus
        if off_ab.stat == "magic":
            primary_stat = char.magic
        elif off_ab.stat == "defense":
            char.temp_defense_bonus += off_ab.bonus
    elif action_type == "Defend":
        if len(char.abilities) > 1:
            def_ab = char.abilities[1]
            action_label = def_ab.name
            char.temp_defense_bonus += def_ab.bonus
        else:
            action_label = "Guard"
            char.temp_defense_bonus += 3

    modifier = max(1, primary_stat // 2) + ability_bonus + char.temp_attack_bonus
    d20 = random.randint(1, 20)
    total = d20 + modifier
    char.temp_attack_bonus = 0

    damage = 0
    if d20 == 20:
        outcome = "Critical Hit"
        damage = max(5, random.randint(5, 8) + max(1, modifier // 2))
    elif d20 == 1:
        outcome = "Critical Miss"
        damage = 0
    elif total >= enemy.defense:
        outcome = "Hit"
        damage = max(3, random.randint(3, 6) + max(1, modifier // 3))
    else:
        outcome = "Miss"
        damage = 0

    if action_type == "Defend" and damage > 0:
        damage = max(1, damage - 1)

    enemy.current_hp = max(0, enemy.current_hp - damage)

    enemy_roll_total = 0
    player_dc = 8 + char.defense + char.temp_defense_bonus
    enemy_hit = False
    enemy_damage = 0
    if enemy.current_hp > 0:
        enemy_roll_total = random.randint(1, 20) + enemy.attack_bonus
        if enemy_roll_total >= player_dc:
            enemy_hit = True
            enemy_damage = random.randint(enemy.damage_min, enemy.damage_max)
            char.current_hp = max(0, char.current_hp - enemy_damage)

    char.temp_defense_bonus = 0

    return DiceRollResult(
        action_label=action_label,
        d20_roll=d20,
        modifier=modifier,
        total=total,
        target_dc=enemy.defense,
        outcome=outcome,
        damage=damage,
        enemy_roll_total=enemy_roll_total,
        player_dc=player_dc,
        enemy_hit=enemy_hit,
        enemy_damage=enemy_damage,
    )


def process_player_turn(
    state: CampaignState,
    action_text: str,
    action_type: str = "Free Action",
) -> CampaignState:
    if state.campaign_stage == "Conclusion":
        return state

    sanitized_action = sanitize_player_input(action_text)
    if not sanitized_action:
        return state

    was_in_combat = state.campaign_stage == "Main Encounter" and state.active_enemy is not None

    state.history.append(
        ChatMessage(
            role="user",
            content=sanitized_action,
            turn=state.current_turn,
            is_combat=was_in_combat,
        )
    )
    if len(state.key_decisions) < 6:
        state.key_decisions.append(sanitized_action)

    state.current_turn = min(state.max_turns, state.current_turn + 1)

    roll_detail_for_chat: dict[str, Any] | None = None
    lower_action = sanitized_action.lower()
    wants_combat = (
        action_type in {"Combat", "Attack", "Use Ability", "Defend"}
        or any(word in lower_action for word in ("attack", "fight", "confront", "strike", "combat"))
    )

    if state.campaign_stage == "Introduction":
        if wants_combat:
            state.campaign_stage = "Main Encounter"
            state.active_enemy = _spawn_environment_enemy(state.environment, state.difficulty)
            state.combat_round = 1
            state.last_roll = None
        else:
            state.campaign_stage = "Exploration"
            state.last_roll = None

    elif state.campaign_stage == "Exploration":
        if wants_combat or state.current_turn >= 5:
            state.campaign_stage = "Main Encounter"
            state.active_enemy = _spawn_environment_enemy(state.environment, state.difficulty)
            state.combat_round = 1
            state.last_roll = None
        else:
            state.last_roll = None

    elif state.campaign_stage == "Main Encounter":
        if state.active_enemy is None:
            state.active_enemy = _spawn_environment_enemy(state.environment, state.difficulty)
            state.combat_round = 1
            state.last_roll = None
        else:
            state.combat_round += 1
            if action_type in {"Attack", "Use Ability", "Defend"}:
                combat_type = action_type
            elif any(word in lower_action for word in ("defend", "guard", "dodge", "brace", "ward", "quick step")):
                combat_type = "Defend"
            elif any(word in lower_action for word in ("ability", "spell", "bolt", "aimed", "power strike")):
                combat_type = "Use Ability"
            else:
                combat_type = "Attack"

            roll = _resolve_combat_exchange(state, combat_type)
            state.last_roll = roll
            roll_detail_for_chat = asdict(roll)

            if state.active_enemy.current_hp <= 0:
                state.enemy_defeated = True
                state.outcome = "Victory"
                state.campaign_stage = "Conclusion"
            elif state.character.current_hp <= 0:
                state.outcome = "Defeat"
                state.campaign_stage = "Conclusion"

    if state.current_turn >= state.max_turns and state.campaign_stage != "Conclusion":
        state.campaign_stage = "Conclusion"
        state.outcome = (
            "Victory"
            if state.character.current_hp > 0 and (state.enemy_defeated or state.active_enemy is None)
            else "Defeat"
        )

    dm = get_dm_client()
    dm_resp = dm.narrate(
        _build_read_only_snapshot(
            state,
            action_type=action_type,
            action_summary=sanitized_action,
        )
    )
    state.history.append(
        ChatMessage(
            role="assistant",
            content=str(dm_resp.get("narration", "The world shifts around you.")),
            turn=state.current_turn,
            npc_speaker=dm_resp.get("npc_speaker"),
            roll_detail=roll_detail_for_chat,
            is_combat=(state.campaign_stage == "Main Encounter" or roll_detail_for_chat is not None),
        )
    )
    state.suggested_options = [str(opt) for opt in dm_resp.get("suggested_options", [])[:3]]
    return state


# ---------------------------------------------------------------------------
# Save / Resume JSON Serialization with Defensive Validation
# ---------------------------------------------------------------------------


def campaign_to_dict(state: CampaignState) -> dict[str, Any]:
    return asdict(state)


def campaign_to_json(state: CampaignState) -> str:
    return json.dumps(campaign_to_dict(state), indent=2, ensure_ascii=False)


def campaign_from_json(raw_bytes: bytes) -> CampaignState:
    if len(raw_bytes) > MAX_SAVE_FILE_BYTES:
        raise ValueError("Save file exceeds the 512 KB safety limit.")
    try:
        payload = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Uploaded file is not valid UTF-8 JSON.") from exc

    if not isinstance(payload, dict):
        raise ValueError("Save file root must be a JSON object.")

    char_raw = payload.get("character")
    if not isinstance(char_raw, dict):
        raise ValueError("Save file is missing a valid 'character' section.")

    stage = str(payload.get("campaign_stage", "Introduction"))
    if stage not in VALID_STAGES:
        raise ValueError(f"Unsupported campaign stage: {stage!r}")

    equip_raw = char_raw.get("equipment") or {}
    equipment = EquipmentSlots(
        weapon=sanitize_player_input(equip_raw.get("weapon", "Iron Longsword"), 60) or "Iron Longsword",
        armor=sanitize_player_input(equip_raw.get("armor", "Chainmail"), 60) or "Chainmail",
        accessory=sanitize_player_input(equip_raw.get("accessory", "Empty"), 60) or "Empty",
    )

    abilities = [
        Ability(
            name=sanitize_player_input(ab.get("name", "Strike"), 60),
            description=sanitize_player_input(ab.get("description", ""), 160),
            stat=str(ab.get("stat", "attack")),
            bonus=max(0, min(20, int(ab.get("bonus", 2)))),
        )
        for ab in char_raw.get("abilities", [])
        if isinstance(ab, dict)
    ]

    consumables = [
        ConsumableItem(
            name=sanitize_player_input(it.get("name", "Health Potion"), 60),
            description=sanitize_player_input(it.get("description", ""), 160),
            effect_type=str(it.get("effect_type", "heal")),
            value=max(0, min(50, int(it.get("value", 6)))),
            quantity=max(0, min(99, int(it.get("quantity", 0)))),
        )
        for it in char_raw.get("consumables", [])
        if isinstance(it, dict)
    ]

    max_hp = max(1, min(100, int(char_raw.get("max_hp", 18))))
    cur_hp = max(0, min(max_hp, int(char_raw.get("current_hp", max_hp))))

    character = CharacterState(
        name=sanitize_player_input(char_raw.get("name", "Rowan"), 40) or "Rowan",
        char_class=sanitize_player_input(char_raw.get("char_class", "Warrior"), 30) or "Warrior",
        current_hp=cur_hp,
        max_hp=max_hp,
        attack=max(0, min(30, int(char_raw.get("attack", 8)))),
        defense=max(0, min(30, int(char_raw.get("defense", 7)))),
        magic=max(0, min(30, int(char_raw.get("magic", 2)))),
        speed=max(0, min(30, int(char_raw.get("speed", 4)))),
        equipment=equipment,
        abilities=abilities,
        consumables=consumables,
        temp_attack_bonus=max(0, min(20, int(char_raw.get("temp_attack_bonus", 0)))),
        temp_defense_bonus=max(0, min(20, int(char_raw.get("temp_defense_bonus", 0)))),
    )

    enemy_raw = payload.get("active_enemy")
    active_enemy: EnemyState | None = None
    if isinstance(enemy_raw, dict):
        e_max = max(1, min(200, int(enemy_raw.get("max_hp", 20))))
        e_cur = max(0, min(e_max, int(enemy_raw.get("current_hp", e_max))))
        active_enemy = EnemyState(
            name=sanitize_player_input(enemy_raw.get("name", "Hollow Guard"), 50) or "Hollow Guard",
            title=sanitize_player_input(enemy_raw.get("title", ""), 60),
            current_hp=e_cur,
            max_hp=e_max,
            defense=max(1, min(30, int(enemy_raw.get("defense", 13)))),
            attack_bonus=max(0, min(20, int(enemy_raw.get("attack_bonus", 3)))),
            damage_min=max(1, min(20, int(enemy_raw.get("damage_min", 2)))),
            damage_max=max(1, min(30, int(enemy_raw.get("damage_max", 4)))),
        )

    roll_raw = payload.get("last_roll")
    last_roll: DiceRollResult | None = None
    if isinstance(roll_raw, dict):
        last_roll = DiceRollResult(
            action_label=sanitize_player_input(roll_raw.get("action_label", "Player attack"), 40),
            d20_roll=max(1, min(20, int(roll_raw.get("d20_roll", 10)))),
            modifier=max(-10, min(30, int(roll_raw.get("modifier", 0)))),
            total=max(-10, min(60, int(roll_raw.get("total", 10)))),
            target_dc=max(1, min(40, int(roll_raw.get("target_dc", 13)))),
            outcome=sanitize_player_input(roll_raw.get("outcome", "Miss"), 25),
            damage=max(0, min(100, int(roll_raw.get("damage", 0)))),
            enemy_roll_total=max(0, min(60, int(roll_raw.get("enemy_roll_total", 0)))),
            player_dc=max(1, min(40, int(roll_raw.get("player_dc", 13)))),
            enemy_hit=bool(roll_raw.get("enemy_hit", False)),
            enemy_damage=max(0, min(100, int(roll_raw.get("enemy_damage", 0)))),
        )

    history: list[ChatMessage] = []
    for msg in payload.get("history", [])[:100]:
        if isinstance(msg, dict) and msg.get("role") in {"assistant", "user"}:
            roll_d = msg.get("roll_detail") if isinstance(msg.get("roll_detail"), dict) else None
            history.append(
                ChatMessage(
                    role=str(msg["role"]),
                    content=str(msg.get("content", ""))[:2000],
                    turn=max(1, min(MAX_TURNS, int(msg.get("turn", 1)))),
                    npc_speaker=(
                        sanitize_player_input(msg["npc_speaker"], 50)
                        if msg.get("npc_speaker")
                        else None
                    ),
                    roll_detail=roll_d,
                    is_combat=bool(msg.get("is_combat", roll_d is not None)),
                )
            )

    max_turns = max(1, min(20, int(payload.get("max_turns", MAX_TURNS))))
    current_turn = max(1, min(max_turns, int(payload.get("current_turn", 1))))
    outcome_val = payload.get("outcome")
    outcome = str(outcome_val) if outcome_val in {"Victory", "Defeat"} else None

    return CampaignState(
        character=character,
        environment=sanitize_player_input(payload.get("environment", "Forest"), 60) or "Forest",
        premise=sanitize_player_input(payload.get("premise", ""), MAX_INPUT_CHARS),
        adventure_direction=sanitize_player_input(payload.get("adventure_direction", ""), MAX_INPUT_CHARS),
        difficulty=str(payload.get("difficulty", "Standard")),
        custom_instructions=sanitize_player_input(payload.get("custom_instructions", ""), MAX_INPUT_CHARS),
        campaign_title=sanitize_player_input(payload.get("campaign_title", "The Watcher in the Pines"), 80)
        or "The Watcher in the Pines",
        chapter_title=sanitize_player_input(payload.get("chapter_title", "CHAPTER 01 · THE OLD ROAD"), 80)
        or "CHAPTER 01 · THE OLD ROAD",
        campaign_stage=stage,
        current_turn=current_turn,
        max_turns=max_turns,
        combat_round=max(0, min(50, int(payload.get("combat_round", 0)))),
        active_enemy=active_enemy,
        last_roll=last_roll,
        history=history,
        suggested_options=[
            sanitize_player_input(opt, 120)
            for opt in payload.get("suggested_options", [])[:4]
            if isinstance(opt, str) and opt.strip()
        ],
        key_decisions=[
            sanitize_player_input(dec, 200)
            for dec in payload.get("key_decisions", [])[:12]
            if isinstance(dec, str) and dec.strip()
        ],
        outcome=outcome,
        enemy_defeated=bool(payload.get("enemy_defeated", False)),
    )
