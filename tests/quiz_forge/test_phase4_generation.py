from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path

import pytest

from quiz_forge.ai.types import AIJsonTaskResponse, AIUsage
from quiz_forge.discovery import write_discovery_artifacts
from quiz_forge.storage import (
    build_output_path,
    list_quiz_records_for_date_type,
    write_quiz_file,
)


def _minimal_quiz_payload(
    *,
    target_date: dt.date,
    quiz_type: str,
    edition: int,
    mode: str,
    generated_at: str,
) -> dict[str, object]:
    return {
        "date": target_date.isoformat(),
        "type": quiz_type,
        "generation": {
            "mode": mode,
            "edition": edition,
            "generated_at": generated_at,
        },
        "source": {
            "retrieved_at": generated_at,
        },
    }


def _sample_candidates() -> list[dict[str, object]]:
    return [
        {"text": "Event A", "year": 1901, "wikipedia_url": "https://example.com/a"},
        {"text": "Event B", "year": 1908, "wikipedia_url": "https://example.com/b"},
        {"text": "Event C", "year": 1915, "wikipedia_url": "https://example.com/c"},
        {"text": "Event D", "year": 1922, "wikipedia_url": "https://example.com/d"},
        {"text": "Event E", "year": 1929, "wikipedia_url": "https://example.com/e"},
        {"text": "Event F", "year": 1936, "wikipedia_url": "https://example.com/f"},
        {"text": "Event G", "year": 1943, "wikipedia_url": "https://example.com/g"},
        {"text": "Event H", "year": 1950, "wikipedia_url": "https://example.com/h"},
    ]


def test_build_output_path_includes_edition() -> None:
    target_date = dt.date(2026, 2, 26)
    first = build_output_path("quizzes", target_date, "history_mcq_4", 1)
    second = build_output_path("quizzes", target_date, "history_mcq_4", 2)
    assert first != second


def test_write_discovery_artifacts_supports_multiple_editions(tmp_path) -> None:
    quizzes_dir = tmp_path / "quizzes"
    target_date = dt.date(2026, 2, 26)

    history_daily = build_output_path(quizzes_dir.as_posix(), target_date, "history_mcq_4", 1)
    history_extra = build_output_path(quizzes_dir.as_posix(), target_date, "history_mcq_4", 2)
    first_daily = build_output_path(quizzes_dir.as_posix(), target_date, "which_came_first", 1)

    write_quiz_file(
        history_daily,
        _minimal_quiz_payload(
            target_date=target_date,
            quiz_type="history_mcq_4",
            edition=1,
            mode="daily",
            generated_at="2026-02-26T06:00:00Z",
        ),
    )
    write_quiz_file(
        history_extra,
        _minimal_quiz_payload(
            target_date=target_date,
            quiz_type="history_mcq_4",
            edition=2,
            mode="extra",
            generated_at="2026-02-26T06:20:00Z",
        ),
    )
    write_quiz_file(
        first_daily,
        _minimal_quiz_payload(
            target_date=target_date,
            quiz_type="which_came_first",
            edition=1,
            mode="daily",
            generated_at="2026-02-26T06:00:00Z",
        ),
    )

    before_cwd = Path.cwd()
    try:
        # discovery uses cwd to derive repository-relative paths
        os.chdir(tmp_path)
        changed = write_discovery_artifacts(
            output_dir=quizzes_dir.as_posix(),
            target_date=target_date,
            generated_now=True,
        )
    finally:
        os.chdir(before_cwd)

    assert len(changed) == 2

    index_payload = json.loads((quizzes_dir / "index" / "2026-02-26.json").read_text(encoding="utf-8"))
    latest_payload = json.loads((quizzes_dir / "latest.json").read_text(encoding="utf-8"))

    assert index_payload["metadata"]["version"] == 2
    assert len(index_payload["quizzes_by_type"]["history_mcq_4"]) == 2
    assert index_payload["quiz_files"]["history_mcq_4"] == index_payload["quizzes_by_type"]["history_mcq_4"][0]["quiz_file"]
    assert latest_payload["metadata"]["version"] == 2
    assert latest_payload["latest_quiz_by_type"]["history_mcq_4"] == index_payload["quizzes_by_type"]["history_mcq_4"][-1][
        "quiz_file"
    ]


def test_cli_extra_mode_generates_multiple_same_day_editions(monkeypatch, tmp_path) -> None:
    from quiz_forge import cli

    target_date = "2026-02-26"
    output_dir = (tmp_path / "quizzes").as_posix()

    monkeypatch.setattr(cli, "fetch_json", lambda *_args, **_kwargs: {"events": []})
    monkeypatch.setattr(cli, "extract_candidates", lambda _payload: _sample_candidates())
    monkeypatch.setenv("AI_MODE", "off")
    monkeypatch.setenv("QUIZ_FORGE_AI_REPORT_PATH", (tmp_path / "ai-report.json").as_posix())

    daily_args = argparse.Namespace(
        date=target_date,
        quiz_types="history_mcq_4",
        output_dir=output_dir,
        timeout=1,
        retries=1,
        mode="daily",
        count=1,
    )
    monkeypatch.setattr(cli, "parse_args", lambda: daily_args)
    assert cli.main() == 0

    extra_args = argparse.Namespace(
        date=target_date,
        quiz_types="history_mcq_4",
        output_dir=output_dir,
        timeout=1,
        retries=1,
        mode="extra",
        count=2,
    )
    monkeypatch.setattr(cli, "parse_args", lambda: extra_args)
    assert cli.main() == 0

    records = list_quiz_records_for_date_type(
        output_dir=output_dir,
        target_date=dt.date.fromisoformat(target_date),
        quiz_type="history_mcq_4",
    )
    assert [record.edition for record in records] == [1, 2, 3]


