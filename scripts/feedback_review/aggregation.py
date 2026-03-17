"""Deterministic aggregation for weekly feedback review."""

from __future__ import annotations

from collections import defaultdict

from .quiz_context import load_quiz_card_context
from .sanitize import sanitize_comment_text
from .types import FeedbackSubmission, QuestionFeedbackSummary, WeeklyFeedbackAggregate, WeeklyWindow


def _empty_histogram() -> dict[int, int]:
    return {rating: 0 for rating in range(1, 6)}


def aggregate_feedback_submissions(
    *,
    submissions: list[FeedbackSubmission],
    content_repo_root: str,
    window: WeeklyWindow,
) -> WeeklyFeedbackAggregate:
    ratings_histogram = _empty_histogram()
    commented_submissions = 0
    grouped: dict[tuple[str, str], list[FeedbackSubmission]] = defaultdict(list)

    for submission in submissions:
        ratings_histogram[submission.rating] = ratings_histogram.get(submission.rating, 0) + 1
        if sanitize_comment_text(submission.comment) is not None:
            commented_submissions += 1
        grouped[(submission.quiz_file, submission.question_id)].append(submission)

    question_summaries: list[QuestionFeedbackSummary] = []
    for (_quiz_file, _question_id), grouped_submissions in grouped.items():
        ordered_submissions = sorted(
            grouped_submissions,
            key=lambda item: (item.updated_at, item.created_at, item.feedback_id),
        )
        first_submission = ordered_submissions[0]
        context = load_quiz_card_context(
            content_repo_root=content_repo_root,
            quiz_file=first_submission.quiz_file,
            question_id=first_submission.question_id,
            question_human_id=first_submission.question_human_id,
        )
        question_histogram = _empty_histogram()
        excerpt_candidates: list[str] = []
        for submission in ordered_submissions:
            question_histogram[submission.rating] = question_histogram.get(submission.rating, 0) + 1
            sanitized = sanitize_comment_text(submission.comment)
            if sanitized is not None:
                excerpt_candidates.append(sanitized)

        unique_excerpts = tuple(dict.fromkeys(excerpt_candidates).keys())
        average_rating = sum(item.rating for item in ordered_submissions) / len(ordered_submissions)
        latest_feedback_at = max(item.updated_at for item in ordered_submissions)

        question_summaries.append(
            QuestionFeedbackSummary(
                quiz_file=context.quiz_file,
                date=context.date,
                quiz_type=context.quiz_type,
                edition=context.edition,
                question_id=context.question_id,
                question_human_id=context.question_human_id or first_submission.question_human_id,
                question_prompt=context.question_prompt,
                choice_labels=context.choice_labels,
                submission_count=len(ordered_submissions),
                average_rating=round(average_rating, 3),
                latest_feedback_at=latest_feedback_at,
                ratings_histogram=question_histogram,
                sanitized_excerpts=unique_excerpts,
            )
        )

    question_summaries.sort(
        key=lambda item: (
            item.average_rating,
            -item.submission_count,
            -_timestamp_sort_key(item.latest_feedback_at),
            item.question_human_id,
            item.question_id,
        )
    )

    return WeeklyFeedbackAggregate(
        window=window,
        total_submissions=len(submissions),
        ratings_histogram=ratings_histogram,
        commented_submissions=commented_submissions,
        question_summaries=tuple(question_summaries),
    )


def _timestamp_sort_key(value: str) -> int:
    return int(value.replace("-", "").replace(":", "").replace("T", "").replace("Z", "").replace(".", ""))
