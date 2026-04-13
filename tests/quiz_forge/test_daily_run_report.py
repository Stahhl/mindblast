from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from quiz_forge.daily_run_report import (
    build_daily_run_report,
    build_daily_run_report_path,
    classify_content_changes,
    write_daily_run_report,
)


def test_build_daily_run_report_path_is_timestamped_per_run() -> None:
    path = build_daily_run_report_path(
        generated_at=dt.datetime(2026, 3, 18, 7, 12, 13, tzinfo=dt.timezone.utc),
        run_id="123456789",
    )
    assert path == "reports/quiz-forge/daily/2026/03/18/2026-03-18T07-12-13Z-run-123456789.json"


def test_classify_content_changes_splits_quiz_and_discovery_artifacts() -> None:
    classification = classify_content_changes(
        [
            "quizzes/abc.json",
            "quizzes/def.json",
            "quizzes/index/2026-03-18.json",
            "quizzes/latest.json",
            "quizzes/human_id_lookup.json",
        ]
    )

    assert classification["generated_quiz_files"] == ["quizzes/abc.json", "quizzes/def.json"]
    assert classification["generated_index_files"] == [
        "quizzes/index/2026-03-18.json",
        "quizzes/latest.json",
    ]
    assert classification["quiz_files_changed"] is True
    assert classification["discovery_files_changed"] is True
    assert classification["human_id_lookup_updated"] is True


