"""Type definitions for quiz-forge AI workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AISettings:
    mode: str
    provider: str
    model: str
    timeout_ms: int
    max_daily_usd: float
    max_monthly_usd: float
    max_calls_per_run: int
    max_input_tokens: int
    max_output_tokens: int
    input_price_per_million_usd: float
    output_price_per_million_usd: float
    ledger_path: str
    report_path: str | None


@dataclass
class AIUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0


@dataclass
class AIRerankResponse:
    ranked_distractor_ids: list[str]
    reason_codes: list[str]
    provider: str
    model: str
    usage: AIUsage


@dataclass
class AIJsonTaskResponse:
    payload: dict[str, Any]
    provider: str
    model: str
    usage: AIUsage


@dataclass
class AIAttempt:
    mode: str
    provider: str
    model: str
    applied: bool
    fallback_reason: str | None = None
    response: AIRerankResponse | None = None


@dataclass
class AIRunStats:
    ai_mode: str
    provider: str
    model: str
    calls_total: int = 0
    input_tokens_total: int = 0
    output_tokens_total: int = 0
    run_estimated_cost_usd: float = 0.0
    fallback_count: int = 0
    fallback_reasons: dict[str, int] = field(default_factory=dict)
    day_spend_usd: float = 0.0
    month_spend_usd: float = 0.0
    day_limit_usd: float = 0.0
    month_limit_usd: float = 0.0

    def add_fallback(self, reason: str) -> None:
        self.fallback_count += 1
        self.fallback_reasons[reason] = self.fallback_reasons.get(reason, 0) + 1

    def add_usage(self, usage: AIUsage) -> None:
        self.input_tokens_total += usage.input_tokens
        self.output_tokens_total += usage.output_tokens
        self.run_estimated_cost_usd += usage.estimated_cost_usd

    def to_report_payload(self, *, date_utc: str) -> dict[str, Any]:
        sorted_reasons = sorted(self.fallback_reasons.items(), key=lambda item: item[0])
        fallback_reason_strings = [f"{reason}:{count}" for reason, count in sorted_reasons]
        return {
            "date_utc": date_utc,
            "ai_mode": self.ai_mode,
            "provider": self.provider,
            "model": self.model,
            "calls_total": self.calls_total,
            "input_tokens_total": self.input_tokens_total,
            "output_tokens_total": self.output_tokens_total,
            "run_estimated_cost_usd": round(self.run_estimated_cost_usd, 8),
            "day_spend_usd": round(self.day_spend_usd, 8),
            "day_limit_usd": round(self.day_limit_usd, 8),
            "month_spend_usd": round(self.month_spend_usd, 8),
            "month_limit_usd": round(self.month_limit_usd, 8),
            "fallback_count": self.fallback_count,
            "fallback_reasons": fallback_reason_strings,
        }
