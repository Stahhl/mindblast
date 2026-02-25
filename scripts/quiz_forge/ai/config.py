"""AI configuration loading helpers."""

from __future__ import annotations

import os
from pathlib import Path

from ..constants import (
    AI_LEDGER_RELATIVE_PATH,
    AI_MODE_OFF,
    AI_PROVIDER_NOOP,
    SUPPORTED_AI_MODES,
    SUPPORTED_AI_PROVIDERS,
)
from .types import AISettings


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc
    if value < 0:
        raise ValueError(f"{name} must be >= 0.")
    return value


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number.") from exc
    if value < 0:
        raise ValueError(f"{name} must be >= 0.")
    return value


def load_ai_settings(*, output_dir: str) -> AISettings:
    mode_raw = os.getenv("AI_MODE", AI_MODE_OFF).strip().lower()
    mode = mode_raw or AI_MODE_OFF
    if mode not in SUPPORTED_AI_MODES:
        supported = ", ".join(SUPPORTED_AI_MODES)
        raise ValueError(f"Unsupported AI_MODE '{mode}'. Supported: {supported}")

    provider_raw = os.getenv("AI_PROVIDER", AI_PROVIDER_NOOP).strip().lower()
    provider = provider_raw or AI_PROVIDER_NOOP
    if provider not in SUPPORTED_AI_PROVIDERS:
        supported = ", ".join(SUPPORTED_AI_PROVIDERS)
        raise ValueError(f"Unsupported AI_PROVIDER '{provider}'. Supported: {supported}")

    model = os.getenv("AI_MODEL", "gpt-5-mini").strip()
    if not model:
        raise ValueError("AI_MODEL must be non-empty.")

    ledger_path = Path(output_dir) / AI_LEDGER_RELATIVE_PATH

    return AISettings(
        mode=mode,
        provider=provider,
        model=model,
        timeout_ms=_env_int("AI_TIMEOUT_MS", 15000),
        max_daily_usd=_env_float("AI_MAX_DAILY_USD", 1.00),
        max_monthly_usd=_env_float("AI_MAX_MONTHLY_USD", 5.00),
        max_calls_per_run=_env_int("AI_MAX_CALLS_PER_RUN", 1),
        max_input_tokens=_env_int("AI_MAX_INPUT_TOKENS", 12000),
        max_output_tokens=_env_int("AI_MAX_OUTPUT_TOKENS", 500),
        input_price_per_million_usd=_env_float("AI_PRICE_INPUT_PER_M_USD", 0.25),
        output_price_per_million_usd=_env_float("AI_PRICE_OUTPUT_PER_M_USD", 2.00),
        ledger_path=ledger_path.as_posix(),
        report_path=os.getenv("QUIZ_FORGE_AI_REPORT_PATH"),
    )
