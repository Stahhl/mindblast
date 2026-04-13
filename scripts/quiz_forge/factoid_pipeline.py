"""AI-native page-grounded pipeline for history factoid quizzes."""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import hashlib
import os
import re
from typing import Any

from .ai.orchestrator import AIOrchestrator
from .builders import _build_history_factoid_typed_quiz
from .constants import AI_MODE_ON, AI_MODE_SHADOW
from .model import build_answer_fact_id, build_factoid_answer_fact_id
from .quality import QualityRunStats
from .selection import candidate_selection_score, order_history_candidates_for_selection
from .source import fetch_wikipedia_page_summary

_ALNUM_TOKEN_RE = re.compile(r"[a-z0-9]+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

_ANSWER_KIND_PROMPT_STYLES = {
    "person": {"who"},
    "place": {"where"},
    "organization": {"what", "which"},
    "work": {"what", "which"},
    "object": {"what", "which"},
    "time": {"when", "what"},
}


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


def _normalize_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split()).strip()
    return normalized or None


def _normalize_token_key(value: str) -> str:
    return _NON_ALNUM_RE.sub(" ", value.casefold()).strip()


def _tokenize(value: str) -> set[str]:
    return {token for token in _ALNUM_TOKEN_RE.findall(value.casefold()) if token}


def _text_contains(needle: str, haystack: str) -> bool:
    normalized_needle = _normalize_text(needle)
    normalized_haystack = _normalize_text(haystack)
    if normalized_needle is None or normalized_haystack is None:
        return False
    return normalized_needle.casefold() in normalized_haystack.casefold()


def _question_leaks_answer(question: str, answer: str) -> bool:
    return _normalize_token_key(answer) in _normalize_token_key(question)


def _normalize_subtype(value: Any) -> str | None:
    normalized = _normalize_text(value)
    if normalized is None:
        return None
    normalized = normalized.casefold().replace("-", "_").replace("/", "_")
    normalized = re.sub(r"[^a-z0-9_ ]+", "", normalized)
    normalized = re.sub(r"\s+", "_", normalized).strip("_")
    if not normalized:
        return None
    return normalized[:40]


def _quality_score(value: Any) -> float:
    if isinstance(value, (int, float)):
        return max(0.0, min(1.0, float(value)))
    return 0.0


def _candidate_id(candidate: dict[str, Any]) -> str:
    return build_factoid_answer_fact_id(
        candidate["source_event"],
        answer_label=str(candidate["answer_label"]),
        entity_type=str(candidate["answer_kind"]),
        entity_subtype=str(candidate["answer_subtype"]),
    )


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
    max_page_contexts: int
    max_page_extract_chars: int


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
        max_stage_tokens=_env_int("FACTOID_AI_MAX_STAGE_TOKENS", 900),
        min_question_score=_env_float("FACTOID_AI_MIN_QUESTION_SCORE", 0.7),
        min_final_score=_env_float("FACTOID_AI_MIN_FINAL_SCORE", 0.75),
        max_page_contexts=_env_int("FACTOID_AI_MAX_PAGE_CONTEXTS", 8),
        max_page_extract_chars=_env_int("FACTOID_AI_MAX_PAGE_EXTRACT_CHARS", 1200),
    )


def _build_page_contexts(
    *,
    candidates: list[dict[str, Any]],
    seed: int,
    retrieval_time: dt.datetime,
    settings: FactoidPipelineSettings,
    timeout: int,
    retries: int,
    quality_stats: QualityRunStats | None,
) -> tuple[list[dict[str, Any]], str | None]:
    ordered = order_history_candidates_for_selection(candidates, seed)
    page_contexts: list[dict[str, Any]] = []

    for event in ordered:
        if len(page_contexts) >= settings.max_page_contexts:
            break
        try:
            summary_payload = fetch_wikipedia_page_summary(
                event["wikipedia_url"],
                timeout=timeout,
                retries=retries,
            )
        except Exception:
            if quality_stats is not None:
                quality_stats.add_ai_stage_failure("page_context_fetch_failed")
            continue

        page_title = _normalize_text(summary_payload.get("title"))
        page_extract = _normalize_text(summary_payload.get("extract"))
        if page_title is None or page_extract is None:
            if quality_stats is not None:
                quality_stats.add_ai_stage_failure("page_context_fetch_failed")
            continue

        page_contexts.append(
            {
                "page_context_id": build_answer_fact_id(event),
                "event_id": build_answer_fact_id(event),
                "source_event": event,
                "event_text": event["text"],
                "event_year": event["year"],
                "page_url": event["wikipedia_url"],
                "page_title": page_title,
                "page_extract": page_extract[: settings.max_page_extract_chars],
                "retrieved_at": retrieval_time.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            }
        )

    if quality_stats is not None:
        quality_stats.add_page_context_fetches(len(page_contexts))

    if not page_contexts:
        return [], "page_context_fetch_failed"
    return page_contexts, None


