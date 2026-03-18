"""Path resolution and file write helpers."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

from .constants import (
    ANSWER_HUMAN_ID_PREFIX,
    GENERATION_MODE_DAILY,
    GENERATION_MODE_EXTRA,
    HUMAN_ID_LOOKUP_FILENAME,
    HUMAN_ID_LOOKUP_VERSION,
    NORMALIZED_MODEL_VERSION,
    QUESTION_HUMAN_ID_PREFIX,
    QUIZ_SCHEMA_VERSION,
    QUIZ_FILENAME_NAMESPACE,
    QUIZ_TYPE_HISTORY_FACTOID_MCQ_4,
    QUIZ_TYPE_HISTORY_MCQ_4,
    QUIZ_TYPE_WHICH_CAME_FIRST,
    SUPPORTED_QUIZ_TYPES,
)
from .model import build_answer_fact, build_question_id, build_question_object


@dataclass(frozen=True)
class QuizRecord:
    path: Path
    quiz_type: str
    date: dt.date
    edition: int
    mode: str
    generated_at: str | None
    payload: dict[str, Any]


def build_output_path(output_dir: str, target_date: dt.date, quiz_type: str, edition: int) -> Path:
    quiz_key = f"{target_date.isoformat()}:{quiz_type}:{edition}"
    quiz_id = uuid.uuid5(QUIZ_FILENAME_NAMESPACE, quiz_key)
    return Path(output_dir) / f"{quiz_id}.json"


def find_existing_quiz_path(
    output_path: Path,
    target_date: dt.date,
    quiz_type: str,
    edition: int,
) -> Path | None:
    if output_path.exists():
        return output_path

    if edition != 1 or quiz_type != QUIZ_TYPE_WHICH_CAME_FIRST:
        return None

    # Backward compatibility: old date-only UUID filename for which_came_first.
    legacy_uuid = uuid.uuid5(QUIZ_FILENAME_NAMESPACE, target_date.isoformat())
    legacy_uuid_path = output_path.parent / f"{legacy_uuid}.json"
    if legacy_uuid_path.exists():
        return legacy_uuid_path

    # Backward compatibility: original YYYY-MM-DD filename.
    legacy_date_path = output_path.parent / f"{target_date.isoformat()}.json"
    if legacy_date_path.exists():
        return legacy_date_path

    return None


def _parse_quiz_record(path: Path, payload: dict[str, Any]) -> QuizRecord | None:
    quiz_type = payload.get("type")
    if not isinstance(quiz_type, str) or quiz_type not in SUPPORTED_QUIZ_TYPES:
        return None

    date_text = payload.get("date")
    if not isinstance(date_text, str):
        return None
    try:
        parsed_date = dt.date.fromisoformat(date_text)
    except ValueError:
        return None

    generation = payload.get("generation")
    edition = 1
    mode = GENERATION_MODE_DAILY
    generated_at: str | None = None
    if isinstance(generation, dict):
        maybe_edition = generation.get("edition")
        maybe_mode = generation.get("mode")
        maybe_generated_at = generation.get("generated_at")
        if isinstance(maybe_edition, int) and maybe_edition >= 1:
            edition = maybe_edition
        if isinstance(maybe_mode, str) and maybe_mode.strip():
            mode = maybe_mode
        if isinstance(maybe_generated_at, str) and maybe_generated_at.strip():
            generated_at = maybe_generated_at

    if generated_at is None:
        source = payload.get("source")
        if isinstance(source, dict):
            source_retrieved_at = source.get("retrieved_at")
            if isinstance(source_retrieved_at, str) and source_retrieved_at.strip():
                generated_at = source_retrieved_at

    return QuizRecord(
        path=path,
        quiz_type=quiz_type,
        date=parsed_date,
        edition=edition,
        mode=mode,
        generated_at=generated_at,
        payload=payload,
    )


def iter_quiz_records(output_dir: str) -> list[QuizRecord]:
    root = Path(output_dir)
    if not root.exists():
        return []

    records: list[QuizRecord] = []
    for path in sorted(root.glob("*.json")):
        payload = load_json_file(path)
        if payload is None:
            continue
        record = _parse_quiz_record(path, payload)
        if record is None:
            continue
        records.append(record)
    return records


def list_quiz_records_for_date(output_dir: str, target_date: dt.date) -> list[QuizRecord]:
    return [record for record in iter_quiz_records(output_dir) if record.date == target_date]


def list_quiz_records_for_date_type(output_dir: str, target_date: dt.date, quiz_type: str) -> list[QuizRecord]:
    records = [
        record
        for record in iter_quiz_records(output_dir)
        if record.date == target_date and record.quiz_type == quiz_type
    ]
    records.sort(key=lambda record: (record.edition, record.path.as_posix()))
    return records


def _utc_timestamp(value: dt.datetime) -> str:
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def to_public_quiz_path(path: Path) -> str:
    normalized_parts = path.as_posix().split("/")
    if "quizzes" in normalized_parts:
        quizzes_index = normalized_parts.index("quizzes")
        return "/".join(normalized_parts[quizzes_index:])
    raise ValueError(f"Path does not contain quizzes/ root: {path}")


def _extract_human_id_number(human_id: str, prefix: str) -> int | None:
    if not human_id.startswith(prefix):
        return None
    suffix = human_id[len(prefix) :]
    if not suffix.isdigit():
        return None
    number = int(suffix)
    if number < 1:
        return None
    return number


def _default_human_id_lookup() -> dict[str, Any]:
    return {
        "metadata": {
            "version": HUMAN_ID_LOOKUP_VERSION,
            "updated_at": None,
        },
        "counters": {
            "question": 0,
            "answer": 0,
        },
        "question_uuid_to_human_id": {},
        "answer_uuid_to_human_id": {},
        "questions": {},
        "answers": {},
    }


def _coerce_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        key: item
        for key, item in value.items()
        if isinstance(key, str)
    }


def _next_human_id(lookup: dict[str, Any], *, counter_key: str, prefix: str) -> str:
    counters = lookup["counters"]
    next_number = int(counters[counter_key]) + 1
    counters[counter_key] = next_number
    return f"{prefix}{next_number}"


def _normalize_generation_mode(raw_mode: Any, edition: int) -> str:
    if isinstance(raw_mode, str) and raw_mode.strip():
        return raw_mode
    if edition == 1:
        return GENERATION_MODE_DAILY
    return GENERATION_MODE_EXTRA


def _ensure_generation_block(quiz: dict[str, Any]) -> bool:
    generation = quiz.get("generation")
    source = quiz.get("source")

    existing_edition = generation.get("edition") if isinstance(generation, dict) else None
    edition = existing_edition if isinstance(existing_edition, int) and existing_edition >= 1 else 1

    existing_mode = generation.get("mode") if isinstance(generation, dict) else None
    mode = _normalize_generation_mode(existing_mode, edition)

    existing_generated_at = generation.get("generated_at") if isinstance(generation, dict) else None
    source_retrieved_at = source.get("retrieved_at") if isinstance(source, dict) else None
    generated_at: str
    if isinstance(existing_generated_at, str) and existing_generated_at.strip():
        generated_at = existing_generated_at
    elif isinstance(source_retrieved_at, str) and source_retrieved_at.strip():
        generated_at = source_retrieved_at
    else:
        generated_at = _utc_timestamp(dt.datetime.now(dt.timezone.utc))

    normalized_generation = {
        "mode": mode,
        "edition": edition,
        "generated_at": generated_at,
    }
    if generation == normalized_generation:
        return False
    quiz["generation"] = normalized_generation
    return True


def _match_choice_to_event(
    *,
    choice: dict[str, Any],
    events_used: list[dict[str, Any]],
    consumed_indexes: set[int],
) -> tuple[int, dict[str, Any]]:
    label = choice.get("label")
    if not isinstance(label, str):
        raise ValueError("Cannot normalize legacy quiz: choice.label is missing.")
    choice_year = choice.get("year")

    for index, event in enumerate(events_used):
        if index in consumed_indexes:
            continue
        if event.get("text") != label:
            continue
        event_year = event.get("year")
        if isinstance(choice_year, int) and event_year != choice_year:
            continue
        return index, event

    raise ValueError("Cannot normalize legacy quiz: could not match choice label to source event.")


def _normalize_legacy_quiz_to_v2(quiz: dict[str, Any]) -> bool:
    metadata = quiz.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("Cannot normalize legacy quiz: metadata is missing.")

    questions = quiz.get("questions")
    answer_facts = quiz.get("answer_facts")
    if (
        metadata.get("version") == QUIZ_SCHEMA_VERSION
        and isinstance(questions, list)
        and questions
        and isinstance(answer_facts, list)
        and answer_facts
    ):
        changed = False
        if metadata.get("normalized_model") != NORMALIZED_MODEL_VERSION:
            metadata["normalized_model"] = NORMALIZED_MODEL_VERSION
            changed = True
        if _ensure_generation_block(quiz):
            changed = True
        return changed

    if metadata.get("version") != 1:
        raise ValueError("Cannot normalize quiz: unsupported metadata.version for backfill.")

    date_value = quiz.get("date")
    if not isinstance(date_value, str):
        raise ValueError("Cannot normalize legacy quiz: date is missing.")
    try:
        target_date = dt.date.fromisoformat(date_value)
    except ValueError as exc:
        raise ValueError("Cannot normalize legacy quiz: invalid date field.") from exc

    quiz_type = quiz.get("type")
    if not isinstance(quiz_type, str) or quiz_type not in SUPPORTED_QUIZ_TYPES:
        raise ValueError("Cannot normalize legacy quiz: unsupported type.")

    generation = quiz.get("generation")
    edition = generation.get("edition") if isinstance(generation, dict) else 1
    if not isinstance(edition, int) or edition < 1:
        edition = 1

    source = quiz.get("source")
    if not isinstance(source, dict):
        raise ValueError("Cannot normalize legacy quiz: source is missing.")
    events_used = source.get("events_used")
    if not isinstance(events_used, list) or not events_used:
        raise ValueError("Cannot normalize legacy quiz: source.events_used is missing.")

    choices = quiz.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("Cannot normalize legacy quiz: choices are missing.")

    correct_choice_id = quiz.get("correct_choice_id")
    if not isinstance(correct_choice_id, str):
        raise ValueError("Cannot normalize legacy quiz: correct_choice_id is missing.")

    consumed_event_indexes: set[int] = set()
    answer_facts_v2: list[dict[str, Any]] = []
    answer_fact_ids: list[str] = []
    normalized_events_used: list[dict[str, Any]] = []
    correct_answer_fact_id: str | None = None

    for choice in choices:
        if not isinstance(choice, dict):
            raise ValueError("Cannot normalize legacy quiz: choice entry is invalid.")
        event_index, event = _match_choice_to_event(
            choice=choice,
            events_used=events_used,
            consumed_indexes=consumed_event_indexes,
        )
        consumed_event_indexes.add(event_index)

        event_text = event.get("text")
        event_year = event.get("year")
        event_wikipedia_url = event.get("wikipedia_url")
        if not isinstance(event_text, str) or not isinstance(event_year, int) or not isinstance(event_wikipedia_url, str):
            raise ValueError("Cannot normalize legacy quiz: source event fields are invalid.")

        role = "correct" if choice.get("id") == correct_choice_id else "distractor"
        event_payload = {
            "text": event_text,
            "year": event_year,
            "wikipedia_url": event_wikipedia_url,
        }
        fact = build_answer_fact(event_payload, quiz_type=quiz_type, role=role)
        if quiz_type == QUIZ_TYPE_HISTORY_FACTOID_MCQ_4:
            fact["facets"]["entity_type"] = "time"
        answer_facts_v2.append(fact)
        answer_fact_ids.append(fact["id"])

        choice["answer_fact_id"] = fact["id"]
        if quiz_type == QUIZ_TYPE_WHICH_CAME_FIRST:
            choice["year"] = event_year
        elif quiz_type in (QUIZ_TYPE_HISTORY_MCQ_4, QUIZ_TYPE_HISTORY_FACTOID_MCQ_4):
            choice.pop("year", None)

        normalized_events_used.append(
            {
                "event_id": fact["id"],
                "text": event_text,
                "year": event_year,
                "wikipedia_url": event_wikipedia_url,
            }
        )
        if role == "correct":
            correct_answer_fact_id = fact["id"]

    if correct_answer_fact_id is None:
        raise ValueError("Cannot normalize legacy quiz: failed to resolve correct answer fact id.")

    question_text = quiz.get("question")
    if not isinstance(question_text, str) or not question_text.strip():
        raise ValueError("Cannot normalize legacy quiz: question text is missing.")

    extra_facets: dict[str, Any] | None = None
    target_year: int | None = None
    if quiz_type in (QUIZ_TYPE_HISTORY_MCQ_4, QUIZ_TYPE_HISTORY_FACTOID_MCQ_4):
        correct_fact = next((fact for fact in answer_facts_v2 if fact["id"] == correct_answer_fact_id), None)
        if isinstance(correct_fact, dict) and isinstance(correct_fact.get("year"), int):
            target_year = correct_fact["year"]
    if quiz_type == QUIZ_TYPE_HISTORY_FACTOID_MCQ_4:
        extra_facets = {
            "question_format": "factoid",
            "answer_kind": "time",
            "prompt_style": "when",
        }

    question_object = build_question_object(
        question_id=build_question_id(target_date, quiz_type, edition),
        prompt=question_text,
        quiz_type=quiz_type,
        answer_fact_ids=answer_fact_ids,
        correct_answer_fact_id=correct_answer_fact_id,
        target_year=target_year,
        extra_facets=extra_facets,
    )

    quiz["questions"] = [question_object]
    quiz["answer_facts"] = answer_facts_v2
    source["events_used"] = normalized_events_used
    metadata["version"] = QUIZ_SCHEMA_VERSION
    metadata["normalized_model"] = NORMALIZED_MODEL_VERSION
    _ensure_generation_block(quiz)
    return True


def load_human_id_lookup(output_dir: str) -> dict[str, Any]:
    lookup_path = Path(output_dir) / HUMAN_ID_LOOKUP_FILENAME
    loaded = load_json_file(lookup_path)
    lookup = _default_human_id_lookup()
    if loaded is None:
        return lookup

    question_uuid_to_human_id = _coerce_mapping(loaded.get("question_uuid_to_human_id"))
    answer_uuid_to_human_id = _coerce_mapping(loaded.get("answer_uuid_to_human_id"))
    questions = _coerce_mapping(loaded.get("questions"))
    answers = _coerce_mapping(loaded.get("answers"))

    normalized_question_map: dict[str, str] = {}
    normalized_answer_map: dict[str, str] = {}

    for question_id, human_id in question_uuid_to_human_id.items():
        if isinstance(human_id, str) and _extract_human_id_number(human_id, QUESTION_HUMAN_ID_PREFIX) is not None:
            normalized_question_map[question_id] = human_id

    for answer_fact_id, human_id in answer_uuid_to_human_id.items():
        if isinstance(human_id, str) and _extract_human_id_number(human_id, ANSWER_HUMAN_ID_PREFIX) is not None:
            normalized_answer_map[answer_fact_id] = human_id

    # Reconcile lookup entries from direct human-id records if reverse maps are incomplete.
    for human_id, entry in questions.items():
        if _extract_human_id_number(human_id, QUESTION_HUMAN_ID_PREFIX) is None or not isinstance(entry, dict):
            continue
        question_id = entry.get("question_id")
        if isinstance(question_id, str) and question_id and question_id not in normalized_question_map:
            normalized_question_map[question_id] = human_id

    for human_id, entry in answers.items():
        if _extract_human_id_number(human_id, ANSWER_HUMAN_ID_PREFIX) is None or not isinstance(entry, dict):
            continue
        answer_fact_id = entry.get("answer_fact_id")
        if isinstance(answer_fact_id, str) and answer_fact_id and answer_fact_id not in normalized_answer_map:
            normalized_answer_map[answer_fact_id] = human_id

    question_counter = max(
        [0, *(_extract_human_id_number(human_id, QUESTION_HUMAN_ID_PREFIX) or 0 for human_id in normalized_question_map.values())]
    )
    answer_counter = max(
        [0, *(_extract_human_id_number(human_id, ANSWER_HUMAN_ID_PREFIX) or 0 for human_id in normalized_answer_map.values())]
    )

    loaded_counters = _coerce_mapping(loaded.get("counters"))
    loaded_question_counter = loaded_counters.get("question")
    loaded_answer_counter = loaded_counters.get("answer")
    if isinstance(loaded_question_counter, int) and loaded_question_counter > question_counter:
        question_counter = loaded_question_counter
    if isinstance(loaded_answer_counter, int) and loaded_answer_counter > answer_counter:
        answer_counter = loaded_answer_counter

    lookup["counters"]["question"] = question_counter
    lookup["counters"]["answer"] = answer_counter
    lookup["question_uuid_to_human_id"] = normalized_question_map
    lookup["answer_uuid_to_human_id"] = normalized_answer_map
    lookup["questions"] = {
        key: value
        for key, value in questions.items()
        if _extract_human_id_number(key, QUESTION_HUMAN_ID_PREFIX) is not None and isinstance(value, dict)
    }
    lookup["answers"] = {
        key: value
        for key, value in answers.items()
        if _extract_human_id_number(key, ANSWER_HUMAN_ID_PREFIX) is not None and isinstance(value, dict)
    }
    return lookup


def apply_human_ids_to_quiz(
    *,
    quiz: dict[str, Any],
    quiz_path: Path,
    lookup: dict[str, Any],
) -> bool:
    changed = _normalize_legacy_quiz_to_v2(quiz)
    questions = quiz.get("questions")
    if not isinstance(questions, list) or not questions or not isinstance(questions[0], dict):
        raise ValueError("Cannot assign human ids: quiz.questions[0] is missing.")
    question = questions[0]
    question_id = question.get("id")
    if not isinstance(question_id, str) or not question_id.strip():
        raise ValueError("Cannot assign human ids: quiz.questions[0].id is missing.")

    question_lookup = lookup["question_uuid_to_human_id"]
    question_human_id = question_lookup.get(question_id)
    if not isinstance(question_human_id, str):
        question_human_id = _next_human_id(
            lookup,
            counter_key="question",
            prefix=QUESTION_HUMAN_ID_PREFIX,
        )
        question_lookup[question_id] = question_human_id
        changed = True

    if question.get("human_id") != question_human_id:
        question["human_id"] = question_human_id
        changed = True

    generation = quiz.get("generation")
    edition = generation.get("edition") if isinstance(generation, dict) else 1
    if not isinstance(edition, int) or edition < 1:
        edition = 1

    question_record = {
        "question_id": question_id,
        "quiz_file": to_public_quiz_path(quiz_path),
        "date": quiz.get("date"),
        "quiz_type": quiz.get("type"),
        "edition": edition,
    }
    existing_question_record = lookup["questions"].get(question_human_id)
    if existing_question_record != question_record:
        lookup["questions"][question_human_id] = question_record
        changed = True

    answer_facts = quiz.get("answer_facts")
    if not isinstance(answer_facts, list) or not answer_facts:
        raise ValueError("Cannot assign human ids: quiz.answer_facts is missing.")

    choices = quiz.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("Cannot assign human ids: quiz.choices is missing.")

    answer_lookup = lookup["answer_uuid_to_human_id"]
    for fact in answer_facts:
        if not isinstance(fact, dict):
            raise ValueError("Cannot assign human ids: answer_facts entry is invalid.")
        answer_fact_id = fact.get("id")
        if not isinstance(answer_fact_id, str) or not answer_fact_id.strip():
            raise ValueError("Cannot assign human ids: answer_facts[].id is missing.")

        answer_human_id = answer_lookup.get(answer_fact_id)
        if not isinstance(answer_human_id, str):
            answer_human_id = _next_human_id(
                lookup,
                counter_key="answer",
                prefix=ANSWER_HUMAN_ID_PREFIX,
            )
            answer_lookup[answer_fact_id] = answer_human_id
            changed = True

        if fact.get("human_id") != answer_human_id:
            fact["human_id"] = answer_human_id
            changed = True

        answer_record = {
            "answer_fact_id": answer_fact_id,
            "label": fact.get("label"),
            "year": fact.get("year"),
        }
        existing_answer_record = lookup["answers"].get(answer_human_id)
        if existing_answer_record != answer_record:
            lookup["answers"][answer_human_id] = answer_record
            changed = True

    for choice in choices:
        if not isinstance(choice, dict):
            raise ValueError("Cannot assign human ids: choice entry is invalid.")
        answer_fact_id = choice.get("answer_fact_id")
        if not isinstance(answer_fact_id, str) or not answer_fact_id.strip():
            raise ValueError("Cannot assign human ids: choices[].answer_fact_id is missing.")

        answer_human_id = answer_lookup.get(answer_fact_id)
        if not isinstance(answer_human_id, str):
            raise ValueError("Cannot assign human ids: answer fact id is not in lookup map.")
        if choice.get("human_id") != answer_human_id:
            choice["human_id"] = answer_human_id
            changed = True

    return changed


def write_human_id_lookup(output_dir: str, lookup: dict[str, Any]) -> Path:
    lookup_path = Path(output_dir) / HUMAN_ID_LOOKUP_FILENAME
    lookup["metadata"] = {
        "version": HUMAN_ID_LOOKUP_VERSION,
        "updated_at": _utc_timestamp(dt.datetime.now(dt.timezone.utc)),
    }
    write_json_file(lookup_path, lookup, prefix=".tmp-human-id-")
    return lookup_path


def load_json_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as file_obj:
        payload = json.load(file_obj)
    if not isinstance(payload, dict):
        return None
    return payload


def write_json_file(path: Path, payload: dict[str, Any], prefix: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, ensure_ascii=True, indent=2) + "\n"

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


def write_quiz_file(path: Path, quiz: dict[str, Any]) -> None:
    write_json_file(path, quiz, prefix=".tmp-quiz-")
