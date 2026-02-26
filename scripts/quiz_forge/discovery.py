"""Discovery artifact generation for static clients."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from .constants import SUPPORTED_QUIZ_TYPES
from .storage import QuizRecord, list_quiz_records_for_date, load_json_file, write_json_file


def _utc_timestamp(value: dt.datetime) -> str:
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_repo_relative(path: Path, root: Path) -> str:
    absolute = path if path.is_absolute() else (root / path)
    try:
        return absolute.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _parse_timestamp(value: str | None) -> dt.datetime | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _normalize_generation_mode(raw_mode: str | None, edition: int) -> str:
    if isinstance(raw_mode, str) and raw_mode.strip():
        return raw_mode
    if edition == 1:
        return "daily"
    return "extra"


def _build_daily_entries(records: list[QuizRecord]) -> dict[str, list[dict[str, Any]]]:
    repo_root = Path.cwd().resolve()
    by_type: dict[str, list[QuizRecord]] = {quiz_type: [] for quiz_type in SUPPORTED_QUIZ_TYPES}
    for record in records:
        by_type[record.quiz_type].append(record)

    entries: dict[str, list[dict[str, Any]]] = {}
    for quiz_type in SUPPORTED_QUIZ_TYPES:
        typed_records = by_type[quiz_type]
        if not typed_records:
            continue

        typed_records.sort(key=lambda record: (record.edition, record.path.as_posix()))
        seen_editions: set[int] = set()
        entry_list: list[dict[str, Any]] = []
        for record in typed_records:
            if record.edition in seen_editions:
                raise ValueError(
                    "Duplicate quiz edition detected for "
                    f"{quiz_type} on {record.date.isoformat()}: edition={record.edition}"
                )
            seen_editions.add(record.edition)
            generated_at = record.generated_at or _utc_timestamp(dt.datetime.now(dt.timezone.utc))
            entry_list.append(
                {
                    "edition": record.edition,
                    "mode": _normalize_generation_mode(record.mode, record.edition),
                    "quiz_file": _as_repo_relative(record.path, repo_root),
                    "generated_at": generated_at,
                }
            )
        entries[quiz_type] = entry_list

    return entries


def _compat_quiz_files(quizzes_by_type: dict[str, list[dict[str, Any]]]) -> dict[str, str]:
    quiz_files: dict[str, str] = {}
    for quiz_type in SUPPORTED_QUIZ_TYPES:
        entries = quizzes_by_type.get(quiz_type)
        if not entries:
            continue

        edition_one = next((entry for entry in entries if entry["edition"] == 1), None)
        if edition_one is not None:
            quiz_files[quiz_type] = str(edition_one["quiz_file"])
            continue
        quiz_files[quiz_type] = str(entries[0]["quiz_file"])

    return quiz_files


def _latest_quiz_files(quizzes_by_type: dict[str, list[dict[str, Any]]]) -> dict[str, str]:
    latest: dict[str, str] = {}
    for quiz_type in SUPPORTED_QUIZ_TYPES:
        entries = quizzes_by_type.get(quiz_type)
        if not entries:
            continue
        latest[quiz_type] = str(entries[-1]["quiz_file"])
    return latest


def _build_daily_index_payload(
    target_date: dt.date,
    records: list[QuizRecord],
    generated_at: dt.datetime,
) -> dict[str, Any]:
    quizzes_by_type = _build_daily_entries(records)
    if not quizzes_by_type:
        raise ValueError(f"No quiz records found for {target_date.isoformat()}.")

    available_types = [quiz_type for quiz_type in SUPPORTED_QUIZ_TYPES if quiz_type in quizzes_by_type]
    quiz_files = _compat_quiz_files(quizzes_by_type)

    return {
        "date": target_date.isoformat(),
        "quiz_files": quiz_files,
        "quizzes_by_type": quizzes_by_type,
        "available_types": available_types,
        "metadata": {
            "version": 2,
            "generated_at": _utc_timestamp(generated_at),
        },
    }


def _build_latest_payload(
    target_date: dt.date,
    daily_index_path: Path,
    available_types: list[str],
    latest_quiz_by_type: dict[str, str],
    updated_at: dt.datetime,
) -> dict[str, Any]:
    return {
        "date": target_date.isoformat(),
        "index_file": _as_repo_relative(daily_index_path, Path.cwd().resolve()),
        "available_types": available_types,
        "latest_quiz_by_type": latest_quiz_by_type,
        "metadata": {
            "version": 2,
            "updated_at": _utc_timestamp(updated_at),
        },
    }


def _validate_daily_index_payload(payload: dict[str, Any]) -> None:
    date_value = payload.get("date")
    if not isinstance(date_value, str) or not date_value:
        raise ValueError("daily index date must be a non-empty string.")

    quizzes_by_type = payload.get("quizzes_by_type")
    if not isinstance(quizzes_by_type, dict) or not quizzes_by_type:
        raise ValueError("daily index quizzes_by_type must be a non-empty object.")

    quiz_files = payload.get("quiz_files")
    if not isinstance(quiz_files, dict) or not quiz_files:
        raise ValueError("daily index quiz_files must be a non-empty object.")

    available_types = payload.get("available_types")
    if not isinstance(available_types, list) or not available_types:
        raise ValueError("daily index available_types must be a non-empty list.")

    ordered_available_types = [quiz_type for quiz_type in SUPPORTED_QUIZ_TYPES if quiz_type in quizzes_by_type]
    if available_types != ordered_available_types:
        raise ValueError("daily index available_types must match quizzes_by_type key order.")

    for quiz_type in available_types:
        entries = quizzes_by_type.get(quiz_type)
        if not isinstance(entries, list) or not entries:
            raise ValueError(f"daily index quizzes_by_type.{quiz_type} must be a non-empty list.")
        previous_edition = 0
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError(f"daily index quizzes_by_type.{quiz_type} entries must be objects.")
            edition = entry.get("edition")
            mode = entry.get("mode")
            quiz_file = entry.get("quiz_file")
            generated_at = entry.get("generated_at")
            if not isinstance(edition, int) or edition < 1:
                raise ValueError(f"daily index quizzes_by_type.{quiz_type}.edition must be >= 1.")
            if edition <= previous_edition:
                raise ValueError(f"daily index quizzes_by_type.{quiz_type} editions must be ascending.")
            previous_edition = edition
            if not isinstance(mode, str) or not mode:
                raise ValueError(f"daily index quizzes_by_type.{quiz_type}.mode must be a non-empty string.")
            if not isinstance(quiz_file, str) or not quiz_file:
                raise ValueError(f"daily index quizzes_by_type.{quiz_type}.quiz_file must be a non-empty string.")
            if not isinstance(generated_at, str) or not generated_at.endswith("Z"):
                raise ValueError(f"daily index quizzes_by_type.{quiz_type}.generated_at must be UTC.")

    for quiz_type, path in quiz_files.items():
        if quiz_type not in quizzes_by_type:
            raise ValueError("daily index quiz_files keys must be included in quizzes_by_type.")
        if not isinstance(path, str) or not path:
            raise ValueError("daily index quiz_files values must be non-empty strings.")

    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("daily index metadata must be an object.")
    if metadata.get("version") != 2:
        raise ValueError("daily index metadata.version must be 2.")
    generated_at = metadata.get("generated_at")
    if not isinstance(generated_at, str) or not generated_at.endswith("Z"):
        raise ValueError("daily index metadata.generated_at must be a UTC timestamp.")


def write_discovery_artifacts(
    output_dir: str,
    target_date: dt.date,
    generated_now: bool,
) -> list[Path]:
    now = dt.datetime.now(dt.timezone.utc)
    output_root = Path(output_dir)
    daily_index_path = output_root / "index" / f"{target_date.isoformat()}.json"
    latest_path = output_root / "latest.json"

    records = list_quiz_records_for_date(output_dir, target_date)
    if not records:
        return []

    existing_daily_index = load_json_file(daily_index_path)
    if generated_now or existing_daily_index is None:
        daily_generated_at = now
    else:
        metadata = existing_daily_index.get("metadata")
        existing_generated_at = metadata.get("generated_at") if isinstance(metadata, dict) else None
        daily_generated_at = _parse_timestamp(existing_generated_at) or now

    daily_index_payload = _build_daily_index_payload(
        target_date=target_date,
        records=records,
        generated_at=daily_generated_at,
    )
    _validate_daily_index_payload(daily_index_payload)

    changed_paths: list[Path] = []
    if existing_daily_index != daily_index_payload:
        write_json_file(daily_index_path, daily_index_payload, prefix=".tmp-index-")
        changed_paths.append(daily_index_path)

    existing_latest = load_json_file(latest_path)
    latest_payload: dict[str, Any] | None = None
    latest_quiz_by_type = _latest_quiz_files(daily_index_payload["quizzes_by_type"])
    available_types = daily_index_payload["available_types"]
    if existing_latest is None:
        latest_payload = _build_latest_payload(
            target_date=target_date,
            daily_index_path=daily_index_path,
            available_types=available_types,
            latest_quiz_by_type=latest_quiz_by_type,
            updated_at=now,
        )
    else:
        existing_date = existing_latest.get("date")
        existing_date_value: dt.date | None = None
        if isinstance(existing_date, str):
            try:
                existing_date_value = dt.date.fromisoformat(existing_date)
            except ValueError:
                existing_date_value = None

        if existing_date_value is None or target_date > existing_date_value:
            latest_payload = _build_latest_payload(
                target_date=target_date,
                daily_index_path=daily_index_path,
                available_types=available_types,
                latest_quiz_by_type=latest_quiz_by_type,
                updated_at=now,
            )
        elif target_date == existing_date_value:
            metadata = existing_latest.get("metadata")
            existing_updated_at = metadata.get("updated_at") if isinstance(metadata, dict) else None
            latest_updated_at = _parse_timestamp(existing_updated_at) or now

            latest_payload = _build_latest_payload(
                target_date=target_date,
                daily_index_path=daily_index_path,
                available_types=available_types,
                latest_quiz_by_type=latest_quiz_by_type,
                updated_at=latest_updated_at,
            )
            if existing_latest != latest_payload:
                latest_payload = _build_latest_payload(
                    target_date=target_date,
                    daily_index_path=daily_index_path,
                    available_types=available_types,
                    latest_quiz_by_type=latest_quiz_by_type,
                    updated_at=now,
                )

    if latest_payload is not None and existing_latest != latest_payload:
        write_json_file(latest_path, latest_payload, prefix=".tmp-latest-")
        changed_paths.append(latest_path)

    return changed_paths
