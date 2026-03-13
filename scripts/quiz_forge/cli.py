"""Main quiz generation workflow."""

from __future__ import annotations

import copy
import datetime as dt
from pathlib import Path
from typing import Any

from .ai import AIOrchestrator, load_ai_settings
from .args import (
    parse_args,
    parse_generation_count,
    parse_generation_mode,
    parse_quiz_types,
    parse_target_date,
)
from .builders import QUIZ_BUILDERS
from .constants import (
    GENERATION_MODE_DAILY,
    GENERATION_MODE_EXTRA,
    QUIZ_TYPE_HISTORY_FACTOID_MCQ_4,
    QUIZ_TYPE_HISTORY_MCQ_4,
    SUPPORTED_QUIZ_TYPES,
)
from .discovery import write_discovery_artifacts
from .factoid_pipeline import apply_factoid_ai_pipeline, load_factoid_pipeline_settings
from .selection import build_seed, pick_history_mcq_distractor_pool
from .source import build_api_url, extract_candidates, fetch_json
from .storage import (
    apply_human_ids_to_quiz,
    build_output_path,
    find_existing_quiz_path,
    iter_quiz_records,
    load_human_id_lookup,
    list_quiz_records_for_date_type,
    write_human_id_lookup,
    write_quiz_file,
)
from .validation import validate_quiz


def _build_generation_plan(
    output_dir: str,
    target_date: dt.date,
    quiz_types: list[str],
    mode: str,
    count: int,
) -> list[tuple[str, int, Path]]:
    pending: list[tuple[str, int, Path]] = []
    for quiz_type in quiz_types:
        existing_records = list_quiz_records_for_date_type(output_dir, target_date, quiz_type)
        existing_editions = {record.edition for record in existing_records}
        if mode == GENERATION_MODE_DAILY:
            edition = 1
            output_path = build_output_path(output_dir, target_date, quiz_type, edition)
            existing_path = find_existing_quiz_path(output_path, target_date, quiz_type, edition)
            if existing_path is not None:
                print(f"Quiz already exists for {quiz_type} edition {edition}: {existing_path}")
                continue
            pending.append((quiz_type, edition, output_path))
            continue

        if mode != GENERATION_MODE_EXTRA:
            raise ValueError(f"Unsupported generation mode: {mode}")

        if 1 not in existing_editions:
            raise ValueError(
                f"Cannot generate extra editions for {quiz_type} on {target_date.isoformat()} "
                "before daily edition 1 exists."
            )

        next_edition = max(existing_editions) + 1
        for edition in range(next_edition, next_edition + count):
            output_path = build_output_path(output_dir, target_date, quiz_type, edition)
            existing_path = find_existing_quiz_path(output_path, target_date, quiz_type, edition)
            if existing_path is not None:
                print(f"Quiz already exists for {quiz_type} edition {edition}: {existing_path}")
                continue
            pending.append((quiz_type, edition, output_path))

    return pending


def _backfill_human_ids(output_dir: str) -> int:
    lookup = load_human_id_lookup(output_dir)
    records = iter_quiz_records(output_dir)
    if not records:
        print(f"No quiz files found in {output_dir}.")
        return 0

    type_order = {quiz_type: index for index, quiz_type in enumerate(SUPPORTED_QUIZ_TYPES)}
    ordered_records = sorted(
        records,
        key=lambda record: (
            record.date.isoformat(),
            type_order.get(record.quiz_type, len(type_order)),
            record.edition,
            record.path.as_posix(),
        ),
    )

    files_to_update: list[tuple[Path, str, int, dict[str, Any]]] = []
    lookup_changed = False

    for record in ordered_records:
        updated_payload = copy.deepcopy(record.payload)
        payload_or_lookup_changed = apply_human_ids_to_quiz(
            quiz=updated_payload,
            quiz_path=record.path,
            lookup=lookup,
        )
        validate_quiz(updated_payload, record.date)
        if updated_payload != record.payload:
            files_to_update.append((record.path, record.quiz_type, record.edition, updated_payload))
        if payload_or_lookup_changed:
            lookup_changed = True

    for path, quiz_type, edition, payload in files_to_update:
        write_quiz_file(path, payload)
        print(f"Backfilled human IDs for {quiz_type} edition {edition}: {path}")

    if lookup_changed:
        lookup_path = write_human_id_lookup(output_dir, lookup)
        print(f"Updated human id lookup: {lookup_path}")

    if not files_to_update and not lookup_changed:
        print("No human id backfill changes needed.")

    return 0


