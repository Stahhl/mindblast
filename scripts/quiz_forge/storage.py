"""Path resolution and file write helpers."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

from .constants import (
    GENERATION_MODE_DAILY,
    QUIZ_FILENAME_NAMESPACE,
    QUIZ_TYPE_WHICH_CAME_FIRST,
    SUPPORTED_QUIZ_TYPES,
)


@dataclass(frozen=True)
class QuizRecord:
    path: Path
    quiz_type: str
    date: dt.date
    edition: int
    mode: str
    generated_at: str | None
    payload: dict[str, Any]


def build_output_path(output_dir: str, target_date: dt.date, quiz_type: str, edition: int) -> Path:
    quiz_key = f"{target_date.isoformat()}:{quiz_type}:{edition}"
    quiz_id = uuid.uuid5(QUIZ_FILENAME_NAMESPACE, quiz_key)
    return Path(output_dir) / f"{quiz_id}.json"


def find_existing_quiz_path(
    output_path: Path,
    target_date: dt.date,
    quiz_type: str,
    edition: int,
) -> Path | None:
    if output_path.exists():
        return output_path

    if edition != 1 or quiz_type != QUIZ_TYPE_WHICH_CAME_FIRST:
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


def _parse_quiz_record(path: Path, payload: dict[str, Any]) -> QuizRecord | None:
    quiz_type = payload.get("type")
    if not isinstance(quiz_type, str) or quiz_type not in SUPPORTED_QUIZ_TYPES:
        return None

    date_text = payload.get("date")
    if not isinstance(date_text, str):
        return None
    try:
        parsed_date = dt.date.fromisoformat(date_text)
    except ValueError:
        return None

    generation = payload.get("generation")
    edition = 1
    mode = GENERATION_MODE_DAILY
    generated_at: str | None = None
    if isinstance(generation, dict):
        maybe_edition = generation.get("edition")
        maybe_mode = generation.get("mode")
        maybe_generated_at = generation.get("generated_at")
        if isinstance(maybe_edition, int) and maybe_edition >= 1:
            edition = maybe_edition
        if isinstance(maybe_mode, str) and maybe_mode.strip():
            mode = maybe_mode
        if isinstance(maybe_generated_at, str) and maybe_generated_at.strip():
            generated_at = maybe_generated_at

    if generated_at is None:
        source = payload.get("source")
        if isinstance(source, dict):
            source_retrieved_at = source.get("retrieved_at")
            if isinstance(source_retrieved_at, str) and source_retrieved_at.strip():
                generated_at = source_retrieved_at

    return QuizRecord(
        path=path,
        quiz_type=quiz_type,
        date=parsed_date,
        edition=edition,
        mode=mode,
        generated_at=generated_at,
        payload=payload,
    )


def iter_quiz_records(output_dir: str) -> list[QuizRecord]:
    root = Path(output_dir)
    if not root.exists():
        return []

    records: list[QuizRecord] = []
    for path in sorted(root.glob("*.json")):
        payload = load_json_file(path)
        if payload is None:
            continue
        record = _parse_quiz_record(path, payload)
        if record is None:
            continue
        records.append(record)
    return records


def list_quiz_records_for_date(output_dir: str, target_date: dt.date) -> list[QuizRecord]:
    return [record for record in iter_quiz_records(output_dir) if record.date == target_date]


def list_quiz_records_for_date_type(output_dir: str, target_date: dt.date, quiz_type: str) -> list[QuizRecord]:
    records = [
        record
        for record in iter_quiz_records(output_dir)
        if record.date == target_date and record.quiz_type == quiz_type
    ]
    records.sort(key=lambda record: (record.edition, record.path.as_posix()))
    return records


def load_json_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as file_obj:
        payload = json.load(file_obj)
    if not isinstance(payload, dict):
        return None
    return payload


def write_json_file(path: Path, payload: dict[str, Any], prefix: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, ensure_ascii=True, indent=2) + "\n"

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=prefix,
        delete=False,
    ) as temp_file:
        temp_file.write(body)
        temp_path = Path(temp_file.name)

    os.replace(temp_path, path)


def write_quiz_file(path: Path, quiz: dict[str, Any]) -> None:
    write_json_file(path, quiz, prefix=".tmp-quiz-")
