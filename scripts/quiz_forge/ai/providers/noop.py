"""No-op AI provider."""

from __future__ import annotations

from typing import Any

from ..types import AIJsonTaskResponse, AIRerankResponse, AISettings, AIUsage


class NoopProvider:
    def rerank_distractors(self, payload: dict[str, Any], settings: AISettings) -> AIRerankResponse:
        del payload, settings
        raise RuntimeError("Noop provider cannot perform rerank calls.")

    def run_json_task(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        settings: AISettings,
        model: str,
        max_output_tokens: int,
    ) -> AIJsonTaskResponse:
        del system_prompt, user_payload, settings, model, max_output_tokens
        raise RuntimeError("Noop provider cannot perform JSON task calls.")


def build_noop_response(*, provider: str, model: str) -> AIRerankResponse:
    return AIRerankResponse(
        ranked_distractor_ids=[],
        reason_codes=["noop"],
        provider=provider,
        model=model,
        usage=AIUsage(),
    )
