"""Main quiz generation workflow."""

from __future__ import annotations

import copy
import datetime as dt
import json
from pathlib import Path
from typing import Any

from .ai import AIOrchestrator, load_ai_settings
from .args import (
    parse_daily_editions_by_type,
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
    QUIZ_TYPE_GEOGRAPHY_FACTOID_MCQ_4,
    QUIZ_TYPE_HISTORY_FACTOID_MCQ_4,
    QUIZ_TYPE_HISTORY_MCQ_4,
    SUPPORTED_QUIZ_TYPES,
)
from .discovery import write_discovery_artifacts
from .factoid_pipeline import generate_ai_native_factoid_quiz, load_factoid_pipeline_settings
from .geography import GEOGRAPHY_SOURCE_URL, load_geography_records
from .popularity import enrich_history_candidates_with_popularity
from .selection import build_seed, pick_history_mcq_distractor_pool
from .source import build_api_url, extract_candidates, fetch_json
from .quality import QualityRunStats, lint_quiz_payload
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
    daily_editions_by_type: dict[str, int],
) -> list[tuple[str, int, Path]]:
    pending: list[tuple[str, int, Path]] = []
    for quiz_type in quiz_types:
        existing_records = list_quiz_records_for_date_type(output_dir, target_date, quiz_type)
        existing_editions = {record.edition for record in existing_records}
        daily_target = daily_editions_by_type.get(quiz_type, 1)
        if mode == GENERATION_MODE_DAILY:
            for edition in range(1, daily_target + 1):
                output_path = build_output_path(output_dir, target_date, quiz_type, edition)
                existing_path = find_existing_quiz_path(output_path, target_date, quiz_type, edition)
                if existing_path is not None:
                    print(f"Quiz already exists for {quiz_type} edition {edition}: {existing_path}")
                    continue
                pending.append((quiz_type, edition, output_path))
            continue

        if mode != GENERATION_MODE_EXTRA:
            raise ValueError(f"Unsupported generation mode: {mode}")

        missing_daily_editions = [edition for edition in range(1, daily_target + 1) if edition not in existing_editions]
        if missing_daily_editions:
            missing_text = ", ".join(str(edition) for edition in missing_daily_editions)
            raise ValueError(
                f"Cannot generate extra editions for {quiz_type} on {target_date.isoformat()} "
                f"before daily editions {missing_text} exist."
            )

        next_edition = max(max(existing_editions), daily_target) + 1
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


def _extract_factoid_answer_kind(payload: dict[str, Any]) -> str | None:
    questions = payload.get("questions")
    if not isinstance(questions, list) or not questions or not isinstance(questions[0], dict):
        return None
    facets = questions[0].get("facets")
    if not isinstance(facets, dict):
        return None
    answer_kind = facets.get("answer_kind")
    if answer_kind in {"person", "place", "organization", "work", "object", "time"}:
        return answer_kind
    return None


def _collect_recent_factoid_answer_kinds(output_dir: str, *, limit: int = 6) -> list[str]:
    records = [
        record
        for record in iter_quiz_records(output_dir)
        if record.quiz_type == QUIZ_TYPE_HISTORY_FACTOID_MCQ_4
    ]
    records.sort(
        key=lambda record: (
            record.date.isoformat(),
            record.generated_at or "",
            record.edition,
            record.path.as_posix(),
        )
    )
    kinds = [
        answer_kind
        for record in records
        if (answer_kind := _extract_factoid_answer_kind(record.payload)) is not None
    ]
    return kinds[-limit:]


def _preferred_factoid_answer_kind(recent_kinds: list[str]) -> str | None:
    person_count = sum(1 for kind in recent_kinds if kind == "person")
    place_count = sum(1 for kind in recent_kinds if kind == "place")
    if person_count == place_count:
        return None
    if person_count > place_count:
        return "place"
    return "person"


def _event_selection_key(event: dict[str, Any]) -> tuple[str, int, str] | None:
    text = event.get("text")
    year = event.get("year")
    wikipedia_url = event.get("wikipedia_url")
    if not isinstance(text, str) or not isinstance(year, int) or not isinstance(wikipedia_url, str):
        return None
    return (text, year, wikipedia_url)


