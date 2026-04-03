"""LLM summarization contract for weekly feedback review."""

from __future__ import annotations

from typing import Any

from quiz_forge.ai import AIOrchestrator
from quiz_forge.ai.types import AIProviderDiagnostics

from .types import WeeklyFeedbackAggregate


def _weekly_feedback_response_schema() -> dict[str, Any]:
    return {
        "name": "weekly_feedback_review",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "executive_summary",
                "themes",
                "positive_signals",
                "questions_to_review",
                "action_items",
            ],
            "properties": {
                "executive_summary": {"type": "string"},
                "themes": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "positive_signals": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "questions_to_review": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["question_human_id", "reason"],
                        "properties": {
                            "question_human_id": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                    },
                },
                "action_items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["title", "detail", "priority"],
                        "properties": {
                            "title": {"type": "string"},
                            "detail": {"type": "string"},
                            "priority": {
                                "type": "string",
                                "enum": ["low", "medium", "high"],
                            },
                        },
                    },
                },
            },
        },
    }


def _validate_summary_payload(payload: dict[str, Any]) -> dict[str, Any]:
    executive_summary = payload.get("executive_summary")
    themes = payload.get("themes")
    positive_signals = payload.get("positive_signals")
    questions_to_review = payload.get("questions_to_review")
    action_items = payload.get("action_items")

    if not isinstance(executive_summary, str) or not executive_summary.strip():
        raise ValueError("executive_summary must be a non-empty string.")
    if not isinstance(themes, list) or not all(isinstance(item, str) and item.strip() for item in themes):
        raise ValueError("themes must be a non-empty string list.")
    if not isinstance(positive_signals, list) or not all(
        isinstance(item, str) and item.strip() for item in positive_signals
    ):
        raise ValueError("positive_signals must be a string list.")
    if not isinstance(questions_to_review, list):
        raise ValueError("questions_to_review must be a list.")
    for item in questions_to_review:
        if not isinstance(item, dict):
            raise ValueError("questions_to_review entries must be objects.")
        if not isinstance(item.get("question_human_id"), str) or not item["question_human_id"].strip():
            raise ValueError("questions_to_review.question_human_id must be a non-empty string.")
        if not isinstance(item.get("reason"), str) or not item["reason"].strip():
            raise ValueError("questions_to_review.reason must be a non-empty string.")
    if not isinstance(action_items, list):
        raise ValueError("action_items must be a list.")
    for item in action_items:
        if not isinstance(item, dict):
            raise ValueError("action_items entries must be objects.")
        if not isinstance(item.get("title"), str) or not item["title"].strip():
            raise ValueError("action_items.title must be a non-empty string.")
        if not isinstance(item.get("detail"), str) or not item["detail"].strip():
            raise ValueError("action_items.detail must be a non-empty string.")
        priority = item.get("priority")
        if priority not in {"low", "medium", "high"}:
            raise ValueError("action_items.priority must be low, medium, or high.")

    return {
        "executive_summary": executive_summary.strip(),
        "themes": [item.strip() for item in themes],
        "positive_signals": [item.strip() for item in positive_signals],
        "questions_to_review": [
            {
                "question_human_id": item["question_human_id"].strip(),
                "reason": item["reason"].strip(),
            }
            for item in questions_to_review
        ],
        "action_items": [
            {
                "title": item["title"].strip(),
                "detail": item["detail"].strip(),
                "priority": item["priority"],
            }
            for item in action_items
        ],
    }


def summarize_weekly_feedback(
    *,
    aggregate: WeeklyFeedbackAggregate,
    ai_orchestrator: AIOrchestrator,
) -> tuple[dict[str, Any] | None, str | None, AIProviderDiagnostics | None]:
    if not ai_orchestrator.is_enabled():
        return None, "ai_disabled", None

    question_summaries = [
        {
            "question_human_id": summary.question_human_id,
            "question_id": summary.question_id,
            "quiz_file": summary.quiz_file,
            "prompt": summary.question_prompt,
            "choices": list(summary.choice_labels),
            "submission_count": summary.submission_count,
            "average_rating": summary.average_rating,
            "latest_feedback_at": summary.latest_feedback_at,
            "ratings_histogram": summary.ratings_histogram,
            "sanitized_excerpts": list(summary.sanitized_excerpts),
            "issue_tags": list(summary.issue_tags),
        }
        for summary in aggregate.question_summaries
    ]
    response, reason = ai_orchestrator.run_json_task(
        task_name="weekly_feedback_review",
        system_prompt=(
            "You are reviewing internal quiz feedback for Mindblast. "
            "Summarize only the provided evidence. "
            "Do not invent missing user intent or propose automatic code changes. "
            "Return JSON only with executive_summary, themes, positive_signals, "
            "questions_to_review, and action_items."
        ),
        user_payload={
            "window": {
                "start_date": aggregate.window.start_date_iso,
                "end_date": aggregate.window.end_date_iso,
            },
            "aggregates": {
                "total_submissions": aggregate.total_submissions,
                "commented_submissions": aggregate.commented_submissions,
                "ratings_histogram": aggregate.ratings_histogram,
                "issue_counts": aggregate.issue_counts,
            },
            "question_summaries": question_summaries,
        },
        max_output_tokens=800,
        response_schema=_weekly_feedback_response_schema(),
    )
    if response is None:
        return None, reason, ai_orchestrator.last_json_task_failure_diagnostics
    try:
        return _validate_summary_payload(response), None, None
    except ValueError as exc:
        return None, f"summary_payload_invalid:{exc}", None
