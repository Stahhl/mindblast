"""Feature-flagged AI pipeline for history factoid quizzes (Phase 5.5)."""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
from typing import Any

from .constants import AI_MODE_ON, AI_MODE_SHADOW
from .ai.orchestrator import AIOrchestrator
from .model import build_factoid_answer_fact_id
from .selection import (
    build_history_factoid_distractor_pool_for_candidate,
    extract_history_factoid_typed_candidates,
    looks_like_person_label,
    looks_like_place_label,
    select_history_factoid_distractors_from_pool,
)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean-like value.")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return int(raw)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return float(raw)


@dataclass(frozen=True)
class FactoidPipelineSettings:
    enabled: bool
    model_qgen: str
    model_ranker: str
    model_distractors: str
    model_judge: str
    max_stage_tokens: int
    min_question_score: float
    min_final_score: float


def load_factoid_pipeline_settings(default_model: str) -> FactoidPipelineSettings:
    model_fallback = os.getenv("AI_MODEL", default_model).strip() or default_model
    strong_model_fallback = os.getenv("FACTOID_AI_STRONG_MODEL", "gpt-5.2").strip() or "gpt-5.2"
    light_model_fallback = os.getenv("FACTOID_AI_LIGHT_MODEL", model_fallback).strip() or model_fallback
    return FactoidPipelineSettings(
        enabled=_env_bool("FACTOID_AI_PIPELINE_ENABLED", False),
        model_qgen=(os.getenv("FACTOID_AI_MODEL_QA_GEN", strong_model_fallback).strip() or strong_model_fallback),
        model_ranker=(os.getenv("FACTOID_AI_MODEL_RANKER", light_model_fallback).strip() or light_model_fallback),
        model_distractors=(
            os.getenv("FACTOID_AI_MODEL_DISTRACTOR_GEN", strong_model_fallback).strip() or strong_model_fallback
        ),
        model_judge=(os.getenv("FACTOID_AI_MODEL_JUDGE", light_model_fallback).strip() or light_model_fallback),
        max_stage_tokens=_env_int("FACTOID_AI_MAX_STAGE_TOKENS", 700),
        min_question_score=_env_float("FACTOID_AI_MIN_QUESTION_SCORE", 0.6),
        min_final_score=_env_float("FACTOID_AI_MIN_FINAL_SCORE", 0.7),
    )


def _quality_score(value: Any) -> float:
    if isinstance(value, (int, float)):
        return max(0.0, min(1.0, float(value)))
    return 0.0


def _normalize_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split()).strip()
    return normalized or None


def _typed_factoid_pairs() -> dict[str, str]:
    return {
        "person": "who",
        "place": "where",
        "time": "when",
    }


_ALNUM_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _candidate_id(candidate: dict[str, Any]) -> str:
    return build_factoid_answer_fact_id(
        candidate["source_event"],
        answer_label=str(candidate["answer_label"]),
        entity_type=str(candidate["answer_kind"]),
    )


def _tokenize(value: str) -> set[str]:
    return {token for token in _ALNUM_TOKEN_RE.findall(value.casefold()) if token}


def _label_matches_answer_kind(answer_kind: str, label: str) -> bool:
    if answer_kind == "person":
        return looks_like_person_label(label)
    if answer_kind == "place":
        return looks_like_place_label(label)
    if answer_kind == "time":
        return any(char.isdigit() for char in label)
    return False


def _normalized_label_is_grounded(
    *,
    normalized_label: str,
    original_label: str,
    source_text: str,
) -> bool:
    normalized_tokens = _tokenize(normalized_label)
    if not normalized_tokens:
        return False
    source_tokens = _tokenize(source_text)
    if not normalized_tokens.issubset(source_tokens):
        return False
    original_tokens = _tokenize(original_label)
    return bool(normalized_tokens & original_tokens)