def _validate_generated_candidate(
    candidate: Any,
    *,
    by_page_context_id: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if not isinstance(candidate, dict):
        return None

    page_context_id = _normalize_text(candidate.get("page_context_id"))
    question = _normalize_text(candidate.get("question"))
    answer_label = _normalize_text(candidate.get("correct_answer"))
    answer_kind = candidate.get("answer_kind")
    answer_subtype = _normalize_subtype(candidate.get("answer_subtype"))
    prompt_style = _normalize_text(candidate.get("prompt_style"))
    evidence_text = _normalize_text(candidate.get("evidence_text"))

    if (
        page_context_id is None
        or question is None
        or answer_label is None
        or answer_kind not in _ANSWER_KIND_PROMPT_STYLES
        or answer_subtype is None
        or prompt_style is None
        or evidence_text is None
    ):
        return None

    if prompt_style not in _ANSWER_KIND_PROMPT_STYLES[answer_kind]:
        return None
    if not question.endswith("?"):
        question = f"{question}?"
    if not question.casefold().startswith(prompt_style.casefold()):
        return None
    if len(question) > 220 or len(answer_label) > 90 or len(evidence_text) > 240:
        return None
    if answer_kind != "time" and any(char.isdigit() for char in answer_label):
        return None
    if answer_kind == "time" and not any(char.isdigit() for char in answer_label):
        return None
    if _question_leaks_answer(question, answer_label):
        return None

    page_context = by_page_context_id.get(page_context_id)
    if page_context is None:
        return None
    page_title = page_context["page_title"]
    page_extract = page_context["page_extract"]

    if not (_text_contains(answer_label, page_title) or _text_contains(answer_label, page_extract)):
        return None
    if not _text_contains(evidence_text, page_extract):
        return None

    return {
        "page_context_id": page_context_id,
        "page_context": page_context,
        "source_event": page_context["source_event"],
        "answer_kind": answer_kind,
        "answer_subtype": answer_subtype,
        "prompt_style": prompt_style,
        "answer_label": answer_label,
        "question_text": question,
        "evidence_text": evidence_text,
        "quality_score": _quality_score(candidate.get("score")),
    }


def _generate_grounded_candidates(
    *,
    page_contexts: list[dict[str, Any]],
    settings: FactoidPipelineSettings,
    ai_orchestrator: AIOrchestrator,
    quality_stats: QualityRunStats | None,
) -> tuple[list[dict[str, Any]], str | None]:
    response, reason = ai_orchestrator.run_json_task(
        task_name="factoid_page_candidate_generate",
        system_prompt=(
            "Generate grounded history quiz candidates from Wikipedia page context. "
            "Return JSON only with candidates. "
            "Each candidate must be answerable from the provided page_title and page_extract. "
            "Do not invent answers, page ids, or evidence spans. "
            "Use short answer labels and realistic quiz wording."
        ),
        user_payload={
            "task": "factoid_page_candidate_generate",
            "page_contexts": [
                {
                    "page_context_id": page_context["page_context_id"],
                    "event_id": page_context["event_id"],
                    "event_text": page_context["event_text"],
                    "event_year": page_context["event_year"],
                    "page_url": page_context["page_url"],
                    "page_title": page_context["page_title"],
                    "page_extract": page_context["page_extract"],
                }
                for page_context in page_contexts
            ],
            "constraints": {
                "grounded_only": True,
                "candidates_per_page_max": 3,
                "must_include_answer_kind": True,
                "must_include_answer_subtype": True,
                "must_include_prompt_style": True,
                "must_include_evidence_text": True,
                "supported_answer_kinds": sorted(_ANSWER_KIND_PROMPT_STYLES),
                "supported_prompt_styles": sorted(
                    {prompt_style for styles in _ANSWER_KIND_PROMPT_STYLES.values() for prompt_style in styles}
                ),
            },
        },
        model=settings.model_qgen,
        max_output_tokens=settings.max_stage_tokens,
        response_schema={
            "name": "factoid_page_candidate_generate",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["candidates"],
                "properties": {
                    "candidates": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": [
                                "page_context_id",
                                "question",
                                "correct_answer",
                                "answer_kind",
                                "answer_subtype",
                                "prompt_style",
                                "evidence_text",
                                "score",
                            ],
                            "properties": {
                                "page_context_id": {"type": "string"},
                                "question": {"type": "string"},
                                "correct_answer": {"type": "string"},
                                "answer_kind": {
                                    "type": "string",
                                    "enum": sorted(_ANSWER_KIND_PROMPT_STYLES),
                                },
                                "answer_subtype": {"type": "string"},
                                "prompt_style": {
                                    "type": "string",
                                    "enum": sorted(
                                        {prompt_style for styles in _ANSWER_KIND_PROMPT_STYLES.values() for prompt_style in styles}
                                    ),
                                },
                                "evidence_text": {"type": "string"},
                                "score": {"type": "number"},
                            },
                        },
                    }
                },
            },
        },
    )
    if response is None:
        if quality_stats is not None and reason is not None:
            quality_stats.add_ai_stage_failure(reason)
        return [], reason or "factoid_page_candidate_generate_failed"

    raw_candidates = response.get("candidates")
    if not isinstance(raw_candidates, list) or not raw_candidates:
        if quality_stats is not None:
            quality_stats.add_ai_stage_failure("candidate_ungrounded")
        return [], "candidate_ungrounded"

    by_page_context_id = {page_context["page_context_id"]: page_context for page_context in page_contexts}
    validated: list[dict[str, Any]] = []
    seen_candidate_ids: set[str] = set()
    for item in raw_candidates:
        validated_candidate = _validate_generated_candidate(item, by_page_context_id=by_page_context_id)
        if validated_candidate is None:
            continue
        if validated_candidate["quality_score"] < settings.min_question_score:
            continue
        candidate_id = _candidate_id(validated_candidate)
        if candidate_id in seen_candidate_ids:
            continue
        seen_candidate_ids.add(candidate_id)
        validated_candidate["candidate_id"] = candidate_id
        validated.append(validated_candidate)

    if not validated:
        if quality_stats is not None:
            quality_stats.add_ai_stage_failure("candidate_ungrounded")
        return [], "candidate_ungrounded"
    return validated, None


