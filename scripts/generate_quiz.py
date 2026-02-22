#!/usr/bin/env python3
"""Generate daily history quizzes from Wikimedia data."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any
from urllib import error, request


API_URL_TEMPLATE = "https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/events/{month}/{day}"
QUIZ_TYPE_WHICH_CAME_FIRST = "which_came_first"
QUIZ_TYPE_HISTORY_MCQ_4 = "history_mcq_4"
SUPPORTED_QUIZ_TYPES = (QUIZ_TYPE_WHICH_CAME_FIRST, QUIZ_TYPE_HISTORY_MCQ_4)
DEFAULT_QUIZ_TYPES = ",".join(SUPPORTED_QUIZ_TYPES)
QUIZ_FILENAME_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "mindblast.quiz-forge.daily.v1")
WHICH_CAME_FIRST_QUESTION = "Which event happened earlier?"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
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


def build_api_url(target_date: dt.date) -> str:
    return API_URL_TEMPLATE.format(month=target_date.month, day=target_date.day)


def build_output_path(output_dir: str, target_date: dt.date, quiz_type: str) -> Path:
    quiz_key = f"{target_date.isoformat()}:{quiz_type}"
    quiz_id = uuid.uuid5(QUIZ_FILENAME_NAMESPACE, quiz_key)
    return Path(output_dir) / f"{quiz_id}.json"


def build_seed(target_date: dt.date, quiz_type: str) -> int:
    key = f"{target_date.isoformat()}:{quiz_type}"
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest(), 16)


def find_existing_quiz_path(output_path: Path, target_date: dt.date, quiz_type: str) -> Path | None:
    if output_path.exists():
        return output_path

    if quiz_type != QUIZ_TYPE_WHICH_CAME_FIRST:
        return None

    # Backward compatibility: old date-only UUID filename for which_came_first.
    legacy_uuid = uuid.uuid5(QUIZ_FILENAME_NAMESPACE, target_date.isoformat())
    legacy_uuid_path = output_path.parent / f"{legacy_uuid}.json"
    if legacy_uuid_path.exists():
        return legacy_uuid_path

    # Backward compatibility: original YYYY-MM-DD filename.
    legacy_date_path = output_path.parent / f"{target_date.isoformat()}.json"
    if legacy_date_path.exists():
        return legacy_date_path

    return None


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


def pick_two_events(candidates: list[dict[str, Any]], seed: int) -> tuple[dict[str, Any], dict[str, Any]]:
    if len(candidates) < 2:
        raise ValueError("Not enough valid events to build a question.")

    ordered = sorted(candidates, key=lambda item: (item["year"], item["text"]))
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


def pick_history_mcq_events(
    candidates: list[dict[str, Any]],
    seed: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    if len(candidates) < 4:
        raise ValueError("Not enough valid events to build a 4-option history MCQ.")

    ordered = sorted(candidates, key=lambda item: (item["year"], item["text"]))
    correct_idx = seed % len(ordered)
    correct = ordered[correct_idx]

    step = (seed % (len(ordered) - 1)) + 1
    distractors: list[dict[str, Any]] = []
    distractor_years: set[int] = set()

    for offset in range(len(ordered) - 1):
        idx = (correct_idx + step + offset) % len(ordered)
        if idx == correct_idx:
            continue

        event = ordered[idx]
        if event["year"] == correct["year"]:
            continue
        if event["year"] in distractor_years:
            continue

        distractors.append(event)
        distractor_years.add(event["year"])
        if len(distractors) == 3:
            break

    if len(distractors) != 3:
        raise ValueError("Could not pick three distinct-year distractors for history_mcq_4.")

    options = [correct, *distractors]
    options.sort(
        key=lambda item: hashlib.sha256(
            f"{seed}:{item['year']}:{item['text']}".encode("utf-8")
        ).hexdigest()
    )

    return correct, distractors, options


def build_source(
    retrieval_time: dt.datetime,
    source_url: str,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "name": "Wikipedia On This Day",
        "url": source_url,
        "retrieved_at": retrieval_time.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "events_used": [
            {
                "text": event["text"],
                "year": event["year"],
                "wikipedia_url": event["wikipedia_url"],
            }
            for event in events
        ],
    }


def build_which_came_first_quiz(
    target_date: dt.date,
    retrieval_time: dt.datetime,
    source_url: str,
    candidates: list[dict[str, Any]],
    seed: int,
) -> dict[str, Any]:
    first, second = pick_two_events(candidates, seed)
    correct_choice_id = "A" if first["year"] < second["year"] else "B"

    return {
        "date": target_date.isoformat(),
        "topics": ["history"],
        "type": QUIZ_TYPE_WHICH_CAME_FIRST,
        "question": WHICH_CAME_FIRST_QUESTION,
        "choices": [
            {"id": "A", "label": first["text"], "year": first["year"]},
            {"id": "B", "label": second["text"], "year": second["year"]},
        ],
        "correct_choice_id": correct_choice_id,
        "source": build_source(retrieval_time, source_url, [first, second]),
        "metadata": {"version": 1},
    }


def build_history_mcq_4_quiz(
    target_date: dt.date,
    retrieval_time: dt.datetime,
    source_url: str,
    candidates: list[dict[str, Any]],
    seed: int,
) -> dict[str, Any]:
    correct, _, options = pick_history_mcq_events(candidates, seed)

    choice_ids = ("A", "B", "C", "D")
    choices: list[dict[str, Any]] = []
    correct_choice_id: str | None = None

    for choice_id, option in zip(choice_ids, options):
        choices.append({"id": choice_id, "label": option["text"]})
        if option is correct:
            correct_choice_id = choice_id

    if correct_choice_id is None:
        raise ValueError("Could not determine correct choice id for history_mcq_4.")

    return {
        "date": target_date.isoformat(),
        "topics": ["history"],
        "type": QUIZ_TYPE_HISTORY_MCQ_4,
        "question": f"Which event happened in {correct['year']}?",
        "choices": choices,
        "correct_choice_id": correct_choice_id,
        "source": build_source(retrieval_time, source_url, options),
        "metadata": {"version": 1},
    }


QUIZ_BUILDERS = {
    QUIZ_TYPE_WHICH_CAME_FIRST: build_which_came_first_quiz,
    QUIZ_TYPE_HISTORY_MCQ_4: build_history_mcq_4_quiz,
}


def validate_common_fields(quiz: dict[str, Any], target_date: dt.date) -> tuple[str, list[dict[str, Any]]]:
    if quiz.get("date") != target_date.isoformat():
        raise ValueError("Invalid date field.")

    if quiz.get("topics") != ["history"]:
        raise ValueError("topics must equal ['history'] in Phase 1.")

    quiz_type = quiz.get("type")
    if quiz_type not in SUPPORTED_QUIZ_TYPES:
        raise ValueError(f"type must be one of {SUPPORTED_QUIZ_TYPES}.")

    question = quiz.get("question")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be a non-empty string.")

    choices = quiz.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("choices must be a non-empty list.")

    ids: list[str] = []
    for choice in choices:
        if not isinstance(choice, dict):
            raise ValueError("each choice must be an object.")

        choice_id = choice.get("id")
        label = choice.get("label")

        if not isinstance(choice_id, str) or not choice_id.strip():
            raise ValueError("choice id must be a non-empty string.")
        if not isinstance(label, str) or not label.strip():
            raise ValueError("choice label must be a non-empty string.")

        ids.append(choice_id)

    if len(set(ids)) != len(ids):
        raise ValueError("choice ids must be unique.")

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
    if not isinstance(events_used, list) or len(events_used) < 2:
        raise ValueError("source.events_used must contain at least 2 entries.")

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

    return quiz_type, choices


def validate_which_came_first_quiz(choices: list[dict[str, Any]], quiz: dict[str, Any]) -> None:
    if len(choices) != 2:
        raise ValueError("which_came_first choices must contain exactly 2 entries.")

    years: list[int] = []
    for choice in choices:
        year = choice.get("year")
        if not isinstance(year, int):
            raise ValueError("which_came_first choice year must be an integer.")
        years.append(year)

    if years[0] == years[1]:
        raise ValueError("which_came_first choice years must be distinct.")

    if quiz.get("question") != WHICH_CAME_FIRST_QUESTION:
        raise ValueError("which_came_first question text is invalid.")

    events_used = quiz["source"]["events_used"]
    if len(events_used) != 2:
        raise ValueError("which_came_first source.events_used must contain exactly 2 entries.")


def validate_history_mcq_4_quiz(choices: list[dict[str, Any]], quiz: dict[str, Any]) -> None:
    if len(choices) != 4:
        raise ValueError("history_mcq_4 choices must contain exactly 4 entries.")

    for choice in choices:
        if "year" in choice:
            raise ValueError("history_mcq_4 choices must not include year.")

    question = quiz.get("question")
    if not isinstance(question, str) or not question.startswith("Which event happened in "):
        raise ValueError("history_mcq_4 question text is invalid.")

    events_used = quiz["source"]["events_used"]
    if len(events_used) != 4:
        raise ValueError("history_mcq_4 source.events_used must contain exactly 4 entries.")


def validate_quiz(quiz: dict[str, Any], target_date: dt.date) -> None:
    quiz_type, choices = validate_common_fields(quiz, target_date)

    if quiz_type == QUIZ_TYPE_WHICH_CAME_FIRST:
        validate_which_came_first_quiz(choices, quiz)
        return

    if quiz_type == QUIZ_TYPE_HISTORY_MCQ_4:
        validate_history_mcq_4_quiz(choices, quiz)
        return

    raise ValueError(f"Unsupported quiz type for validation: {quiz_type}")


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


if __name__ == "__main__":
    raise SystemExit(main())
