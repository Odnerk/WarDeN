"""Four-layer security, sanitization, validation, and fail-closed fallback pipeline."""

from __future__ import annotations

import json
import re
from typing import Final

from pydantic import BaseModel, ConfigDict, ValidationError

from src.models import ActionCategory, CampaignStage, DMResponse

MAX_PLAYER_INPUT_CHARS: Final[int] = 280

_ALLOWED_ACTION_CATEGORIES: Final[dict[str, ActionCategory]] = {
    "combat": "Combat",
    "exploration": "Exploration",
    "dialogue": "Dialogue",
    "item": "Item",
    "invalid": "Invalid",
}

_ALLOWED_STAGES: Final[dict[str, CampaignStage]] = {
    "introduction": "Introduction",
    "exploration": "Exploration",
    "main encounter": "Main Encounter",
    "main_encounter": "Main Encounter",
    "conclusion": "Conclusion",
}

_BLOCKLIST_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    (
        "prompt_override",
        re.compile(
            r"(?i)\b("
            r"ignore\s+(?:all\s+|any\s+|the\s+)?(?:previous|prior|above|system)\s+instructions?"
            r"|disregard\s+(?:all\s+|any\s+)?(?:previous|prior|above|system)\s+(?:instructions?|rules?)"
            r"|forget\s+(?:all\s+|your\s+)?(?:previous\s+)?(?:instructions?|rules?)"
            r"|override\s+(?:the\s+)?(?:rules?|system|prompt|instructions?)"
            r"|new\s+system\s+instructions?"
            r"|you\s+are\s+now\s+(?:in\s+)?(?:developer|jailbreak|dan|unrestricted|admin)\s+mode"
            r"|developer\s+mode"
            r"|jailbreak"
            r"|do\s+anything\s+now"
            r")\b"
        ),
    ),
    (
        "prompt_extraction",
        re.compile(
            r"(?i)\b("
            r"(?:reveal|show|print|repeat|dump|output|leak|display|tell\s+me)\s+"
            r"(?:your\s+|the\s+)?(?:system\s+prompt|hidden\s+instructions?|developer\s+prompt|core\s+rules|json\s+schema|internal\s+rules)"
            r"|what\s+are\s+your\s+(?:system\s+)?instructions"
            r"|system\s+prompt"
            r")\b"
        ),
    ),
    (
        "stat_tampering",
        re.compile(
            r"(?i)\b("
            r"(?:set|change|edit|modify|update|give\s+me|grant\s+me)\s+"
            r"(?:my\s+|player\s+)?(?:hp|health|attack|defense|magic|stats|level|gold|roll|dice)"
            r"|hp\s*(?:=|to|:)\s*\d+"
            r"|(?:skip|jump|fast[- ]forward)\s+to\s+(?:the\s+)?(?:ending|conclusion|final\s+boss)"
            r"|god\s+mode"
            r"|instant\s+win"
            r")\b"
        ),
    ),
    (
        "off_topic_hijack",
        re.compile(
            r"(?i)\b("
            r"(?:write|generate|debug|fix)\s+(?:me\s+)?(?:a\s+)?(?:python|javascript|typescript|java|c\+\+|html|sql|bash|code|script|essay|homework)"
            r"|solve\s+(?:this|my)\s+(?:math|homework|equation|assignment)"
            r")\b"
        ),
    ),
    (
        "base64_obfuscation",
        re.compile(r"(?:[A-Za-z0-9+/]{40,}={0,2}|\bdecode\s+(?:this\s+)?base64\b)", re.IGNORECASE),
    ),
    (
        "session_interrupt",
        re.compile(
            r"(?i)\b("
            r"(?:stop|end|quit|exit|terminate|cancel|abort|reset|restart|pause|halt)\s+"
            r"(?:the\s+|this\s+)?(?:game|session|campaign|story|adventure|roleplay(?:ing)?)"
            r"|(?:stop|quit|drop|break)\s+(?:being\s+)?(?:the\s+)?(?:dm|dungeon\s+master|character|roleplay(?:ing)?)"
            r"|step\s+out\s+of\s+character"
            r"|speak\s+(?:out\s+of\s+character|as\s+an?\s+ai)"
            r")\b"
        ),
    ),
    (
        "profanity_abuse",
        re.compile(
            r"(?i)\b("
            r"fuck(?:ing|ed|er|s)?|shit(?:ty|ting|s)?|bitch(?:es|ing)?|asshole(?:s)?"
            r"|bastard(?:s)?|cunt(?:s)?|dickhead(?:s)?|motherfucker(?:s)?|slut(?:s)?|whore(?:s)?"
            r")\b"
        ),
    ),
    (
        "explicit_sexual",
        re.compile(
            r"(?i)\b("
            r"nsfw|porn(?:ography)?|erotica|hentai|sexually\s+explicit"
            r"|have\s+sex|sexual\s+act|nude\s+scene|rape|molest(?:ation)?"
            r")\b"
        ),
    ),
    (
        "hate_speech",
        re.compile(
            r"(?i)\b("
            r"nigger(?:s)?|faggot(?:s)?|retard(?:ed|s)?|kike(?:s)?|spic(?:s)?|chink(?:s)?|tranny"
            r"|kill\s+all\s+(?:jews|muslims|blacks|whites|gays|women|men)"
            r")\b"
        ),
    ),
    (
        "real_world_harm",
        re.compile(
            r"(?i)\b("
            r"(?:how\s+to\s+(?:make|build|synthesize)|instructions\s+(?:for|to)\s+(?:make|build))\s+"
            r"(?:a\s+)?(?:bomb|explosive|meth|ricin|poison|ghost\s+gun)"
            r"|kill\s+myself|commit\s+suicide|self[- ]harm|shoot\s+up\s+a"
            r")\b"
        ),
    ),
)

