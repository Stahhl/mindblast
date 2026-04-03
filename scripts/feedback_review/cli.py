"""CLI for weekly feedback review report generation."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any

from quiz_forge.ai import AIOrchestrator, load_ai_settings

from .aggregation import aggregate_feedback_submissions
from .firestore_reader import FirestoreFeedbackReader, parse_feedback_submission
from .rendering import (
    build_weekly_report_payload,
    build_weekly_report_stem,
    render_weekly_report_markdown,
    write_text_file,
)
from .summarization import summarize_weekly_feedback
from .types import FeedbackSubmission
from .window import build_previous_completed_days_window


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate weekly internal feedback review reports.")
    parser.add_argument("--content-repo-root", default="../mindblast-content")
    parser.add_argument("--run-date", default=None, help="UTC run date (YYYY-MM-DD). Defaults to today in UTC.")
    parser.add_argument("--feedback-json", default=None, help="Optional local JSON fixture file for feedback records.")
    parser.add_argument("--firestore-project-id", default=None)
    parser.add_argument("--firestore-credentials-path", default=None)
    parser.add_argument("--firestore-collection", default="quiz_feedback")
    parser.add_argument("--disable-ai", action="store_true")
    return parser.parse_args()


def _parse_run_date(value: str | None) -> dt.date:
    if value is None:
        return dt.datetime.now(dt.timezone.utc).date()
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid --run-date value '{value}'. Expected YYYY-MM-DD.") from exc


def _load_feedback_fixture(path: Path) -> list[FeedbackSubmission]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("feedback fixture must be a JSON array")
    submissions: list[FeedbackSubmission] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"feedback fixture entry {index} must be an object")
        submissions.append(parse_feedback_submission(f"fixture-{index + 1}", item))
    submissions.sort(key=lambda item: (item.feedback_date_utc, item.updated_at, item.feedback_id))
    return submissions


def _write_report_outputs(
    *,
    content_repo_root: Path,
    aggregate: Any,
    markdown_body: str,
    json_payload: dict[str, Any],
) -> tuple[Path, Path]:
    year_dir, stem = build_weekly_report_stem(aggregate.window.end_date)
    report_root = content_repo_root / "reports" / "feedback" / "weekly" / year_dir
    markdown_path = report_root / f"{stem}.md"
    json_path = report_root / f"{stem}.json"
    write_text_file(markdown_path, markdown_body, prefix=".tmp-feedback-report-")
    write_text_file(json_path, json.dumps(json_payload, ensure_ascii=True, indent=2) + "\n", prefix=".tmp-feedback-report-")
    return markdown_path, json_path


def _resolve_ai_state_dir() -> Path:
    raw = os.getenv("FEEDBACK_REVIEW_AI_STATE_DIR", ".tmp/feedback-review-ai").strip()
    if not raw:
        raw = ".tmp/feedback-review-ai"
    return Path(raw)


def main() -> int:
    args = parse_args()
    run_date = _parse_run_date(args.run_date)
    content_repo_root = Path(args.content_repo_root)
    window = build_previous_completed_days_window(run_date)

    if args.feedback_json:
        submissions = _load_feedback_fixture(Path(args.feedback_json))
    else:
        reader = FirestoreFeedbackReader(
            project_id=args.firestore_project_id,
            credentials_path=args.firestore_credentials_path,
            collection_name=args.firestore_collection,
        )
        submissions = reader.list_feedback_for_window(window)

    if not submissions:
        print(
            f"No production feedback found for window {window.start_date_iso} to {window.end_date_iso}; skipping report."
        )
        return 0

    aggregate = aggregate_feedback_submissions(
        submissions=submissions,
        content_repo_root=content_repo_root.as_posix(),
        window=window,
    )
    generated_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    llm_summary: dict[str, Any] | None = None
    ai_unavailable_reason: str | None = None
    ai_diagnostics = None
    ai_orchestrator: AIOrchestrator | None = None
    if not args.disable_ai:
        ai_settings = load_ai_settings(output_dir=_resolve_ai_state_dir().as_posix())
        ai_orchestrator = AIOrchestrator(settings=ai_settings, target_date=run_date)
        llm_summary, ai_unavailable_reason, ai_diagnostics = summarize_weekly_feedback(
            aggregate=aggregate,
            ai_orchestrator=ai_orchestrator,
        )
        ai_orchestrator.finalize()
        ai_orchestrator.write_report()

    markdown_body = render_weekly_report_markdown(
        aggregate=aggregate,
        generated_at=generated_at,
        llm_summary=llm_summary,
        ai_unavailable_reason=ai_unavailable_reason,
        ai_diagnostics=ai_diagnostics,
    )
    json_payload = build_weekly_report_payload(
        aggregate=aggregate,
        generated_at=generated_at,
        llm_summary=llm_summary,
        ai_unavailable_reason=ai_unavailable_reason,
        ai_diagnostics=ai_diagnostics,
    )
    markdown_path, json_path = _write_report_outputs(
        content_repo_root=content_repo_root,
        aggregate=aggregate,
        markdown_body=markdown_body,
        json_payload=json_payload,
    )
    print(f"Wrote weekly feedback markdown report: {markdown_path}")
    print(f"Wrote weekly feedback JSON report: {json_path}")
    return 0
