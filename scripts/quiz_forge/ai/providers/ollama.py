"""Ollama provider implementation for local development."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib import error, request

from ..types import AIJsonTaskResponse, AIRerankResponse, AISettings, AIUsage


class OllamaProvider:
    def _run_ollama_chat(
        self,
        *,
        system_prompt: str,
        payload: dict[str, Any],
        settings: AISettings,
        model: str,
        max_output_tokens: int,
    ) -> tuple[dict[str, Any], AIUsage]:
        endpoint = os.getenv("OLLAMA_ENDPOINT", "http://127.0.0.1:11434/api/chat").strip()
        body = {
            "model": model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
            ],
            "options": {
                "temperature": 0,
                "num_predict": max_output_tokens,
            },
        }

        req = request.Request(
            endpoint,
            method="POST",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with request.urlopen(req, timeout=settings.timeout_ms / 1000) as response:
                raw_response = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Ollama request failed with HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Ollama request failed: {exc}") from exc

        try:
            payload_json = json.loads(raw_response)
            content = payload_json.get("message", {}).get("content")
            if not isinstance(content, str) or not content.strip():
                raise ValueError("Ollama response did not include message content.")
            content_json = json.loads(content)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Could not parse Ollama response content: {exc}") from exc

        if not isinstance(content_json, dict):
            raise RuntimeError("Ollama response content must decode to a JSON object.")

        usage = AIUsage(
            input_tokens=int(payload_json.get("prompt_eval_count", 0) or 0),
            output_tokens=int(payload_json.get("eval_count", 0) or 0),
            estimated_cost_usd=0.0,
        )
        return content_json, usage

    def rerank_distractors(self, payload: dict[str, Any], settings: AISettings) -> AIRerankResponse:
        system_prompt = (
            "You are ranking distractors for a history multiple-choice quiz. "
            "Return JSON only with ranked_distractor_ids and optional reason_codes. "
            "Never invent new IDs."
        )
        ranked_json, usage = self._run_ollama_chat(
            system_prompt=system_prompt,
            payload=payload,
            settings=settings,
            model=settings.model,
            max_output_tokens=settings.max_output_tokens,
        )

        ranked_ids = ranked_json.get("ranked_distractor_ids")
        reason_codes = ranked_json.get("reason_codes", [])
        return AIRerankResponse(
            ranked_distractor_ids=list(ranked_ids) if isinstance(ranked_ids, list) else [],
            reason_codes=[str(item) for item in reason_codes] if isinstance(reason_codes, list) else [],
            provider="ollama",
            model=settings.model,
            usage=usage,
        )

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
        del response_schema
        payload_json, usage = self._run_ollama_chat(
            system_prompt=system_prompt,
            payload=user_payload,
            settings=settings,
            model=model,
            max_output_tokens=max_output_tokens,
        )
        return AIJsonTaskResponse(
            payload=payload_json,
            provider="ollama",
            model=model,
            usage=usage,
        )
