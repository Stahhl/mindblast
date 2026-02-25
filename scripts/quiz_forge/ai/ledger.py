"""Persistent AI usage ledger for spend guardrails."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from ..storage import load_json_file, write_json_file
from .types import AIUsage


def _empty_ledger() -> dict[str, Any]:
    return {
        "metadata": {
            "version": 1,
            "updated_at": None,
        },
        "daily": {},
        "monthly": {},
    }


def _normalize_bucket(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {"spend_usd": 0.0, "calls": 0.0, "input_tokens": 0.0, "output_tokens": 0.0}
    return {
        "spend_usd": float(value.get("spend_usd", 0.0)),
        "calls": float(value.get("calls", 0.0)),
        "input_tokens": float(value.get("input_tokens", 0.0)),
        "output_tokens": float(value.get("output_tokens", 0.0)),
    }


def load_ledger(path: Path) -> dict[str, Any]:
    payload = load_json_file(path)
    if payload is None:
        return _empty_ledger()
    if not isinstance(payload.get("daily"), dict) or not isinstance(payload.get("monthly"), dict):
        return _empty_ledger()
    if not isinstance(payload.get("metadata"), dict):
        payload["metadata"] = {"version": 1, "updated_at": None}
    return payload


def get_spend_totals(ledger: dict[str, Any], target_date: dt.date) -> tuple[float, float]:
    day_key = target_date.isoformat()
    month_key = target_date.strftime("%Y-%m")
    daily_bucket = _normalize_bucket(ledger.get("daily", {}).get(day_key))
    monthly_bucket = _normalize_bucket(ledger.get("monthly", {}).get(month_key))
    return daily_bucket["spend_usd"], monthly_bucket["spend_usd"]


def record_usage(ledger: dict[str, Any], target_date: dt.date, usage: AIUsage) -> None:
    day_key = target_date.isoformat()
    month_key = target_date.strftime("%Y-%m")

    daily = ledger.setdefault("daily", {})
    monthly = ledger.setdefault("monthly", {})

    daily_bucket = _normalize_bucket(daily.get(day_key))
    monthly_bucket = _normalize_bucket(monthly.get(month_key))

    for bucket in (daily_bucket, monthly_bucket):
        bucket["calls"] += 1
        bucket["input_tokens"] += usage.input_tokens
        bucket["output_tokens"] += usage.output_tokens
        bucket["spend_usd"] += usage.estimated_cost_usd

    daily[day_key] = {
        "calls": int(daily_bucket["calls"]),
        "input_tokens": int(daily_bucket["input_tokens"]),
        "output_tokens": int(daily_bucket["output_tokens"]),
        "spend_usd": round(daily_bucket["spend_usd"], 8),
    }
    monthly[month_key] = {
        "calls": int(monthly_bucket["calls"]),
        "input_tokens": int(monthly_bucket["input_tokens"]),
        "output_tokens": int(monthly_bucket["output_tokens"]),
        "spend_usd": round(monthly_bucket["spend_usd"], 8),
    }

    metadata = ledger.setdefault("metadata", {})
    metadata["version"] = 1
    metadata["updated_at"] = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def save_ledger(path: Path, ledger: dict[str, Any]) -> None:
    write_json_file(path, ledger, prefix=".tmp-ai-ledger-")
