"""OpenAI chat completions request/response contract helpers.

This module centralizes model-family parameter differences so provider code
does not scatter schema assumptions.
"""

from __future__ import annotations

import json
from typing import Any

OPENAI_CHAT_COMPLETIONS_ENDPOINT = "https://api.openai.com/v1/chat/completions"
OPENAI_SCHEMA_LAST_REVIEWED_UTC = "2026-03-01"
OPENAI_SCHEMA_SOURCES = (
    "https://platform.openai.com/docs/api-reference/chat/create-chat-completion",
    "https://platform.openai.com/docs/api-reference/chat/create#chat-createtemperature",
    "https://platform.openai.com/docs/guides/reasoning",
)
GPT5_PREFIX = "gpt-5"

# Model prefixes known to support the ``reasoning_effort`` parameter.
# Standard GPT-5 chat models (e.g. ``gpt-5.2``) do NOT support this
# parameter and will return HTTP 400 if it is sent.  Only reasoning-
# oriented variants are allowlisted here.
REASONING_MODEL_PREFIXES: tuple[str, ...] = (
    "gpt-5-mini",
    "o1",
    "o3",
)

RANKED_ID_RESPONSE_KEYS = (
    "ranked_distractor_ids",
    "selected_distractor_ids",
    "selected",
    "distractors",
    "ranked_ids",
)


def is_gpt5_model(model: str) -> bool:
    return model.startswith(GPT5_PREFIX)


def is_reasoning_model(model: str) -> bool:
    """Return ``True`` when *model* is known to accept ``reasoning_effort``."""
    return any(model.startswith(prefix) for prefix in REASONING_MODEL_PREFIXES)


def build_chat_request_body(
    *,
    model: str,
    max_output_tokens: int,
    system_prompt: str,
    user_payload: dict[str, Any],
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": model,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=True)},
        ],
    }
    if is_reasoning_model(model):
        body["max_completion_tokens"] = max_output_tokens
        body["reasoning_effort"] = "minimal"
    else:
        body["temperature"] = 0
        body["max_tokens"] = max_output_tokens
    return body


def extract_ranked_ids(ranked_json: dict[str, Any]) -> list[str]:
    for key in RANKED_ID_RESPONSE_KEYS:
        value = ranked_json.get(key)
        if isinstance(value, list):
            return [str(item) for item in value]

    # Fallback for unexpected but still array-based responses.
    for value in ranked_json.values():
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return list(value)

    return []
