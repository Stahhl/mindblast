from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from quiz_forge.ai.orchestrator import AIOrchestrator
from quiz_forge.ai.types import AIJsonTaskResponse, AIRerankResponse, AISettings, AIUsage


def _settings(tmp_path: Path, *, mode: str = "on") -> AISettings:
    return AISettings(
        mode=mode,
        provider="openai",
        model="gpt-5-mini",
        timeout_ms=1000,
        max_daily_usd=1.0,
        max_monthly_usd=5.0,
        max_calls_per_run=1,
        max_input_tokens=12000,
        max_output_tokens=500,
        input_price_per_million_usd=0.25,
        output_price_per_million_usd=2.0,
        ledger_path=(tmp_path / "ledger.json").as_posix(),
        report_path=(tmp_path / "report.json").as_posix(),
    )


def _sample_correct_and_candidates() -> tuple[dict[str, object], list[dict[str, object]]]:
    correct = {"text": "Event A", "year": 1901, "wikipedia_url": "https://example.com/a"}
    candidates = [
        {"text": "Event B", "year": 1910, "wikipedia_url": "https://example.com/b"},
        {"text": "Event C", "year": 1920, "wikipedia_url": "https://example.com/c"},
        {"text": "Event D", "year": 1930, "wikipedia_url": "https://example.com/d"},
        {"text": "Event E", "year": 1940, "wikipedia_url": "https://example.com/e"},
    ]
    return correct, candidates


def test_orchestrator_blocks_when_daily_budget_reached(tmp_path, mocker) -> None:
    settings = _settings(tmp_path)
    ledger = {
        "metadata": {"version": 1, "updated_at": "2026-02-25T00:00:00Z"},
        "daily": {"2026-02-25": {"calls": 1, "input_tokens": 10, "output_tokens": 5, "spend_usd": 1.0}},
        "monthly": {"2026-02": {"calls": 1, "input_tokens": 10, "output_tokens": 5, "spend_usd": 1.0}},
    }
    Path(settings.ledger_path).write_text(json.dumps(ledger), encoding="utf-8")

    orchestrator = AIOrchestrator(settings=settings, target_date=dt.date(2026, 2, 25))
    provider_mock = mocker.patch("quiz_forge.ai.providers.openai.OpenAIProvider.rerank_distractors")

    correct, candidates = _sample_correct_and_candidates()
    attempt = orchestrator.rerank_history_mcq(
        question_prompt="Which event happened in 1901?",
        correct_event=correct,
        distractor_candidates=candidates,
    )

    assert attempt.applied is False
    assert attempt.fallback_reason == "daily_budget_reached"
    provider_mock.assert_not_called()


def test_orchestrator_records_usage_and_applies_valid_response(tmp_path, mocker) -> None:
    settings = _settings(tmp_path, mode="on")
    orchestrator = AIOrchestrator(settings=settings, target_date=dt.date(2026, 2, 25))
    correct, candidates = _sample_correct_and_candidates()

    from quiz_forge.model import build_answer_fact_id

    ranked_ids = [build_answer_fact_id(item) for item in candidates[:3]]
    mocker.patch(
        "quiz_forge.ai.providers.openai.OpenAIProvider.rerank_distractors",
        return_value=AIRerankResponse(
            ranked_distractor_ids=ranked_ids,
            reason_codes=["test"],
            provider="openai",
            model="gpt-5-mini",
            usage=AIUsage(input_tokens=100, output_tokens=20, estimated_cost_usd=0.0),
        ),
    )

    attempt = orchestrator.rerank_history_mcq(
        question_prompt="Which event happened in 1901?",
        correct_event=correct,
        distractor_candidates=candidates,
    )
    orchestrator.finalize()
    orchestrator.write_report()

    assert attempt.applied is True
    assert attempt.response is not None
    assert attempt.response.ranked_distractor_ids == ranked_ids

    ledger = json.loads(Path(settings.ledger_path).read_text(encoding="utf-8"))
    assert ledger["daily"]["2026-02-25"]["calls"] == 1
    assert ledger["monthly"]["2026-02"]["calls"] == 1

    report = json.loads(Path(settings.report_path).read_text(encoding="utf-8"))
    assert report["calls_total"] == 1
    assert report["fallback_count"] == 0