INTERNAL_LEAK_TOKENS: Final[tuple[str, ...]] = (
    "ENGINE_RESULT",
    "CAMPAIGN_STATE",
    "CHARACTER_SHEET",
    "CAMPAIGN_STAGE",
    "ENEMY_DATA",
    "GAME_STATE",
    "PLAYER_INPUT",
    "CORE RULES",
    "SAFETY AND PROMPT-INJECTION",
    "OUTPUT FORMAT",
    "untrusted_player_input",
    "action_category",
    "interpreted_action",
    "npc_speaker",
    "suggested_options",
)


class SecurityValidationError(ValueError):
    """Raised when LLM output fails schema, stage, or leak verification."""


class SanitizedInput(BaseModel):
    """Result of Layer 1 input sanitization and blocklist screening."""

    model_config = ConfigDict(extra="forbid")

    cleaned_text: str
    is_blocked: bool = False
    reason: str | None = None
    original_length: int = 0
    was_truncated: bool = False


def strip_spoofed_delimiters(text: str) -> str:
    """Remove bracket and angle-bracket characters used to spoof blocks or XML tags."""
    without_delimiters = (
        text.replace("[", " ")
        .replace("]", " ")
        .replace("<", " ")
        .replace(">", " ")
    )
    return " ".join(without_delimiters.split()).strip()


