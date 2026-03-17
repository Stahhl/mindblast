from __future__ import annotations

import json

import pytest

from quiz_forge.ai.providers.openai import OpenAIProvider
from quiz_forge.ai.types import AISettings


def _settings(model: str) -> AISettings:
    return AISettings(
        mode="shadow",
        provider="openai",
        model=model,
        timeout_ms=15000,
        max_daily_usd=1.0,
        max_monthly_usd=5.0,
        max_calls_per_run=1,
        max_input_tokens=12000,
        max_output_tokens=500,
        input_price_per_million_usd=0.25,
        output_price_per_million_usd=2.0,
        ledger_path="/tmp/unused-ledger.json",
        report_path=None,
    )


def _payload() -> dict[str, object]:
    return {
        "task": "rerank_distractors",
        "quiz_type": "history_mcq_4",
        "question_prompt": "Which event happened in 1901?",
        "correct_answer_fact_id": "fact-correct",
        "correct_answer": {"id": "fact-correct", "label": "Event A", "year": 1901},
        "distractor_candidates": [
            {"id": "fact-b", "label": "Event B", "year": 1902},
            {"id": "fact-c", "label": "Event C", "year": 1903},
            {"id": "fact-d", "label": "Event D", "year": 1904},
        ],
        "constraints": {"max_returned": 3},
    }


class _FakeResponse:
    def __init__(self, body: str) -> None:
        self._body = body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        return None

    def read(self) -> bytes:
        return self._body.encode("utf-8")


