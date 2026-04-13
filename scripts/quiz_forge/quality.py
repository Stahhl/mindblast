"""Deterministic quality linting for generated quiz payloads."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from .constants import QUIZ_TYPE_HISTORY_FACTOID_MCQ_4, QUIZ_TYPE_HISTORY_MCQ_4
from .selection import looks_like_person_label, looks_like_place_label

ISSUE_MIXED_ENTITY_TYPES = "mixed_entity_types"
ISSUE_PROMPT_LEAK_YEAR = "prompt_leak_year"
ISSUE_PROMPT_LEAK_LOCATION = "prompt_leak_location"
ISSUE_WEAK_DISTRACTOR_PLAUSIBILITY = "weak_distractor_plausibility"

QUALITY_ISSUE_CODES = (
    ISSUE_MIXED_ENTITY_TYPES,
    ISSUE_PROMPT_LEAK_YEAR,
    ISSUE_PROMPT_LEAK_LOCATION,
    ISSUE_WEAK_DISTRACTOR_PLAUSIBILITY,
)

_YEAR_TOKEN_RE = re.compile(r"(?<!\d)(\d{3,4})(?!\d)")
_NORMALIZE_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_LOCATION_LEAK_RE = re.compile(
    r"\b(?:in|at|near|from)\s+(?:the\s+)?[A-Z][^?]{0,40}(?:,\s*[A-Z][^?]{0,25})",
)


def _normalize_text(value: str) -> str:
    return " ".join(value.split()).strip()


def _normalize_token_key(value: str) -> str:
    return _NORMALIZE_NON_ALNUM_RE.sub(" ", value.casefold()).strip()


def _extract_prompt(payload: dict[str, Any]) -> str:
    prompt = payload.get("question")
    if isinstance(prompt, str) and prompt.strip():
        return _normalize_text(prompt)
    questions = payload.get("questions")
    if isinstance(questions, list) and questions and isinstance(questions[0], dict):
        question_prompt = questions[0].get("prompt")
        if isinstance(question_prompt, str) and question_prompt.strip():
            return _normalize_text(question_prompt)
    return ""


def _extract_choices(payload: dict[str, Any]) -> list[dict[str, Any]]:
    choices = payload.get("choices")
    if not isinstance(choices, list):
        return []
    return [choice for choice in choices if isinstance(choice, dict)]


def _choice_label(choice: dict[str, Any]) -> str:
    label = choice.get("label")
    if isinstance(label, str):
        return _normalize_text(label)
    return ""


def _correct_choice(payload: dict[str, Any]) -> dict[str, Any] | None:
    correct_choice_id = payload.get("correct_choice_id")
    if not isinstance(correct_choice_id, str):
        return None
    for choice in _extract_choices(payload):
        if choice.get("id") == correct_choice_id:
            return choice
    return None


def _question_facets(payload: dict[str, Any]) -> dict[str, Any]:
    questions = payload.get("questions")
    if isinstance(questions, list) and questions and isinstance(questions[0], dict):
        facets = questions[0].get("facets")
        if isinstance(facets, dict):
            return facets
    return {}


def _target_year(payload: dict[str, Any]) -> int | None:
    question = payload.get("question")
    if isinstance(question, str):
        match = re.search(r"Which event happened in (-?\d{1,4})\?", question)
        if match is not None:
            return int(match.group(1))
    questions = payload.get("questions")
    if isinstance(questions, list) and questions and isinstance(questions[0], dict):
        selection_rules = questions[0].get("selection_rules")
        if isinstance(selection_rules, dict):
            value = selection_rules.get("target_year")
            if isinstance(value, int):
                return value
    return None


def _answer_facts_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    answer_facts = payload.get("answer_facts")
    if not isinstance(answer_facts, list):
        return {}
    return {
        fact["id"]: fact
        for fact in answer_facts
        if isinstance(fact, dict) and isinstance(fact.get("id"), str)
    }


def _correct_answer_label(payload: dict[str, Any]) -> str | None:
    correct_choice = _correct_choice(payload)
    if correct_choice is not None:
        label = _choice_label(correct_choice)
        if label:
            return label

    questions = payload.get("questions")
    if not isinstance(questions, list) or not questions or not isinstance(questions[0], dict):
        return None
    correct_answer_fact_id = questions[0].get("correct_answer_fact_id")
    if not isinstance(correct_answer_fact_id, str):
        return None
    fact = _answer_facts_by_id(payload).get(correct_answer_fact_id)
    if isinstance(fact, dict) and isinstance(fact.get("label"), str) and fact["label"].strip():
        return _normalize_text(fact["label"])
    return None


def _choice_entity_matches(answer_kind: str, label: str) -> bool:
    if answer_kind == "person":
        return looks_like_person_label(label)
    if answer_kind == "place":
        return looks_like_place_label(label)
    if answer_kind == "time":
        return bool(_YEAR_TOKEN_RE.search(label))
    return True


def _detect_history_mcq_issues(payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    target_year = _target_year(payload)
    correct_choice = _correct_choice(payload)
    if target_year is None or correct_choice is None:
        return issues

    year_token = str(target_year)
    correct_label = _choice_label(correct_choice)
    distractor_labels = [
        _choice_label(choice)
        for choice in _extract_choices(payload)
        if choice is not correct_choice
    ]
    if re.search(rf"(?<!\d){re.escape(year_token)}(?!\d)", correct_label) and not any(
        re.search(rf"(?<!\d){re.escape(year_token)}(?!\d)", label) for label in distractor_labels
    ):
        issues.append(ISSUE_PROMPT_LEAK_YEAR)
    return issues


def _prompt_contains_label(prompt: str, label: str) -> bool:
    normalized_prompt = _normalize_token_key(prompt)
    normalized_label = _normalize_token_key(label)
    if not normalized_prompt or not normalized_label:
        return False
    return normalized_label in normalized_prompt


def _prompt_location_leak(prompt: str, correct_answer_label: str | None) -> bool:
    if _LOCATION_LEAK_RE.search(prompt) is not None:
        return True
    if not correct_answer_label:
        return False
    normalized_prompt = _normalize_token_key(prompt)
    label_parts = [part.strip() for part in correct_answer_label.split(",") if part.strip()]
    if len(label_parts) >= 2:
        return all(_normalize_token_key(part) in normalized_prompt for part in label_parts[:2])
    return False


def _detect_history_factoid_issues(payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    prompt = _extract_prompt(payload)
    facets = _question_facets(payload)
    answer_kind = facets.get("answer_kind")
    correct_answer_label = _correct_answer_label(payload)
    choices = _extract_choices(payload)

    if answer_kind == "time" and correct_answer_label and _prompt_contains_label(prompt, correct_answer_label):
        issues.append(ISSUE_PROMPT_LEAK_YEAR)
    elif answer_kind in {"person", "place"}:
        if correct_answer_label and _prompt_contains_label(prompt, correct_answer_label):
            issues.append(ISSUE_PROMPT_LEAK_LOCATION if answer_kind == "place" else ISSUE_WEAK_DISTRACTOR_PLAUSIBILITY)
        if answer_kind == "place" and _prompt_location_leak(prompt, correct_answer_label):
            if ISSUE_PROMPT_LEAK_LOCATION not in issues:
                issues.append(ISSUE_PROMPT_LEAK_LOCATION)

        mismatched_labels = [
            label
            for label in (_choice_label(choice) for choice in choices)
            if label and not _choice_entity_matches(answer_kind, label)
        ]
        if mismatched_labels:
            issues.append(ISSUE_WEAK_DISTRACTOR_PLAUSIBILITY)
            if ISSUE_MIXED_ENTITY_TYPES not in issues:
                issues.append(ISSUE_MIXED_ENTITY_TYPES)
    elif correct_answer_label and _prompt_contains_label(prompt, correct_answer_label):
        issues.append(ISSUE_WEAK_DISTRACTOR_PLAUSIBILITY)

    return issues


def lint_quiz_payload(payload: dict[str, Any]) -> tuple[str, ...]:
    quiz_type = payload.get("type")
    if quiz_type == QUIZ_TYPE_HISTORY_MCQ_4:
        issues = _detect_history_mcq_issues(payload)
    elif quiz_type == QUIZ_TYPE_HISTORY_FACTOID_MCQ_4:
        issues = _detect_history_factoid_issues(payload)
    else:
        issues = []
    return tuple(issue for issue in QUALITY_ISSUE_CODES if issue in issues)


@dataclass
class QualityRunStats:
    lint_failures: dict[str, int] = field(default_factory=dict)
    fallback_paths: dict[str, int] = field(default_factory=dict)
    factoid_final_subtypes: dict[str, int] = field(default_factory=dict)
    ai_quality_rejection_count: int = 0
    typed_candidate_rejections: dict[str, int] = field(default_factory=dict)
    ai_distractor_rejection_lints: dict[str, int] = field(default_factory=dict)
    ai_stage_failures: dict[str, int] = field(default_factory=dict)
    page_context_fetch_count: int = 0
    popularity_enriched_count: int = 0
    popularity_neutral_count: int = 0
    popularity_fallback_reasons: dict[str, int] = field(default_factory=dict)
    selected_popularity_score_total: float = 0.0
    selected_popularity_score_count: int = 0

    def add_issues(self, issues: tuple[str, ...]) -> None:
        for issue in issues:
            self.lint_failures[issue] = self.lint_failures.get(issue, 0) + 1

    def add_fallback_path(self, path: str) -> None:
        self.fallback_paths[path] = self.fallback_paths.get(path, 0) + 1

    def add_factoid_subtype(self, subtype: str) -> None:
        self.factoid_final_subtypes[subtype] = self.factoid_final_subtypes.get(subtype, 0) + 1

    def add_ai_quality_rejection(self) -> None:
        self.ai_quality_rejection_count += 1

    def add_typed_candidate_rejection(self, reason: str) -> None:
        self.typed_candidate_rejections[reason] = self.typed_candidate_rejections.get(reason, 0) + 1

    def add_ai_distractor_rejection_lints(self, issues: tuple[str, ...]) -> None:
        for issue in issues:
            self.ai_distractor_rejection_lints[issue] = self.ai_distractor_rejection_lints.get(issue, 0) + 1

    def add_ai_stage_failure(self, reason: str) -> None:
        self.ai_stage_failures[reason] = self.ai_stage_failures.get(reason, 0) + 1

    def add_page_context_fetches(self, count: int) -> None:
        self.page_context_fetch_count += max(0, count)

    def add_popularity_enrichment(self, *, enriched_count: int, neutral_count: int) -> None:
        self.popularity_enriched_count += max(0, enriched_count)
        self.popularity_neutral_count += max(0, neutral_count)

    def add_popularity_fallback_reason(self, reason: str) -> None:
        self.popularity_fallback_reasons[reason] = self.popularity_fallback_reasons.get(reason, 0) + 1

    def add_selected_popularity_score(self, score: float) -> None:
        bounded = max(0.0, min(1.0, float(score)))
        self.selected_popularity_score_total += bounded
        self.selected_popularity_score_count += 1

    def to_report_payload(self) -> dict[str, Any]:
        average_selected_popularity_score = (
            self.selected_popularity_score_total / self.selected_popularity_score_count
            if self.selected_popularity_score_count
            else None
        )
        return {
            "lint_failure_count": sum(self.lint_failures.values()),
            "lint_failures": [f"{code}:{count}" for code, count in sorted(self.lint_failures.items())],
            "fallback_count": sum(self.fallback_paths.values()),
            "fallback_paths": [f"{code}:{count}" for code, count in sorted(self.fallback_paths.items())],
            "factoid_final_subtypes": [
                f"{code}:{count}" for code, count in sorted(self.factoid_final_subtypes.items())
            ],
            "ai_quality_rejection_count": self.ai_quality_rejection_count,
            "typed_candidate_rejections": [
                f"{code}:{count}" for code, count in sorted(self.typed_candidate_rejections.items())
            ],
            "ai_distractor_rejection_lints": [
                f"{code}:{count}" for code, count in sorted(self.ai_distractor_rejection_lints.items())
            ],
            "ai_stage_failures": [f"{code}:{count}" for code, count in sorted(self.ai_stage_failures.items())],
            "page_context_fetch_count": self.page_context_fetch_count,
            "popularity_enriched_count": self.popularity_enriched_count,
            "popularity_neutral_count": self.popularity_neutral_count,
            "popularity_fallback_reasons": [
                f"{code}:{count}" for code, count in sorted(self.popularity_fallback_reasons.items())
            ],
            "selected_popularity_score_avg": average_selected_popularity_score,
        }
