"""Path resolution and file write helpers."""

from __future__ import annotations

import datetime as dt
import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

from .constants import QUIZ_FILENAME_NAMESPACE, QUIZ_TYPE_WHICH_CAME_FIRST


def build_output_path(output_dir: str, target_date: dt.date, quiz_type: str) -> Path:
    quiz_key = f"{target_date.isoformat()}:{quiz_type}"
    quiz_id = uuid.uuid5(QUIZ_FILENAME_NAMESPACE, quiz_key)
    return Path(output_dir) / f"{quiz_id}.json"


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
