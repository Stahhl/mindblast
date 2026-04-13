from __future__ import annotations

import datetime as dt

from quiz_forge.popularity import (
    build_edits_url,
    build_pageviews_url,
    enrich_history_candidates_with_popularity,
    extract_wikipedia_page_title,
    parse_edits_metrics,
    parse_pageviews_metrics,
)
from quiz_forge.selection import order_history_candidates_for_selection


def _wiki_candidate(title: str, year: int) -> dict[str, object]:
    return {
        "text": f"{title} event",
        "year": year,
        "wikipedia_url": f"https://en.wikipedia.org/wiki/{title}",
    }


def test_extract_wikipedia_page_title_returns_article_title() -> None:
    assert extract_wikipedia_page_title("https://en.wikipedia.org/wiki/Paul_McCartney") == "Paul_McCartney"
    assert extract_wikipedia_page_title("https://en.wikipedia.org/wiki/Yesterday_(song)") == "Yesterday_(song)"
    assert extract_wikipedia_page_title("https://example.com/not-a-wiki-path") is None


def test_build_popularity_urls_use_long_window() -> None:
    target_date = dt.date(2026, 4, 13)

    pageviews_url = build_pageviews_url(page_title="Paul_McCartney", target_date=target_date)
    edits_url = build_edits_url(page_title="Paul_McCartney", target_date=target_date)

    assert pageviews_url.endswith("/Paul_McCartney/daily/20250413/20260412")
    assert edits_url.endswith("/Paul_McCartney/all-editor-types/daily/20250413/20260412")


def test_parse_popularity_metrics() -> None:
    pageviews_total, pageviews_median_90d = parse_pageviews_metrics(
        {
            "items": [
                {"views": 10},
                {"views": 30},
                {"views": 20},
            ]
        }
    )

    assert pageviews_total == 60
    assert pageviews_median_90d == 20.0
    assert parse_edits_metrics({"items": [{"edits": 1}, {"edits": 3}, {"edits": 5}]}) == 9


def test_enrich_history_candidates_with_popularity_assigns_percentiles_and_neutral_fallback(monkeypatch) -> None:
    candidates = [
        _wiki_candidate("Popular_Page", 1969),
        _wiki_candidate("Edited_Page", 1970),
        _wiki_candidate("Broken_Page", 1971),
        {
            "text": "No title event",
            "year": 1972,
            "wikipedia_url": "https://example.com/not-wikipedia",
        },
    ]

    def fake_fetch(*, page_title: str, **_kwargs) -> dict[str, object]:
        if page_title == "Popular_Page":
            return {
                "page_title": page_title,
                "pageviews_total_365d": 1000,
                "pageviews_median_90d": 10.0,
                "edits_total_365d": 20,
                "pageviews_percentile": 0.5,
                "edits_percentile": 0.5,
                "popularity_score": 0.5,
                "popularity_status": "ok",
            }
        if page_title == "Edited_Page":
            return {
                "page_title": page_title,
                "pageviews_total_365d": 1000,
                "pageviews_median_90d": 10.0,
                "edits_total_365d": 80,
                "pageviews_percentile": 0.5,
                "edits_percentile": 0.5,
                "popularity_score": 0.5,
                "popularity_status": "ok",
            }
        raise TimeoutError("boom")

    monkeypatch.setattr("quiz_forge.popularity.fetch_popularity_signals_for_title", fake_fetch)

    enriched, report = enrich_history_candidates_with_popularity(
        candidates=candidates,
        target_date=dt.date(2026, 4, 13),
        timeout=1,
        retries=1,
    )

    assert report == {
        "enriched_count": 2,
        "neutral_count": 2,
        "fallback_reasons": {
            "TimeoutError": 1,
            "page_title_unresolved": 1,
        },
    }
    by_title = {candidate.get("page_title"): candidate["popularity_signals"] for candidate in enriched}
    assert by_title["Edited_Page"]["pageviews_percentile"] == by_title["Popular_Page"]["pageviews_percentile"]
    assert by_title["Edited_Page"]["edits_percentile"] > by_title["Popular_Page"]["edits_percentile"]
    assert by_title["Edited_Page"]["popularity_score"] > by_title["Popular_Page"]["popularity_score"]
    assert by_title["Broken_Page"]["popularity_status"] == "fallback:TimeoutError"
    assert by_title[None]["popularity_status"] == "fallback:page_title_unresolved"


def test_order_history_candidates_for_selection_prefers_higher_popularity() -> None:
    seed = 12345
    candidates = [
        _wiki_candidate("Low_Page", 1900)
        | {"popularity_signals": {"popularity_score": 0.1, "popularity_status": "ok"}},
        _wiki_candidate("High_Page", 1901)
        | {"popularity_signals": {"popularity_score": 0.9, "popularity_status": "ok"}},
        _wiki_candidate("Medium_Page", 1902)
        | {"popularity_signals": {"popularity_score": 0.5, "popularity_status": "ok"}},
    ]

    ordered = order_history_candidates_for_selection(candidates, seed)

    assert [candidate["page_title"] if "page_title" in candidate else candidate["wikipedia_url"] for candidate in ordered] == [
        "https://en.wikipedia.org/wiki/High_Page",
        "https://en.wikipedia.org/wiki/Medium_Page",
        "https://en.wikipedia.org/wiki/Low_Page",
    ]


def test_order_history_candidates_for_selection_falls_back_when_all_popularity_is_neutral() -> None:
    ordered = order_history_candidates_for_selection(
        [
            _wiki_candidate("Zulu", 1950),
            _wiki_candidate("Alpha", 1900),
            _wiki_candidate("Bravo", 1900),
        ],
        seed=99,
    )

    assert [(candidate["year"], candidate["text"]) for candidate in ordered] == [
        (1900, "Alpha event"),
        (1900, "Bravo event"),
        (1950, "Zulu event"),
    ]


def test_less_popular_candidates_remain_selectable_under_seeded_randomness() -> None:
    candidates = [
        _wiki_candidate("Slightly_Popular", 1900)
        | {"popularity_signals": {"popularity_score": 0.55, "popularity_status": "ok"}},
        _wiki_candidate("Slightly_Less_Popular", 1901)
        | {"popularity_signals": {"popularity_score": 0.45, "popularity_status": "ok"}},
    ]

    first_titles = {
        order_history_candidates_for_selection(candidates, seed)[0]["wikipedia_url"]
        for seed in range(1, 200)
    }

    assert first_titles == {
        "https://en.wikipedia.org/wiki/Slightly_Popular",
        "https://en.wikipedia.org/wiki/Slightly_Less_Popular",
    }
