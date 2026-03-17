"""Provider interface for AI calls."""

from __future__ import annotations

from typing import Any, Protocol

from ..types import AIJsonTaskResponse, AIRerankResponse, AISettings


class AIRerankProvider(Protocol):
    def rerank_distractors(self, payload: dict[str, Any], settings: AISettings) -> AIRerankResponse:
        """Return ranked distractor IDs and usage metadata."""

    def run_json_task(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        settings: AISettings,
        model: str,
        max_output_tokens: int,
        response_schema: dict[str, Any] | None = None,
    ) -> AIJsonTaskResponse:
        """Run a generic JSON task and return parsed payload + usage metadata."""
