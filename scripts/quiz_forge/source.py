"""Source fetching and candidate extraction."""

from __future__ import annotations

import datetime as dt
import json
import time
from typing import Any
from urllib import error, request

from .constants import API_URL_TEMPLATE


def build_api_url(target_date: dt.date) -> str:
    return API_URL_TEMPLATE.format(month=target_date.month, day=target_date.day)


def fetch_json(url: str, timeout: int, retries: int) -> dict[str, Any]:
    headers = {"User-Agent": "quiz-forge/1.0 (mindblast project)"}
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            req = request.Request(url, headers=headers)
            with request.urlopen(req, timeout=timeout) as response:
                payload = response.read().decode("utf-8")
            return json.loads(payload)
        except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt == retries:
                break
            time.sleep(min(2**attempt, 8))

    raise RuntimeError(f"Failed to fetch source after {retries} attempts: {last_error}") from last_error


def first_wikipedia_url(event: dict[str, Any]) -> str | None:
    pages = event.get("pages")
    if not isinstance(pages, list):
        return None

    for page in pages:
        if not isinstance(page, dict):
            continue
        content_urls = page.get("content_urls")
        if not isinstance(content_urls, dict):
            continue
        desktop = content_urls.get("desktop")
        if not isinstance(desktop, dict):
            continue
        page_url = desktop.get("page")
        if isinstance(page_url, str) and page_url.strip():
            return page_url.strip()

    return None


def extract_candidates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    events = payload.get("events")
    if not isinstance(events, list):
        raise ValueError("Source payload missing 'events' list.")

    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()

    for raw_event in events:
        if not isinstance(raw_event, dict):
            continue

        raw_text = raw_event.get("text")
        raw_year = raw_event.get("year")

        if not isinstance(raw_text, str):
            continue
        text = raw_text.strip()
        if not text:
            continue

        if isinstance(raw_year, int):
            year = raw_year
        elif isinstance(raw_year, str) and raw_year.strip().lstrip("-").isdigit():
            year = int(raw_year.strip())
        else:
            continue

        page_url = first_wikipedia_url(raw_event)
        if not page_url:
            continue

        key = (text, year)
        if key in seen:
            continue
        seen.add(key)

        candidates.append({"text": text, "year": year, "wikipedia_url": page_url})

    return candidates
