"""Persisted daily quiz-forge run report helpers."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any, Iterable


REPORT_VERSION = 1

_EMPTY_QUALITY_PAYLOAD: dict[str, Any] = {
    "lint_failure_count": 0,
    "lint_failures": [],
    "fallback_count": 0,
    "fallback_paths": [],
    "factoid_final_subtypes": [],
    "ai_quality_rejection_count": 0,
}

_EMPTY_AI_PAYLOAD: dict[str, Any] = {
    "ai_mode": None,
    "provider": None,
    "model": None,
    "calls_total": 0,
    "input_tokens_total": 0,
    "output_tokens_total": 0,
    "run_estimated_cost_usd": 0.0,
    "day_spend_usd": 0.0,
    "month_spend_usd": 0.0,
    "day_limit_usd": 0.0,
    "month_limit_usd": 0.0,
    "fallback_count": 0,
    "fallback_reasons": [],
    "quality": dict(_EMPTY_QUALITY_PAYLOAD),
}


def _normalize_changed_paths(changed_paths: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for path in changed_paths:
        cleaned = path.strip().strip('"').strip("'")
        if cleaned:
            normalized.append(cleaned)
    return sorted(set(normalized))


def build_daily_run_report_path(*, generated_at: dt.datetime, run_id: str) -> str:
    normalized = generated_at.astimezone(dt.timezone.utc).replace(microsecond=0)
    timestamp = normalized.strftime("%Y-%m-%dT%H-%M-%SZ")
    return (
        f"reports/quiz-forge/daily/"
        f"{normalized.year:04d}/{normalized.month:02d}/{normalized.day:02d}/"
        f"{timestamp}-run-{run_id}.json"
    )


def classify_content_changes(changed_paths: Iterable[str]) -> dict[str, Any]:
    normalized_paths = _normalize_changed_paths(changed_paths)

    generated_quiz_files = [
        path
        for path in normalized_paths
        if path.startswith("quizzes/")
        and path.endswith(".json")
        and "/" not in path.removeprefix("quizzes/")
        and path not in {"quizzes/latest.json", "quizzes/human_id_lookup.json"}
    ]
    generated_index_files = [
        path
        for path in normalized_paths
        if path == "quizzes/latest.json" or path.startswith("quizzes/index/")
    ]
    human_id_lookup_updated = "quizzes/human_id_lookup.json" in normalized_paths

    return {
        "changed_paths": normalized_paths,
        "generated_quiz_files": generated_quiz_files,
        "generated_index_files": generated_index_files,
        "quiz_files_changed": bool(generated_quiz_files),
        "discovery_files_changed": bool(generated_index_files),
        "human_id_lookup_updated": human_id_lookup_updated,
    }


def _load_raw_ai_report(raw_report_path: Path | None) -> dict[str, Any]:
    if raw_report_path is None or not raw_report_path.exists():
        return dict(_EMPTY_AI_PAYLOAD)
    payload = json.loads(raw_report_path.read_text(encoding="utf-8"))
    merged = dict(_EMPTY_AI_PAYLOAD)
    merged.update({key: payload.get(key) for key in merged if key != "quality"})
    quality = dict(_EMPTY_QUALITY_PAYLOAD)
    raw_quality = payload.get("quality")
    if isinstance(raw_quality, dict):
        quality.update({key: raw_quality.get(key, quality[key]) for key in quality})
    merged["quality"] = quality
    return merged


def render_daily_run_discord_message(report: dict[str, Any]) -> str:
    status_text = "SUCCESS" if report.get("job_status") == "success" else "FAILURE"
    status_emoji = "✅" if report.get("job_status") == "success" else "❌"

    request = report.get("request", {})
    lines = [
        f"{status_emoji} mindblast quiz-forge daily job: {status_text}",
        f"repo: {report.get('repository', 'unknown')}",
        f"workflow: {report.get('workflow', 'unknown')}",
        f"run: {report.get('run_url', 'unknown')}",
        "request:",
        f"  target date: {request.get('target_date', 'unknown')}",
        f"  quiz types: {', '.join(request.get('quiz_types') or []) or 'none'}",
        f"  mode/count: {request.get('mode', 'unknown')}/{request.get('count', 'unknown')}",
    ]

    lines.extend(
        [
            "ai:",
            f"  mode: {report.get('ai_mode', 'unknown')}",
            f"  provider/model: {report.get('provider', 'unknown')}/{report.get('model', 'unknown')}",
            f"  calls: {report.get('calls_total', 0)}",
            f"  tokens in/out: {report.get('input_tokens_total', 0)}/{report.get('output_tokens_total', 0)}",
            f"  run spend usd: {report.get('run_estimated_cost_usd', 0)}",
            f"  day spend usd: {report.get('day_spend_usd', 0)} / {report.get('day_limit_usd', 0)}",
            f"  month spend usd: {report.get('month_spend_usd', 0)} / {report.get('month_limit_usd', 0)}",
            f"  fallbacks: {report.get('fallback_count', 0)} ({', '.join(report.get('fallback_reasons') or []) or 'none'})",
        ]
    )

    quality = report.get("quality")
    if isinstance(quality, dict):
        lines.extend(
            [
                "quality:",
                f"  lint failures: {quality.get('lint_failure_count', 0)} ({', '.join(quality.get('lint_failures') or []) or 'none'})",
                f"  fallback paths: {quality.get('fallback_count', 0)} ({', '.join(quality.get('fallback_paths') or []) or 'none'})",
                f"  factoid subtypes: {', '.join(quality.get('factoid_final_subtypes') or []) or 'none'}",
                f"  ai quality rejections: {quality.get('ai_quality_rejection_count', 0)}",
            ]
        )

    artifact_outcomes = report.get("artifact_outcomes")
    if isinstance(artifact_outcomes, dict):
        lines.extend(
            [
                "artifacts:",
                f"  quiz files changed: {'yes' if artifact_outcomes.get('quiz_files_changed') else 'no'} ({len(artifact_outcomes.get('generated_quiz_files') or [])})",
                f"  discovery changed: {'yes' if artifact_outcomes.get('discovery_files_changed') else 'no'} ({len(artifact_outcomes.get('generated_index_files') or [])})",
                f"  human id lookup updated: {'yes' if artifact_outcomes.get('human_id_lookup_updated') else 'no'}",
                f"  content repo commit: {'yes' if artifact_outcomes.get('content_repo_commit_occurred') else 'no'}",
            ]
        )

    return "\n".join(lines)


def build_daily_run_report(
    *,
    raw_report_path: Path | None,
    generated_at: dt.datetime,
    workflow: str,
    repository: str,
    run_id: str,
    run_attempt: str,
    run_url: str,
    job_status: str,
    trigger: str,
    target_date: str,
    quiz_types: list[str],
    mode: str,
    count: str,
    changed_paths: Iterable[str],
    content_repo: str,
    content_repo_ref: str,
    content_repo_commit_before: str | None,
) -> tuple[str, dict[str, Any]]:
    raw_payload = _load_raw_ai_report(raw_report_path)
    artifact_outcomes = classify_content_changes(changed_paths)
    artifact_outcomes.update(
        {
            "content_repo_commit_occurred": True,
            "content_repo_commit_before": content_repo_commit_before,
            "content_repo_commit_after": None,
        }
    )

    report = {
        "report_version": REPORT_VERSION,
        "generated_at": generated_at.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "workflow": workflow,
        "repository": repository,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "run_url": run_url,
        "job_status": job_status,
        "trigger": trigger,
        "content_repo": content_repo,
        "content_repo_ref": content_repo_ref,
        "request": {
            "target_date": target_date,
            "quiz_types": quiz_types,
            "mode": mode,
            "count": count,
        },
        "date_utc": raw_payload.get("date_utc", target_date),
        "ai_mode": raw_payload.get("ai_mode"),
        "provider": raw_payload.get("provider"),
        "model": raw_payload.get("model"),
        "calls_total": raw_payload.get("calls_total", 0),
        "input_tokens_total": raw_payload.get("input_tokens_total", 0),
        "output_tokens_total": raw_payload.get("output_tokens_total", 0),
        "run_estimated_cost_usd": raw_payload.get("run_estimated_cost_usd", 0.0),
        "day_spend_usd": raw_payload.get("day_spend_usd", 0.0),
        "month_spend_usd": raw_payload.get("month_spend_usd", 0.0),
        "day_limit_usd": raw_payload.get("day_limit_usd", 0.0),
        "month_limit_usd": raw_payload.get("month_limit_usd", 0.0),
        "fallback_count": raw_payload.get("fallback_count", 0),
        "fallback_reasons": list(raw_payload.get("fallback_reasons") or []),
        "quality": raw_payload.get("quality", dict(_EMPTY_QUALITY_PAYLOAD)),
        "artifact_outcomes": artifact_outcomes,
    }
    report["discord_message_text"] = render_daily_run_discord_message(report)
    return build_daily_run_report_path(generated_at=generated_at, run_id=run_id), report


def write_daily_run_report(*, content_repo_root: Path, report_path: str, report: dict[str, Any]) -> Path:
    absolute_path = content_repo_root / report_path
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return absolute_path
