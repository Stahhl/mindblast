"""Quiz payload validation."""

from __future__ import annotations

import datetime as dt
from typing import Any

from .constants import (
    GENERATION_MODE_DAILY,
    SUPPORTED_GENERATION_MODES,
    NORMALIZED_MODEL_VERSION,
    QUIZ_SCHEMA_VERSION,
    QUIZ_TYPE_HISTORY_FACTOID_MCQ_4,
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
        answer_fact_id = choice.get("answer_fact_id")
        if not isinstance(answer_fact_id, str) or not answer_fact_id.strip():
            raise ValueError("choice.answer_fact_id must be a non-empty string.")
        choice_human_id = choice.get("human_id")
        if choice_human_id is not None and not _is_valid_human_id(choice_human_id, "A"):
            raise ValueError("choice.human_id must match A<integer> when present.")

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
        event_id = event.get("event_id")
        text = event.get("text")
        year = event.get("year")
        wikipedia_url = event.get("wikipedia_url")
        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError("source.events_used.event_id must be a non-empty string.")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("source.events_used.text must be a non-empty string.")
        if not isinstance(year, int):
            raise ValueError("source.events_used.year must be an integer.")
        if not isinstance(wikipedia_url, str) or not wikipedia_url.strip():
            raise ValueError("source.events_used.wikipedia_url must be a non-empty string.")

    metadata = quiz.get("metadata")
    if not isinstance(metadata, dict) or metadata.get("version") != QUIZ_SCHEMA_VERSION:
        raise ValueError(f"metadata.version must be {QUIZ_SCHEMA_VERSION}.")
    normalized_model = metadata.get("normalized_model")
    if normalized_model != NORMALIZED_MODEL_VERSION:
        raise ValueError(f"metadata.normalized_model must be {NORMALIZED_MODEL_VERSION}.")

    generation = quiz.get("generation")
    if not isinstance(generation, dict):
        raise ValueError("generation must be an object.")
    generation_mode = generation.get("mode")
    if generation_mode not in SUPPORTED_GENERATION_MODES:
        supported = ", ".join(SUPPORTED_GENERATION_MODES)
        raise ValueError(f"generation.mode must be one of: {supported}.")
    edition = generation.get("edition")
    if not isinstance(edition, int) or edition < 1:
        raise ValueError("generation.edition must be an integer >= 1.")
    generated_at = generation.get("generated_at")
    if not isinstance(generated_at, str) or not generated_at.endswith("Z"):
        raise ValueError("generation.generated_at must be a UTC timestamp.")
    if edition == 1 and generation_mode != GENERATION_MODE_DAILY:
        raise ValueError("generation.mode must be daily for edition 1.")

    return quiz_type, choices


def _is_valid_human_id(value: Any, prefix: str) -> bool:
    if not isinstance(value, str):
        return False
    if not value.startswith(prefix):
        return False
    suffix = value[len(prefix) :]
    if not suffix.isdigit():
        return False
    return int(suffix) >= 1


def _validate_answer_facts(quiz: dict[str, Any]) -> dict[str, dict[str, Any]]:
    answer_facts = quiz.get("answer_facts")
    if not isinstance(answer_facts, list) or not answer_facts:
        raise ValueError("answer_facts must be a non-empty list.")

    facts_by_id: dict[str, dict[str, Any]] = {}
    for idx, fact in enumerate(answer_facts):
        if not isinstance(fact, dict):
            raise ValueError(f"answer_facts[{idx}] must be an object.")

        fact_id = fact.get("id")
        label = fact.get("label")
        year = fact.get("year")

        if not isinstance(fact_id, str) or not fact_id.strip():
            raise ValueError(f"answer_facts[{idx}].id must be a non-empty string.")
        if fact_id in facts_by_id:
            raise ValueError("answer_facts ids must be unique.")
        if not isinstance(label, str) or not label.strip():
            raise ValueError(f"answer_facts[{idx}].label must be a non-empty string.")
        if not isinstance(year, int):
            raise ValueError(f"answer_facts[{idx}].year must be an integer.")
        human_id = fact.get("human_id")
        if human_id is not None and not _is_valid_human_id(human_id, "A"):
            raise ValueError(f"answer_facts[{idx}].human_id must match A<integer> when present.")

        tags = fact.get("tags")
        if not isinstance(tags, list) or not tags or not all(isinstance(tag, str) and tag.strip() for tag in tags):
            raise ValueError(f"answer_facts[{idx}].tags must be a non-empty string list.")

        facets = fact.get("facets")
        if not isinstance(facets, dict):
            raise ValueError(f"answer_facts[{idx}].facets must be an object.")

        match = fact.get("match")
        if not isinstance(match, dict):
            raise ValueError(f"answer_facts[{idx}].match must be an object.")

        vector_metadata = fact.get("vector_metadata")
        if not isinstance(vector_metadata, dict):
            raise ValueError(f"answer_facts[{idx}].vector_metadata must be an object.")
        embedding_text = vector_metadata.get("text_for_embedding")
        embedding_status = vector_metadata.get("embedding_status")
        if not isinstance(embedding_text, str) or not embedding_text.strip():
            raise ValueError(
                f"answer_facts[{idx}].vector_metadata.text_for_embedding must be a non-empty string."
            )
        if not isinstance(embedding_status, str) or not embedding_status.strip():
            raise ValueError(
                f"answer_facts[{idx}].vector_metadata.embedding_status must be a non-empty string."
            )

        facts_by_id[fact_id] = fact

    return facts_by_id


def _validate_questions(
    quiz: dict[str, Any],
    quiz_type: str,
    facts_by_id: dict[str, dict[str, Any]],
    legacy_choices: list[dict[str, Any]],
) -> None:
    source = quiz.get("source")
    source_events = source.get("events_used") if isinstance(source, dict) else None
    if not isinstance(source_events, list):
        raise ValueError("source.events_used must be a list.")
    source_event_ids = [event.get("event_id") for event in source_events if isinstance(event, dict)]
    if any(not isinstance(event_id, str) or event_id not in facts_by_id for event_id in source_event_ids):
        raise ValueError("source.events_used.event_id must reference existing answer_facts.")

    questions = quiz.get("questions")
    if not isinstance(questions, list) or len(questions) != 1:
        raise ValueError("questions must contain exactly one entry.")

    question = questions[0]
    if not isinstance(question, dict):
        raise ValueError("questions[0] must be an object.")

    question_id = question.get("id")
    prompt = question.get("prompt")
    question_type = question.get("type")
    answer_fact_ids = question.get("answer_fact_ids")
    correct_answer_fact_id = question.get("correct_answer_fact_id")

    if not isinstance(question_id, str) or not question_id.strip():
        raise ValueError("questions[0].id must be a non-empty string.")
    question_human_id = question.get("human_id")
    if question_human_id is not None and not _is_valid_human_id(question_human_id, "Q"):
        raise ValueError("questions[0].human_id must match Q<integer> when present.")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("questions[0].prompt must be a non-empty string.")
    if question_type != quiz_type:
        raise ValueError("questions[0].type must match quiz.type.")
    if not isinstance(answer_fact_ids, list) or not answer_fact_ids:
        raise ValueError("questions[0].answer_fact_ids must be a non-empty list.")
    if not all(isinstance(item, str) and item.strip() for item in answer_fact_ids):
        raise ValueError("questions[0].answer_fact_ids entries must be non-empty strings.")
    if len(set(answer_fact_ids)) != len(answer_fact_ids):
        raise ValueError("questions[0].answer_fact_ids must be unique.")
    if not isinstance(correct_answer_fact_id, str) or not correct_answer_fact_id.strip():
        raise ValueError("questions[0].correct_answer_fact_id must be a non-empty string.")
    if correct_answer_fact_id not in answer_fact_ids:
        raise ValueError("questions[0].correct_answer_fact_id must be in answer_fact_ids.")
    if any(answer_fact_id not in facts_by_id for answer_fact_id in answer_fact_ids):
        raise ValueError("questions[0].answer_fact_ids must reference existing answer_facts.")
    if set(source_event_ids) != set(answer_fact_ids):
        raise ValueError("questions[0].answer_fact_ids must match source.events_used.event_id set.")

    if prompt != quiz.get("question"):
        raise ValueError("questions[0].prompt must match legacy question field.")

    legacy_answer_fact_ids = [choice["answer_fact_id"] for choice in legacy_choices]
    if answer_fact_ids != legacy_answer_fact_ids:
        raise ValueError("questions[0].answer_fact_ids must match legacy choices order.")

    correct_choice_id = quiz.get("correct_choice_id")
    correct_choice = next((choice for choice in legacy_choices if choice["id"] == correct_choice_id), None)
    if correct_choice is None:
        raise ValueError("correct_choice_id must match one of the legacy choices.")
    if correct_choice["answer_fact_id"] != correct_answer_fact_id:
        raise ValueError("questions[0].correct_answer_fact_id must match legacy correct choice.")

    answer_fact_human_ids = {
        fact_id: fact.get("human_id")
        for fact_id, fact in facts_by_id.items()
    }
    has_choice_human_ids = any(choice.get("human_id") is not None for choice in legacy_choices)
    has_answer_fact_human_ids = any(human_id is not None for human_id in answer_fact_human_ids.values())
    if has_choice_human_ids != has_answer_fact_human_ids:
        raise ValueError("choice and answer_fact human ids must either both be present or both be absent.")
    if has_choice_human_ids and has_answer_fact_human_ids:
        for idx, choice in enumerate(legacy_choices):
            choice_human_id = choice.get("human_id")
            answer_fact_human_id = answer_fact_human_ids.get(choice["answer_fact_id"])
            if choice_human_id != answer_fact_human_id:
                raise ValueError(
                    f"choices[{idx}].human_id must match answer_facts human_id for choices[{idx}].answer_fact_id."
                )

    tags = question.get("tags")
    if not isinstance(tags, list) or not tags or not all(isinstance(tag, str) and tag.strip() for tag in tags):
        raise ValueError("questions[0].tags must be a non-empty string list.")
    facets = question.get("facets")
    if not isinstance(facets, dict):
        raise ValueError("questions[0].facets must be an object.")
    selection_rules = question.get("selection_rules")
    if not isinstance(selection_rules, dict):
        raise ValueError("questions[0].selection_rules must be an object.")


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


def validate_history_factoid_mcq_4_quiz(choices: list[dict[str, Any]], quiz: dict[str, Any]) -> None:
    if len(choices) != 4:
        raise ValueError("history_factoid_mcq_4 choices must contain exactly 4 entries.")

    for choice in choices:
        if "year" in choice:
            raise ValueError("history_factoid_mcq_4 choices must not include year.")

    question = quiz.get("question")
    if not isinstance(question, str) or not question.strip().endswith("?"):
        raise ValueError("history_factoid_mcq_4 question text must end with '?'.")

    questions = quiz.get("questions")
    if not isinstance(questions, list) or not questions or not isinstance(questions[0], dict):
        raise ValueError("history_factoid_mcq_4 questions[0] must be present.")
    facets = questions[0].get("facets")
    if not isinstance(facets, dict):
        raise ValueError("history_factoid_mcq_4 questions[0].facets must be an object.")
    if facets.get("question_format") != "factoid":
        raise ValueError("history_factoid_mcq_4 facets.question_format must be 'factoid'.")
    answer_kind = facets.get("answer_kind")
    prompt_style = facets.get("prompt_style")
    allowed_pairs = {
        "person": "who",
        "place": "where",
        "time": "when",
    }
    if answer_kind not in allowed_pairs:
        raise ValueError("history_factoid_mcq_4 facets.answer_kind must be one of person/place/time.")
    if prompt_style != allowed_pairs[answer_kind]:
        raise ValueError("history_factoid_mcq_4 facets.prompt_style must align with answer_kind.")
    if not question.strip().lower().startswith(prompt_style):
        raise ValueError("history_factoid_mcq_4 question text must align with facets.prompt_style.")

    events_used = quiz["source"]["events_used"]
    if len(events_used) != 4:
        raise ValueError("history_factoid_mcq_4 source.events_used must contain exactly 4 entries.")

    answer_facts = quiz.get("answer_facts")
    if not isinstance(answer_facts, list) or len(answer_facts) != 4:
        raise ValueError("history_factoid_mcq_4 answer_facts must contain exactly 4 entries.")
    for fact in answer_facts:
        if not isinstance(fact, dict):
            raise ValueError("history_factoid_mcq_4 answer_facts entries must be objects.")
        fact_facets = fact.get("facets")
        if not isinstance(fact_facets, dict):
            raise ValueError("history_factoid_mcq_4 answer_facts facets must be objects.")
        if fact_facets.get("entity_type") != answer_kind:
            raise ValueError("history_factoid_mcq_4 answer_facts entity_type must align with answer_kind.")


def validate_quiz(quiz: dict[str, Any], target_date: dt.date) -> None:
    quiz_type, choices = validate_common_fields(quiz, target_date)
    facts_by_id = _validate_answer_facts(quiz)
    _validate_questions(quiz, quiz_type, facts_by_id, choices)

    if quiz_type == QUIZ_TYPE_WHICH_CAME_FIRST:
        validate_which_came_first_quiz(choices, quiz)
        return

    if quiz_type == QUIZ_TYPE_HISTORY_MCQ_4:
        validate_history_mcq_4_quiz(choices, quiz)
        return

    if quiz_type == QUIZ_TYPE_HISTORY_FACTOID_MCQ_4:
        validate_history_factoid_mcq_4_quiz(choices, quiz)
        return

    raise ValueError(f"Unsupported quiz type for validation: {quiz_type}")