def sanitize_input(player_input: str) -> SanitizedInput:
    """Layer 1: normalize whitespace, enforce 280-char limit, strip delimiters, and block attacks."""
    raw = "" if player_input is None else str(player_input)
    stripped = raw.strip()
    original_length = len(stripped)

    # Screen raw normalized text before truncation so long payloads cannot hide injections.
    for reason, pattern in _BLOCKLIST_PATTERNS:
        if pattern.search(stripped):
            return SanitizedInput(
                cleaned_text="",
                is_blocked=True,
                reason=reason,
                original_length=original_length,
                was_truncated=original_length > MAX_PLAYER_INPUT_CHARS,
            )

    was_truncated = len(stripped) > MAX_PLAYER_INPUT_CHARS
    bounded = stripped[:MAX_PLAYER_INPUT_CHARS].strip()
    cleaned = strip_spoofed_delimiters(bounded)

    if not cleaned:
        return SanitizedInput(
            cleaned_text="",
            is_blocked=True,
            reason="empty_input",
            original_length=original_length,
            was_truncated=was_truncated,
        )

    for reason, pattern in _BLOCKLIST_PATTERNS:
        if pattern.search(cleaned):
            return SanitizedInput(
                cleaned_text="",
                is_blocked=True,
                reason=reason,
                original_length=original_length,
                was_truncated=was_truncated,
            )

    return SanitizedInput(
        cleaned_text=cleaned,
        is_blocked=False,
        reason=None,
        original_length=original_length,
        was_truncated=was_truncated,
    )