def main() -> int:
    args = parse_args()
    if getattr(args, "backfill_human_ids", False):
        return _backfill_human_ids(args.output_dir)

    target_date = parse_target_date(args.date)
    quiz_types = parse_quiz_types(args.quiz_types)
    generation_mode = parse_generation_mode(args.mode)
    generation_count = parse_generation_count(args.count)
    ai_settings = load_ai_settings(output_dir=args.output_dir)
    ai_orchestrator = AIOrchestrator(settings=ai_settings, target_date=target_date)
    factoid_pipeline_settings = load_factoid_pipeline_settings(ai_settings.model)

    pending = _build_generation_plan(
        output_dir=args.output_dir,
        target_date=target_date,
        quiz_types=quiz_types,
        mode=generation_mode,
        count=generation_count,
    )
    human_id_lookup = load_human_id_lookup(args.output_dir)
    human_id_lookup_changed = False

    generated: list[tuple[str, int, Path, dict[str, Any]]] = []
    if pending:
        retrieval_time = dt.datetime.now(dt.timezone.utc)
        source_url = build_api_url(target_date)
        source_payload = fetch_json(source_url, timeout=args.timeout, retries=args.retries)
        candidates = extract_candidates(source_payload)
        reusable_correct_events: list[dict[str, Any]] = []

        for quiz_type, edition, output_path in pending:
            builder = QUIZ_BUILDERS[quiz_type]
            seed = build_seed(target_date, quiz_type, edition)
            ai_ranked_distractor_ids: list[str] | None = None
            if quiz_type == QUIZ_TYPE_HISTORY_MCQ_4 and ai_orchestrator.is_enabled():
                correct_event, distractor_pool = pick_history_mcq_distractor_pool(
                    candidates,
                    seed,
                    preferred_distractor_events=reusable_correct_events,
                    max_distractors=8,
                )
                question_prompt = f"Which event happened in {correct_event['year']}?"
                ai_attempt = ai_orchestrator.rerank_history_mcq(
                    question_prompt=question_prompt,
                    correct_event=correct_event,
                    distractor_candidates=distractor_pool,
                )
                if ai_attempt.applied and ai_attempt.response is not None:
                    ai_ranked_distractor_ids = ai_attempt.response.ranked_distractor_ids
                    print(
                        f"AI rerank applied for {quiz_type}: "
                        f"provider={ai_attempt.response.provider} model={ai_attempt.response.model}"
                    )
                elif ai_attempt.response is not None:
                    print(
                        f"AI rerank (shadow) for {quiz_type}: "
                        f"provider={ai_attempt.response.provider} model={ai_attempt.response.model}"
                    )
                elif ai_attempt.fallback_reason:
                    print(f"AI rerank fallback for {quiz_type}: {ai_attempt.fallback_reason}")

            quiz = builder(
                target_date,
                retrieval_time,
                source_url,
                candidates,
                seed,
                edition,
                generation_mode,
                preferred_distractor_events=reusable_correct_events,
                ai_ranked_distractor_ids=ai_ranked_distractor_ids,
            )
            if quiz_type == QUIZ_TYPE_HISTORY_FACTOID_MCQ_4:
                quiz, factoid_reason = apply_factoid_ai_pipeline(
                    quiz=quiz,
                    settings=factoid_pipeline_settings,
                    ai_orchestrator=ai_orchestrator,
                )
                if factoid_pipeline_settings.enabled:
                    if factoid_reason is None:
                        print("AI factoid pipeline applied for history_factoid_mcq_4.")
                    elif factoid_reason == "shadow_mode":
                        print("AI factoid pipeline shadow run completed for history_factoid_mcq_4.")
                    else:
                        print(f"AI factoid pipeline fallback for history_factoid_mcq_4: {factoid_reason}")

            if apply_human_ids_to_quiz(quiz=quiz, quiz_path=output_path, lookup=human_id_lookup):
                human_id_lookup_changed = True

            validate_quiz(quiz, target_date)
            generated.append((quiz_type, edition, output_path, quiz))

            questions = quiz.get("questions")
            answer_facts = quiz.get("answer_facts")
            if not isinstance(questions, list) or not questions:
                continue
            if not isinstance(answer_facts, list) or not answer_facts:
                continue

            question = questions[0]
            if not isinstance(question, dict):
                continue
            correct_answer_fact_id = question.get("correct_answer_fact_id")
            if not isinstance(correct_answer_fact_id, str):
                continue

            correct_fact = next(
                (
                    fact
                    for fact in answer_facts
                    if isinstance(fact, dict) and fact.get("id") == correct_answer_fact_id
                ),
                None,
            )
            if correct_fact is None:
                continue

            year = correct_fact.get("year")
            matching_source_event = next(
                (
                    source_event
                    for source_event in quiz.get("source", {}).get("events_used", [])
                    if isinstance(source_event, dict) and source_event.get("event_id") == correct_answer_fact_id
                ),
                None,
            )
            source_text = matching_source_event.get("text") if isinstance(matching_source_event, dict) else None
            source_url_for_fact = (
                matching_source_event.get("wikipedia_url") if isinstance(matching_source_event, dict) else None
            )
            if isinstance(source_text, str) and isinstance(year, int) and isinstance(source_url_for_fact, str):
                reusable_correct_events.append(
                    {
                        "text": source_text,
                        "year": year,
                        "wikipedia_url": source_url_for_fact,
                    }
                )

    for quiz_type, edition, output_path, quiz in generated:
        write_quiz_file(output_path, quiz)
        print(f"Created quiz file for {quiz_type} edition {edition}: {output_path}")
    if generated and human_id_lookup_changed:
        lookup_path = write_human_id_lookup(args.output_dir, human_id_lookup)
        print(f"Updated human id lookup: {lookup_path}")

    ai_orchestrator.finalize()
    ai_orchestrator.write_report()
    if ai_settings.report_path:
        print(f"Wrote AI run report: {ai_settings.report_path}")

    discovery_changes = write_discovery_artifacts(
        output_dir=args.output_dir,
        target_date=target_date,
        generated_now=bool(generated),
    )
    for discovery_path in discovery_changes:
        print(f"Updated discovery artifact: {discovery_path}")

    if not generated and not discovery_changes:
        print("No new quizzes or discovery updates.")

    return 0