def test_extra_mode_requires_daily_edition_first(tmp_path) -> None:
    from quiz_forge.cli import _build_generation_plan

    with pytest.raises(ValueError):
        _build_generation_plan(
            output_dir=(tmp_path / "quizzes").as_posix(),
            target_date=dt.date(2026, 2, 26),
            quiz_types=["history_mcq_4"],
            mode="extra",
            count=1,
        )


def test_cli_generates_history_factoid_mcq(monkeypatch, tmp_path) -> None:
    from quiz_forge import cli

    target_date = "2026-02-26"
    output_dir = (tmp_path / "quizzes").as_posix()

    monkeypatch.setattr(cli, "fetch_json", lambda *_args, **_kwargs: {"events": []})
    monkeypatch.setattr(cli, "extract_candidates", lambda _payload: _sample_candidates())
    monkeypatch.setenv("AI_MODE", "off")
    monkeypatch.setenv("QUIZ_FORGE_AI_REPORT_PATH", (tmp_path / "ai-report.json").as_posix())

    args = argparse.Namespace(
        date=target_date,
        quiz_types="history_factoid_mcq_4",
        output_dir=output_dir,
        timeout=1,
        retries=1,
        mode="daily",
        count=1,
    )
    monkeypatch.setattr(cli, "parse_args", lambda: args)
    assert cli.main() == 0

    records = list_quiz_records_for_date_type(
        output_dir=output_dir,
        target_date=dt.date.fromisoformat(target_date),
        quiz_type="history_factoid_mcq_4",
    )
    assert [record.edition for record in records] == [1]
    payload = records[0].payload
    assert payload["type"] == "history_factoid_mcq_4"
    assert isinstance(payload.get("question"), str) and payload["question"].endswith("?")
    assert len(payload["choices"]) == 4
    assert all("year" not in choice for choice in payload["choices"])
    facets = payload["questions"][0]["facets"]
    assert facets["question_format"] == "factoid"
    assert facets["answer_kind"] == "time"
    assert facets["prompt_style"] == "when"


def test_cli_applies_factoid_ai_pipeline_when_enabled(monkeypatch, tmp_path, mocker) -> None:
    from quiz_forge import cli

    target_date = "2026-02-26"
    output_dir = (tmp_path / "quizzes").as_posix()

    monkeypatch.setattr(cli, "fetch_json", lambda *_args, **_kwargs: {"events": []})
    monkeypatch.setattr(cli, "extract_candidates", lambda _payload: _sample_candidates())
    monkeypatch.setenv("AI_MODE", "on")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_MODEL", "gpt-5-mini")
    monkeypatch.setenv("AI_MAX_CALLS_PER_RUN", "8")
    monkeypatch.setenv("FACTOID_AI_PIPELINE_ENABLED", "true")
    monkeypatch.setenv("QUIZ_FORGE_AI_REPORT_PATH", (tmp_path / "ai-report.json").as_posix())

    def fake_run_json_task(*args, **kwargs) -> AIJsonTaskResponse:  # noqa: ANN002,ANN003
        del args
        user_payload = kwargs["user_payload"]
        task = user_payload.get("task")
        if task == "factoid_question_generation":
            payload = {"candidates": [{"question": "When was this event officially recognized?", "score": 0.95}]}
        elif task == "factoid_question_rank":
            payload = {"best_index": 0, "best_score": 0.95}
        elif task == "factoid_distractor_label_generation":
            choices = user_payload.get("choices", [])
            labels_by_id = {
                choice["id"]: ("1901" if choice.get("is_correct") else f"Distractor {idx + 1}")
                for idx, choice in enumerate(choices)
                if isinstance(choice, dict) and isinstance(choice.get("id"), str)
            }
            payload = {"choice_labels_by_id": labels_by_id}
        elif task == "factoid_final_judge":
            payload = {"final_score": 0.99, "publishable": True}
        else:
            raise AssertionError(f"Unexpected task: {task}")

        return AIJsonTaskResponse(
            payload=payload,
            provider="openai",
            model="gpt-5-mini",
            usage=AIUsage(input_tokens=20, output_tokens=10, estimated_cost_usd=0.0),
        )

    run_json_mock = mocker.patch(
        "quiz_forge.ai.providers.openai.OpenAIProvider.run_json_task",
        side_effect=fake_run_json_task,
    )

    args = argparse.Namespace(
        date=target_date,
        quiz_types="history_factoid_mcq_4",
        output_dir=output_dir,
        timeout=1,
        retries=1,
        mode="daily",
        count=1,
    )
    monkeypatch.setattr(cli, "parse_args", lambda: args)
    assert cli.main() == 0
    assert run_json_mock.call_count == 4

    records = list_quiz_records_for_date_type(
        output_dir=output_dir,
        target_date=dt.date.fromisoformat(target_date),
        quiz_type="history_factoid_mcq_4",
    )
    payload = records[0].payload
    assert payload["question"] == "When was this event officially recognized?"
    assert payload["metadata"]["generation_method"] == "ai_native_factoid_v1"