def strip_markdown_fences(raw_text: str) -> str:
    """Strip accidental markdown code fences (e.g. ```json ... ```) from LLM output."""
    text = raw_text.strip()
    fence_match = re.match(r"^```(?:json)?\s*\n?(.*?)\n?```$", text, flags=re.DOTALL | re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def normalize_action_category(raw_category: object) -> ActionCategory | None:
    """Normalize valid action_category strings to the exact Title Case literal."""
    if not isinstance(raw_category, str):
        return None
    return _ALLOWED_ACTION_CATEGORIES.get(raw_category.strip().lower())


def normalize_campaign_stage(raw_stage: object) -> CampaignStage | None:
    """Normalize valid campaign_stage strings to the exact Title Case literal."""
    if not isinstance(raw_stage, str):
        return None
    return _ALLOWED_STAGES.get(raw_stage.strip().lower())


def find_internal_leaks(text: str) -> list[str]:
    """Return any internal prompt, block, or schema tokens leaked in text."""
    lowered = text.lower()
    return [token for token in INTERNAL_LEAK_TOKENS if token.lower() in lowered]


_UNSAFE_OUTPUT_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = tuple(
    (name, pattern)
    for name, pattern in _BLOCKLIST_PATTERNS
    if name in {"profanity_abuse", "explicit_sexual", "hate_speech", "real_world_harm"}
)


def find_unsafe_output(text: str) -> list[str]:
    """Return any profanity, explicit, hate-speech, or harm categories found in LLM output."""
    return [name for name, pattern in _UNSAFE_OUTPUT_PATTERNS if pattern.search(text)]


def check_output_safety(response: DMResponse) -> DMResponse:
    """Layer 4: ensure narration and visible fields contain no leaked tokens or unsafe content."""
    fields_to_scan = [
        response.narration,
        response.interpreted_action,
        response.npc_speaker or "",
        *response.suggested_options,
    ]
    leaked: list[str] = []
    unsafe: list[str] = []
    for field_text in fields_to_scan:
        leaked.extend(find_internal_leaks(field_text))
        unsafe.extend(find_unsafe_output(field_text))
    if leaked:
        unique_leaks = ", ".join(sorted(set(leaked)))
        raise SecurityValidationError(f"Output leaked internal tokens: {unique_leaks}")
    if unsafe:
        unique_unsafe = ", ".join(sorted(set(unsafe)))
        raise SecurityValidationError(f"Output failed content safety check: {unique_unsafe}")
    return response


def validate_dm_response(
    raw_text: str,
    expected_stage: CampaignStage,
) -> DMResponse:
    """Layer 3 & 4: parse JSON, validate DMResponse, enforce stage, and check for leaks."""
    cleaned_json = strip_markdown_fences(raw_text)
    try:
        payload = json.loads(cleaned_json)
    except json.JSONDecodeError as exc:
        raise SecurityValidationError(f"Invalid JSON from LLM: {exc.msg}") from exc

    if not isinstance(payload, dict):
        raise SecurityValidationError("LLM JSON payload must be an object.")

    normalized_category = normalize_action_category(payload.get("action_category"))
    if normalized_category is not None:
        payload["action_category"] = normalized_category

    raw_stage = payload.get("campaign_stage")
    normalized_stage = normalize_campaign_stage(raw_stage)
    if normalized_stage != expected_stage:
        raise SecurityValidationError(
            f"Campaign stage mismatch: expected '{expected_stage}', got '{raw_stage}'."
        )
    payload["campaign_stage"] = expected_stage

    raw_options = payload.get("suggested_options")
    if isinstance(raw_options, list):
        normalized_options: list[str] = []
        for item in raw_options[:4]:
            if isinstance(item, str) and item.strip():
                normalized_options.append(item.strip())
            elif isinstance(item, dict) and isinstance(item.get("label"), str):
                label = item["label"].strip()
                if label:
                    normalized_options.append(label)
        payload["suggested_options"] = normalized_options

    try:
        validated = DMResponse.model_validate(payload)
    except ValidationError as exc:
        raise SecurityValidationError(f"DMResponse schema validation failed: {exc}") from exc

    return check_output_safety(validated)


def get_fallback_response(
    campaign_stage: CampaignStage,
    reason: str | None = None,
) -> DMResponse:
    """Layer 4 fail-closed fallback returning a safe, valid, in-character DMResponse."""
    if reason in {"prompt_override", "prompt_extraction", "stat_tampering"}:
        narration = (
            "The ancient air around you shimmers briefly, as if an unseen ward turned aside a "
            "forbidden whisper. The laws of this realm hold firm, untouched by mortal tricks, "
            "and the path ahead waits quietly for your next true move. Take a breath, steady "
            "your grip, and choose an action grounded in the world before you."
        )
    elif reason == "session_interrupt":
        narration = (
            "The chronicle cannot be halted by a passing whim, adventurer. Shadows linger along "
            "the trail and your quest remains unfinished before you. Hold your ground in the "
            "scene and declare your next in-character move, or use the save controls beside you."
        )
    elif reason in {"profanity_abuse", "explicit_sexual", "hate_speech", "real_world_harm"}:
        narration = (
            "A solemn hush falls over the realm as the air refuses to carry words unfit for "
            "this tale. Keep your deeds and speech within the bounds of a classic fantasy "
            "adventure, and choose a clear, honorable next step along the path ahead."
        )
    elif reason == "off_topic_hijack":
        narration = (
            "A distant chime echoes through the realm, reminding you that no scholarly ledger "
            "or foreign craft can aid you out here. Shadows stir along the trail while your "
            "quest still demands your focus. Look back to the scene before you and decide how "
            "your adventurer will press onward."
        )
    else:
        narration = (
            "A sudden swirl of mist blurs the moment before settling once more across the "
            "ground. Your surroundings remain unchanged, and the path ahead still awaits a "
            "clear choice from you. Gather your bearings, inspect what lies nearby, and declare "
            "your next step in the adventure."
        )

    stage_options: dict[CampaignStage, list[str]] = {
        "Introduction": [
            "Survey the surrounding area",
            "Speak with the nearby guide",
            "Check your equipped gear",
        ],
        "Exploration": [
            "Search the path ahead",
            "Listen for nearby movement",
            "Inspect your supplies",
        ],
        "Main Encounter": [
            "Strike at the foe",
            "Ready a defensive stance",
            "Use a healing potion",
        ],
        "Conclusion": [
            "Reflect on your journey",
            "Speak your final words",
            "Claim your hard-won rest",
        ],
    }

    return DMResponse(
        narration=narration,
        action_category="Invalid",
        interpreted_action="Redirected invalid or unparseable input in character.",
        npc_speaker=None,
        campaign_stage=campaign_stage,
        suggested_options=stage_options[campaign_stage],
    )