def test_orchestrator_provider_error_includes_actionable_label(tmp_path, mocker) -> None:
    settings = _settings(tmp_path, mode="on")
    orchestrator = AIOrchestrator(settings=settings, target_date=dt.date(2026, 2, 25))
    correct, candidates = _sample_correct_and_candidates()

    mocker.patch(
        "quiz_forge.ai.providers.openai.OpenAIProvider.rerank_distractors",
        side_effect=RuntimeError("OpenAI request failed with HTTP 401: unauthorized"),
    )

    attempt = orchestrator.rerank_history_mcq(
        question_prompt="Which event happened in 1901?",
        correct_event=correct,
        distractor_candidates=candidates,
    )
    orchestrator.write_report()

    assert attempt.applied is False
    assert attempt.fallback_reason == "provider_error:RuntimeError:http_401"

    report = json.loads(Path(settings.report_path).read_text(encoding="utf-8"))
    assert "provider_error:RuntimeError:http_401:1" in report["fallback_reasons"]


def test_orchestrator_run_json_task_uses_specific_parse_failure_label(tmp_path, mocker) -> None:
    settings = _settings(tmp_path, mode="on")
    orchestrator = AIOrchestrator(settings=settings, target_date=dt.date(2026, 2, 25))

    mocker.patch(
        "quiz_forge.ai.providers.openai.OpenAIProvider.run_json_task",
        side_effect=RuntimeError(
            "OpenAI response parse failure [json_decode_error]: Expecting value: line 1 column 1 (char 0)"
        ),
    )

    payload, reason = orchestrator.run_json_task(
        task_name="weekly_feedback_review",
        system_prompt="Return JSON.",
        user_payload={"task": "test"},
    )
    orchestrator.write_report()

    assert payload is None
    assert reason == "weekly_feedback_review:provider_error:RuntimeError:json_decode_error"
    assert orchestrator.last_json_task_failure_diagnostics is not None
    assert orchestrator.last_json_task_failure_diagnostics.failure_label == "json_decode_error"

    report = json.loads(Path(settings.report_path).read_text(encoding="utf-8"))
    assert "weekly_feedback_review:provider_error:RuntimeError:json_decode_error:1" in report["fallback_reasons"]


def test_orchestrator_run_json_task_retries_weekly_empty_content_once(tmp_path, mocker) -> None:
    settings = _settings(tmp_path, mode="on")
    settings.max_calls_per_run = 3
    orchestrator = AIOrchestrator(settings=settings, target_date=dt.date(2026, 2, 25))
    provider_mock = mocker.patch(
        "quiz_forge.ai.providers.openai.OpenAIProvider.run_json_task",
        side_effect=[
            RuntimeError("OpenAI response parse failure [empty_content]: keys=['content'], content_type=list"),
            AIJsonTaskResponse(
                payload={"result": "ok"},
                provider="openai",
                model="gpt-5.2",
                usage=AIUsage(input_tokens=44, output_tokens=12, estimated_cost_usd=0.0),
            ),
        ],
    )

    payload, reason = orchestrator.run_json_task(
        task_name="weekly_feedback_review",
        system_prompt="Return JSON.",
        user_payload={"task": "test"},
        model="gpt-5.2",
    )

    assert reason is None
    assert payload == {"result": "ok"}
    assert provider_mock.call_count == 2
    assert orchestrator.stats.calls_total == 2
    assert orchestrator.last_json_task_failure_diagnostics is None


