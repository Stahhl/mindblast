"""Quiz card context resolution for feedback review."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quiz_forge.storage import load_json_file

from .types import QuizCardContext


def _resolve_content_path(content_repo_root: Path, quiz_file: str) -> Path:
    resolved = (content_repo_root / quiz_file).resolve()
    safe_root = content_repo_root.resolve()
    try:
        resolved.relative_to(safe_root)
    except ValueError as exc:
        raise ValueError(f"quiz_file escapes content root: {quiz_file}")
    return resolved


def _choice_labels(payload: dict[str, Any], question: dict[str, Any]) -> tuple[str, ...]:
    choices = payload.get("choices")
    labels: list[str] = []
    if isinstance(choices, list):
        for choice in choices:
            if isinstance(choice, dict) and isinstance(choice.get("label"), str) and choice["label"].strip():
                labels.append(choice["label"].strip())
        if labels:
            return tuple(labels)

    answer_facts = payload.get("answer_facts")
    if not isinstance(answer_facts, list):
        return ()
    facts_by_id = {
        fact.get("id"): fact
        for fact in answer_facts
        if isinstance(fact, dict) and isinstance(fact.get("id"), str)
    }
    answer_fact_ids = question.get("answer_fact_ids")
    if not isinstance(answer_fact_ids, list):
        return ()
    derived_labels = [
        fact["label"].strip()
        for answer_fact_id in answer_fact_ids
        if isinstance(answer_fact_id, str)
        and isinstance((fact := facts_by_id.get(answer_fact_id)), dict)
        and isinstance(fact.get("label"), str)
        and fact["label"].strip()
    ]
    return tuple(derived_labels)


def load_quiz_card_context(
    *,
    content_repo_root: str | Path,
    quiz_file: str,
    question_id: str,
    question_human_id: str | None = None,
) -> QuizCardContext:
    root = Path(content_repo_root)
    payload_path = _resolve_content_path(root, quiz_file)
    payload = load_json_file(payload_path)
    if payload is None:
        raise ValueError(f"Quiz payload not found: {quiz_file}")

    questions = payload.get("questions")
    if not isinstance(questions, list):
        raise ValueError(f"Quiz payload has no questions array: {quiz_file}")

    selected_question: dict[str, Any] | None = None
    for question in questions:
        if not isinstance(question, dict):
            continue
        if question.get("id") == question_id:
            selected_question = question
            break
    if selected_question is None:
        raise ValueError(f"Question {question_id} not found in {quiz_file}")

    matched_human_id = selected_question.get("human_id")
    if question_human_id is not None and matched_human_id not in {None, question_human_id}:
        raise ValueError(f"Question human id mismatch for {quiz_file}: {question_human_id}")

    question_prompt = selected_question.get("prompt")
    if not isinstance(question_prompt, str) or not question_prompt.strip():
        raise ValueError(f"Question prompt missing for {quiz_file}: {question_id}")

    date = payload.get("date")
    quiz_type = payload.get("type")
    generation = payload.get("generation")
    edition = generation.get("edition") if isinstance(generation, dict) else 1
    if not isinstance(date, str) or not isinstance(quiz_type, str) or not isinstance(edition, int):
        raise ValueError(f"Quiz payload metadata missing for {quiz_file}")

    return QuizCardContext(
        quiz_file=quiz_file,
        date=date,
        quiz_type=quiz_type,
        edition=edition,
        question_id=question_id,
        question_human_id=matched_human_id if isinstance(matched_human_id, str) else None,
        question_prompt=question_prompt.strip(),
        choice_labels=_choice_labels(payload, selected_question),
    )
