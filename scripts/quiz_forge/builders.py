"""Quiz payload builders keyed by quiz type."""

from __future__ import annotations

import datetime as dt
import hashlib
from typing import Any

from .constants import (
    NORMALIZED_MODEL_VERSION,
    QUIZ_SCHEMA_VERSION,
    QUIZ_TYPE_GEOGRAPHY_FACTOID_MCQ_4,
    QUIZ_TYPE_HISTORY_FACTOID_MCQ_4,
    QUIZ_TYPE_HISTORY_MCQ_4,
    QUIZ_TYPE_WHICH_CAME_FIRST,
    SUPPORTED_GENERATION_MODES,
    WHICH_CAME_FIRST_QUESTION,
)
from .geography import GEOGRAPHY_SOURCE_NAME, geography_option_sort_key, pick_geography_factoid_records
from .model import (
    build_answer_fact,
    build_answer_fact_id,
    build_answer_fact_id_from_key,
    build_factoid_answer_fact_id,
    build_question_id,
    build_question_object,
)
from .selection import pick_history_mcq_distractor_pool, pick_two_events
from .selection import build_history_factoid_distractors_for_candidate
from .selection import iter_history_factoid_typed_candidate_sets, iter_history_mcq_correct_events
from .quality import QualityRunStats, lint_quiz_payload


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


