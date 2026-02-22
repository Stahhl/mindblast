"""Main quiz generation workflow."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from .args import parse_args, parse_quiz_types, parse_target_date
from .builders import QUIZ_BUILDERS
from .discovery import write_discovery_artifacts
from .selection import build_seed
from .source import build_api_url, extract_candidates, fetch_json
from .storage import build_output_path, find_existing_quiz_path, write_quiz_file
from .validation import validate_quiz


def main() -> int:
    args = parse_args()
    target_date = parse_target_date(args.date)
    quiz_types = parse_quiz_types(args.quiz_types)

    pending: list[tuple[str, Path]] = []
    quiz_paths: dict[str, Path] = {}
    for quiz_type in quiz_types:
        output_path = build_output_path(args.output_dir, target_date, quiz_type)
        existing_path = find_existing_quiz_path(output_path, target_date, quiz_type)
        if existing_path is not None:
            print(f"Quiz already exists for {quiz_type}: {existing_path}")
            quiz_paths[quiz_type] = existing_path
            continue
        pending.append((quiz_type, output_path))
        quiz_paths[quiz_type] = output_path

    generated: list[tuple[str, Path, dict[str, Any]]] = []
    if pending:
        retrieval_time = dt.datetime.now(dt.timezone.utc)
        source_url = build_api_url(target_date)
        source_payload = fetch_json(source_url, timeout=args.timeout, retries=args.retries)
        candidates = extract_candidates(source_payload)

        for quiz_type, output_path in pending:
            builder = QUIZ_BUILDERS[quiz_type]
            seed = build_seed(target_date, quiz_type)
            quiz = builder(target_date, retrieval_time, source_url, candidates, seed)
            validate_quiz(quiz, target_date)
            generated.append((quiz_type, output_path, quiz))

    for quiz_type, output_path, quiz in generated:
        write_quiz_file(output_path, quiz)
        print(f"Created quiz file for {quiz_type}: {output_path}")

    discovery_changes = write_discovery_artifacts(
        output_dir=args.output_dir,
        target_date=target_date,
        quiz_types=quiz_types,
        quiz_paths=quiz_paths,
        generated_now=bool(generated),
    )
    for discovery_path in discovery_changes:
        print(f"Updated discovery artifact: {discovery_path}")

    if not generated and not discovery_changes:
        print("No new quizzes or discovery updates.")

    return 0
