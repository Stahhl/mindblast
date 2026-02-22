"""Quiz payload builders keyed by quiz type."""

from __future__ import annotations

import datetime as dt
from typing import Any

from .constants import (
    QUIZ_TYPE_HISTORY_MCQ_4,
    QUIZ_TYPE_WHICH_CAME_FIRST,
    WHICH_CAME_FIRST_QUESTION,
)
from .selection import pick_history_mcq_events, pick_two_events


def build_source(
    retrieval_time: dt.datetime,
    source_url: str,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "name": "Wikipedia On This Day",
        "url": source_url,
        "retrieved_at": retrieval_time.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "events_used": [
            {
                "text": event["text"],
                "year": event["year"],
                "wikipedia_url": event["wikipedia_url"],
            }
            for event in events
        ],
    }


def build_which_came_first_quiz(
    target_date: dt.date,
    retrieval_time: dt.datetime,
    source_url: str,
    candidates: list[dict[str, Any]],
    seed: int,
) -> dict[str, Any]:
    first, second = pick_two_events(candidates, seed)
    correct_choice_id = "A" if first["year"] < second["year"] else "B"

    return {
        "date": target_date.isoformat(),
        "topics": ["history"],
        "type": QUIZ_TYPE_WHICH_CAME_FIRST,
        "question": WHICH_CAME_FIRST_QUESTION,
        "choices": [
            {"id": "A", "label": first["text"], "year": first["year"]},
            {"id": "B", "label": second["text"], "year": second["year"]},
        ],
        "correct_choice_id": correct_choice_id,
        "source": build_source(retrieval_time, source_url, [first, second]),
        "metadata": {"version": 1},
    }


def build_history_mcq_4_quiz(
    target_date: dt.date,
    retrieval_time: dt.datetime,
    source_url: str,
    candidates: list[dict[str, Any]],
    seed: int,
) -> dict[str, Any]:
    correct, _, options = pick_history_mcq_events(candidates, seed)

    choice_ids = ("A", "B", "C", "D")
    choices: list[dict[str, Any]] = []
    correct_choice_id: str | None = None

    for choice_id, option in zip(choice_ids, options):
        choices.append({"id": choice_id, "label": option["text"]})
        if option is correct:
            correct_choice_id = choice_id

    if correct_choice_id is None:
        raise ValueError("Could not determine correct choice id for history_mcq_4.")

    return {
        "date": target_date.isoformat(),
        "topics": ["history"],
        "type": QUIZ_TYPE_HISTORY_MCQ_4,
        "question": f"Which event happened in {correct['year']}?",
        "choices": choices,
        "correct_choice_id": correct_choice_id,
        "source": build_source(retrieval_time, source_url, options),
        "metadata": {"version": 1},
    }


QUIZ_BUILDERS = {
    QUIZ_TYPE_WHICH_CAME_FIRST: build_which_came_first_quiz,
    QUIZ_TYPE_HISTORY_MCQ_4: build_history_mcq_4_quiz,
}