def _record_selected_popularity_scores(
    *,
    quiz: dict[str, Any],
    candidates: list[dict[str, Any]],
    quality_stats: QualityRunStats,
) -> None:
    by_key = {
        key: candidate
        for candidate in candidates
        if (key := _event_selection_key(candidate)) is not None
    }
    source = quiz.get("source")
    if not isinstance(source, dict):
        return
    events_used = source.get("events_used")
    if not isinstance(events_used, list):
        return

    for event in events_used:
        if not isinstance(event, dict):
            continue
        key = _event_selection_key(event)
        if key is None:
            continue
        candidate = by_key.get(key)
        if not isinstance(candidate, dict):
            continue
        popularity = candidate.get("popularity_signals")
        if not isinstance(popularity, dict):
            continue
        score = popularity.get("popularity_score")
        if isinstance(score, (int, float)):
            quality_stats.add_selected_popularity_score(float(score))


def _write_quality_report(report_path: str | None, *, quality_stats: QualityRunStats, date_utc: str) -> None:
    if not report_path:
        return
    payload: dict[str, Any] = {}
    report_file = Path(report_path)
    if report_file.exists():
        payload = json.loads(report_file.read_text(encoding="utf-8"))
    payload["date_utc"] = payload.get("date_utc", date_utc)
    payload["quality"] = quality_stats.to_report_payload()
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    if getattr(args, "backfill_human_ids", False):
        return _backfill_human_ids(args.output_dir)

    target_date = parse_target_date(args.date)
    quiz_types = parse_quiz_types(args.quiz_types)
    generation_mode = parse_generation_mode(args.mode)
    generation_count = parse_generation_count(args.count)
    daily_editions_by_type = parse_daily_editions_by_type(args.daily_editions_by_type, quiz_types=quiz_types)
    ai_settings = load_ai_settings(output_dir=args.output_dir)
    ai_orchestrator = AIOrchestrator(settings=ai_settings, target_date=target_date)
    factoid_pipeline_settings = load_factoid_pipeline_settings(ai_settings.model)
    quality_stats = QualityRunStats()

    pending = _build_generation_plan(
        output_dir=args.output_dir,
        target_date=target_date,
        quiz_types=quiz_types,
        mode=generation_mode,
        count=generation_count,
        daily_editions_by_type=daily_editions_by_type,
    )
    human_id_lookup = load_human_id_lookup(args.output_dir)
    human_id_lookup_changed = False
    recent_factoid_answer_kinds = _collect_recent_factoid_answer_kinds(args.output_dir)

    generated: list[tuple[str, int, Path, dict[str, Any]]] = []
    if pending:
        retrieval_time = dt.datetime.now(dt.timezone.utc)
        history_source_url: str | None = None
        history_candidates: list[dict[str, Any]] | None = None
        geography_source_url: str | None = None
        geography_candidates: list[dict[str, Any]] | None = None

        if any(quiz_type != QUIZ_TYPE_GEOGRAPHY_FACTOID_MCQ_4 for quiz_type, _, _ in pending):
            history_source_url = build_api_url(target_date)
            source_payload = fetch_json(history_source_url, timeout=args.timeout, retries=args.retries)
            history_candidates = extract_candidates(source_payload)
            try:
                history_candidates, popularity_report = enrich_history_candidates_with_popularity(
                    candidates=history_candidates,
                    target_date=target_date,
                    timeout=args.timeout,
                    retries=args.retries,
                )
            except Exception as exc:  # noqa: BLE001
                quality_stats.add_popularity_enrichment(
                    enriched_count=0,
                    neutral_count=len(history_candidates),
                )
                quality_stats.add_popularity_fallback_reason(f"enrichment_failed:{type(exc).__name__}")
                print(f"Popularity enrichment fallback for history candidates: {type(exc).__name__}")
            else:
                quality_stats.add_popularity_enrichment(
                    enriched_count=int(popularity_report.get("enriched_count", 0)),
                    neutral_count=int(popularity_report.get("neutral_count", 0)),
                )
                fallback_reasons = popularity_report.get("fallback_reasons")
                if isinstance(fallback_reasons, dict):
                    for reason, count in fallback_reasons.items():
                        if not isinstance(reason, str):
                            continue
                        for _ in range(max(0, int(count))):
                            quality_stats.add_popularity_fallback_reason(reason)
        if any(quiz_type == QUIZ_TYPE_GEOGRAPHY_FACTOID_MCQ_4 for quiz_type, _, _ in pending):
            geography_source_url = GEOGRAPHY_SOURCE_URL
            geography_candidates = load_geography_records()
        reusable_correct_events: list[dict[str, Any]] = []

        for quiz_type, edition, output_path in pending:
            builder = QUIZ_BUILDERS[quiz_type]
            seed = build_seed(target_date, quiz_type, edition)
            if quiz_type == QUIZ_TYPE_GEOGRAPHY_FACTOID_MCQ_4:
                source_url = geography_source_url
                candidates = geography_candidates
            else:
                source_url = history_source_url
                candidates = history_candidates
            if not isinstance(source_url, str) or candidates is None:
                raise ValueError(f"Missing source inputs for {quiz_type}.")
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

            if quiz_type == QUIZ_TYPE_HISTORY_FACTOID_MCQ_4:
                preferred_answer_kind = _preferred_factoid_answer_kind(recent_factoid_answer_kinds)
                ai_native_quiz: dict[str, Any] | None = None
                ai_native_reason: str | None = None
                if factoid_pipeline_settings.enabled:
                    ai_native_quiz, ai_native_reason = generate_ai_native_factoid_quiz(
                        target_date=target_date,
                        retrieval_time=retrieval_time,
                        source_url=source_url,
                        candidates=candidates,
                        seed=seed,
                        edition=edition,
                        generation_mode=generation_mode,
                        preferred_answer_kind=preferred_answer_kind,
                        settings=factoid_pipeline_settings,
                        ai_orchestrator=ai_orchestrator,
                        timeout=args.timeout,
                        retries=args.retries,
                        quality_stats=quality_stats,
                    )
                    if ai_native_quiz is not None:
                        factoid_issues = lint_quiz_payload(ai_native_quiz)
                        if factoid_issues:
                            quality_stats.add_issues(factoid_issues)
                            quality_stats.add_fallback_path("history_factoid_mcq_4:ai_native_rejected")
                            quality_stats.add_ai_quality_rejection()
                            print(
                                "AI-native factoid quiz rejected by quality lint for history_factoid_mcq_4: "
                                + ", ".join(factoid_issues)
                            )
                            ai_native_quiz = None
                            ai_native_reason = "quality_lint_rejected"
                if ai_native_quiz is not None:
                    quiz = ai_native_quiz
                    print("AI-native page-grounded factoid quiz applied for history_factoid_mcq_4.")
                else:
                    if factoid_pipeline_settings.enabled and ai_native_reason is not None:
                        quality_stats.add_fallback_path("history_factoid_mcq_4:ai_native_fallback")
                        print(f"AI-native factoid fallback for history_factoid_mcq_4: {ai_native_reason}")
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
                        preferred_answer_kind=preferred_answer_kind,
                        quality_stats=quality_stats,
                    )
            elif quiz_type == QUIZ_TYPE_HISTORY_MCQ_4:
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
                    quality_stats=quality_stats,
                )
            else:
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
                answer_kind = _extract_factoid_answer_kind(quiz)
                if answer_kind is not None:
                    recent_factoid_answer_kinds.append(answer_kind)
                    recent_factoid_answer_kinds = recent_factoid_answer_kinds[-6:]
                print(f"Final factoid subtype for history_factoid_mcq_4: {answer_kind or 'unknown'}")

            if apply_human_ids_to_quiz(quiz=quiz, quiz_path=output_path, lookup=human_id_lookup):
                human_id_lookup_changed = True

            validate_quiz(quiz, target_date)
            generated.append((quiz_type, edition, output_path, quiz))
            if quiz_type != QUIZ_TYPE_GEOGRAPHY_FACTOID_MCQ_4 and history_candidates is not None:
                _record_selected_popularity_scores(
                    quiz=quiz,
                    candidates=history_candidates,
                    quality_stats=quality_stats,
                )

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
    _write_quality_report(ai_settings.report_path, quality_stats=quality_stats, date_utc=target_date.isoformat())
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
