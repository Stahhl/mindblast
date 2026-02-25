"""Provider interface for AI reranking."""

from __future__ import annotations

from typing import Any, Protocol

from ..types import AIRerankResponse, AISettings


class AIRerankProvider(Protocol):
    def rerank_distractors(self, payload: dict[str, Any], settings: AISettings) -> AIRerankResponse:
        """Return ranked distractor IDs and usage metadata."""
