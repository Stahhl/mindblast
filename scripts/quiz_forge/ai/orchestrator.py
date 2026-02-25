"""AI orchestration for quiz-forge."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from ..constants import AI_MODE_OFF, AI_MODE_ON, AI_MODE_SHADOW, AI_PROVIDER_NOOP
from .ledger import get_spend_totals, load_ledger, record_usage, save_ledger
from .providers import build_provider
from .tasks.rerank_distractors import build_rerank_payload, estimate_input_tokens, validate_ranked_ids
from .types import AIAttempt, AIRunStats, AISettings, AIUsage


def _estimate_cost_usd(*, input_tokens: int, output_tokens: int, settings: AISettings) -> float:
    input_cost = (input_tokens / 1_000_000) * settings.input_price_per_million_usd
    output_cost = (output_tokens / 1_000_000) * settings.output_price_per_million_usd
    return input_cost + output_cost


class AIOrchestrator:
    def __init__(self, *, settings: AISettings, target_date: dt.date) -> None:
        self.settings = settings
        self.target_date = target_date
        self.provider = build_provider(settings.provider)
        self.ledger_path = Path(settings.ledger_path)
        self.ledger = load_ledger(self.ledger_path)
        self.ledger_dirty = False

        day_spend, month_spend = get_spend_totals(self.ledger, target_date)
        self.stats = AIRunStats(
            ai_mode=settings.mode,
            provider=settings.provider,
            model=settings.model,
            day_spend_usd=day_spend,
            month_spend_usd=month_spend,
            day_limit_usd=settings.max_daily_usd,
            month_limit_usd=settings.max_monthly_usd,
        )

    def is_enabled(self) -> bool:
        return self.settings.mode != AI_MODE_OFF and self.settings.provider != AI_PROVIDER_NOOP

    def _fallback(self, reason: str) -> AIAttempt:
        self.stats.add_fallback(reason)
        return AIAttempt(
            mode=self.settings.mode,
            provider=self.settings.provider,
            model=self.settings.model,
            applied=False,
            fallback_reason=reason,
        )

    def rerank_history_mcq(
        self,
        *,
        question_prompt: str,
        correct_event: dict[str, Any],
        distractor_candidates: list[dict[str, Any]],
    ) -> AIAttempt:
        if self.settings.mode == AI_MODE_OFF:
            return AIAttempt(
                mode=self.settings.mode,
                provider=self.settings.provider,
                model=self.settings.model,
                applied=False,
                fallback_reason=None,
            )

        if self.settings.provider == AI_PROVIDER_NOOP:
            return self._fallback("provider_noop")

        if self.stats.calls_total >= self.settings.max_calls_per_run:
            return self._fallback("run_call_limit_reached")

        if self.stats.day_spend_usd >= self.settings.max_daily_usd:
            return self._fallback("daily_budget_reached")
        if self.stats.month_spend_usd >= self.settings.max_monthly_usd:
            return self._fallback("monthly_budget_reached")

        payload = build_rerank_payload(
            question_prompt=question_prompt,
            correct_event=correct_event,
            distractor_candidates=distractor_candidates,
        )
        estimated_input_tokens = estimate_input_tokens(payload)
        if estimated_input_tokens > self.settings.max_input_tokens:
            return self._fallback("input_token_limit_precheck")

        self.stats.calls_total += 1
        try:
            response = self.provider.rerank_distractors(payload, self.settings)
        except Exception as exc:  # noqa: BLE001 - keep fallback behavior resilient
            return self._fallback(f"provider_error:{type(exc).__name__}")

        # Record usage even if response is later rejected.
        usage = AIUsage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            estimated_cost_usd=_estimate_cost_usd(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                settings=self.settings,
            ),
        )
        response.usage = usage

        self.stats.add_usage(usage)
        record_usage(self.ledger, self.target_date, usage)
        self.ledger_dirty = True
        self.stats.day_spend_usd, self.stats.month_spend_usd = get_spend_totals(self.ledger, self.target_date)

        if response.usage.input_tokens > self.settings.max_input_tokens:
            return self._fallback("input_token_limit_exceeded")
        if response.usage.output_tokens > self.settings.max_output_tokens:
            return self._fallback("output_token_limit_exceeded")
        if self.stats.day_spend_usd > self.settings.max_daily_usd:
            return self._fallback("daily_budget_exceeded_after_call")
        if self.stats.month_spend_usd > self.settings.max_monthly_usd:
            return self._fallback("monthly_budget_exceeded_after_call")

        is_valid, reason = validate_ranked_ids(
            ranked_ids=response.ranked_distractor_ids,
            distractor_candidates=distractor_candidates,
            correct_event=correct_event,
        )
        if not is_valid:
            return self._fallback(reason)

        if self.settings.mode == AI_MODE_SHADOW:
            return AIAttempt(
                mode=self.settings.mode,
                provider=self.settings.provider,
                model=self.settings.model,
                applied=False,
                fallback_reason="shadow_mode",
                response=response,
            )

        if self.settings.mode != AI_MODE_ON:
            return self._fallback("invalid_mode")

        return AIAttempt(
            mode=self.settings.mode,
            provider=self.settings.provider,
            model=self.settings.model,
            applied=True,
            fallback_reason=None,
            response=response,
        )

    def finalize(self) -> None:
        if not self.ledger_dirty:
            return
        save_ledger(self.ledger_path, self.ledger)

    def write_report(self) -> None:
        if not self.settings.report_path:
            return
        report_path = Path(self.settings.report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.stats.to_report_payload(date_utc=self.target_date.isoformat())
        report_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
