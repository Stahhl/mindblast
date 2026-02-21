#!/usr/bin/env python3
"""Generate one daily 'which came first' history quiz from Wikimedia data."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib import error, request


API_URL_TEMPLATE = "https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/events/{month}/{day}"
QUESTION_TEXT = "Which event happened earlier?"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date",
        default=None,
        help="UTC date to generate for (YYYY-MM-DD). Defaults to today in UTC.",
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


def build_api_url(target_date: dt.date) -> str:
    return API_URL_TEMPLATE.format(month=target_date.month, day=target_date.day)


def fetch_json(url: str, timeout: int, retries: int) -> dict[str, Any]:
    headers = {"User-Agent": "quiz-forge/1.0 (mindblast project)"}
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            req = request.Request(url, headers=headers)
            with request.urlopen(req, timeout=timeout) as response:
                payload = response.read().decode("utf-8")
            return json.loads(payload)
        except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt == retries:
                break
            time.sleep(min(2**attempt, 8))

    raise RuntimeError(f"Failed to fetch source after {retries} attempts: {last_error}") from last_error


def first_wikipedia_url(event: dict[str, Any]) -> str | None:
    pages = event.get("pages")
    if not isinstance(pages, list):
        return None

    for page in pages:
        if not isinstance(page, dict):
            continue
        content_urls = page.get("content_urls")
        if not isinstance(content_urls, dict):
            continue
        desktop = content_urls.get("desktop")
        if not isinstance(desktop, dict):
            continue
        page_url = desktop.get("page")
        if isinstance(page_url, str) and page_url.strip():
            return page_url.strip()

    return None


def extract_candidates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    events = payload.get("events")
    if not isinstance(events, list):
        raise ValueError("Source payload missing 'events' list.")

    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()

    for raw_event in events:
        if not isinstance(raw_event, dict):
            continue

        raw_text = raw_event.get("text")
        raw_year = raw_event.get("year")

        if not isinstance(raw_text, str):
            continue
        text = raw_text.strip()
        if not text:
            continue

        if isinstance(raw_year, int):
            year = raw_year
        elif isinstance(raw_year, str) and raw_year.strip().lstrip("-").isdigit():
            year = int(raw_year.strip())
        else:
            continue

        page_url = first_wikipedia_url(raw_event)
        if not page_url:
            continue

        key = (text, year)
        if key in seen:
            continue
        seen.add(key)

        candidates.append({"text": text, "year": year, "wikipedia_url": page_url})

    return candidates


def pick_two_events(candidates: list[dict[str, Any]], target_date: dt.date) -> tuple[dict[str, Any], dict[str, Any]]:
    if len(candidates) < 2:
        raise ValueError("Not enough valid events to build a question.")

    ordered = sorted(candidates, key=lambda item: (item["year"], item["text"]))
    seed = int(hashlib.sha256(target_date.isoformat().encode("utf-8")).hexdigest(), 16)

    first_idx = seed % len(ordered)
    step = (seed % (len(ordered) - 1)) + 1

    for offset in range(len(ordered) - 1):
        second_idx = (first_idx + step + offset) % len(ordered)
        if second_idx == first_idx:
            continue
        first = ordered[first_idx]
        second = ordered[second_idx]
        if first["year"] != second["year"]:
            return first, second

    raise ValueError("Could not pick two events with distinct years.")


def build_quiz(
    target_date: dt.date,
    retrieval_time: dt.datetime,
    source_url: str,
    first: dict[str, Any],
    second: dict[str, Any],
) -> dict[str, Any]:
    correct_choice_id = "A" if first["year"] < second["year"] else "B"

    return {
        "date": target_date.isoformat(),
        "topics": ["history"],
        "type": "which_came_first",
        "question": QUESTION_TEXT,
        "choices": [
            {"id": "A", "label": first["text"], "year": first["year"]},
            {"id": "B", "label": second["text"], "year": second["year"]},
        ],
        "correct_choice_id": correct_choice_id,
        "source": {
            "name": "Wikipedia On This Day",
            "url": source_url,
            "retrieved_at": retrieval_time.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "events_used": [
                {
                    "text": first["text"],
                    "year": first["year"],
                    "wikipedia_url": first["wikipedia_url"],
                },
                {
                    "text": second["text"],
                    "year": second["year"],
                    "wikipedia_url": second["wikipedia_url"],
                },
            ],
        },
        "metadata": {"version": 1},
    }


def validate_quiz(quiz: dict[str, Any], target_date: dt.date) -> None:
    if quiz.get("date") != target_date.isoformat():
        raise ValueError("Invalid date field.")

    if quiz.get("topics") != ["history"]:
        raise ValueError("topics must equal ['history'] in Phase 1.")

    if quiz.get("type") != "which_came_first":
        raise ValueError("type must be 'which_came_first'.")

    question = quiz.get("question")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be a non-empty string.")

    choices = quiz.get("choices")
    if not isinstance(choices, list) or len(choices) != 2:
        raise ValueError("choices must contain exactly 2 entries.")

    ids: list[str] = []
    years: list[int] = []

    for choice in choices:
        if not isinstance(choice, dict):
            raise ValueError("each choice must be an object.")
        choice_id = choice.get("id")
        label = choice.get("label")
        year = choice.get("year")

        if not isinstance(choice_id, str) or not choice_id.strip():
            raise ValueError("choice id must be a non-empty string.")
        if not isinstance(label, str) or not label.strip():
            raise ValueError("choice label must be a non-empty string.")
        if not isinstance(year, int):
            raise ValueError("choice year must be an integer.")

        ids.append(choice_id)
        years.append(year)

    if len(set(ids)) != 2:
        raise ValueError("choice ids must be unique.")
    if years[0] == years[1]:
        raise ValueError("choice years must be distinct.")

    correct_choice_id = quiz.get("correct_choice_id")
    if correct_choice_id not in ids:
        raise ValueError("correct_choice_id must match one of the choice ids.")

    source = quiz.get("source")
    if not isinstance(source, dict):
        raise ValueError("source must be an object.")

    for key in ("name", "url", "retrieved_at"):
        value = source.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"source.{key} must be a non-empty string.")

    events_used = source.get("events_used")
    if not isinstance(events_used, list) or len(events_used) != 2:
        raise ValueError("source.events_used must contain exactly 2 entries.")

    for event in events_used:
        if not isinstance(event, dict):
            raise ValueError("source.events_used entries must be objects.")
        text = event.get("text")
        year = event.get("year")
        wikipedia_url = event.get("wikipedia_url")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("source.events_used.text must be a non-empty string.")
        if not isinstance(year, int):
            raise ValueError("source.events_used.year must be an integer.")
        if not isinstance(wikipedia_url, str) or not wikipedia_url.strip():
            raise ValueError("source.events_used.wikipedia_url must be a non-empty string.")

    metadata = quiz.get("metadata")
    if not isinstance(metadata, dict) or metadata.get("version") != 1:
        raise ValueError("metadata.version must be 1.")


def write_quiz_file(path: Path, quiz: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(quiz, ensure_ascii=True, indent=2) + "\n"

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=".tmp-quiz-",
        delete=False,
    ) as temp_file:
        temp_file.write(body)
        temp_path = Path(temp_file.name)

    os.replace(temp_path, path)


def main() -> int:
    args = parse_args()
    target_date = parse_target_date(args.date)
    output_path = Path(args.output_dir) / f"{target_date.isoformat()}.json"

    if output_path.exists():
        print(f"Quiz already exists: {output_path}")
        return 0

    retrieval_time = dt.datetime.now(dt.timezone.utc)
    source_url = build_api_url(target_date)
    source_payload = fetch_json(source_url, timeout=args.timeout, retries=args.retries)

    candidates = extract_candidates(source_payload)
    first, second = pick_two_events(candidates, target_date)
    quiz = build_quiz(target_date, retrieval_time, source_url, first, second)
    validate_quiz(quiz, target_date)
    write_quiz_file(output_path, quiz)

    print(f"Created quiz file: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
