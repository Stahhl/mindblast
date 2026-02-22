"""Discovery artifact generation for static clients."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from .storage import load_json_file, write_json_file


def _utc_timestamp(value: dt.datetime) -> str:
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_repo_relative(path: Path, root: Path) -> str:
    absolute = path if path.is_absolute() else (root / path)
    try:
        return absolute.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _build_daily_index_payload(
    target_date: dt.date,
    quiz_types: list[str],
    quiz_paths: dict[str, Path],
    generated_at: dt.datetime,
) -> dict[str, Any]:
    quiz_files: dict[str, str] = {}
    root = Path.cwd().resolve()
    for quiz_type in quiz_types:
        quiz_path = quiz_paths[quiz_type]
        if not quiz_path.exists():
            raise ValueError(f"Missing quiz file for index: {quiz_type} -> {quiz_path}")
        quiz_files[quiz_type] = _as_repo_relative(quiz_path, root)

    available_types = list(quiz_files.keys())

    return {
        "date": target_date.isoformat(),
        "quiz_files": quiz_files,
        "available_types": available_types,
        "metadata": {
            "version": 1,
            "generated_at": _utc_timestamp(generated_at),
        },
    }


def _build_latest_payload(
    target_date: dt.date,
    daily_index_path: Path,
    available_types: list[str],
    updated_at: dt.datetime,
) -> dict[str, Any]:
    return {
        "date": target_date.isoformat(),
        "index_file": _as_repo_relative(daily_index_path, Path.cwd().resolve()),
        "available_types": available_types,
        "metadata": {
            "version": 1,
            "updated_at": _utc_timestamp(updated_at),
        },
    }


def _validate_daily_index_payload(payload: dict[str, Any]) -> None:
    date_value = payload.get("date")
    if not isinstance(date_value, str) or not date_value:
        raise ValueError("daily index date must be a non-empty string.")

    quiz_files = payload.get("quiz_files")
    if not isinstance(quiz_files, dict) or not quiz_files:
        raise ValueError("daily index quiz_files must be a non-empty object.")

    available_types = payload.get("available_types")
    if not isinstance(available_types, list) or not available_types:
        raise ValueError("daily index available_types must be a non-empty list.")

    quiz_file_keys = list(quiz_files.keys())
    if quiz_file_keys != available_types:
        raise ValueError("daily index available_types must match quiz_files keys order.")

    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("daily index metadata must be an object.")
    if metadata.get("version") != 1:
        raise ValueError("daily index metadata.version must be 1.")
    generated_at = metadata.get("generated_at")
    if not isinstance(generated_at, str) or not generated_at.endswith("Z"):
        raise ValueError("daily index metadata.generated_at must be a UTC timestamp.")


def write_discovery_artifacts(
    output_dir: str,
    target_date: dt.date,
    quiz_types: list[str],
    quiz_paths: dict[str, Path],
    generated_now: bool,
) -> list[Path]:
    now = dt.datetime.now(dt.timezone.utc)
    output_root = Path(output_dir)
    daily_index_path = output_root / "index" / f"{target_date.isoformat()}.json"
    latest_path = output_root / "latest.json"

    existing_daily_index = load_json_file(daily_index_path)
    if generated_now or existing_daily_index is None:
        daily_generated_at = now
    else:
        metadata = existing_daily_index.get("metadata")
        existing_generated_at = metadata.get("generated_at") if isinstance(metadata, dict) else None
        if isinstance(existing_generated_at, str) and existing_generated_at.endswith("Z"):
            daily_generated_at = dt.datetime.fromisoformat(existing_generated_at.replace("Z", "+00:00"))
        else:
            daily_generated_at = now

    daily_index_payload = _build_daily_index_payload(
        target_date=target_date,
        quiz_types=quiz_types,
        quiz_paths=quiz_paths,
        generated_at=daily_generated_at,
    )
    _validate_daily_index_payload(daily_index_payload)

    changed_paths: list[Path] = []
    if existing_daily_index != daily_index_payload:
        write_json_file(daily_index_path, daily_index_payload, prefix=".tmp-index-")
        changed_paths.append(daily_index_path)

    existing_latest = load_json_file(latest_path)
    latest_payload: dict[str, Any] | None = None
    if existing_latest is None:
        latest_payload = _build_latest_payload(
            target_date=target_date,
            daily_index_path=daily_index_path,
            available_types=daily_index_payload["available_types"],
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
                available_types=daily_index_payload["available_types"],
                updated_at=now,
            )
        elif target_date == existing_date_value:
            metadata = existing_latest.get("metadata")
            existing_updated_at = metadata.get("updated_at") if isinstance(metadata, dict) else None
            if isinstance(existing_updated_at, str) and existing_updated_at.endswith("Z"):
                latest_updated_at = dt.datetime.fromisoformat(existing_updated_at.replace("Z", "+00:00"))
            else:
                latest_updated_at = now

            latest_payload = _build_latest_payload(
                target_date=target_date,
                daily_index_path=daily_index_path,
                available_types=daily_index_payload["available_types"],
                updated_at=latest_updated_at,
            )
            if existing_latest != latest_payload:
                latest_payload = _build_latest_payload(
                    target_date=target_date,
                    daily_index_path=daily_index_path,
                    available_types=daily_index_payload["available_types"],
                    updated_at=now,
                )

    if latest_payload is not None and existing_latest != latest_payload:
        write_json_file(latest_path, latest_payload, prefix=".tmp-latest-")
        changed_paths.append(latest_path)

    return changed_paths
