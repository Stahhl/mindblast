"""Popularity enrichment for history candidates."""

from __future__ import annotations

import datetime as dt
from statistics import median
from typing import Any
from urllib.parse import quote, unquote, urlparse

from .source import fetch_json

WIKIMEDIA_PAGEVIEWS_API_TEMPLATE = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
    "en.wikipedia.org/all-access/all-agents/{title}/daily/{start}/{end}"
)
WIKIMEDIA_EDITS_API_TEMPLATE = (
    "https://wikimedia.org/api/rest_v1/metrics/edits/per-page/"
    "en.wikipedia.org/{title}/all-editor-types/daily/{start}/{end}"
)


def extract_wikipedia_page_title(page_url: str) -> str | None:
    parsed = urlparse(page_url.strip())
    if not parsed.scheme or not parsed.netloc:
        return None
    path = parsed.path.strip("/")
    if not path.startswith("wiki/"):
        return None
    title = unquote(path[len("wiki/") :]).strip()
    if not title:
        return None
    return title.replace(" ", "_")


def _encode_page_title(page_title: str) -> str:
    return quote(page_title.replace(" ", "_"), safe="()")


def _window_end_date(target_date: dt.date) -> dt.date:
    return target_date - dt.timedelta(days=1)


def build_pageviews_url(*, page_title: str, target_date: dt.date) -> str:
    end_date = _window_end_date(target_date)
    start_date = end_date - dt.timedelta(days=364)
    return WIKIMEDIA_PAGEVIEWS_API_TEMPLATE.format(
        title=_encode_page_title(page_title),
        start=start_date.strftime("%Y%m%d"),
        end=end_date.strftime("%Y%m%d"),
    )


def build_edits_url(*, page_title: str, target_date: dt.date) -> str:
    end_date = _window_end_date(target_date)
    start_date = end_date - dt.timedelta(days=364)
    return WIKIMEDIA_EDITS_API_TEMPLATE.format(
        title=_encode_page_title(page_title),
        start=start_date.strftime("%Y%m%d"),
        end=end_date.strftime("%Y%m%d"),
    )


def parse_pageviews_metrics(payload: dict[str, Any]) -> tuple[int, float]:
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("pageviews payload missing items")
    views = [int(item.get("views", 0) or 0) for item in items if isinstance(item, dict)]
    if not views:
        raise ValueError("pageviews payload had no usable views")
    trailing_90 = views[-90:] if len(views) >= 90 else views
    return sum(views), float(median(trailing_90))


def parse_edits_metrics(payload: dict[str, Any]) -> int:
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("edits payload missing items")
    edits = [int(item.get("edits", 0) or 0) for item in items if isinstance(item, dict)]
    if not edits:
        raise ValueError("edits payload had no usable edits")
    return sum(edits)


def _percentile_map(values_by_key: dict[str, float | None], *, neutral_keys: set[str]) -> dict[str, float]:
    valid_items = [(key, value) for key, value in values_by_key.items() if value is not None and key not in neutral_keys]
    if not valid_items:
        return {key: 0.5 for key in values_by_key}

    sorted_valid = sorted(valid_items, key=lambda item: (item[1], item[0]))
    denominator = max(1, len(sorted_valid) - 1)
    percentiles: dict[str, float] = {}
    index = 0
    while index < len(sorted_valid):
        value = sorted_valid[index][1]
        end_index = index
        while end_index + 1 < len(sorted_valid) and sorted_valid[end_index + 1][1] == value:
            end_index += 1
        percentile = ((index + end_index) / 2) / denominator if denominator else 1.0
        for tie_index in range(index, end_index + 1):
            percentiles[sorted_valid[tie_index][0]] = percentile
        index = end_index + 1
    for key in values_by_key:
        percentiles.setdefault(key, 0.5)
    return percentiles