def _reviewed_candidate_sort_key(candidate: dict[str, Any]) -> tuple[int, str, int, str]:
    answer_kind_priority = {"person": 0, "place": 1, "time": 2}
    source_event = candidate["source_event"]
    return (
        answer_kind_priority.get(str(candidate["answer_kind"]), 9),
        str(candidate["answer_label"]).casefold(),
        int(source_event["year"]),
        str(source_event["text"]),
    )


def _reviewed_typed_candidates(
    *,
    candidates: list[dict[str, Any]],
    settings: FactoidPipelineSettings,
    ai_orchestrator: AIOrchestrator,
) -> tuple[list[dict[str, Any]], str | None]:
    extracted_by_kind = extract_history_factoid_typed_candidates(candidates)
    extracted_candidates = [
        candidate
        for answer_kind in ("person", "place")
        for candidate in extracted_by_kind[answer_kind]
    ]
    if not extracted_candidates:
        return [], "factoid_typed_candidate_none_extracted"

    candidate_payload = [
        {
            "candidate_id": _candidate_id(candidate),
            "answer_kind": candidate["answer_kind"],
            "prompt_style": candidate["prompt_style"],
            "answer_label": candidate["answer_label"],
            "question_text": candidate["question_text"],
            "source_year": candidate["source_event"]["year"],
            "source_text": candidate["source_event"]["text"],
            "source_url": candidate["source_event"]["wikipedia_url"],
        }
        for candidate in sorted(extracted_candidates, key=_reviewed_candidate_sort_key)
    ]
    response, reason = ai_orchestrator.run_json_task(
        task_name="factoid_typed_candidate_review",
        system_prompt=(
            "Review grounded history factoid candidates. "
            "Return JSON only with candidate_reviews. "
            "Approve only candidates whose answer_label is a short standalone entity matching answer_kind. "
            "For person questions, approve only real people. "
            "For place questions, approve only places/locations. "
            "Reject fragments, event titles, wars, organizations, time phrases, vague labels, or mixed-type answers. "
            "Do not invent new facts or new candidate ids."
        ),
        user_payload={
            "task": "factoid_typed_candidate_review",
            "candidates": candidate_payload,
            "constraints": {
                "allowed_answer_kinds": ["person", "place"],
                "allowed_prompt_styles": ["who", "where"],
                "must_preserve_candidate_ids": True,
                "grounded_only": True,
            },
        },
        model=settings.model_qgen,
        max_output_tokens=settings.max_stage_tokens,
        response_schema={
            "name": "factoid_typed_candidate_review",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["candidate_reviews"],
                "properties": {
                    "candidate_reviews": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": [
                                "candidate_id",
                                "answer_kind",
                                "normalized_answer_label",
                                "prompt_style",
                                "supported",
                                "rejection_reason",
                            ],
                            "properties": {
                                "candidate_id": {"type": "string"},
                                "answer_kind": {"type": "string", "enum": ["person", "place"]},
                                "normalized_answer_label": {"type": "string"},
                                "prompt_style": {"type": "string", "enum": ["who", "where"]},
                                "supported": {"type": "boolean"},
                                "rejection_reason": {"type": "string"},
                            },
                        },
                    }
                },
            },
        },
    )
    if response is None:
        return [], reason or "factoid_typed_candidate_review_failed"

    raw_reviews = response.get("candidate_reviews")
    if not isinstance(raw_reviews, list) or not raw_reviews:
        return [], "factoid_typed_candidate_review_empty"

    by_candidate_id = {
        _candidate_id(candidate): candidate
        for candidate in extracted_candidates
    }
    reviewed: list[dict[str, Any]] = []
    for item in raw_reviews:
        if not isinstance(item, dict):
            continue
        candidate_id = _normalize_text(item.get("candidate_id"))
        answer_kind = item.get("answer_kind")
        prompt_style = item.get("prompt_style")
        normalized_answer_label = _normalize_text(item.get("normalized_answer_label"))
        supported = item.get("supported")
        if not isinstance(candidate_id, str) or candidate_id not in by_candidate_id:
            continue
        original = by_candidate_id[candidate_id]
        if answer_kind != original["answer_kind"] or prompt_style != original["prompt_style"]:
            continue
        if supported is not True:
            continue
        if normalized_answer_label is None:
            continue
        source_text = _normalize_text(original["source_event"].get("text"))
        if source_text is None:
            continue
        if not _label_matches_answer_kind(answer_kind, normalized_answer_label):
            continue
        if not _normalized_label_is_grounded(
            normalized_label=normalized_answer_label,
            original_label=str(original["answer_label"]),
            source_text=source_text,
        ):
            continue
        reviewed_candidate = dict(original)
        reviewed_candidate["answer_label"] = normalized_answer_label
        reviewed.append(reviewed_candidate)

    if not reviewed:
        return [], "factoid_typed_candidate_review_no_supported_candidates"

    return reviewed, None