def test_orchestrator_run_json_task_persists_retry_diagnostics_after_second_failure(tmp_path, mocker) -> None:
    settings = _settings(tmp_path, mode="on")
    settings.max_calls_per_run = 3
    orchestrator = AIOrchestrator(settings=settings, target_date=dt.date(2026, 2, 25))
    provider_mock = mocker.patch(
        "quiz_forge.ai.providers.openai.OpenAIProvider.run_json_task",
        side_effect=[
            RuntimeError("OpenAI response parse failure [empty_content]: keys=['content'], content_type=list"),
            RuntimeError("OpenAI response parse failure [missing_message]: choices[0].message missing"),
        ],
    )

    payload, reason = orchestrator.run_json_task(
        task_name="weekly_feedback_review",
        system_prompt="Return JSON.",
        user_payload={"task": "test"},
        model="gpt-5.2",
    )

    assert payload is None
    assert reason == "weekly_feedback_review:provider_error:RuntimeError:missing_message"
    assert provider_mock.call_count == 2
    assert orchestrator.stats.calls_total == 2
    assert orchestrator.last_json_task_failure_diagnostics is not None
    assert orchestrator.last_json_task_failure_diagnostics.failure_label == "missing_message"
    assert orchestrator.last_json_task_failure_diagnostics.retry_attempted is True
    assert orchestrator.last_json_task_failure_diagnostics.retry_count == 1


def test_orchestrator_run_json_task_does_not_retry_non_weekly_empty_content(tmp_path, mocker) -> None:
    settings = _settings(tmp_path, mode="on")
    settings.max_calls_per_run = 3
    orchestrator = AIOrchestrator(settings=settings, target_date=dt.date(2026, 2, 25))
    provider_mock = mocker.patch(
        "quiz_forge.ai.providers.openai.OpenAIProvider.run_json_task",
        side_effect=RuntimeError("OpenAI response parse failure [empty_content]: keys=['content'], content_type=list"),
    )

    payload, reason = orchestrator.run_json_task(
        task_name="factoid_generation",
        system_prompt="Return JSON.",
        user_payload={"task": "test"},
        model="gpt-5.2",
    )

    assert payload is None
    assert reason == "factoid_generation:provider_error:RuntimeError:empty_content"
    assert provider_mock.call_count == 1
    assert orchestrator.stats.calls_total == 1


def test_orchestrator_run_json_task_records_usage(tmp_path, mocker) -> None:
    settings = _settings(tmp_path, mode="on")
    orchestrator = AIOrchestrator(settings=settings, target_date=dt.date(2026, 2, 25))
    mocker.patch(
        "quiz_forge.ai.providers.openai.OpenAIProvider.run_json_task",
        return_value=AIJsonTaskResponse(
            payload={"result": "ok"},
            provider="openai",
            model="gpt-5-mini",
            usage=AIUsage(input_tokens=42, output_tokens=12, estimated_cost_usd=0.0),
        ),
    )

    payload, reason = orchestrator.run_json_task(
        task_name="test",
        system_prompt="Return JSON.",
        user_payload={"task": "test", "value": 1},
    )
    orchestrator.finalize()

    assert reason is None
    assert payload == {"result": "ok"}

    ledger = json.loads(Path(settings.ledger_path).read_text(encoding="utf-8"))
    assert ledger["daily"]["2026-02-25"]["calls"] == 1
    assert ledger["monthly"]["2026-02"]["calls"] == 1


def test_orchestrator_run_json_task_respects_call_limit(tmp_path, mocker) -> None:
    settings = _settings(tmp_path, mode="on")
    settings.max_calls_per_run = 0
    orchestrator = AIOrchestrator(settings=settings, target_date=dt.date(2026, 2, 25))
    provider_mock = mocker.patch("quiz_forge.ai.providers.openai.OpenAIProvider.run_json_task")

    payload, reason = orchestrator.run_json_task(
        task_name="test",
        system_prompt="Return JSON.",
        user_payload={"task": "test"},
    )

    assert payload is None
    assert reason == "test:run_call_limit_reached"
    provider_mock.assert_not_called()
