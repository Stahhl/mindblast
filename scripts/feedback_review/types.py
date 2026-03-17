"""Typed models for weekly feedback review."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass


@dataclass(frozen=True)
class WeeklyWindow:
    start_date: dt.date
    end_date: dt.date

    @property
    def start_date_iso(self) -> str:
        return self.start_date.isoformat()

    @property
    def end_date_iso(self) -> str:
        return self.end_date.isoformat()


@dataclass(frozen=True)
class FeedbackSubmission:
    feedback_id: str
    quiz_file: str
    date: str
    quiz_type: str
    edition: int
    question_id: str
    question_human_id: str
    rating: int
    feedback_date_utc: str
    created_at: str
    updated_at: str
    comment: str | None = None


@dataclass(frozen=True)
class QuizCardContext:
    quiz_file: str
    date: str
    quiz_type: str
    edition: int
    question_id: str
    question_human_id: str | None
    question_prompt: str
    choice_labels: tuple[str, ...]


@dataclass(frozen=True)
class QuestionFeedbackSummary:
    quiz_file: str
    date: str
    quiz_type: str
    edition: int
    question_id: str
    question_human_id: str
    question_prompt: str
    choice_labels: tuple[str, ...]
    submission_count: int
    average_rating: float
    latest_feedback_at: str
    ratings_histogram: dict[int, int]
    sanitized_excerpts: tuple[str, ...]


@dataclass(frozen=True)
class WeeklyFeedbackAggregate:
    window: WeeklyWindow
    total_submissions: int
    ratings_histogram: dict[int, int]
    commented_submissions: int
    question_summaries: tuple[QuestionFeedbackSummary, ...]
