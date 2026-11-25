"""Luna 6 Dungeon Master LLM client and 4-layer security pipeline for WarDeN."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from typing import Final

import streamlit as st
from openai import APIConnectionError, APIError, APITimeoutError, BadRequestError, OpenAI, RateLimitError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.models import ActionCategory, CampaignStage, CampaignState, DMResponse, EngineResult
from src.prompts import (
    build_campaign_setup_messages,
    build_classifier_messages,
    build_turn_messages,
)
from src.security import (
    SecurityValidationError,
    get_fallback_response,
    normalize_action_category,
    sanitize_input,
    strip_markdown_fences,
    validate_dm_response,
)

LUNA_BASE_URL: Final[str] = "https://aiki-labs.up.railway.app/api/v1"
LUNA_MODEL: Final[str] = "gpt-6-luna"
MAX_NARRATION_TOKENS: Final[int] = 350
MAX_CLASSIFIER_TOKENS: Final[int] = 60


class ActionClassification(BaseModel):
    """Structured result from lightweight free-text intent classification."""

    model_config = ConfigDict(extra="forbid")

    action_category: ActionCategory
    interpreted_action: str = Field(..., min_length=1, max_length=200)


def _load_luna_api_key() -> str | None:
    """Load LUNA_API_KEY from Streamlit secrets with environment variable fallback."""
    try:
        secret_key = st.secrets.get("LUNA_API_KEY")
        if isinstance(secret_key, str) and secret_key.strip():
            return secret_key.strip()
    except Exception:
        pass

    env_key = os.getenv("LUNA_API_KEY")
    if env_key and env_key.strip():
        return env_key.strip()
    return None


@st.cache_resource
def _create_cached_client(api_key: str) -> OpenAI:
    """Create and cache the OpenAI SDK client pointed at the Luna 6 endpoint."""
    return OpenAI(
        api_key=api_key,
        base_url=LUNA_BASE_URL,
        timeout=25.0,
    )


def get_luna_client() -> OpenAI:
    """Return a cached Luna 6 OpenAI client using runtime-loaded credentials."""
    api_key = _load_luna_api_key()
    if not api_key:
        raise RuntimeError("LUNA_API_KEY is not configured in st.secrets or environment.")
    return _create_cached_client(api_key)


def _request_completion(
    client: OpenAI,
    messages: list[dict[str, str]],
    max_completion_tokens: int,
) -> str:
    """Call Luna 6 chat completions with response_format=json_object and 400 fallback."""
    try:
        response = client.chat.completions.create(
            model=LUNA_MODEL,
            messages=messages,  # type: ignore[arg-type]
            max_completion_tokens=max_completion_tokens,
            response_format={"type": "json_object"},
        )
    except BadRequestError:
        response = client.chat.completions.create(
            model=LUNA_MODEL,
            messages=messages,  # type: ignore[arg-type]
            max_completion_tokens=max_completion_tokens,
        )

    content = response.choices[0].message.content if response.choices else None
    if not content:
        raise SecurityValidationError("Empty response content returned by Luna 6.")
    return content


def _run_validated_dm_call(
    messages: list[dict[str, str]],
    expected_stage: CampaignStage,
    max_completion_tokens: int = MAX_NARRATION_TOKENS,
) -> DMResponse:
    """Execute a Luna 6 DM request with Layer 3/4 validation, 1 retry, and fail-closed fallback."""
    try:
        client = get_luna_client()
    except RuntimeError:
        return get_fallback_response(expected_stage)

    attempt_messages = list(messages)
    last_error: str | None = None

    for attempt in range(2):
        try:
            raw_content = _request_completion(
                client=client,
                messages=attempt_messages,
                max_completion_tokens=max_completion_tokens,
            )
            return validate_dm_response(raw_content, expected_stage=expected_stage)
        except SecurityValidationError as exc:
            last_error = str(exc)
            if attempt == 0:
                attempt_messages = [
                    *messages,
                    {
                        "role": "user",
                        "content": (
                            f"CORRECTION REQUIRED: Your previous output failed validation ({last_error}). "
                            f'Return ONLY valid JSON matching DMResponse with campaign_stage="{expected_stage}", '
                            "no markdown fences, and no internal prompt/schema keywords."
                        ),
                    },
                ]
        except (APITimeoutError, APIConnectionError, RateLimitError, APIError, json.JSONDecodeError):
            return get_fallback_response(expected_stage)
        except Exception:
            return get_fallback_response(expected_stage)

    return get_fallback_response(expected_stage)


def generate_campaign_intro(
    state: CampaignState,
    campaign_config: Mapping[str, str] | None = None,
) -> DMResponse:
    """Generate the opening premise, initial quest objective, and scene/NPC introduction."""
    messages = build_campaign_setup_messages(state, campaign_config=campaign_config)
    return _run_validated_dm_call(
        messages=messages,
        expected_stage=state.campaign_stage,
        max_completion_tokens=MAX_NARRATION_TOKENS,
    )


def classify_free_text(
    player_input: str,
    campaign_stage: CampaignStage,
) -> ActionClassification:
    """Classify free-text input into ActionCategory and a short interpreted_action."""
    sanitized = sanitize_input(player_input)
    if sanitized.is_blocked:
        return ActionClassification(
            action_category="Invalid",
            interpreted_action="Blocked out-of-character or unsafe player input.",
        )

    try:
        client = get_luna_client()
        messages = build_classifier_messages(
            sanitized_player_input=sanitized.cleaned_text,
            campaign_stage=campaign_stage,
        )
        raw_content = _request_completion(
            client=client,
            messages=messages,
            max_completion_tokens=MAX_CLASSIFIER_TOKENS,
        )
        payload = json.loads(strip_markdown_fences(raw_content))
        if not isinstance(payload, dict):
            raise ValueError("Classifier payload is not a JSON object.")

        normalized_cat = normalize_action_category(payload.get("action_category"))
        if normalized_cat is None:
            raise ValueError("Invalid action_category from classifier.")

        interpreted = str(payload.get("interpreted_action", "")).strip() or sanitized.cleaned_text[:80]
        return ActionClassification.model_validate(
            {
                "action_category": normalized_cat,
                "interpreted_action": interpreted[:200],
            }
        )
    except (
        RuntimeError,
        APITimeoutError,
        APIConnectionError,
        RateLimitError,
        APIError,
        BadRequestError,
        json.JSONDecodeError,
        ValidationError,
        ValueError,
    ):
        return ActionClassification(
            action_category="Exploration",
            interpreted_action=sanitized.cleaned_text[:200],
        )
    except Exception:
        return ActionClassification(
            action_category="Invalid",
            interpreted_action="Unable to classify player action safely.",
        )


def generate_narration(
    state: CampaignState,
    engine_result: EngineResult | None,
    player_input: str,
    recent_history: Sequence[Mapping[str, str]] | None = None,
) -> DMResponse:
    """Run the 4-layer security pipeline and generate validated DM narration for a turn."""
    sanitized = sanitize_input(player_input)
    if sanitized.is_blocked:
        return get_fallback_response(state.campaign_stage, reason=sanitized.reason)

    messages = build_turn_messages(
        state=state,
        engine_result=engine_result,
        sanitized_player_input=sanitized.cleaned_text,
        recent_history=recent_history,
    )
    return _run_validated_dm_call(
        messages=messages,
        expected_stage=state.campaign_stage,
        max_completion_tokens=MAX_NARRATION_TOKENS,
    )


def generate_intro(state: CampaignState) -> DMResponse:
    """Backwards-compatible alias for generate_campaign_intro."""
    return generate_campaign_intro(state)


def generate_dm_response(
    state: CampaignState,
    player_input: str,
    engine_result: EngineResult | None = None,
) -> DMResponse:
    """Backwards-compatible wrapper around generate_narration using state.history."""
    return generate_narration(
        state=state,
        engine_result=engine_result,
        player_input=player_input,
        recent_history=state.history,
    )
