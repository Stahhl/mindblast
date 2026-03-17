"""Comment sanitization helpers for internal feedback review."""

from __future__ import annotations

import re


_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", flags=re.IGNORECASE)
_URL_RE = re.compile(r"\b(?:https?://|www\.)\S+\b", flags=re.IGNORECASE)
_LONG_NUMERIC_RE = re.compile(r"\b\d{6,}\b")
_WHITESPACE_RE = re.compile(r"\s+")

DEFAULT_EXCERPT_MAX_LENGTH = 280


def sanitize_comment_text(
    comment: str | None,
    *,
    max_length: int = DEFAULT_EXCERPT_MAX_LENGTH,
) -> str | None:
    if comment is None:
        return None
    if max_length < 1:
        raise ValueError("max_length must be >= 1.")

    normalized = _WHITESPACE_RE.sub(" ", comment).strip()
    if not normalized:
        return None

    normalized = _EMAIL_RE.sub("[redacted-email]", normalized)
    normalized = _URL_RE.sub("[redacted-url]", normalized)
    normalized = _LONG_NUMERIC_RE.sub("[redacted-number]", normalized)
    normalized = _WHITESPACE_RE.sub(" ", normalized).strip()
    if not normalized:
        return None

    if len(normalized) > max_length:
        normalized = f"{normalized[: max_length - 3].rstrip()}..."
    return normalized or None
