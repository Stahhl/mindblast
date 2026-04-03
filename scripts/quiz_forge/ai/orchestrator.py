"""AI orchestration for quiz-forge."""

from __future__ import annotations

import datetime as dt
import json
import re
import os
from pathlib import Path
from typing import Any

from ..constants import AI_MODE_OFF, AI_MODE_ON, AI_MODE_SHADOW, AI_PROVIDER_NOOP
from .ledger import get_spend_totals, load_ledger, record_usage, save_ledger
from .providers import build_provider
from .tasks.rerank_distractors import build_rerank_payload, estimate_input_tokens, validate_ranked_ids
from .types import AIAttempt, AIProviderDiagnostics, AIProviderResponseError, AIRunStats, AISettings, AIUsage


def _estimate_cost_usd(*, input_tokens: int, output_tokens: int, settings: AISettings) -> float:
    input_cost = (input_tokens / 1_000_000) * settings.input_price_per_million_usd
    output_cost = (output_tokens / 1_000_000) * settings.output_price_per_million_usd
    return input_cost + output_cost


def _normalize_error_text(message: str) -> str:
    normalized = " ".join(message.split())
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if api_key:
        normalized = normalized.replace(api_key, "[REDACTED]")
    normalized = re.sub(r"Bearer\s+[A-Za-z0-9._-]+", "Bearer [REDACTED]", normalized, flags=re.IGNORECASE)
    return normalized


def _provider_error_label(exc: Exception) -> str:
    if isinstance(exc, AIProviderResponseError):
        return exc.failure_label

    message = _normalize_error_text(str(exc))
    lowered = message.lower()

    parse_label_match = re.search(r"parse failure \[([a-z0-9_]+)\]", lowered)
    if parse_label_match is not None:
        return parse_label_match.group(1)

    http_match = re.search(r"http\s+(\d{3})", message, flags=re.IGNORECASE)
    if http_match is not None:
        return f"http_{http_match.group(1)}"
    if "timed out" in lowered or "timeout" in lowered:
        return "timeout"
    if "connection refused" in lowered:
        return "connection_refused"
    if "name or service not known" in lowered or "temporary failure in name resolution" in lowered:
        return "dns_error"
    if "openai_api_key is required" in lowered:
        return "missing_api_key"
    if "could not parse openai rerank response" in lowered or "could not parse openai response content" in lowered:
        return "parse_error"

    compact = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    if not compact:
        return "unknown"
    return compact[:64]


def _provider_error_summary(exc: Exception) -> str | None:
    if isinstance(exc, AIProviderResponseError):
        return _normalize_error_text(exc.summary)
    message = _normalize_error_text(str(exc))
    parse_match = re.search(r"parse failure \[[a-z0-9_]+\]:\s*(.+)$", message, flags=re.IGNORECASE)
    if parse_match is not None:
        return parse_match.group(1).strip()
    return None


class AIOrchestrator:
    def __init__(self, *, settings: AISettings, target_date: dt.date) -> None:
        self.settings = settings
        self.target_date = target_date
        self.provider = build_provider(settings.provider)
        self.ledger_path = Path(settings.ledger_path)
        self.ledger = load_ledger(self.ledger_path)
        self.ledger_dirty = False
        self.last_json_task_failure_diagnostics: AIProviderDiagnostics | None = None

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

    def _json_fallback(self, reason: str) -> tuple[None, str]:
        self.stats.add_fallback(reason)
        return None, reason

    @staticmethod
    def _task_reason(task_name: str, reason: str) -> str:
        if not task_name:
            return reason
        return f"{task_name}:{reason}"

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
            reason = f"provider_error:{type(exc).__name__}:{_provider_error_label(exc)}"
            return self._fallback(reason)

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

    def run_json_task(
        self,
        *,
        task_name: str,
        system_prompt: str,
        user_payload: dict[str, Any],
        model: str | None = None,
        max_output_tokens: int | None = None,
        response_schema: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, str | None]:
        self.last_json_task_failure_diagnostics = None

        if self.settings.mode == AI_MODE_OFF:
            return self._json_fallback(self._task_reason(task_name, "ai_mode_off"))

        if self.settings.provider == AI_PROVIDER_NOOP:
            return self._json_fallback(self._task_reason(task_name, "provider_noop"))

        if self.stats.calls_total >= self.settings.max_calls_per_run:
            return self._json_fallback(self._task_reason(task_name, "run_call_limit_reached"))

        if self.stats.day_spend_usd >= self.settings.max_daily_usd:
            return self._json_fallback(self._task_reason(task_name, "daily_budget_reached"))
        if self.stats.month_spend_usd >= self.settings.max_monthly_usd:
            return self._json_fallback(self._task_reason(task_name, "monthly_budget_reached"))

        effective_model = (model or self.settings.model).strip() or self.settings.model
        requested_max_output = max_output_tokens if max_output_tokens is not None else self.settings.max_output_tokens
        if requested_max_output <= 0:
            return self._json_fallback(self._task_reason(task_name, "output_token_limit_precheck"))
        effective_max_output = min(requested_max_output, self.settings.max_output_tokens)

        estimated_input_tokens = estimate_input_tokens(
            {
                "system_prompt": system_prompt,
                "user_payload": user_payload,
            }
        )
        if estimated_input_tokens > self.settings.max_input_tokens:
            return self._json_fallback(self._task_reason(task_name, "input_token_limit_precheck"))

        retry_count = 0
        while True:
            self.stats.calls_total += 1
            try:
                response = self.provider.run_json_task(
                    system_prompt=system_prompt,
                    user_payload=user_payload,
                    settings=self.settings,
                    model=effective_model,
                    max_output_tokens=effective_max_output,
                    response_schema=response_schema,
                )
            except Exception as exc:  # noqa: BLE001 - keep fallback behavior resilient
                failure_label = _provider_error_label(exc)
                retryable = (
                    task_name == "weekly_feedback_review"
                    and failure_label == "empty_content"
                    and retry_count == 0
                    and self.stats.calls_total < self.settings.max_calls_per_run
                )
                if retryable:
                    retry_count += 1
                    continue

                error_summary = _provider_error_summary(exc)
                if error_summary:
                    provider = exc.provider if isinstance(exc, AIProviderResponseError) else self.settings.provider
                    model = exc.model if isinstance(exc, AIProviderResponseError) else effective_model
                    self.last_json_task_failure_diagnostics = AIProviderDiagnostics(
                        provider=provider,
                        model=model,
                        failure_label=failure_label,
                        last_error_summary=error_summary,
                        retry_attempted=retry_count > 0,
                        retry_count=retry_count,
                    )

                reason = self._task_reason(task_name, f"provider_error:{type(exc).__name__}:{failure_label}")
                return self._json_fallback(reason)
            break

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
            return self._json_fallback(self._task_reason(task_name, "input_token_limit_exceeded"))
        if response.usage.output_tokens > effective_max_output:
            return self._json_fallback(self._task_reason(task_name, "output_token_limit_exceeded"))
        if self.stats.day_spend_usd > self.settings.max_daily_usd:
            return self._json_fallback(self._task_reason(task_name, "daily_budget_exceeded_after_call"))
        if self.stats.month_spend_usd > self.settings.max_monthly_usd:
            return self._json_fallback(self._task_reason(task_name, "monthly_budget_exceeded_after_call"))

        if not isinstance(response.payload, dict):
            return self._json_fallback(self._task_reason(task_name, "provider_response_invalid"))

        return response.payload, None

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
