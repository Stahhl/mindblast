"""Normalized question/answer-fact model helpers."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from .constants import ANSWER_FACT_NAMESPACE, QUIZ_QUESTION_NAMESPACE


def _century_label(year: int) -> str:
    if year > 0:
        century = ((year - 1) // 100) + 1
        return f"{century}th-century"
    century = ((abs(year) - 1) // 100) + 1
    return f"{century}th-century-bce"


def _decade_label(year: int) -> str:
    if year >= 0:
        return f"{(year // 10) * 10}s"
    decade = ((abs(year) // 10) * 10)
    return f"{decade}s-bce"


def build_answer_fact_id(event: dict[str, Any]) -> str:
    key = f"{event['year']}|{event['text']}|{event['wikipedia_url']}"
    return str(uuid.uuid5(ANSWER_FACT_NAMESPACE, key))


def build_answer_fact_id_from_key(key: str) -> str:
    return str(uuid.uuid5(ANSWER_FACT_NAMESPACE, key))


def build_factoid_answer_fact_id(
    source_event: dict[str, Any],
    *,
    answer_label: str,
    entity_type: str,
) -> str:
    key = (
        f"{source_event['year']}|{source_event['text']}|{source_event['wikipedia_url']}|"
        f"{entity_type}|{answer_label.strip()}"
    )
    return str(uuid.uuid5(ANSWER_FACT_NAMESPACE, key))


def build_question_id(target_date: dt.date, quiz_type: str, edition: int) -> str:
    key = f"{target_date.isoformat()}|{quiz_type}|{edition}"
    return str(uuid.uuid5(QUIZ_QUESTION_NAMESPACE, key))


def build_answer_fact(
    event: dict[str, Any],
    *,
    quiz_type: str,
    role: str,
    fact_id: str | None = None,
    label: str | None = None,
    entity_type: str | None = None,
    embedding_text: str | None = None,
) -> dict[str, Any]:
    fact_id = fact_id or build_answer_fact_id(event)
    year = event["year"]
    fact_label = label or event["text"]
    vector_text = embedding_text or event["text"]
    facets = {
        "topic": "history",
        "temporal_century": _century_label(year),
        "temporal_decade": _decade_label(year),
        "source": "wikipedia_on_this_day",
    }
    if entity_type:
        facets["entity_type"] = entity_type
    return {
        "id": fact_id,
        "label": fact_label,
        "year": year,
        "tags": [
            "history",
            quiz_type,
            f"role:{role}",
            _century_label(year),
            _decade_label(year),
        ],
        "facets": facets,
        "match": {
            "distractor_profile": {
                "year": year,
                "temporal_century": _century_label(year),
                "temporal_decade": _decade_label(year),
            }
        },
        "vector_metadata": {
            "text_for_embedding": vector_text,
            "embedding_status": "not_generated",
        },
    }


def build_question_object(
    *,
    question_id: str,
    prompt: str,
    quiz_type: str,
    answer_fact_ids: list[str],
    correct_answer_fact_id: str,
    target_year: int | None = None,
    topic: str = "history",
    extra_facets: dict[str, Any] | None = None,
    extra_selection_rules: dict[str, Any] | None = None,
) -> dict[str, Any]:
    selection_rules: dict[str, Any] = {
        "distractor_same_year_allowed": False,
    }
    if target_year is not None:
        selection_rules["target_year"] = target_year
    if extra_selection_rules:
        selection_rules.update(extra_selection_rules)

    facets: dict[str, Any] = {
        "topic": topic,
        "difficulty_band": "baseline",
    }
    if extra_facets:
        facets.update(extra_facets)

    return {
        "id": question_id,
        "type": quiz_type,
        "prompt": prompt,
        "answer_fact_ids": answer_fact_ids,
        "correct_answer_fact_id": correct_answer_fact_id,
        "tags": [topic, quiz_type],
        "facets": facets,
        "selection_rules": selection_rules,
    }
