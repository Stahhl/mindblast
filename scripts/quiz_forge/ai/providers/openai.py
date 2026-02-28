"""OpenAI provider implementation."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib import error, request

from ..types import AIJsonTaskResponse, AIRerankResponse, AISettings, AIUsage
from .openai_contract import (
    OPENAI_CHAT_COMPLETIONS_ENDPOINT,
    build_chat_request_body,
    extract_ranked_ids,
)


class OpenAIProvider:
    endpoint = OPENAI_CHAT_COMPLETIONS_ENDPOINT

    def _require_api_key(self) -> str:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required when AI_PROVIDER=openai.")
        return api_key

    def _post_chat_completion(
        self,
        *,
        api_key: str,
        body: dict[str, Any],
        timeout_ms: int,
    ) -> dict[str, Any]:
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
            with request.urlopen(req, timeout=timeout_ms / 1000) as response:
                raw_response = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI request failed with HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"OpenAI request failed: {exc}") from exc

        try:
            payload_json = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Could not parse OpenAI response JSON: {exc}") from exc

        return payload_json

    def _extract_content_json(self, payload_json: dict[str, Any]) -> dict[str, Any]:
        try:
            content = (
                payload_json["choices"][0]["message"]["content"]
                if isinstance(payload_json.get("choices"), list) and payload_json["choices"]
                else None
            )
            if not isinstance(content, str) or not content.strip():
                raise ValueError("OpenAI response did not contain text content.")
            content_json = json.loads(content)
        except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Could not parse OpenAI response content: {exc}") from exc

        if not isinstance(content_json, dict):
            raise RuntimeError("OpenAI response content must decode to a JSON object.")
        return content_json

    @staticmethod
    def _extract_usage(payload_json: dict[str, Any]) -> AIUsage:
        usage = payload_json.get("usage", {})
        return AIUsage(
            input_tokens=int(usage.get("prompt_tokens", 0) or 0),
            output_tokens=int(usage.get("completion_tokens", 0) or 0),
            estimated_cost_usd=0.0,  # Estimated centrally by orchestrator pricing config.
        )

    def rerank_distractors(self, payload: dict[str, Any], settings: AISettings) -> AIRerankResponse:
        api_key = self._require_api_key()

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

        payload_json = self._post_chat_completion(
            api_key=api_key,
            body=body,
            timeout_ms=settings.timeout_ms,
        )
        ranked_json = self._extract_content_json(payload_json)

        ranked_ids = extract_ranked_ids(ranked_json)
        reason_codes = ranked_json.get("reason_codes", [])

        return AIRerankResponse(
            ranked_distractor_ids=ranked_ids,
            reason_codes=[str(item) for item in reason_codes] if isinstance(reason_codes, list) else [],
            provider="openai",
            model=settings.model,
            usage=self._extract_usage(payload_json),
        )

    def run_json_task(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        settings: AISettings,
        model: str,
        max_output_tokens: int,
    ) -> AIJsonTaskResponse:
        api_key = self._require_api_key()

        body = build_chat_request_body(
            model=model,
            max_output_tokens=max_output_tokens,
            system_prompt=system_prompt,
            user_payload=user_payload,
        )
        payload_json = self._post_chat_completion(
            api_key=api_key,
            body=body,
            timeout_ms=settings.timeout_ms,
        )
        content_json = self._extract_content_json(payload_json)

        return AIJsonTaskResponse(
            payload=content_json,
            provider="openai",
            model=model,
            usage=self._extract_usage(payload_json),
        )
