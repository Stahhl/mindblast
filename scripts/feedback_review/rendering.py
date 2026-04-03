"""Report payload and markdown rendering for weekly feedback review."""

from __future__ import annotations

import datetime as dt
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from quiz_forge.ai.types import AIProviderDiagnostics

from .types import WeeklyFeedbackAggregate


def build_weekly_report_stem(window_end_date: dt.date) -> tuple[str, str]:
    iso_year, iso_week, _ = window_end_date.isocalendar()
    year_dir = f"{iso_year}"
    stem = f"{iso_year}-W{iso_week:02d}"
    return year_dir, stem


def build_weekly_report_payload(
    *,
    aggregate: WeeklyFeedbackAggregate,
    generated_at: str,
    llm_summary: dict[str, Any] | None,
    ai_unavailable_reason: str | None = None,
    ai_diagnostics: AIProviderDiagnostics | None = None,
) -> dict[str, Any]:
    questions = [
        {
            "quiz_file": summary.quiz_file,
            "date": summary.date,
            "quiz_type": summary.quiz_type,
            "edition": summary.edition,
            "question_id": summary.question_id,
            "question_human_id": summary.question_human_id,
            "question_prompt": summary.question_prompt,
            "choice_labels": list(summary.choice_labels),
            "submission_count": summary.submission_count,
            "average_rating": summary.average_rating,
            "latest_feedback_at": summary.latest_feedback_at,
            "ratings_histogram": summary.ratings_histogram,
            "sanitized_excerpts": list(summary.sanitized_excerpts),
            "issue_tags": list(summary.issue_tags),
        }
        for summary in aggregate.question_summaries
    ]
    payload = {
        "metadata": {
            "version": 1,
            "generated_at": generated_at,
        },
        "window": {
            "start_date": aggregate.window.start_date_iso,
            "end_date": aggregate.window.end_date_iso,
        },
        "aggregates": {
            "total_submissions": aggregate.total_submissions,
            "ratings_histogram": aggregate.ratings_histogram,
            "commented_submissions": aggregate.commented_submissions,
            "question_count": len(aggregate.question_summaries),
            "issue_counts": aggregate.issue_counts,
        },
        "questions": questions,
        "llm_summary": llm_summary,
        "ai_unavailable_reason": ai_unavailable_reason,
    }
    if ai_diagnostics is not None:
        payload["ai_diagnostics"] = ai_diagnostics.to_report_payload()
    return payload


def render_weekly_report_markdown(
    *,
    aggregate: WeeklyFeedbackAggregate,
    generated_at: str,
    llm_summary: dict[str, Any] | None,
    ai_unavailable_reason: str | None = None,
    ai_diagnostics: AIProviderDiagnostics | None = None,
) -> str:
    lines = [
        "# Weekly Feedback Review",
        "",
        f"- Window: `{aggregate.window.start_date_iso}` to `{aggregate.window.end_date_iso}`",
        f"- Generated at: `{generated_at}`",
        f"- Total submissions: `{aggregate.total_submissions}`",
        f"- Commented submissions: `{aggregate.commented_submissions}`",
        f"- Ratings histogram: `{json.dumps(aggregate.ratings_histogram, sort_keys=True)}`",
        "",
    ]

    if llm_summary is None:
        lines.extend(
            [
                "## AI Summary",
                "",
                f"AI summary unavailable: `{ai_unavailable_reason or 'not_requested'}`",
            ]
        )
        if ai_diagnostics is not None:
            lines.append(
                "Diagnostics: "
                f"`provider={ai_diagnostics.provider}` "
                f"`model={ai_diagnostics.model}` "
                f"`failure={ai_diagnostics.failure_label}` "
                f"`retry_attempted={str(ai_diagnostics.retry_attempted).lower()}` "
                f"`retry_count={ai_diagnostics.retry_count}` "
                f"`summary={ai_diagnostics.last_error_summary}`"
            )
        lines.append("")
    else:
        lines.extend(
            [
                "## AI Summary",
                "",
                str(llm_summary.get("executive_summary", "")).strip() or "No executive summary.",
                "",
            ]
        )
        for heading, key in (
            ("Themes", "themes"),
            ("Positive Signals", "positive_signals"),
        ):
            lines.append(f"### {heading}")
            lines.append("")
            values = llm_summary.get(key)
            if isinstance(values, list) and values:
                for value in values:
                    lines.append(f"- {value}")
            else:
                lines.append("- None")
            lines.append("")

        lines.append("### Questions To Review")
        lines.append("")
        questions_to_review = llm_summary.get("questions_to_review")
        if isinstance(questions_to_review, list) and questions_to_review:
            for item in questions_to_review:
                if isinstance(item, dict):
                    ref = str(item.get("question_human_id", "unknown"))
                    reason = str(item.get("reason", "")).strip() or "No reason provided."
                    lines.append(f"- `{ref}`: {reason}")
        else:
            lines.append("- None")
        lines.append("")

        lines.append("### Action Items")
        lines.append("")
        action_items = llm_summary.get("action_items")
        if isinstance(action_items, list) and action_items:
            for item in action_items:
                if isinstance(item, dict):
                    title = str(item.get("title", "")).strip() or "Untitled"
                    detail = str(item.get("detail", "")).strip() or "No detail provided."
                    priority = str(item.get("priority", "unspecified")).strip()
                    lines.append(f"- `{priority}` {title}: {detail}")
        else:
            lines.append("- None")
        lines.append("")

    lines.extend(["## Questions", ""])
    for summary in aggregate.question_summaries:
        lines.extend(
            [
                f"### {summary.question_human_id}",
                "",
                f"- Question ID: `{summary.question_id}`",
                f"- Quiz file: `{summary.quiz_file}`",
                f"- Quiz type: `{summary.quiz_type}`",
                f"- Date / edition: `{summary.date}` / `{summary.edition}`",
                f"- Prompt: {summary.question_prompt}",
                f"- Choices: {', '.join(f'`{label}`' for label in summary.choice_labels) if summary.choice_labels else 'None'}",
                f"- Submission count: `{summary.submission_count}`",
                f"- Average rating: `{summary.average_rating}`",
                f"- Latest feedback at: `{summary.latest_feedback_at}`",
                f"- Ratings histogram: `{json.dumps(summary.ratings_histogram, sort_keys=True)}`",
                "",
                "Sanitized excerpts:",
            ]
        )
        if summary.sanitized_excerpts:
            for excerpt in summary.sanitized_excerpts:
                lines.append(f"- {excerpt}")
        else:
            lines.append("- None")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_text_file(path: Path, body: str, *, prefix: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=prefix,
        delete=False,
    ) as temp_file:
        temp_file.write(body)
        temp_path = Path(temp_file.name)
    os.replace(temp_path, path)