def test_build_daily_run_report_uses_raw_ai_payload_and_renders_discord_text(tmp_path: Path) -> None:
    raw_report_path = tmp_path / "raw.json"
    raw_report_path.write_text(
        json.dumps(
            {
                "date_utc": "2026-03-18",
                "ai_mode": "shadow",
                "provider": "openai",
                "model": "gpt-5-mini",
                "calls_total": 1,
                "input_tokens_total": 11,
                "output_tokens_total": 22,
                "run_estimated_cost_usd": 0.123,
                "day_spend_usd": 0.456,
                "month_spend_usd": 0.789,
                "day_limit_usd": 1.0,
                "month_limit_usd": 5.0,
                "fallback_count": 2,
                "fallback_reasons": ["foo:1", "bar:1"],
                "quality": {
                    "lint_failure_count": 1,
                    "lint_failures": ["prompt_leak_year"],
                    "fallback_count": 2,
                    "fallback_paths": ["history_mcq_4:alternate_correct_event"],
                    "factoid_final_subtypes": ["time"],
                    "ai_quality_rejection_count": 1,
                    "typed_candidate_rejections": ["factoid_typed_candidate_review_no_supported_candidates:1"],
                    "ai_distractor_rejection_lints": ["mixed_entity_types:1"],
                    "ai_stage_failures": ["page_context_fetch_failed:1"],
                    "page_context_fetch_count": 4,
                    "popularity_enriched_count": 7,
                    "popularity_neutral_count": 1,
                    "popularity_fallback_reasons": ["TimeoutError:1"],
                    "selected_popularity_score_avg": 0.812,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    report_path, report = build_daily_run_report(
        raw_report_path=raw_report_path,
        generated_at=dt.datetime(2026, 3, 18, 7, 12, 13, tzinfo=dt.timezone.utc),
        workflow="Daily Quiz Generation",
        repository="Stahhl/mindblast",
        run_id="123",
        run_attempt="2",
        run_url="https://example.invalid/run/123",
        job_status="success",
        trigger="workflow_dispatch",
        target_date="2026-03-18",
        quiz_types=["which_came_first", "history_mcq_4"],
        mode="extra",
        count="2",
        daily_editions_by_type={
            "which_came_first": 1,
            "history_mcq_4": 1,
            "history_factoid_mcq_4": 3,
            "geography_factoid_mcq_4": 1,
        },
        changed_paths=[
            "quizzes/abc.json",
            "quizzes/index/2026-03-18.json",
            "quizzes/latest.json",
        ],
        content_repo="Stahhl/mindblast-content",
        content_repo_ref="main",
        content_repo_commit_before="abc123",
    )

    assert report_path == "reports/quiz-forge/daily/2026/03/18/2026-03-18T07-12-13Z-run-123.json"
    assert report["repository"] == "Stahhl/mindblast"
    assert report["request"]["quiz_types"] == ["which_came_first", "history_mcq_4"]
    assert report["request"]["daily_editions_by_type"]["history_factoid_mcq_4"] == 3
    assert report["request"]["daily_editions_by_type"]["geography_factoid_mcq_4"] == 1
    assert report["artifact_outcomes"]["generated_quiz_files"] == ["quizzes/abc.json"]
    assert report["artifact_outcomes"]["content_repo_commit_occurred"] is True
    assert report["artifact_outcomes"]["content_repo_commit_after"] is None
    assert "quality:" in report["discord_message_text"]
    assert "typed candidate rejections: factoid_typed_candidate_review_no_supported_candidates:1" in report["discord_message_text"]
    assert "ai distractor rejection lints: mixed_entity_types:1" in report["discord_message_text"]
    assert "popularity enriched/neutral: 7/1" in report["discord_message_text"]
    assert "popularity fallbacks: TimeoutError:1" in report["discord_message_text"]
    assert "selected popularity avg: 0.812" in report["discord_message_text"]
    assert "artifacts:" in report["discord_message_text"]
    assert "mode/count: extra/2" in report["discord_message_text"]
    assert (
        "daily editions: geography_factoid_mcq_4=1, history_factoid_mcq_4=3, history_mcq_4=1, which_came_first=1"
        in report["discord_message_text"]
    )


def test_build_daily_run_report_tolerates_missing_raw_report_on_failure(tmp_path: Path) -> None:
    report_path, report = build_daily_run_report(
        raw_report_path=tmp_path / "missing.json",
        generated_at=dt.datetime(2026, 3, 18, 7, 12, 13, tzinfo=dt.timezone.utc),
        workflow="Daily Quiz Generation",
        repository="Stahhl/mindblast",
        run_id="456",
        run_attempt="1",
        run_url="https://example.invalid/run/456",
        job_status="failure",
        trigger="schedule",
        target_date="2026-03-18",
        quiz_types=["history_factoid_mcq_4"],
        mode="daily",
        count="1",
        daily_editions_by_type={"history_factoid_mcq_4": 3},
        changed_paths=[],
        content_repo="Stahhl/mindblast-content",
        content_repo_ref="main",
        content_repo_commit_before="def456",
    )

    assert report_path.endswith("run-456.json")
    assert report["ai_mode"] is None
    assert report["fallback_reasons"] == []
    assert report["quality"]["lint_failures"] == []
    assert "FAILURE" in report["discord_message_text"]
    assert "content repo commit: yes" in report["discord_message_text"]


def test_write_daily_run_report_persists_json(tmp_path: Path) -> None:
    _, report = build_daily_run_report(
        raw_report_path=None,
        generated_at=dt.datetime(2026, 3, 18, 7, 12, 13, tzinfo=dt.timezone.utc),
        workflow="Daily Quiz Generation",
        repository="Stahhl/mindblast",
        run_id="789",
        run_attempt="1",
        run_url="https://example.invalid/run/789",
        job_status="success",
        trigger="schedule",
        target_date="2026-03-18",
        quiz_types=["which_came_first"],
        mode="daily",
        count="1",
        daily_editions_by_type={"which_came_first": 1},
        changed_paths=["quizzes/example.json"],
        content_repo="Stahhl/mindblast-content",
        content_repo_ref="main",
        content_repo_commit_before="ghi789",
    )

    written = write_daily_run_report(
        content_repo_root=tmp_path,
        report_path="reports/quiz-forge/daily/2026/03/18/example.json",
        report=report,
    )

    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["report_version"] == 1
    assert payload["artifact_outcomes"]["generated_quiz_files"] == ["quizzes/example.json"]
