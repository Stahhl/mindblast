from __future__ import annotations

import argparse
from pathlib import Path

from quiz_forge.ai.types import AIRerankResponse, AIUsage


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


def _patch_cli_args(monkeypatch, tmp_path: Path) -> None:
    from quiz_forge import cli

    args = argparse.Namespace(
        date="2026-02-25",
        quiz_types="which_came_first,history_mcq_4",
        output_dir=(tmp_path / "quizzes").as_posix(),
        timeout=1,
        retries=1,
        mode="daily",
        count=1,
        daily_editions_by_type="which_came_first=1,history_mcq_4=1,history_factoid_mcq_4=3,geography_factoid_mcq_4=1",
        backfill_human_ids=False,
    )
    monkeypatch.setattr(cli, "parse_args", lambda: args)


def _patch_cli_source(monkeypatch) -> None:
    from quiz_forge import cli

    monkeypatch.setattr(cli, "fetch_json", lambda *_args, **_kwargs: {"events": []})
    monkeypatch.setattr(cli, "extract_candidates", lambda _payload: _sample_candidates())


def test_cli_calls_openai_rerank_for_history_mcq(monkeypatch, tmp_path, mocker) -> None:
    from quiz_forge import cli

    _patch_cli_args(monkeypatch, tmp_path)
    _patch_cli_source(monkeypatch)

    monkeypatch.setenv("AI_MODE", "shadow")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_MODEL", "gpt-5-mini")
    monkeypatch.setenv("QUIZ_FORGE_AI_REPORT_PATH", (tmp_path / "ai-report.json").as_posix())

    rerank_mock = mocker.patch(
        "quiz_forge.ai.providers.openai.OpenAIProvider.rerank_distractors",
        return_value=AIRerankResponse(
            ranked_distractor_ids=[],
            reason_codes=["test"],
            provider="openai",
            model="gpt-5-mini",
            usage=AIUsage(),
        ),
    )

    exit_code = cli.main()

    assert exit_code == 0
    assert rerank_mock.call_count == 1
    assert (tmp_path / "quizzes" / "latest.json").exists()
    assert (tmp_path / "ai-report.json").exists()


def test_cli_does_not_call_openai_when_ai_mode_off(monkeypatch, tmp_path, mocker) -> None:
    from quiz_forge import cli

    _patch_cli_args(monkeypatch, tmp_path)
    _patch_cli_source(monkeypatch)

    monkeypatch.setenv("AI_MODE", "off")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_MODEL", "gpt-5-mini")
    monkeypatch.setenv("QUIZ_FORGE_AI_REPORT_PATH", (tmp_path / "ai-report.json").as_posix())

    rerank_mock = mocker.patch("quiz_forge.ai.providers.openai.OpenAIProvider.rerank_distractors")

    exit_code = cli.main()

    assert exit_code == 0
    rerank_mock.assert_not_called()
    assert (tmp_path / "ai-report.json").exists()