def _eligible_groups(
    candidates: list[dict[str, Any]],
) -> list[tuple[tuple[str, str], list[dict[str, Any]]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for candidate in candidates:
        key = (str(candidate["answer_kind"]), str(candidate["answer_subtype"]))
        grouped.setdefault(key, []).append(candidate)

    eligible: list[tuple[tuple[str, str], list[dict[str, Any]]]] = []
    for key, group in grouped.items():
        unique_labels = {str(candidate["answer_label"]).casefold() for candidate in group}
        unique_ids = {str(candidate["candidate_id"]) for candidate in group}
        if len(unique_labels) >= 4 and len(unique_ids) >= 4:
            eligible.append((key, group))
    eligible.sort(key=lambda item: item[0])
    return eligible


def _candidate_rank_key(seed: int, candidate: dict[str, Any]) -> tuple[float, float, str]:
    tie_break = hashlib.sha256(f"{seed}:{candidate['candidate_id']}".encode("utf-8")).hexdigest()
    source_event = candidate.get("source_event")
    selection_score = 0.5
    if isinstance(source_event, dict):
        selection_score = candidate_selection_score(seed, source_event)
    return (-float(candidate["quality_score"]), -selection_score, tie_break)


def _group_rank_key(
    seed: int,
    item: tuple[tuple[str, str], list[dict[str, Any]]],
) -> tuple[tuple[float, float, str], tuple[str, str]]:
    group_key, group = item
    best_candidate = min(group, key=lambda candidate: _candidate_rank_key(seed, candidate))
    return _candidate_rank_key(seed, best_candidate), group_key


def _select_candidate_group(
    *,
    candidates: list[dict[str, Any]],
    seed: int,
    preferred_answer_kind: str | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]] | tuple[None, None]:
    eligible = _eligible_groups(candidates)
    if not eligible:
        return None, None

    if preferred_answer_kind is not None:
        preferred_groups = [item for item in eligible if item[0][0] == preferred_answer_kind]
    else:
        preferred_groups = []
    candidate_groups = preferred_groups or eligible
    ordered_groups = sorted(candidate_groups, key=lambda item: _group_rank_key(seed, item))
    group = ordered_groups[0][1]

    ordered_group = sorted(group, key=lambda item: _candidate_rank_key(seed, item))
    correct_candidate = ordered_group[0]
    distractor_pool = [
        candidate for candidate in ordered_group[1:] if candidate["candidate_id"] != correct_candidate["candidate_id"]
    ]
    return correct_candidate, distractor_pool


def _select_distractors(
    *,
    correct_candidate: dict[str, Any],
    distractor_pool: list[dict[str, Any]],
    settings: FactoidPipelineSettings,
    ai_orchestrator: AIOrchestrator,
    quality_stats: QualityRunStats | None,
) -> tuple[list[dict[str, Any]] | None, str | None]:
    if len(distractor_pool) < 3:
        if quality_stats is not None:
            quality_stats.add_ai_stage_failure("insufficient_same_subtype_pool")
        return None, "insufficient_same_subtype_pool"

    response, reason = ai_orchestrator.run_json_task(
        task_name="factoid_distractor_select",
        system_prompt=(
            "Select sourced distractors for a grounded history multiple-choice quiz. "
            "Return JSON only with selected_distractor_ids. "
            "Use only provided candidate ids and choose exactly 3 distractors. "
            "Do not mix answer kinds or subtypes."
        ),
        user_payload={
            "task": "factoid_distractor_select",
            "answer_kind": correct_candidate["answer_kind"],
            "answer_subtype": correct_candidate["answer_subtype"],
            "question": correct_candidate["question_text"],
            "correct_candidate": {
                "candidate_id": correct_candidate["candidate_id"],
                "answer_label": correct_candidate["answer_label"],
                "page_title": correct_candidate["page_context"]["page_title"],
            },
            "distractor_candidates": [
                {
                    "candidate_id": candidate["candidate_id"],
                    "answer_label": candidate["answer_label"],
                    "page_title": candidate["page_context"]["page_title"],
                    "page_url": candidate["page_context"]["page_url"],
                }
                for candidate in distractor_pool
            ],
            "constraints": {
                "return_exactly": 3,
                "ids_must_come_from_candidates": True,
                "same_answer_kind_required": True,
                "same_answer_subtype_required": True,
                "synthetic_distractors_forbidden": True,
            },
        },
        model=settings.model_distractors,
        max_output_tokens=260,
        response_schema={
            "name": "factoid_distractor_select",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["selected_distractor_ids"],
                "properties": {
                    "selected_distractor_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    }
                },
            },
        },
    )
    if response is None:
        if quality_stats is not None and reason is not None:
            quality_stats.add_ai_stage_failure(reason)
        return None, reason or "factoid_distractor_select_failed"

    selected_ids = response.get("selected_distractor_ids")
    if not isinstance(selected_ids, list) or len(selected_ids) != 3 or not all(isinstance(item, str) for item in selected_ids):
        if quality_stats is not None:
            quality_stats.add_ai_stage_failure("factoid_distractor_select_invalid_ids")
        return None, "factoid_distractor_select_invalid_ids"

    by_candidate_id = {candidate["candidate_id"]: candidate for candidate in distractor_pool}
    if len(set(selected_ids)) != 3 or any(candidate_id not in by_candidate_id for candidate_id in selected_ids):
        if quality_stats is not None:
            quality_stats.add_ai_stage_failure("factoid_distractor_select_invalid_ids")
        return None, "factoid_distractor_select_invalid_ids"

    selected = [by_candidate_id[candidate_id] for candidate_id in selected_ids]
    if any(
        candidate["answer_kind"] != correct_candidate["answer_kind"]
        or candidate["answer_subtype"] != correct_candidate["answer_subtype"]
        for candidate in selected
    ):
        if quality_stats is not None:
            quality_stats.add_ai_stage_failure("insufficient_same_subtype_pool")
        return None, "insufficient_same_subtype_pool"
    return selected, None


