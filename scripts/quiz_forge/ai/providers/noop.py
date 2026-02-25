"""No-op AI provider."""

from __future__ import annotations

from typing import Any

from ..types import AIRerankResponse, AISettings, AIUsage


class NoopProvider:
    def rerank_distractors(self, payload: dict[str, Any], settings: AISettings) -> AIRerankResponse:
        del payload, settings
        raise RuntimeError("Noop provider cannot perform rerank calls.")


def build_noop_response(*, provider: str, model: str) -> AIRerankResponse:
    return AIRerankResponse(
        ranked_distractor_ids=[],
        reason_codes=["noop"],
        provider=provider,
        model=model,
        usage=AIUsage(),
    )