def _build_history_factoid_typed_quiz(
    *,
    target_date: dt.date,
    retrieval_time: dt.datetime,
    source_url: str,
    seed: int,
    edition: int,
    generation_mode: str,
    correct_factoid: dict[str, Any],
    distractor_factoids: list[dict[str, Any]],
) -> dict[str, Any]:
    factoid_options = [correct_factoid, *distractor_factoids]
    factoid_options.sort(
        key=lambda item: hashlib.sha256(
            (
                f"{seed}:{item['answer_label']}:{item['source_event']['year']}:"
                f"{item['source_event']['text']}"
            ).encode("utf-8")
        ).hexdigest()
    )
    answer_kind = correct_factoid["answer_kind"]
    prompt_style = correct_factoid["prompt_style"]
    question_text = correct_factoid["question_text"]
    factoid_option_ids = [
        build_factoid_answer_fact_id(
            option["source_event"],
            answer_label=option["answer_label"],
            entity_type=answer_kind,
        )
        for option in factoid_options
    ]
    if len(set(factoid_option_ids)) != len(factoid_option_ids):
        raise ValueError("history_factoid_mcq_4 options must produce unique answer_fact ids.")

    choice_ids = ("A", "B", "C", "D")
    choices = []
    correct_choice_id: str | None = None
    answer_facts = []
    correct_answer_fact_id: str | None = None

    for choice_id, option in zip(choice_ids, factoid_options):
        source_event = option["source_event"]
        fact_id = build_factoid_answer_fact_id(
            source_event,
            answer_label=option["answer_label"],
            entity_type=answer_kind,
        )
        role = "correct" if option is correct_factoid else "distractor"
        fact = build_answer_fact(
            source_event,
            quiz_type=QUIZ_TYPE_HISTORY_FACTOID_MCQ_4,
            role=role,
            fact_id=fact_id,
            label=option["answer_label"],
            entity_type=answer_kind,
            embedding_text=f"{option['answer_label']} -- {source_event['text']}",
        )
        answer_facts.append(fact)
        choices.append(
            {
                "id": choice_id,
                "label": option["answer_label"],
                "answer_fact_id": fact["id"],
            }
        )
        option["answer_fact_id"] = fact["id"]
        if option is correct_factoid:
            correct_choice_id = choice_id
            correct_answer_fact_id = fact["id"]

    if correct_choice_id is None or correct_answer_fact_id is None:
        raise ValueError("Could not determine correct choice id for history_factoid_mcq_4.")

    correct_source_event = correct_factoid["source_event"]
    question_object = build_question_object(
        question_id=build_question_id(target_date, QUIZ_TYPE_HISTORY_FACTOID_MCQ_4, edition),
        prompt=question_text,
        quiz_type=QUIZ_TYPE_HISTORY_FACTOID_MCQ_4,
        answer_fact_ids=[fact["id"] for fact in answer_facts],
        correct_answer_fact_id=correct_answer_fact_id,
        target_year=correct_source_event["year"],
        extra_facets={
            "question_format": "factoid",
            "answer_kind": answer_kind,
            "prompt_style": prompt_style,
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
        "source": build_source(retrieval_time, source_url, factoid_options),
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


def build_source(
    retrieval_time: dt.datetime,
    source_url: str,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    def normalize_source_event(event: dict[str, Any]) -> dict[str, Any]:
        source_event = event.get("source_event")
        source_payload = source_event if isinstance(source_event, dict) else event
        event_id = event.get("answer_fact_id")
        if not isinstance(event_id, str) or not event_id.strip():
            event_id = build_answer_fact_id(source_payload)
        return {
            "event_id": event_id,
            "text": source_payload["text"],
            "year": source_payload["year"],
            "wikipedia_url": source_payload["wikipedia_url"],
        }

    return {
        "name": "Wikipedia On This Day",
        "url": source_url,
        "retrieved_at": retrieval_time.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "events_used": [normalize_source_event(event) for event in events],
    }


def _build_geography_answer_fact(record: dict[str, Any], *, role: str) -> dict[str, Any]:
    fact_id = build_answer_fact_id_from_key(
        "geography|country|"
        f"{record['country_qid']}|{record['capital_qid']}|{record['country_label']}|{record['capital_label']}"
    )
    return {
        "id": fact_id,
        "label": record["country_label"],
        "year": 0,
        "tags": [
            "geography",
            QUIZ_TYPE_GEOGRAPHY_FACTOID_MCQ_4,
            f"role:{role}",
            "entity:country",
        ],
        "facets": {
            "topic": "geography",
            "source": "wikidata",
            "entity_type": "country",
        },
        "match": {
            "distractor_profile": {
                "entity_type": "country",
                "capital_label": record["capital_label"],
            }
        },
        "vector_metadata": {
            "text_for_embedding": f"{record['country_label']} -- capital {record['capital_label']}",
            "embedding_status": "not_generated",
        },
    }


def _build_geography_source(
    retrieval_time: dt.datetime,
    source_url: str,
    options: list[dict[str, Any]],
    answer_fact_ids: list[str],
) -> dict[str, Any]:
    records_used = []
    for option, answer_fact_id in zip(options, answer_fact_ids):
        records_used.append(
            {
                "record_id": answer_fact_id,
                "country_label": option["country_label"],
                "capital_label": option["capital_label"],
                "country_qid": option["country_qid"],
                "capital_qid": option["capital_qid"],
                "country_url": option["country_url"],
                "capital_url": option["capital_url"],
            }
        )
    return {
        "name": GEOGRAPHY_SOURCE_NAME,
        "url": source_url,
        "retrieved_at": retrieval_time.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "records_used": records_used,
    }


def _build_history_mcq_4_payload(
    *,
    target_date: dt.date,
    retrieval_time: dt.datetime,
    source_url: str,
    seed: int,
    edition: int,
    generation_mode: str,
    correct: dict[str, Any],
    selected_distractors: list[dict[str, Any]],
) -> dict[str, Any]:
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


def _build_history_factoid_time_quiz(
    *,
    target_date: dt.date,
    retrieval_time: dt.datetime,
    source_url: str,
    seed: int,
    edition: int,
    generation_mode: str,
    correct: dict[str, Any],
    distractors: list[dict[str, Any]],
) -> dict[str, Any]:
    options = [correct, *distractors]
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
        fact = build_answer_fact(
            option,
            quiz_type=QUIZ_TYPE_HISTORY_FACTOID_MCQ_4,
            role=role,
            entity_type="time",
        )
        answer_facts.append(fact)
        choices.append(
            {
                "id": choice_id,
                "label": _format_year_label(option["year"]),
                "answer_fact_id": fact["id"],
            }
        )
        option["answer_fact_id"] = fact["id"]
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
    quality_stats: QualityRunStats | None = None,
) -> dict[str, Any]:
    if generation_mode not in SUPPORTED_GENERATION_MODES:
        raise ValueError(f"Unsupported generation mode: {generation_mode}")
    last_issues: tuple[str, ...] = ()
    for attempt_index, correct in enumerate(iter_history_mcq_correct_events(candidates, seed)):
        correct_seed = seed + attempt_index
        correct_event_for_pool = correct if attempt_index else None
        _, distractor_pool = pick_history_mcq_distractor_pool(
            candidates,
            correct_seed,
            preferred_distractor_events=preferred_distractor_events,
            max_distractors=8,
            correct_event=correct_event_for_pool,
        )
        selected_distractors = distractor_pool[:3]
        if attempt_index == 0 and ai_ranked_distractor_ids:
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

        payload = _build_history_mcq_4_payload(
            target_date=target_date,
            retrieval_time=retrieval_time,
            source_url=source_url,
            seed=correct_seed,
            edition=edition,
            generation_mode=generation_mode,
            correct=correct,
            selected_distractors=selected_distractors,
        )
        issues = lint_quiz_payload(payload)
        if not issues:
            return payload
        last_issues = issues
        if quality_stats is not None:
            quality_stats.add_issues(issues)
            quality_stats.add_fallback_path("history_mcq_4:alternate_correct_event")

    raise ValueError(
        "Could not build lint-clean history_mcq_4 quiz."
        if not last_issues
        else f"Could not build lint-clean history_mcq_4 quiz: {', '.join(last_issues)}."
    )


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
    preferred_answer_kind: str | None = None,
    ai_selected_factoid_candidate: dict[str, Any] | None = None,
    ai_selected_factoid_distractors: list[dict[str, Any]] | None = None,
    quality_stats: QualityRunStats | None = None,
) -> dict[str, Any]:
    del ai_ranked_distractor_ids
    if generation_mode not in SUPPORTED_GENERATION_MODES:
        raise ValueError(f"Unsupported generation mode: {generation_mode}")

    if ai_selected_factoid_candidate is not None:
        try:
            distractors = (
                ai_selected_factoid_distractors
                if ai_selected_factoid_distractors is not None
                else build_history_factoid_distractors_for_candidate(
                    candidates,
                    seed=seed,
                    correct_candidate=ai_selected_factoid_candidate,
                )
            )
            payload = _build_history_factoid_typed_quiz(
                target_date=target_date,
                retrieval_time=retrieval_time,
                source_url=source_url,
                seed=seed,
                edition=edition,
                generation_mode=generation_mode,
                correct_factoid=ai_selected_factoid_candidate,
                distractor_factoids=distractors,
            )
            issues = lint_quiz_payload(payload)
            if not issues:
                if quality_stats is not None:
                    quality_stats.add_factoid_subtype(f"typed:{ai_selected_factoid_candidate['answer_kind']}")
                return payload
            if quality_stats is not None:
                quality_stats.add_issues(issues)
                if ai_selected_factoid_distractors is not None:
                    quality_stats.add_ai_distractor_rejection_lints(issues)
                    quality_stats.add_fallback_path("history_factoid_mcq_4:ai_distractor_rejected")
                else:
                    quality_stats.add_fallback_path("history_factoid_mcq_4:ai_candidate_rejected")
        except ValueError:
            # AI-selected factoids are opportunistic. If they cannot produce four
            # unique answer facts, fall back to the deterministic typed/time flow.
            if quality_stats is not None:
                if ai_selected_factoid_distractors is not None:
                    quality_stats.add_fallback_path("history_factoid_mcq_4:ai_distractor_invalid")
                else:
                    quality_stats.add_fallback_path("history_factoid_mcq_4:ai_candidate_invalid")

    try:
        typed_candidate_sets = iter_history_factoid_typed_candidate_sets(
            candidates,
            seed,
            preferred_answer_kind=preferred_answer_kind,
        )
    except ValueError:
        typed_candidate_sets = []

    for attempt_index, (correct_factoid, distractor_factoids, selected_kind) in enumerate(typed_candidate_sets):
        payload = _build_history_factoid_typed_quiz(
            target_date=target_date,
            retrieval_time=retrieval_time,
            source_url=source_url,
            seed=seed + attempt_index,
            edition=edition,
            generation_mode=generation_mode,
            correct_factoid=correct_factoid,
            distractor_factoids=distractor_factoids,
        )
        issues = lint_quiz_payload(payload)
        if not issues:
            if quality_stats is not None:
                quality_stats.add_factoid_subtype(f"typed:{selected_kind}")
            return payload
        if quality_stats is not None:
            quality_stats.add_issues(issues)
            quality_stats.add_fallback_path("history_factoid_mcq_4:alternate_typed_candidate")

    for attempt_index, correct in enumerate(iter_history_mcq_correct_events(candidates, seed)):
        correct_seed = seed + attempt_index
        _, distractor_pool = pick_history_mcq_distractor_pool(
            candidates,
            correct_seed,
            preferred_distractor_events=preferred_distractor_events,
            max_distractors=3,
            correct_event=correct,
        )
        payload = _build_history_factoid_time_quiz(
            target_date=target_date,
            retrieval_time=retrieval_time,
            source_url=source_url,
            seed=correct_seed,
            edition=edition,
            generation_mode=generation_mode,
            correct=correct,
            distractors=distractor_pool[:3],
        )
        issues = lint_quiz_payload(payload)
        if not issues:
            if quality_stats is not None:
                quality_stats.add_factoid_subtype("time")
                if attempt_index > 0 or typed_candidate_sets:
                    quality_stats.add_fallback_path("history_factoid_mcq_4:time_builder")
            return payload
        if quality_stats is not None:
            quality_stats.add_issues(issues)
            quality_stats.add_fallback_path("history_factoid_mcq_4:alternate_time_candidate")

    raise ValueError("Could not build lint-clean history_factoid_mcq_4 quiz.")


def build_geography_factoid_mcq_4_quiz(
    target_date: dt.date,
    retrieval_time: dt.datetime,
    source_url: str,
    candidates: list[dict[str, Any]],
    seed: int,
    edition: int,
    generation_mode: str,
    preferred_distractor_events: list[dict[str, Any]] | None = None,
    ai_ranked_distractor_ids: list[str] | None = None,
    quality_stats: QualityRunStats | None = None,
) -> dict[str, Any]:
    del preferred_distractor_events
    del ai_ranked_distractor_ids
    del quality_stats
    if generation_mode not in SUPPORTED_GENERATION_MODES:
        raise ValueError(f"Unsupported generation mode: {generation_mode}")

    correct, distractors = pick_geography_factoid_records(candidates, seed)
    options = [correct, *distractors]
    options.sort(key=lambda item: geography_option_sort_key(seed, item))

    choice_ids = ("A", "B", "C", "D")
    choices: list[dict[str, Any]] = []
    answer_facts: list[dict[str, Any]] = []
    correct_choice_id: str | None = None
    correct_answer_fact_id: str | None = None

    for choice_id, option in zip(choice_ids, options):
        role = "correct" if option is correct else "distractor"
        fact = _build_geography_answer_fact(option, role=role)
        answer_facts.append(fact)
        choices.append(
            {
                "id": choice_id,
                "label": option["country_label"],
                "answer_fact_id": fact["id"],
            }
        )
        if option is correct:
            correct_choice_id = choice_id
            correct_answer_fact_id = fact["id"]

    if correct_choice_id is None or correct_answer_fact_id is None:
        raise ValueError("Could not determine correct choice id for geography_factoid_mcq_4.")

    question_text = f"Which country has the capital {correct['capital_label']}?"
    question_object = build_question_object(
        question_id=build_question_id(target_date, QUIZ_TYPE_GEOGRAPHY_FACTOID_MCQ_4, edition),
        prompt=question_text,
        quiz_type=QUIZ_TYPE_GEOGRAPHY_FACTOID_MCQ_4,
        answer_fact_ids=[fact["id"] for fact in answer_facts],
        correct_answer_fact_id=correct_answer_fact_id,
        topic="geography",
        extra_facets={
            "question_format": "factoid",
            "answer_kind": "country",
            "prompt_style": "capital_to_country",
        },
        extra_selection_rules={
            "capital_label": correct["capital_label"],
        },
    )

    return {
        "date": target_date.isoformat(),
        "topics": ["geography"],
        "type": QUIZ_TYPE_GEOGRAPHY_FACTOID_MCQ_4,
        "questions": [question_object],
        "answer_facts": answer_facts,
        "question": question_text,
        "choices": choices,
        "correct_choice_id": correct_choice_id,
        "source": _build_geography_source(
            retrieval_time,
            source_url,
            options,
            [fact["id"] for fact in answer_facts],
        ),
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
    QUIZ_TYPE_GEOGRAPHY_FACTOID_MCQ_4: build_geography_factoid_mcq_4_quiz,
}