def _judge_final_quiz(
    *,
    quiz: dict[str, Any],
    correct_candidate: dict[str, Any],
    settings: FactoidPipelineSettings,
    ai_orchestrator: AIOrchestrator,
    quality_stats: QualityRunStats | None,
) -> str | None:
    response, reason = ai_orchestrator.run_json_task(
        task_name="factoid_final_judge",
        system_prompt=(
            "Judge the publishability of a grounded history multiple-choice quiz. "
            "Return JSON only with final_score and publishable. "
            "Favor clarity, realism, answerability, and absence of answer leakage."
        ),
        user_payload={
            "task": "factoid_final_judge",
            "question": quiz["question"],
            "answer_kind": correct_candidate["answer_kind"],
            "answer_subtype": correct_candidate["answer_subtype"],
            "correct_answer": correct_candidate["answer_label"],
            "evidence_text": correct_candidate["evidence_text"],
            "choices": [
                {"id": choice["id"], "label": choice["label"]}
                for choice in quiz.get("choices", [])
                if isinstance(choice, dict)
            ],
            "quality_bar": settings.min_final_score,
        },
        model=settings.model_judge,
        max_output_tokens=220,
        response_schema={
            "name": "factoid_final_judge",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["final_score", "publishable"],
                "properties": {
                    "final_score": {"type": "number"},
                    "publishable": {"type": "boolean"},
                },
            },
        },
    )
    if response is None:
        if quality_stats is not None and reason is not None:
            quality_stats.add_ai_stage_failure(reason)
        return reason or "factoid_final_judge_failed"

    final_score = _quality_score(response.get("final_score"))
    publishable = bool(response.get("publishable"))
    if not publishable or final_score < settings.min_final_score:
        if quality_stats is not None:
            quality_stats.add_ai_stage_failure("final_judge_rejected")
        return "final_judge_rejected"
    return None


