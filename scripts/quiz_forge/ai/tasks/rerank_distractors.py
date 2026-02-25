"""Task helpers for distractor reranking."""

from __future__ import annotations

import json
from typing import Any

from ...constants import QUIZ_TYPE_HISTORY_MCQ_4
from ...model import build_answer_fact


def _candidate_payload(event: dict[str, Any]) -> dict[str, Any]:
    fact = build_answer_fact(event, quiz_type=QUIZ_TYPE_HISTORY_MCQ_4, role="distractor_candidate")
    return {
        "id": fact["id"],
        "label": fact["label"],
        "year": fact["year"],
        "tags": fact["tags"],
        "facets": fact["facets"],
    }


def build_rerank_payload(
    *,
    question_prompt: str,
    correct_event: dict[str, Any],
    distractor_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    correct_fact = build_answer_fact(correct_event, quiz_type=QUIZ_TYPE_HISTORY_MCQ_4, role="correct")
    return {
        "task": "rerank_distractors",
        "quiz_type": QUIZ_TYPE_HISTORY_MCQ_4,
        "question_prompt": question_prompt,
        "correct_answer_fact_id": correct_fact["id"],
        "correct_answer": {
            "id": correct_fact["id"],
            "label": correct_fact["label"],
            "year": correct_fact["year"],
            "tags": correct_fact["tags"],
            "facets": correct_fact["facets"],
        },
        "distractor_candidates": [_candidate_payload(item) for item in distractor_candidates],
        "constraints": {
            "max_returned": 3,
            "must_use_candidate_ids_only": True,
            "allow_generated_text": False,
            "distinct_year_from_correct": True,
            "distinct_years_between_distractors": True,
        },
    }


def estimate_input_tokens(payload: dict[str, Any]) -> int:
    serialized = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    # Approximate token count for pre-flight budget checks.
    return max(1, (len(serialized) + 3) // 4)


def validate_ranked_ids(
    *,
    ranked_ids: list[str],
    distractor_candidates: list[dict[str, Any]],
    correct_event: dict[str, Any],
) -> tuple[bool, str]:
    if len(ranked_ids) != 3:
        return False, "invalid_ranked_count"
    if len(set(ranked_ids)) != len(ranked_ids):
        return False, "duplicate_ranked_ids"

    candidate_payloads = [_candidate_payload(event) for event in distractor_candidates]
    ids_to_candidate = {item["id"]: item for item in candidate_payloads}
    if any(item not in ids_to_candidate for item in ranked_ids):
        return False, "ranked_id_not_in_candidates"

    correct_year = correct_event["year"]
    ranked_years: list[int] = []
    for ranked_id in ranked_ids:
        candidate = ids_to_candidate[ranked_id]
        year = candidate["year"]
        if year == correct_year:
            return False, "ranked_year_matches_correct"
        ranked_years.append(year)

    if len(set(ranked_years)) != len(ranked_years):
        return False, "ranked_years_not_distinct"

    return True, "ok"
