from __future__ import annotations

import argparse
import datetime as dt

import pytest

from quiz_forge.geography import load_geography_records
from quiz_forge.selection import build_seed
from quiz_forge.validation import validate_quiz


def test_build_geography_factoid_mcq_4_quiz_produces_valid_payload() -> None:
    from quiz_forge.builders import build_geography_factoid_mcq_4_quiz

    target_date = dt.date(2026, 3, 19)
    retrieval_time = dt.datetime(2026, 3, 19, 6, 0, tzinfo=dt.timezone.utc)
    records = load_geography_records()
    payload = build_geography_factoid_mcq_4_quiz(
        target_date=target_date,
        retrieval_time=retrieval_time,
        source_url="https://www.wikidata.org/wiki/Wikidata:Licensing",
        candidates=records,
        seed=build_seed(target_date, "geography_factoid_mcq_4", 1),
        edition=1,
        generation_mode="daily",
    )

    validate_quiz(payload, target_date)

    assert payload["type"] == "geography_factoid_mcq_4"
    assert payload["topics"] == ["geography"]
    assert payload["question"].startswith("Which country has the capital ")
    assert len(payload["choices"]) == 4
    assert len(payload["source"]["records_used"]) == 4
    assert payload["questions"][0]["facets"]["answer_kind"] == "country"
    assert payload["questions"][0]["facets"]["prompt_style"] == "capital_to_country"


def test_validate_geography_factoid_quiz_rejects_wrong_topics() -> None:
    from quiz_forge.builders import build_geography_factoid_mcq_4_quiz

    target_date = dt.date(2026, 3, 19)
    payload = build_geography_factoid_mcq_4_quiz(
        target_date=target_date,
        retrieval_time=dt.datetime(2026, 3, 19, 6, 0, tzinfo=dt.timezone.utc),
        source_url="https://www.wikidata.org/wiki/Wikidata:Licensing",
        candidates=load_geography_records(),
        seed=build_seed(target_date, "geography_factoid_mcq_4", 1),
        edition=1,
        generation_mode="daily",
    )
    payload["topics"] = ["history"]

    with pytest.raises(ValueError, match="topics must equal"):
        validate_quiz(payload, target_date)


def test_build_geography_factoid_mcq_4_quiz_fails_when_eligible_records_are_insufficient() -> None:
    from quiz_forge.builders import build_geography_factoid_mcq_4_quiz

    target_date = dt.date(2026, 3, 19)
    retrieval_time = dt.datetime(2026, 3, 19, 6, 0, tzinfo=dt.timezone.utc)
    insufficient_records = [
        {
            "country_label": "Canada",
            "capital_label": "Ottawa",
            "country_qid": "Q16",
            "capital_qid": "Q1930",
            "country_url": "https://www.wikidata.org/wiki/Q16",
            "capital_url": "https://www.wikidata.org/wiki/Q1930",
        },
        {
            "country_label": "Peru",
            "capital_label": "Lima",
            "country_qid": "Q419",
            "capital_qid": "Q2868",
            "country_url": "https://www.wikidata.org/wiki/Q419",
            "capital_url": "https://www.wikidata.org/wiki/Q2868",
        },
        {
            "country_label": "Japan",
            "capital_label": "Tokyo",
            "country_qid": "Q17",
            "capital_qid": "Q1490",
            "country_url": "https://www.wikidata.org/wiki/Q17",
            "capital_url": "https://www.wikidata.org/wiki/Q1490",
        },
        {
            "country_label": "Bolivia",
            "capital_label": "La Paz",
            "country_qid": "Q750",
            "capital_qid": "Q1491",
            "country_url": "https://www.wikidata.org/wiki/Q750",
            "capital_url": "https://www.wikidata.org/wiki/Q1491",
            "blocked_reason": "disputed_or_multiple_capitals",
        },
    ]

    with pytest.raises(ValueError, match="Not enough valid geography records"):
        build_geography_factoid_mcq_4_quiz(
            target_date=target_date,
            retrieval_time=retrieval_time,
            source_url="https://www.wikidata.org/wiki/Wikidata:Licensing",
            candidates=insufficient_records,
            seed=build_seed(target_date, "geography_factoid_mcq_4", 1),
            edition=1,
            generation_mode="daily",
        )


def test_cli_can_generate_geography_without_history_source_fetch(monkeypatch, tmp_path) -> None:
    from quiz_forge import cli

    args = argparse.Namespace(
        date="2026-03-19",
        quiz_types="geography_factoid_mcq_4",
        output_dir=(tmp_path / "quizzes").as_posix(),
        timeout=1,
        retries=1,
        mode="daily",
        count=1,
        daily_editions_by_type="which_came_first=1,history_mcq_4=1,history_factoid_mcq_4=3,geography_factoid_mcq_4=1",
        backfill_human_ids=False,
    )
    monkeypatch.setattr(cli, "parse_args", lambda: args)

    def _unexpected_fetch(*_args, **_kwargs):
        raise AssertionError("history source fetch should not be used")

    monkeypatch.setattr(cli, "fetch_json", _unexpected_fetch)

    exit_code = cli.main()

    assert exit_code == 0
    assert (tmp_path / "quizzes" / "latest.json").exists()
    assert len(list((tmp_path / "quizzes").glob("*.json"))) >= 1
