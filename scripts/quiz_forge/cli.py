"""Main quiz generation workflow."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from .args import parse_args, parse_quiz_types, parse_target_date
from .builders import QUIZ_BUILDERS
from .selection import build_seed
from .source import build_api_url, extract_candidates, fetch_json
from .storage import build_output_path, find_existing_quiz_path, write_quiz_file
from .validation import validate_quiz


def main() -> int:
    args = parse_args()
    target_date = parse_target_date(args.date)
    quiz_types = parse_quiz_types(args.quiz_types)

    pending: list[tuple[str, Path]] = []
    for quiz_type in quiz_types:
        output_path = build_output_path(args.output_dir, target_date, quiz_type)
        existing_path = find_existing_quiz_path(output_path, target_date, quiz_type)
        if existing_path is not None:
            print(f"Quiz already exists for {quiz_type}: {existing_path}")
            continue
        pending.append((quiz_type, output_path))

    if not pending:
        print("No new quizzes to generate.")
        return 0

    retrieval_time = dt.datetime.now(dt.timezone.utc)
    source_url = build_api_url(target_date)
    source_payload = fetch_json(source_url, timeout=args.timeout, retries=args.retries)
    candidates = extract_candidates(source_payload)

    generated: list[tuple[str, Path, dict[str, Any]]] = []
    for quiz_type, output_path in pending:
        builder = QUIZ_BUILDERS[quiz_type]
        seed = build_seed(target_date, quiz_type)
        quiz = builder(target_date, retrieval_time, source_url, candidates, seed)
        validate_quiz(quiz, target_date)
        generated.append((quiz_type, output_path, quiz))

    for quiz_type, output_path, quiz in generated:
        write_quiz_file(output_path, quiz)
        print(f"Created quiz file for {quiz_type}: {output_path}")

    return 0
