"""CLI argument parsing helpers."""

from __future__ import annotations

import argparse
import datetime as dt

from .constants import DEFAULT_QUIZ_TYPES, SUPPORTED_QUIZ_TYPES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate daily history quizzes from Wikimedia data.")
    parser.add_argument(
        "--date",
        default=None,
        help="UTC date to generate for (YYYY-MM-DD). Defaults to today in UTC.",
    )
    parser.add_argument(
        "--quiz-types",
        default=DEFAULT_QUIZ_TYPES,
        help=(
            "Comma-separated quiz types to generate. "
            f"Supported: {', '.join(SUPPORTED_QUIZ_TYPES)}"
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="quizzes",
        help="Directory where quiz JSON files are written.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=15,
        help="HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Max HTTP retries.",
    )
    return parser.parse_args()


def parse_target_date(value: str | None) -> dt.date:
    if value is None:
        return dt.datetime.now(dt.timezone.utc).date()
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid --date value '{value}'. Expected YYYY-MM-DD.") from exc


def parse_quiz_types(value: str) -> list[str]:
    raw_types = [item.strip() for item in value.split(",") if item.strip()]
    if not raw_types:
        raise ValueError("--quiz-types must include at least one type.")

    parsed: list[str] = []
    seen: set[str] = set()
    for quiz_type in raw_types:
        if quiz_type not in SUPPORTED_QUIZ_TYPES:
            supported = ", ".join(SUPPORTED_QUIZ_TYPES)
            raise ValueError(f"Unsupported quiz type '{quiz_type}'. Supported: {supported}")
        if quiz_type in seen:
            continue
        seen.add(quiz_type)
        parsed.append(quiz_type)

    return parsed
