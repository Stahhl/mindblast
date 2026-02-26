"""OpenAI provider implementation."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib import error, request

from ..types import AIRerankResponse, AISettings, AIUsage
from .openai_contract import (
    OPENAI_CHAT_COMPLETIONS_ENDPOINT,
    build_chat_request_body,
    extract_ranked_ids,
)


class OpenAIProvider:
    endpoint = OPENAI_CHAT_COMPLETIONS_ENDPOINT

    def rerank_distractors(self, payload: dict[str, Any], settings: AISettings) -> AIRerankResponse:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required when AI_PROVIDER=openai.")

        system_prompt = (
            "You are ranking distractors for a history multiple-choice quiz. "
            "Return JSON only. Never invent new facts. "
            "Use only candidate IDs from distractor_candidates and return exactly 3 IDs."
        )
        user_payload = {
            "task": payload.get("task"),
            "quiz_type": payload.get("quiz_type"),
            "question_prompt": payload.get("question_prompt"),
            "correct_answer_fact_id": payload.get("correct_answer_fact_id"),
            "correct_answer": payload.get("correct_answer"),
            "distractor_candidates": payload.get("distractor_candidates"),
            "constraints": payload.get("constraints"),
        }

        body = build_chat_request_body(
            model=settings.model,
            max_output_tokens=settings.max_output_tokens,
            system_prompt=system_prompt,
            user_payload=user_payload,
        )

        request_body = json.dumps(body).encode("utf-8")
        req = request.Request(
            self.endpoint,
            method="POST",
            data=request_body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with request.urlopen(req, timeout=settings.timeout_ms / 1000) as response:
                raw_response = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI request failed with HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"OpenAI request failed: {exc}") from exc

        try:
            payload_json = json.loads(raw_response)
            content = (
                payload_json["choices"][0]["message"]["content"]
                if isinstance(payload_json.get("choices"), list) and payload_json["choices"]
                else None
            )
            if not isinstance(content, str) or not content.strip():
                raise ValueError("OpenAI response did not contain text content.")
            ranked_json = json.loads(content)
        except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Could not parse OpenAI rerank response: {exc}") from exc

        ranked_ids = extract_ranked_ids(ranked_json)
        reason_codes = ranked_json.get("reason_codes", [])
        usage = payload_json.get("usage", {})

        return AIRerankResponse(
            ranked_distractor_ids=ranked_ids,
            reason_codes=[str(item) for item in reason_codes] if isinstance(reason_codes, list) else [],
            provider="openai",
            model=settings.model,
            usage=AIUsage(
                input_tokens=int(usage.get("prompt_tokens", 0) or 0),
                output_tokens=int(usage.get("completion_tokens", 0) or 0),
                estimated_cost_usd=0.0,  # Estimated centrally by orchestrator pricing config.
            ),
        )