def fetch_popularity_signals_for_title(
    *,
    page_title: str,
    target_date: dt.date,
    timeout: int,
    retries: int,
) -> dict[str, Any]:
    pageviews_payload = fetch_json(build_pageviews_url(page_title=page_title, target_date=target_date), timeout, retries)
    edits_payload = fetch_json(build_edits_url(page_title=page_title, target_date=target_date), timeout, retries)
    pageviews_total_365d, pageviews_median_90d = parse_pageviews_metrics(pageviews_payload)
    edits_total_365d = parse_edits_metrics(edits_payload)
    return {
        "page_title": page_title,
        "pageviews_total_365d": pageviews_total_365d,
        "pageviews_median_90d": pageviews_median_90d,
        "edits_total_365d": edits_total_365d,
        "pageviews_percentile": 0.5,
        "edits_percentile": 0.5,
        "popularity_score": 0.5,
        "popularity_status": "ok",
    }


def enrich_history_candidates_with_popularity(
    *,
    candidates: list[dict[str, Any]],
    target_date: dt.date,
    timeout: int,
    retries: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_title: dict[str, dict[str, Any]] = {}
    fallback_reasons: dict[str, int] = {}
    neutral_titles: set[str] = set()

    for candidate in candidates:
        page_url = candidate.get("wikipedia_url")
        page_title = extract_wikipedia_page_title(page_url) if isinstance(page_url, str) else None
        if page_title is None:
            neutral_titles.add(str(candidate.get("wikipedia_url", "")))
            fallback_reasons["page_title_unresolved"] = fallback_reasons.get("page_title_unresolved", 0) + 1
            continue
        if page_title in by_title:
            continue
        try:
            by_title[page_title] = fetch_popularity_signals_for_title(
                page_title=page_title,
                target_date=target_date,
                timeout=timeout,
                retries=retries,
            )
        except Exception as exc:  # noqa: BLE001
            reason = type(exc).__name__
            fallback_reasons[reason] = fallback_reasons.get(reason, 0) + 1
            by_title[page_title] = {
                "page_title": page_title,
                "pageviews_total_365d": 0,
                "pageviews_median_90d": 0.0,
                "edits_total_365d": 0,
                "pageviews_percentile": 0.5,
                "edits_percentile": 0.5,
                "popularity_score": 0.5,
                "popularity_status": f"fallback:{reason}",
            }
            neutral_titles.add(page_title)

    pageviews_values = {title: float(signals["pageviews_total_365d"]) for title, signals in by_title.items()}
    edits_values = {title: float(signals["edits_total_365d"]) for title, signals in by_title.items()}
    pageviews_percentiles = _percentile_map(pageviews_values, neutral_keys=neutral_titles)
    edits_percentiles = _percentile_map(edits_values, neutral_keys=neutral_titles)
    for title, signals in by_title.items():
        if title in neutral_titles:
            continue
        pageviews_percentile = pageviews_percentiles[title]
        edits_percentile = edits_percentiles[title]
        signals["pageviews_percentile"] = pageviews_percentile
        signals["edits_percentile"] = edits_percentile
        signals["popularity_score"] = (0.8 * pageviews_percentile) + (0.2 * edits_percentile)

    enriched: list[dict[str, Any]] = []
    ok_count = 0
    neutral_count = 0
    for candidate in candidates:
        page_url = candidate.get("wikipedia_url")
        page_title = extract_wikipedia_page_title(page_url) if isinstance(page_url, str) else None
        if page_title is None:
            popularity_signals = {
                "page_title": None,
                "pageviews_total_365d": 0,
                "pageviews_median_90d": 0.0,
                "edits_total_365d": 0,
                "pageviews_percentile": 0.5,
                "edits_percentile": 0.5,
                "popularity_score": 0.5,
                "popularity_status": "fallback:page_title_unresolved",
            }
            neutral_count += 1
        else:
            popularity_signals = dict(by_title[page_title])
            if popularity_signals["popularity_status"] == "ok":
                ok_count += 1
            else:
                neutral_count += 1
        enriched_candidate = dict(candidate)
        enriched_candidate["page_title"] = page_title
        enriched_candidate["popularity_signals"] = popularity_signals
        enriched.append(enriched_candidate)

    return enriched, {
        "enriched_count": ok_count,
        "neutral_count": neutral_count,
        "fallback_reasons": fallback_reasons,
    }