def _select_ai_typed_distractors(
    *,
    correct_candidate: dict[str, Any],
    reviewed_candidates: list[dict[str, Any]],
    settings: FactoidPipelineSettings,
    ai_orchestrator: AIOrchestrator,
) -> tuple[list[dict[str, Any]] | None, str | None]:
    answer_kind = str(correct_candidate.get("answer_kind"))
    distractor_pool = build_history_factoid_distractor_pool_for_candidate(
        reviewed_candidates,
        correct_candidate=correct_candidate,
    )
    if len({candidate["answer_label"].casefold() for candidate in distractor_pool}) < 3:
        return None, "factoid_typed_distractor_pool_too_small"

    response, reason = ai_orchestrator.run_json_task(
        task_name="factoid_typed_distractor_select",
        system_prompt=(
            "Select grounded distractors for a history factoid multiple-choice quiz. "
            "Return JSON only with selected_distractor_ids and optional reason_codes. "
            "Use only provided candidate ids. "
            "All selected distractors must match answer_kind exactly. "
            "Never mix people, places, events, wars, organizations, or time expressions in one answer set. "
            "Prefer short standalone entity labels and avoid vague fragments."
        ),
        user_payload={
            "task": "factoid_typed_distractor_select",
            "answer_kind": answer_kind,
            "question_prompt": correct_candidate["question_text"],
            "correct_candidate": {
                "candidate_id": _candidate_id(correct_candidate),
                "answer_label": correct_candidate["answer_label"],
            },
            "distractor_candidates": [
                {
                    "candidate_id": _candidate_id(candidate),
                    "answer_label": candidate["answer_label"],
                    "source_year": candidate["source_event"]["year"],
                    "source_text": candidate["source_event"]["text"],
                }
                for candidate in sorted(distractor_pool, key=_reviewed_candidate_sort_key)
            ],
            "constraints": {
                "return_exactly": 3,
                "ids_must_come_from_candidates": True,
                "grounded_only": True,
                "same_entity_type_only": True,
            },
        },
        model=settings.model_distractors,
        max_output_tokens=260,
        response_schema={
            "name": "factoid_typed_distractor_select",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["selected_distractor_ids", "reason_codes"],
                "properties": {
                    "selected_distractor_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "reason_codes": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
    )
    if response is None:
        return None, reason or "factoid_typed_distractor_select_failed"

    selected_candidate_ids = response.get("selected_distractor_ids")
    if not isinstance(selected_candidate_ids, list) or not all(isinstance(item, str) for item in selected_candidate_ids):
        return None, "factoid_typed_distractor_select_invalid_ids"

    try:
        return (
            select_history_factoid_distractors_from_pool(
                distractor_pool,
                selected_candidate_ids=list(selected_candidate_ids),
            ),
            None,
        )
    except ValueError:
        return None, "factoid_typed_distractor_select_invalid_ids"


def _validate_ai_factoid_candidate(candidate: Any, *, source_event: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(candidate, dict):
        return None
    answer_kind = candidate.get("answer_kind")
    prompt_style = candidate.get("prompt_style")
    if answer_kind not in _typed_factoid_pairs():
        return None
    if prompt_style != _typed_factoid_pairs()[answer_kind]:
        return None

    question = _normalize_text(candidate.get("question"))
    answer_label = _normalize_text(candidate.get("correct_answer"))
    if question is None or answer_label is None:
        return None
    if not question.endswith("?"):
        question = f"{question}?"
    if not question.lower().startswith(prompt_style):
        return None
    if len(question) > 220 or len(answer_label) > 80:
        return None
    if answer_kind != "time" and any(char.isdigit() for char in answer_label):
        return None
    if answer_kind == "time" and not any(char.isdigit() for char in answer_label):
        return None
    source_text = _normalize_text(source_event.get("text"))
    if source_text is None:
        return None
    lowered_source = source_text.casefold()
    if answer_kind in {"person", "place"} and answer_label.casefold() not in lowered_source:
        return None

    return {
        "answer_kind": answer_kind,
        "prompt_style": prompt_style,
        "answer_label": answer_label,
        "question_text": question,
        "source_event": source_event,
        "quality_score": _quality_score(candidate.get("score")),
    }


def propose_ai_factoid_candidate(
    *,
    candidates: list[dict[str, Any]],
    seed: int,
    preferred_answer_kind: str | None,
    settings: FactoidPipelineSettings,
    ai_orchestrator: AIOrchestrator,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]] | None, str | None]:
    if not settings.enabled:
        return None, None, "factoid_pipeline_disabled"
    if not ai_orchestrator.is_enabled():
        return None, None, "factoid_pipeline_ai_disabled"
    if len(candidates) < 4:
        return None, None, "factoid_ai_candidate_not_enough_source_events"

    reviewed_candidates, review_reason = _reviewed_typed_candidates(
        candidates=candidates,
        settings=settings,
        ai_orchestrator=ai_orchestrator,
    )
    if not reviewed_candidates:
        return None, None, review_reason or "factoid_typed_candidate_review_failed"

    by_kind = {"person": [], "place": []}
    for candidate in reviewed_candidates:
        answer_kind = str(candidate["answer_kind"])
        if answer_kind in by_kind:
            by_kind[answer_kind].append(candidate)

    eligible_kinds = [
        answer_kind
        for answer_kind in ("person", "place")
        if len({_candidate_id(candidate) for candidate in by_kind[answer_kind]}) >= 4
    ]
    if not eligible_kinds:
        return None, None, "factoid_typed_candidate_review_not_enough_grounded_candidates"

    if preferred_answer_kind in eligible_kinds:
        selected_kind = preferred_answer_kind
    else:
        selected_kind = eligible_kinds[seed % len(eligible_kinds)]

    ordered_candidates = sorted(by_kind[selected_kind], key=_reviewed_candidate_sort_key)
    correct_candidate = ordered_candidates[seed % len(ordered_candidates)]

    selected_distractors, distractor_reason = _select_ai_typed_distractors(
        correct_candidate=correct_candidate,
        reviewed_candidates=ordered_candidates,
        settings=settings,
        ai_orchestrator=ai_orchestrator,
    )
    return correct_candidate, selected_distractors, distractor_reason


def _extract_correct_and_choices(quiz: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source = quiz.get("source")
    if not isinstance(source, dict):
        raise ValueError("quiz.source must be an object.")
    events = source.get("events_used")
    if not isinstance(events, list) or len(events) != 4:
        raise ValueError("quiz.source.events_used must contain exactly 4 entries.")
    by_event_id = {
        event["event_id"]: event
        for event in events
        if isinstance(event, dict) and isinstance(event.get("event_id"), str)
    }
    choices = quiz.get("choices")
    if not isinstance(choices, list) or len(choices) != 4:
        raise ValueError("quiz.choices must contain exactly 4 entries.")
    correct_choice_id = quiz.get("correct_choice_id")
    correct_choice = next(
        (
            choice
            for choice in choices
            if isinstance(choice, dict)
            and choice.get("id") == correct_choice_id
            and isinstance(choice.get("answer_fact_id"), str)
        ),
        None,
    )
    if correct_choice is None:
        raise ValueError("Correct choice not found in quiz.")
    correct_event = by_event_id.get(correct_choice["answer_fact_id"])
    if correct_event is None:
        raise ValueError("Correct source event not found.")
    return correct_event, [choice for choice in choices if isinstance(choice, dict)]


def apply_factoid_ai_pipeline(
    *,
    quiz: dict[str, Any],
    settings: FactoidPipelineSettings,
    ai_orchestrator: AIOrchestrator,
) -> tuple[dict[str, Any], str | None]:
    """Return updated quiz and optional fallback reason.

    This pipeline intentionally fails closed and leaves the deterministic quiz unchanged.
    """
    if not settings.enabled:
        return quiz, "factoid_pipeline_disabled"
    if not ai_orchestrator.is_enabled():
        return quiz, "factoid_pipeline_ai_disabled"
    questions = quiz.get("questions")
    question = questions[0] if isinstance(questions, list) and questions and isinstance(questions[0], dict) else None
    facets = question.get("facets") if isinstance(question, dict) else None
    if not isinstance(facets, dict):
        return quiz, "factoid_pipeline_missing_question_facets"
    if facets.get("answer_kind") != "time" or facets.get("prompt_style") != "when":
        return quiz, "factoid_pipeline_unsupported_prompt_style"

    correct_event, choices = _extract_correct_and_choices(quiz)
    correct_year = correct_event.get("year")
    correct_text = correct_event.get("text")
    article_url = correct_event.get("wikipedia_url")
    if not isinstance(correct_year, int) or not isinstance(correct_text, str) or not isinstance(article_url, str):
        return quiz, "factoid_pipeline_missing_source_context"

    qgen_payload = {
        "task": "factoid_question_generation",
        "expected_prompt_style": "when",
        "answer_kind": "time",
        "article_url": article_url,
        "event_text": correct_text,
        "event_year": correct_year,
        "constraints": {
            "question_must_end_with_question_mark": True,
            "question_should_start_with_when": True,
            "max_question_length": 180,
            "num_candidates": 3,
        },
    }
    qgen_response, qgen_reason = ai_orchestrator.run_json_task(
        task_name="factoid_qgen",
        system_prompt=(
            "Generate concise history factoid questions. "
            "Return JSON only with candidates array. "
            "Each candidate: question (string), score (0..1). "
            "All questions must be 'when' style and answerable by year."
        ),
        user_payload=qgen_payload,
        model=settings.model_qgen,
        max_output_tokens=settings.max_stage_tokens,
    )
    if qgen_response is None:
        return quiz, qgen_reason or "factoid_qgen_failed"
    candidates = qgen_response.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return quiz, "factoid_qgen_empty"

    rank_payload = {
        "task": "factoid_question_rank",
        "candidates": candidates,
        "quality_bar": settings.min_question_score,
    }
    rank_response, rank_reason = ai_orchestrator.run_json_task(
        task_name="factoid_qrank",
        system_prompt=(
            "Rank candidate history factoid questions. "
            "Return JSON only with best_index (int) and best_score (0..1)."
        ),
        user_payload=rank_payload,
        model=settings.model_ranker,
        max_output_tokens=220,
    )
    if rank_response is None:
        return quiz, rank_reason or "factoid_qrank_failed"
    best_index_raw = rank_response.get("best_index")
    best_score = _quality_score(rank_response.get("best_score"))
    if not isinstance(best_index_raw, int) or best_index_raw < 0 or best_index_raw >= len(candidates):
        return quiz, "factoid_qrank_invalid_index"
    if best_score < settings.min_question_score:
        return quiz, "factoid_qrank_below_threshold"
    selected_candidate = candidates[best_index_raw]
    if not isinstance(selected_candidate, dict):
        return quiz, "factoid_qrank_invalid_candidate"
    selected_question = selected_candidate.get("question")
    if not isinstance(selected_question, str) or not selected_question.strip():
        return quiz, "factoid_qrank_missing_question"
    selected_question = " ".join(selected_question.split()).strip()
    if not selected_question.endswith("?"):
        selected_question = f"{selected_question}?"
    if not selected_question.lower().startswith("when"):
        return quiz, "factoid_qrank_not_when_style"

    distractor_payload = {
        "task": "factoid_distractor_label_generation",
        "answer_kind": "time",
        "question": selected_question,
        "choices": [
            {
                "id": choice["id"],
                "label": choice.get("label"),
                "is_correct": bool(choice.get("id") == quiz.get("correct_choice_id")),
            }
            for choice in choices
        ],
        "constraints": {
            "return_choice_labels_by_id": True,
            "must_keep_choice_ids": True,
            "short_labels": True,
        },
    }
    distractor_response, distractor_reason = ai_orchestrator.run_json_task(
        task_name="factoid_distractors",
        system_prompt=(
            "Rewrite multiple-choice labels for a history 'when' question. "
            "Return JSON only with choice_labels_by_id object keyed by choice id. "
            "Keep labels short, factual, and suitable for time answers."
        ),
        user_payload=distractor_payload,
        model=settings.model_distractors,
        max_output_tokens=260,
    )
    if distractor_response is None:
        return quiz, distractor_reason or "factoid_distractors_failed"
    labels_by_id = distractor_response.get("choice_labels_by_id")
    if not isinstance(labels_by_id, dict):
        return quiz, "factoid_distractors_invalid_labels"

    updated_choices: list[dict[str, Any]] = []
    for choice in choices:
        choice_id = choice.get("id")
        if not isinstance(choice_id, str):
            return quiz, "factoid_distractors_invalid_choice_id"
        replacement = labels_by_id.get(choice_id, choice.get("label"))
        if not isinstance(replacement, str) or not replacement.strip():
            return quiz, "factoid_distractors_empty_label"
        updated = dict(choice)
        updated["label"] = " ".join(replacement.split())
        updated_choices.append(updated)

    judge_payload = {
        "task": "factoid_final_judge",
        "question": selected_question,
        "choices": [{"id": choice["id"], "label": choice["label"]} for choice in updated_choices],
        "correct_choice_id": quiz.get("correct_choice_id"),
        "quality_bar": settings.min_final_score,
    }
    judge_response, judge_reason = ai_orchestrator.run_json_task(
        task_name="factoid_final_rank",
        system_prompt=(
            "Judge quality of a history factoid multiple-choice question. "
            "Return JSON only with final_score (0..1) and publishable (boolean)."
        ),
        user_payload=judge_payload,
        model=settings.model_judge,
        max_output_tokens=200,
    )
    if judge_response is None:
        return quiz, judge_reason or "factoid_judge_failed"
    final_score = _quality_score(judge_response.get("final_score"))
    publishable = bool(judge_response.get("publishable"))
    if not publishable or final_score < settings.min_final_score:
        return quiz, "factoid_judge_below_threshold"

    if ai_orchestrator.settings.mode == AI_MODE_SHADOW:
        return quiz, "shadow_mode"
    if ai_orchestrator.settings.mode != AI_MODE_ON:
        return quiz, "invalid_mode"

    updated_quiz = dict(quiz)
    updated_quiz["question"] = selected_question
    updated_quiz["choices"] = updated_choices

    questions = updated_quiz.get("questions")
    if isinstance(questions, list) and questions and isinstance(questions[0], dict):
        question_obj = dict(questions[0])
        question_obj["prompt"] = selected_question
        facets = question_obj.get("facets")
        if isinstance(facets, dict):
            new_facets = dict(facets)
            new_facets["generation_method"] = "ai_native_factoid_v1"
            question_obj["facets"] = new_facets
        questions = list(questions)
        questions[0] = question_obj
        updated_quiz["questions"] = questions

    metadata = updated_quiz.get("metadata")
    if isinstance(metadata, dict):
        new_metadata = dict(metadata)
        new_metadata["pipeline_version"] = "phase5_5_v1"
        new_metadata["generation_method"] = "ai_native_factoid_v1"
        updated_quiz["metadata"] = new_metadata

    return updated_quiz, None