def generate_ai_native_factoid_quiz(
    *,
    target_date: dt.date,
    retrieval_time: dt.datetime,
    source_url: str,
    candidates: list[dict[str, Any]],
    seed: int,
    edition: int,
    generation_mode: str,
    preferred_answer_kind: str | None,
    settings: FactoidPipelineSettings,
    ai_orchestrator: AIOrchestrator,
    timeout: int,
    retries: int,
    quality_stats: QualityRunStats | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    if not settings.enabled:
        return None, "factoid_pipeline_disabled"
    if not ai_orchestrator.is_enabled():
        return None, "factoid_pipeline_ai_disabled"
    if len(candidates) < 4:
        return None, "factoid_ai_candidate_not_enough_source_events"

    page_contexts, page_reason = _build_page_contexts(
        candidates=candidates,
        seed=seed,
        retrieval_time=retrieval_time,
        settings=settings,
        timeout=timeout,
        retries=retries,
        quality_stats=quality_stats,
    )
    if not page_contexts:
        return None, page_reason or "page_context_fetch_failed"

    grounded_candidates, generation_reason = _generate_grounded_candidates(
        page_contexts=page_contexts,
        settings=settings,
        ai_orchestrator=ai_orchestrator,
        quality_stats=quality_stats,
    )
    if not grounded_candidates:
        return None, generation_reason or "candidate_ungrounded"

    correct_candidate, distractor_pool = _select_candidate_group(
        candidates=grounded_candidates,
        seed=seed,
        preferred_answer_kind=preferred_answer_kind,
    )
    if correct_candidate is None or distractor_pool is None:
        if quality_stats is not None:
            quality_stats.add_ai_stage_failure("insufficient_same_subtype_pool")
        return None, "insufficient_same_subtype_pool"

    distractors, distractor_reason = _select_distractors(
        correct_candidate=correct_candidate,
        distractor_pool=distractor_pool,
        settings=settings,
        ai_orchestrator=ai_orchestrator,
        quality_stats=quality_stats,
    )
    if distractors is None:
        return None, distractor_reason or "factoid_distractor_select_failed"

    if ai_orchestrator.settings.mode == AI_MODE_SHADOW:
        return None, "shadow_mode"
    if ai_orchestrator.settings.mode != AI_MODE_ON:
        return None, "invalid_mode"

    quiz = _build_history_factoid_typed_quiz(
        target_date=target_date,
        retrieval_time=retrieval_time,
        source_url=source_url,
        seed=seed,
        edition=edition,
        generation_mode=generation_mode,
        correct_factoid=correct_candidate,
        distractor_factoids=distractors,
    )

    judge_reason = _judge_final_quiz(
        quiz=quiz,
        correct_candidate=correct_candidate,
        settings=settings,
        ai_orchestrator=ai_orchestrator,
        quality_stats=quality_stats,
    )
    if judge_reason is not None:
        return None, judge_reason

    metadata = dict(quiz.get("metadata", {}))
    metadata["pipeline_version"] = "phase5_5_page_grounded_v1"
    metadata["generation_method"] = "ai_native_factoid_v1"
    quiz["metadata"] = metadata

    questions = quiz.get("questions")
    if isinstance(questions, list) and questions and isinstance(questions[0], dict):
        question = dict(questions[0])
        facets = dict(question.get("facets", {}))
        facets["generation_method"] = "ai_native_factoid_v1"
        question["facets"] = facets
        questions = list(questions)
        questions[0] = question
        quiz["questions"] = questions

    if quality_stats is not None:
        quality_stats.add_factoid_subtype(
            f"ai_native:{correct_candidate['answer_kind']}:{correct_candidate['answer_subtype']}"
        )

    return quiz, None
