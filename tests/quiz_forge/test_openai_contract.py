from __future__ import annotations

import json
from pathlib import Path

from quiz_forge.ai.providers.openai_contract import (
    OPENAI_SCHEMA_LAST_REVIEWED_UTC,
    OPENAI_SCHEMA_SOURCES,
    RANKED_ID_RESPONSE_KEYS,
    build_chat_request_body,
    extract_ranked_ids,
    is_gpt5_model,
    is_reasoning_model,
)


def _user_payload() -> dict[str, object]:
    return {
        "task": "rerank_distractors",
        "quiz_type": "history_mcq_4",
        "question_prompt": "Which event happened in 1901?",
    }


def test_gpt5_request_schema_uses_completion_tokens_and_minimal_reasoning() -> None:
    body = build_chat_request_body(
        model="gpt-5-mini",
        max_output_tokens=500,
        system_prompt="system",
        user_payload=_user_payload(),
    )
    assert is_gpt5_model("gpt-5-mini")
    assert is_reasoning_model("gpt-5-mini")
    assert body["max_completion_tokens"] == 500
    assert body["reasoning_effort"] == "minimal"
    assert "max_tokens" not in body
    assert "temperature" not in body


def test_non_gpt5_request_schema_uses_max_tokens_and_temperature() -> None:
    body = build_chat_request_body(
        model="gpt-4o-mini",
        max_output_tokens=500,
        system_prompt="system",
        user_payload=_user_payload(),
    )
    assert not is_gpt5_model("gpt-4o-mini")
    assert not is_reasoning_model("gpt-4o-mini")
    assert body["max_tokens"] == 500
    assert body["temperature"] == 0
    assert "max_completion_tokens" not in body
    assert "reasoning_effort" not in body


def test_gpt5_standard_chat_model_uses_completion_tokens_and_temperature() -> None:
    """gpt-5.2 is a standard GPT-5 chat model: max_completion_tokens + temperature, no reasoning_effort."""
    body = build_chat_request_body(
        model="gpt-5.2",
        max_output_tokens=700,
        system_prompt="system",
        user_payload=_user_payload(),
    )
    assert is_gpt5_model("gpt-5.2")
    assert not is_reasoning_model("gpt-5.2")
    assert body["max_completion_tokens"] == 700
    assert body["temperature"] == 0
    assert "max_tokens" not in body
    assert "reasoning_effort" not in body


def test_is_reasoning_model_allowlist() -> None:
    assert is_reasoning_model("gpt-5-mini")
    assert is_reasoning_model("gpt-5-mini-2026-01-15")
    assert is_reasoning_model("o1")
    assert is_reasoning_model("o1-mini")
    assert is_reasoning_model("o3")
    assert is_reasoning_model("o3-mini")
    assert not is_reasoning_model("gpt-5")
    assert not is_reasoning_model("gpt-5.2")
    assert not is_reasoning_model("gpt-5.1-turbo")
    assert not is_reasoning_model("gpt-4o")
    assert not is_reasoning_model("gpt-4o-mini")


def test_extract_ranked_ids_supports_all_known_response_keys() -> None:
    for key in RANKED_ID_RESPONSE_KEYS:
        ranked = extract_ranked_ids({key: ["a", "b", "c"]})
        assert ranked == ["a", "b", "c"]


def test_openai_snapshot_matches_contract_module() -> None:
    root = Path(__file__).resolve().parents[2]
    snapshot_path = (
        root / "docs" / "api_contracts" / "openai_chat_completions_rerank.snapshot.json"
    )
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))

    assert snapshot["last_reviewed_utc"] == OPENAI_SCHEMA_LAST_REVIEWED_UTC
    assert snapshot["source_urls"] == list(OPENAI_SCHEMA_SOURCES)
    assert snapshot["response_contract"]["accepted_ranked_ids_keys"] == list(
        RANKED_ID_RESPONSE_KEYS
    )
