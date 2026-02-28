"""Quiz payload builders keyed by quiz type."""

from __future__ import annotations

import datetime as dt
import hashlib
from typing import Any

from .constants import (
    NORMALIZED_MODEL_VERSION,
    QUIZ_SCHEMA_VERSION,
    QUIZ_TYPE_HISTORY_FACTOID_MCQ_4,
    QUIZ_TYPE_HISTORY_MCQ_4,
    QUIZ_TYPE_WHICH_CAME_FIRST,
    SUPPORTED_GENERATION_MODES,
    WHICH_CAME_FIRST_QUESTION,
)
from .model import (
    build_answer_fact,
    build_answer_fact_id,
    build_question_id,
    build_question_object,
)
from .selection import pick_history_mcq_distractor_pool, pick_two_events


def _format_year_label(year: int) -> str:
    if year >= 0:
        return str(year)
    return f"{abs(year)} BCE"


def _build_factoid_when_question(event_text: str) -> str:
    condensed = " ".join(event_text.split())
    condensed = condensed.rstrip(" .!?")
    if len(condensed) > 220:
        condensed = f"{condensed[:217].rstrip()}..."
    return f"When did this happen: {condensed}?"


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
                "event_id": build_answer_fact_id(event),
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
    edition: int,
    generation_mode: str,
    preferred_distractor_events: list[dict[str, Any]] | None = None,
    ai_ranked_distractor_ids: list[str] | None = None,
) -> dict[str, Any]:
    del preferred_distractor_events
    del ai_ranked_distractor_ids
    first, second = pick_two_events(candidates, seed)
    options = [first, second]
    correct_event = first if first["year"] < second["year"] else second

    if generation_mode not in SUPPORTED_GENERATION_MODES:
        raise ValueError(f"Unsupported generation mode: {generation_mode}")
    question_id = build_question_id(target_date, QUIZ_TYPE_WHICH_CAME_FIRST, edition)
    answer_facts = [
        build_answer_fact(
            first,
            quiz_type=QUIZ_TYPE_WHICH_CAME_FIRST,
            role="correct" if first is correct_event else "distractor",
        ),
        build_answer_fact(
            second,
            quiz_type=QUIZ_TYPE_WHICH_CAME_FIRST,
            role="correct" if second is correct_event else "distractor",
        ),
    ]
    answer_fact_ids = [fact["id"] for fact in answer_facts]
    correct_answer_fact_id = build_answer_fact_id(correct_event)
    question_object = build_question_object(
        question_id=question_id,
        prompt=WHICH_CAME_FIRST_QUESTION,
        quiz_type=QUIZ_TYPE_WHICH_CAME_FIRST,
        answer_fact_ids=answer_fact_ids,
        correct_answer_fact_id=correct_answer_fact_id,
    )

    legacy_choice_ids = ("A", "B")
    choices: list[dict[str, Any]] = []
    correct_choice_id: str | None = None
    for choice_id, event in zip(legacy_choice_ids, options):
        fact_id = build_answer_fact_id(event)
        choices.append({"id": choice_id, "label": event["text"], "year": event["year"], "answer_fact_id": fact_id})
        if fact_id == correct_answer_fact_id:
            correct_choice_id = choice_id

    if correct_choice_id is None:
        raise ValueError("Could not determine correct choice id for which_came_first.")

    return {
        "date": target_date.isoformat(),
        "topics": ["history"],
        "type": QUIZ_TYPE_WHICH_CAME_FIRST,
        "questions": [question_object],
        "answer_facts": answer_facts,
        "question": WHICH_CAME_FIRST_QUESTION,
        "choices": choices,
        "correct_choice_id": correct_choice_id,
        "source": build_source(retrieval_time, source_url, [first, second]),
        "generation": {
            "mode": generation_mode,
            "edition": edition,
            "generated_at": retrieval_time.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        },
        "metadata": {
            "version": QUIZ_SCHEMA_VERSION,
            "normalized_model": NORMALIZED_MODEL_VERSION,
        },
    }