def test_openai_provider_uses_max_completion_tokens_for_gpt5(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    captured: dict[str, object] = {}

    def fake_urlopen(req, timeout):  # noqa: ANN001
        captured["timeout"] = timeout
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResponse(
            json.dumps(
                {
                    "choices": [{"message": {"content": json.dumps({"selected": ["fact-b", "fact-c", "fact-d"]})}}],
                    "usage": {"prompt_tokens": 123, "completion_tokens": 12},
                }
            )
        )

    monkeypatch.setattr("quiz_forge.ai.providers.openai.request.urlopen", fake_urlopen)

    provider = OpenAIProvider()
    response = provider.rerank_distractors(_payload(), _settings("gpt-5-mini"))

    assert response.ranked_distractor_ids == ["fact-b", "fact-c", "fact-d"]
    body = captured["body"]
    assert isinstance(body, dict)
    assert body.get("max_completion_tokens") == 500
    assert "max_tokens" not in body
    assert "temperature" not in body
    assert body.get("reasoning_effort") == "minimal"


def test_openai_provider_uses_max_tokens_for_non_gpt5(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    captured: dict[str, object] = {}

    def fake_urlopen(req, timeout):  # noqa: ANN001
        captured["timeout"] = timeout
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResponse(
            json.dumps(
                {
                    "choices": [{"message": {"content": json.dumps({"ranked_distractor_ids": ["fact-b", "fact-c", "fact-d"]})}}],
                    "usage": {"prompt_tokens": 123, "completion_tokens": 12},
                }
            )
        )

    monkeypatch.setattr("quiz_forge.ai.providers.openai.request.urlopen", fake_urlopen)

    provider = OpenAIProvider()
    response = provider.rerank_distractors(_payload(), _settings("gpt-4o-mini"))

    assert response.ranked_distractor_ids == ["fact-b", "fact-c", "fact-d"]
    body = captured["body"]
    assert isinstance(body, dict)
    assert body.get("max_tokens") == 500
    assert "max_completion_tokens" not in body
    assert body.get("temperature") == 0


def test_openai_provider_run_json_task_uses_requested_model_and_tokens(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    captured: dict[str, object] = {}

    def fake_urlopen(req, timeout):  # noqa: ANN001
        captured["timeout"] = timeout
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResponse(
            json.dumps(
                {
                    "choices": [{"message": {"content": json.dumps({"result": "ok"})}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                }
            )
        )

    monkeypatch.setattr("quiz_forge.ai.providers.openai.request.urlopen", fake_urlopen)

    provider = OpenAIProvider()
    response = provider.run_json_task(
        system_prompt="Return JSON only.",
        user_payload={"task": "test"},
        settings=_settings("gpt-5-mini"),
        model="gpt-4o-mini",
        max_output_tokens=321,
    )

    assert response.payload == {"result": "ok"}
    body = captured["body"]
    assert isinstance(body, dict)
    assert body.get("model") == "gpt-4o-mini"
    assert body.get("max_tokens") == 321
    assert "max_completion_tokens" not in body


def test_openai_provider_run_json_task_accepts_fenced_json(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fake_urlopen(req, timeout):  # noqa: ANN001
        del req, timeout
        return _FakeResponse(
            json.dumps(
                {
                    "choices": [{"message": {"content": "```json\n{\"result\":\"ok\"}\n```"}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                }
            )
        )

    monkeypatch.setattr("quiz_forge.ai.providers.openai.request.urlopen", fake_urlopen)

    provider = OpenAIProvider()
    response = provider.run_json_task(
        system_prompt="Return JSON only.",
        user_payload={"task": "test"},
        settings=_settings("gpt-5-mini"),
        model="gpt-5-mini",
        max_output_tokens=321,
    )

    assert response.payload == {"result": "ok"}


def test_openai_provider_run_json_task_accepts_content_part_array(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fake_urlopen(req, timeout):  # noqa: ANN001
        del req, timeout
        return _FakeResponse(
            json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": [
                                    {"type": "text", "text": "{\"result\":\"ok\",\"source\":\"content-array\"}"}
                                ]
                            }
                        }
                    ],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                }
            )
        )

    monkeypatch.setattr("quiz_forge.ai.providers.openai.request.urlopen", fake_urlopen)

    provider = OpenAIProvider()
    response = provider.run_json_task(
        system_prompt="Return JSON only.",
        user_payload={"task": "test"},
        settings=_settings("gpt-5-mini"),
        model="gpt-5-mini",
        max_output_tokens=321,
    )

    assert response.payload == {"result": "ok", "source": "content-array"}


def test_openai_provider_run_json_task_raises_refusal_label(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fake_urlopen(req, timeout):  # noqa: ANN001
        del req, timeout
        return _FakeResponse(
            json.dumps(
                {
                    "choices": [{"message": {"content": "", "refusal": "I can’t help with that."}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                }
            )
        )

    monkeypatch.setattr("quiz_forge.ai.providers.openai.request.urlopen", fake_urlopen)

    provider = OpenAIProvider()
    with pytest.raises(RuntimeError, match=r"parse failure \[refusal\]"):
        provider.run_json_task(
            system_prompt="Return JSON only.",
            user_payload={"task": "test"},
            settings=_settings("gpt-5-mini"),
            model="gpt-5-mini",
            max_output_tokens=321,
        )


def test_openai_provider_run_json_task_raises_empty_content_label(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fake_urlopen(req, timeout):  # noqa: ANN001
        del req, timeout
        return _FakeResponse(
            json.dumps(
                {
                    "choices": [{"message": {"content": []}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                }
            )
        )

    monkeypatch.setattr("quiz_forge.ai.providers.openai.request.urlopen", fake_urlopen)

    provider = OpenAIProvider()
    with pytest.raises(RuntimeError, match=r"parse failure \[empty_content\]"):
        provider.run_json_task(
            system_prompt="Return JSON only.",
            user_payload={"task": "test"},
            settings=_settings("gpt-5-mini"),
            model="gpt-5-mini",
            max_output_tokens=321,
        )


def test_openai_provider_run_json_task_raises_json_decode_label(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fake_urlopen(req, timeout):  # noqa: ANN001
        del req, timeout
        return _FakeResponse(
            json.dumps(
                {
                    "choices": [{"message": {"content": "not json"}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                }
            )
        )

    monkeypatch.setattr("quiz_forge.ai.providers.openai.request.urlopen", fake_urlopen)

    provider = OpenAIProvider()
    with pytest.raises(RuntimeError, match=r"parse failure \[json_decode_error\]"):
        provider.run_json_task(
            system_prompt="Return JSON only.",
            user_payload={"task": "test"},
            settings=_settings("gpt-5-mini"),
            model="gpt-5-mini",
            max_output_tokens=321,
        )
