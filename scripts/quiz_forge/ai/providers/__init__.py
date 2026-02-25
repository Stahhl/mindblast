"""Provider factory helpers."""

from __future__ import annotations

from .noop import NoopProvider
from .ollama import OllamaProvider
from .openai import OpenAIProvider


def build_provider(name: str) -> object:
    if name == "openai":
        return OpenAIProvider()
    if name == "ollama":
        return OllamaProvider()
    if name == "noop":
        return NoopProvider()
    raise ValueError(f"Unsupported AI provider '{name}'.")