def build_history_mcq_4_quiz(
    target_date: dt.date,
    retrieval_time: dt.datetime,
    source_url: str,
    candidates: list[dict[str, Any]],
    seed: int,
    edition: int,
    generation_mode: str,
    preferred_distractor_events: list[dict[str, Any]] | None = None,
    ai_ranked_distractor_ids: list[str] | None = None,
) -> dict[str, Any]:
    if generation_mode not in SUPPORTED_GENERATION_MODES:
        raise ValueError(f"Unsupported generation mode: {generation_mode}")
    correct, distractor_pool = pick_history_mcq_distractor_pool(
        candidates,
        seed,
        preferred_distractor_events=preferred_distractor_events,
        max_distractors=8,
    )
    selected_distractors = distractor_pool[:3]
    if ai_ranked_distractor_ids:
        by_fact_id = {build_answer_fact_id(item): item for item in distractor_pool}
        ranked_selection: list[dict[str, Any]] = []
        for fact_id in ai_ranked_distractor_ids:
            candidate = by_fact_id.get(fact_id)
            if candidate is None:
                ranked_selection = []
                break
            ranked_selection.append(candidate)
        if len(ranked_selection) == 3 and len({item["year"] for item in ranked_selection}) == 3:
            selected_distractors = ranked_selection

    options = [correct, *selected_distractors]
    options.sort(
        key=lambda item: hashlib.sha256(
            f"{seed}:{item['year']}:{item['text']}".encode("utf-8")
        ).hexdigest()
    )
    question_text = f"Which event happened in {correct['year']}?"

    choice_ids = ("A", "B", "C", "D")
    choices: list[dict[str, Any]] = []
    correct_choice_id: str | None = None
    answer_facts: list[dict[str, Any]] = []

    for choice_id, option in zip(choice_ids, options):
        role = "correct" if option is correct else "distractor"
        fact = build_answer_fact(option, quiz_type=QUIZ_TYPE_HISTORY_MCQ_4, role=role)
        answer_facts.append(fact)
        choices.append({"id": choice_id, "label": option["text"], "answer_fact_id": fact["id"]})
        if option is correct:
            correct_choice_id = choice_id

    if correct_choice_id is None:
        raise ValueError("Could not determine correct choice id for history_mcq_4.")

    question_object = build_question_object(
        question_id=build_question_id(target_date, QUIZ_TYPE_HISTORY_MCQ_4, edition),
        prompt=question_text,
        quiz_type=QUIZ_TYPE_HISTORY_MCQ_4,
        answer_fact_ids=[fact["id"] for fact in answer_facts],
        correct_answer_fact_id=build_answer_fact_id(correct),
        target_year=correct["year"],
    )

    return {
        "date": target_date.isoformat(),
        "topics": ["history"],
        "type": QUIZ_TYPE_HISTORY_MCQ_4,
        "questions": [question_object],
        "answer_facts": answer_facts,
        "question": question_text,
        "choices": choices,
        "correct_choice_id": correct_choice_id,
        "source": build_source(retrieval_time, source_url, options),
        "generation": {
            "mode": generation_mode,
            "edition": edition,
            "generated_at": retrieval_time.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        },
        "metadata": {
            "version": QUIZ_SCHEMA_VERSION,
            "normalized_model": NORMALIZED_MODEL_VERSION,
        },
    }


def build_history_factoid_mcq_4_quiz(
    target_date: dt.date,
    retrieval_time: dt.datetime,
    source_url: str,
    candidates: list[dict[str, Any]],
    seed: int,
    edition: int,
    generation_mode: str,
    preferred_distractor_events: list[dict[str, Any]] | None = None,
    ai_ranked_distractor_ids: list[str] | None = None,
) -> dict[str, Any]:
    del ai_ranked_distractor_ids
    if generation_mode not in SUPPORTED_GENERATION_MODES:
        raise ValueError(f"Unsupported generation mode: {generation_mode}")

    correct, distractor_pool = pick_history_mcq_distractor_pool(
        candidates,
        seed,
        preferred_distractor_events=preferred_distractor_events,
        max_distractors=3,
    )
    options = [correct, *distractor_pool[:3]]
    options.sort(
        key=lambda item: hashlib.sha256(
            f"{seed}:{item['year']}:{item['text']}".encode("utf-8")
        ).hexdigest()
    )
    question_text = _build_factoid_when_question(correct["text"])

    choice_ids = ("A", "B", "C", "D")
    choices: list[dict[str, Any]] = []
    correct_choice_id: str | None = None
    answer_facts: list[dict[str, Any]] = []

    for choice_id, option in zip(choice_ids, options):
        role = "correct" if option is correct else "distractor"
        fact = build_answer_fact(option, quiz_type=QUIZ_TYPE_HISTORY_FACTOID_MCQ_4, role=role)
        fact["facets"]["entity_type"] = "time"
        answer_facts.append(fact)
        choices.append(
            {
                "id": choice_id,
                "label": _format_year_label(option["year"]),
                "answer_fact_id": fact["id"],
            }
        )
        if option is correct:
            correct_choice_id = choice_id

    if correct_choice_id is None:
        raise ValueError("Could not determine correct choice id for history_factoid_mcq_4.")

    question_object = build_question_object(
        question_id=build_question_id(target_date, QUIZ_TYPE_HISTORY_FACTOID_MCQ_4, edition),
        prompt=question_text,
        quiz_type=QUIZ_TYPE_HISTORY_FACTOID_MCQ_4,
        answer_fact_ids=[fact["id"] for fact in answer_facts],
        correct_answer_fact_id=build_answer_fact_id(correct),
        target_year=correct["year"],
        extra_facets={
            "question_format": "factoid",
            "answer_kind": "time",
            "prompt_style": "when",
        },
    )

    return {
        "date": target_date.isoformat(),
        "topics": ["history"],
        "type": QUIZ_TYPE_HISTORY_FACTOID_MCQ_4,
        "questions": [question_object],
        "answer_facts": answer_facts,
        "question": question_text,
        "choices": choices,
        "correct_choice_id": correct_choice_id,
        "source": build_source(retrieval_time, source_url, options),
        "generation": {
            "mode": generation_mode,
            "edition": edition,
            "generated_at": retrieval_time.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        },
        "metadata": {
            "version": QUIZ_SCHEMA_VERSION,
            "normalized_model": NORMALIZED_MODEL_VERSION,
        },
    }


QUIZ_BUILDERS = {
    QUIZ_TYPE_WHICH_CAME_FIRST: build_which_came_first_quiz,
    QUIZ_TYPE_HISTORY_MCQ_4: build_history_mcq_4_quiz,
    QUIZ_TYPE_HISTORY_FACTOID_MCQ_4: build_history_factoid_mcq_4_quiz,
}
