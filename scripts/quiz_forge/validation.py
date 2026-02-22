"""Quiz payload validation."""

from __future__ import annotations

import datetime as dt
from typing import Any

from .constants import (
    QUIZ_TYPE_HISTORY_MCQ_4,
    QUIZ_TYPE_WHICH_CAME_FIRST,
    SUPPORTED_QUIZ_TYPES,
    WHICH_CAME_FIRST_QUESTION,
)


def validate_common_fields(quiz: dict[str, Any], target_date: dt.date) -> tuple[str, list[dict[str, Any]]]:
    if quiz.get("date") != target_date.isoformat():
        raise ValueError("Invalid date field.")

    if quiz.get("topics") != ["history"]:
        raise ValueError("topics must equal ['history'] in Phase 1.")

    quiz_type = quiz.get("type")
    if quiz_type not in SUPPORTED_QUIZ_TYPES:
        raise ValueError(f"type must be one of {SUPPORTED_QUIZ_TYPES}.")

    question = quiz.get("question")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be a non-empty string.")

    choices = quiz.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("choices must be a non-empty list.")

    ids: list[str] = []
    for choice in choices:
        if not isinstance(choice, dict):
            raise ValueError("each choice must be an object.")

        choice_id = choice.get("id")
        label = choice.get("label")

        if not isinstance(choice_id, str) or not choice_id.strip():
            raise ValueError("choice id must be a non-empty string.")
        if not isinstance(label, str) or not label.strip():
            raise ValueError("choice label must be a non-empty string.")

        ids.append(choice_id)

    if len(set(ids)) != len(ids):
        raise ValueError("choice ids must be unique.")

    correct_choice_id = quiz.get("correct_choice_id")
    if correct_choice_id not in ids:
        raise ValueError("correct_choice_id must match one of the choice ids.")

    source = quiz.get("source")
    if not isinstance(source, dict):
        raise ValueError("source must be an object.")

    for key in ("name", "url", "retrieved_at"):
        value = source.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"source.{key} must be a non-empty string.")

    events_used = source.get("events_used")
    if not isinstance(events_used, list) or len(events_used) < 2:
        raise ValueError("source.events_used must contain at least 2 entries.")

    for event in events_used:
        if not isinstance(event, dict):
            raise ValueError("source.events_used entries must be objects.")
        text = event.get("text")
        year = event.get("year")
        wikipedia_url = event.get("wikipedia_url")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("source.events_used.text must be a non-empty string.")
        if not isinstance(year, int):
            raise ValueError("source.events_used.year must be an integer.")
        if not isinstance(wikipedia_url, str) or not wikipedia_url.strip():
            raise ValueError("source.events_used.wikipedia_url must be a non-empty string.")

    metadata = quiz.get("metadata")
    if not isinstance(metadata, dict) or metadata.get("version") != 1:
        raise ValueError("metadata.version must be 1.")

    return quiz_type, choices


def validate_which_came_first_quiz(choices: list[dict[str, Any]], quiz: dict[str, Any]) -> None:
    if len(choices) != 2:
        raise ValueError("which_came_first choices must contain exactly 2 entries.")

    years: list[int] = []
    for choice in choices:
        year = choice.get("year")
        if not isinstance(year, int):
            raise ValueError("which_came_first choice year must be an integer.")
        years.append(year)

    if years[0] == years[1]:
        raise ValueError("which_came_first choice years must be distinct.")

    if quiz.get("question") != WHICH_CAME_FIRST_QUESTION:
        raise ValueError("which_came_first question text is invalid.")

    events_used = quiz["source"]["events_used"]
    if len(events_used) != 2:
        raise ValueError("which_came_first source.events_used must contain exactly 2 entries.")


def validate_history_mcq_4_quiz(choices: list[dict[str, Any]], quiz: dict[str, Any]) -> None:
    if len(choices) != 4:
        raise ValueError("history_mcq_4 choices must contain exactly 4 entries.")

    for choice in choices:
        if "year" in choice:
            raise ValueError("history_mcq_4 choices must not include year.")

    question = quiz.get("question")
    if not isinstance(question, str) or not question.startswith("Which event happened in "):
        raise ValueError("history_mcq_4 question text is invalid.")

    events_used = quiz["source"]["events_used"]
    if len(events_used) != 4:
        raise ValueError("history_mcq_4 source.events_used must contain exactly 4 entries.")


def validate_quiz(quiz: dict[str, Any], target_date: dt.date) -> None:
    quiz_type, choices = validate_common_fields(quiz, target_date)

    if quiz_type == QUIZ_TYPE_WHICH_CAME_FIRST:
        validate_which_came_first_quiz(choices, quiz)
        return

    if quiz_type == QUIZ_TYPE_HISTORY_MCQ_4:
        validate_history_mcq_4_quiz(choices, quiz)
        return

    raise ValueError(f"Unsupported quiz type for validation: {quiz_type}")
