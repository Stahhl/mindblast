from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path

import pytest

from quiz_forge.ai.types import AIJsonTaskResponse, AIUsage
from quiz_forge.discovery import write_discovery_artifacts
from quiz_forge.quality import QualityRunStats, lint_quiz_payload
from quiz_forge.storage import (
    apply_human_ids_to_quiz,
    build_output_path,
    load_human_id_lookup,
    load_json_file,
    list_quiz_records_for_date_type,
    write_quiz_file,
)


def _minimal_quiz_payload(
    *,
    target_date: dt.date,
    quiz_type: str,
    edition: int,
    mode: str,
    generated_at: str,
) -> dict[str, object]:
    return {
        "date": target_date.isoformat(),
        "type": quiz_type,
        "generation": {
            "mode": mode,
            "edition": edition,
            "generated_at": generated_at,
        },
        "source": {
            "retrieved_at": generated_at,
        },
    }


def _sample_candidates() -> list[dict[str, object]]:
    return [
        {"text": "Event A", "year": 1901, "wikipedia_url": "https://example.com/a"},
        {"text": "Event B", "year": 1908, "wikipedia_url": "https://example.com/b"},
        {"text": "Event C", "year": 1915, "wikipedia_url": "https://example.com/c"},
        {"text": "Event D", "year": 1922, "wikipedia_url": "https://example.com/d"},
        {"text": "Event E", "year": 1929, "wikipedia_url": "https://example.com/e"},
        {"text": "Event F", "year": 1936, "wikipedia_url": "https://example.com/f"},
        {"text": "Event G", "year": 1943, "wikipedia_url": "https://example.com/g"},
        {"text": "Event H", "year": 1950, "wikipedia_url": "https://example.com/h"},
    ]


def _person_factoid_candidates() -> list[dict[str, object]]:
    return [
        {
            "text": "Neil Armstrong walks on the Moon during Apollo 11.",
            "year": 1969,
            "wikipedia_url": "https://example.com/neil-armstrong",
        },
        {
            "text": "Napoleon Bonaparte abdicates as Emperor of the French.",
            "year": 1814,
            "wikipedia_url": "https://example.com/napoleon",
        },
        {
            "text": "Martin Luther King Jr. delivers his I've Been to the Mountaintop speech.",
            "year": 1968,
            "wikipedia_url": "https://example.com/mlk",
        },
        {
            "text": "Amelia Earhart departs from Honolulu in her attempt to fly around the world.",
            "year": 1937,
            "wikipedia_url": "https://example.com/amelia",
        },
        {
            "text": "Julius Caesar is assassinated by Roman senators in the Theatre of Pompey.",
            "year": -44,
            "wikipedia_url": "https://example.com/caesar",
        },
    ]


def _place_factoid_candidates() -> list[dict[str, object]]:
    return [
        {
            "text": "In Kyoto, Emperor Komei grants an imperial audience to foreign diplomats for the first time.",
            "year": 1863,
            "wikipedia_url": "https://example.com/kyoto",
        },
        {
            "text": "At Waterloo, Napoleon Bonaparte is defeated by the Seventh Coalition.",
            "year": 1815,
            "wikipedia_url": "https://example.com/waterloo",
        },
        {
            "text": "In Karachi, Pakistan, a bomb blast kills at least 48 people in a predominantly Shia Muslim area.",
            "year": 2013,
            "wikipedia_url": "https://example.com/karachi",
        },
        {
            "text": "In Honolulu, Amelia Earhart departs in her attempt to fly around the world.",
            "year": 1937,
            "wikipedia_url": "https://example.com/honolulu",
        },
        {
            "text": "At the Winter Palace, demonstrators demand political reform from the Russian Empire.",
            "year": 1905,
            "wikipedia_url": "https://example.com/winter-palace",
        },
    ]


def _place_factoid_embedded_candidates() -> list[dict[str, object]]:
    return [
        {
            "text": "A bomb blast in Karachi, Pakistan, kills at least 48 people in a predominantly Shia Muslim area.",
            "year": 2013,
            "wikipedia_url": "https://example.com/karachi",
        },
        {
            "text": "An armistice is signed in Versailles after months of negotiation.",
            "year": 1919,
            "wikipedia_url": "https://example.com/versailles",
        },
        {
            "text": "Protesters gather at Tiananmen Square during a state visit by Mikhail Gorbachev.",
            "year": 1989,
            "wikipedia_url": "https://example.com/tiananmen-square",
        },
        {
            "text": "A military convoy departs from Baghdad for the northern front.",
            "year": 2003,
            "wikipedia_url": "https://example.com/baghdad",
        },
        {
            "text": "Athletes parade in Barcelona during the opening ceremony of the Summer Olympics.",
            "year": 1992,
            "wikipedia_url": "https://example.com/barcelona",
        },
    ]


def _page_summary_payload_for_url(page_url: str) -> dict[str, str]:
    payloads = {
        "https://example.com/neil-armstrong": {
            "title": "Neil Armstrong",
            "extract": "Neil Armstrong walks on the Moon during Apollo 11.",
        },
        "https://example.com/napoleon": {
            "title": "Napoleon Bonaparte",
            "extract": "Napoleon Bonaparte abdicates as Emperor of the French.",
        },
        "https://example.com/mlk": {
            "title": "Martin Luther King Jr.",
            "extract": "Martin Luther King Jr. delivers his I've Been to the Mountaintop speech.",
        },
        "https://example.com/amelia": {
            "title": "Amelia Earhart",
            "extract": "Amelia Earhart departs from Honolulu in her attempt to fly around the world.",
        },
        "https://example.com/caesar": {
            "title": "Julius Caesar",
            "extract": "Julius Caesar is assassinated by Roman senators in the Theatre of Pompey.",
        },
        "https://example.com/a": {
            "title": "The Beatles",
            "extract": "The Beatles were an English rock band formed in Liverpool in 1960.",
        },
        "https://example.com/b": {
            "title": "Wings",
            "extract": "Wings were a rock band formed by Paul McCartney, Linda McCartney, and Denny Laine.",
        },
        "https://example.com/c": {
            "title": "The Quarrymen",
            "extract": "The Quarrymen were the skiffle group joined by Paul McCartney in 1957.",
        },
        "https://example.com/d": {
            "title": "The Who",
            "extract": "The Who are an English rock band formed in London in 1964.",
        },
    }
    return payloads[page_url]


def _mixed_factoid_candidates() -> list[dict[str, object]]:
    return [*_person_factoid_candidates(), *_place_factoid_candidates()]


def _minimal_existing_factoid_payload(
    *,
    target_date: dt.date,
    generated_at: str,
    answer_kind: str,
    prompt_style: str,
) -> dict[str, object]:
    return {
        "date": target_date.isoformat(),
        "type": "history_factoid_mcq_4",
        "question": "Placeholder?",
        "questions": [
            {
                "id": f"q-{target_date.isoformat()}",
                "type": "history_factoid_mcq_4",
                "prompt": "Placeholder?",
                "answer_fact_ids": [],
                "correct_answer_fact_id": "fact-a",
                "tags": ["history", "history_factoid_mcq_4"],
                "facets": {
                    "topic": "history",
                    "difficulty_band": "baseline",
                    "question_format": "factoid",
                    "answer_kind": answer_kind,
                    "prompt_style": prompt_style,
                },
                "selection_rules": {},
            }
        ],
        "generation": {
            "mode": "daily",
            "edition": 1,
            "generated_at": generated_at,
        },
        "source": {
            "retrieved_at": generated_at,
        },
    }


def _legacy_which_came_first_payload(*, target_date: dt.date) -> dict[str, object]:
    return {
        "date": target_date.isoformat(),
        "topics": ["history"],
        "type": "which_came_first",
        "question": "Which event happened earlier?",
        "choices": [
            {
                "id": "A",
                "label": "Event A happened.",
                "year": 1901,
            },
            {
                "id": "B",
                "label": "Event B happened.",
                "year": 1888,
            },
        ],
        "correct_choice_id": "B",
        "source": {
            "name": "Wikipedia On This Day",
            "url": "https://example.com/source",
            "retrieved_at": "2026-02-26T06:00:00Z",
            "events_used": [
                {
                    "text": "Event A happened.",
                    "year": 1901,
                    "wikipedia_url": "https://example.com/a",
                },
                {
                    "text": "Event B happened.",
                    "year": 1888,
                    "wikipedia_url": "https://example.com/b",
                },
            ],
        },
        "metadata": {
            "version": 1,
        },
    }


def test_build_output_path_includes_edition() -> None:
    target_date = dt.date(2026, 2, 26)
    first = build_output_path("quizzes", target_date, "history_mcq_4", 1)
    second = build_output_path("quizzes", target_date, "history_mcq_4", 2)
    assert first != second


def test_write_discovery_artifacts_supports_multiple_editions(tmp_path) -> None:
    quizzes_dir = tmp_path / "quizzes"
    target_date = dt.date(2026, 2, 26)

    history_daily = build_output_path(quizzes_dir.as_posix(), target_date, "history_mcq_4", 1)
    history_extra = build_output_path(quizzes_dir.as_posix(), target_date, "history_mcq_4", 2)
    first_daily = build_output_path(quizzes_dir.as_posix(), target_date, "which_came_first", 1)

    write_quiz_file(
        history_daily,
        _minimal_quiz_payload(
            target_date=target_date,
            quiz_type="history_mcq_4",
            edition=1,
            mode="daily",
            generated_at="2026-02-26T06:00:00Z",
        ),
    )
    write_quiz_file(
        history_extra,
        _minimal_quiz_payload(
            target_date=target_date,
            quiz_type="history_mcq_4",
            edition=2,
            mode="extra",
            generated_at="2026-02-26T06:20:00Z",
        ),
    )
    write_quiz_file(
        first_daily,
        _minimal_quiz_payload(
            target_date=target_date,
            quiz_type="which_came_first",
            edition=1,
            mode="daily",
            generated_at="2026-02-26T06:00:00Z",
        ),
    )

    before_cwd = Path.cwd()
    try:
        # discovery uses cwd to derive repository-relative paths
        os.chdir(tmp_path)
        changed = write_discovery_artifacts(
            output_dir=quizzes_dir.as_posix(),
            target_date=target_date,
            generated_now=True,
        )
    finally:
        os.chdir(before_cwd)

    assert len(changed) == 2

    index_payload = json.loads((quizzes_dir / "index" / "2026-02-26.json").read_text(encoding="utf-8"))
    latest_payload = json.loads((quizzes_dir / "latest.json").read_text(encoding="utf-8"))

    assert index_payload["metadata"]["version"] == 2
    assert len(index_payload["quizzes_by_type"]["history_mcq_4"]) == 2
    assert index_payload["quiz_files"]["history_mcq_4"] == index_payload["quizzes_by_type"]["history_mcq_4"][0]["quiz_file"]
    assert latest_payload["metadata"]["version"] == 2
    assert latest_payload["latest_quiz_by_type"]["history_mcq_4"] == index_payload["quizzes_by_type"]["history_mcq_4"][-1][
        "quiz_file"
    ]


def test_write_discovery_artifacts_normalizes_public_paths_for_external_content_repo(tmp_path) -> None:
    repo_root = tmp_path / "mindblast"
    quizzes_dir = repo_root / ".content-repo" / "quizzes"
    quizzes_dir.mkdir(parents=True)
    target_date = dt.date(2026, 3, 18)

    history_daily = build_output_path(quizzes_dir.as_posix(), target_date, "history_mcq_4", 1)
    first_daily = build_output_path(quizzes_dir.as_posix(), target_date, "which_came_first", 1)

    write_quiz_file(
        history_daily,
        _minimal_quiz_payload(
            target_date=target_date,
            quiz_type="history_mcq_4",
            edition=1,
            mode="daily",
            generated_at="2026-03-18T06:18:00Z",
        ),
    )
    write_quiz_file(
        first_daily,
        _minimal_quiz_payload(
            target_date=target_date,
            quiz_type="which_came_first",
            edition=1,
            mode="daily",
            generated_at="2026-03-18T06:18:00Z",
        ),
    )

    before_cwd = Path.cwd()
    try:
        os.chdir(repo_root)
        changed = write_discovery_artifacts(
            output_dir=quizzes_dir.as_posix(),
            target_date=target_date,
            generated_now=True,
        )
    finally:
        os.chdir(before_cwd)

    assert changed
    latest_payload = json.loads((quizzes_dir / "latest.json").read_text(encoding="utf-8"))
    index_payload = json.loads((quizzes_dir / "index" / "2026-03-18.json").read_text(encoding="utf-8"))

    assert latest_payload["index_file"] == "quizzes/index/2026-03-18.json"
    assert all(path.startswith("quizzes/") for path in latest_payload["latest_quiz_by_type"].values())
    assert all(entry["quiz_file"].startswith("quizzes/") for entries in index_payload["quizzes_by_type"].values() for entry in entries)
    assert ".content-repo/" not in json.dumps(latest_payload)
    assert ".content-repo/" not in json.dumps(index_payload)


def test_apply_human_ids_uses_public_quiz_paths_for_external_content_repo() -> None:
    from quiz_forge.builders import build_history_mcq_4_quiz

    repo_root = Path("/tmp/mindblast-test-root")
    quiz_path = repo_root / ".content-repo" / "quizzes" / "1234.json"
    payload = build_history_mcq_4_quiz(
        dt.date(2026, 3, 18),
        dt.datetime(2026, 3, 18, 6, 0, tzinfo=dt.timezone.utc),
        "https://example.com/source",
        _sample_candidates(),
        seed=1,
        edition=1,
        generation_mode="daily",
    )
    lookup = load_human_id_lookup((repo_root / ".content-repo" / "quizzes").as_posix())

    changed = apply_human_ids_to_quiz(quiz=payload, quiz_path=quiz_path, lookup=lookup)

    assert changed is True
    question = payload["questions"][0]
    assert lookup["questions"][question["human_id"]]["quiz_file"] == "quizzes/1234.json"


def test_cli_extra_mode_generates_multiple_same_day_editions(monkeypatch, tmp_path) -> None:
    from quiz_forge import cli

    target_date = "2026-02-26"
    output_dir = (tmp_path / "quizzes").as_posix()

    monkeypatch.setattr(cli, "fetch_json", lambda *_args, **_kwargs: {"events": []})
    monkeypatch.setattr(cli, "extract_candidates", lambda _payload: _sample_candidates())
    monkeypatch.setenv("AI_MODE", "off")
    monkeypatch.setenv("QUIZ_FORGE_AI_REPORT_PATH", (tmp_path / "ai-report.json").as_posix())

    daily_args = argparse.Namespace(
        date=target_date,
        quiz_types="history_mcq_4",
        output_dir=output_dir,
        timeout=1,
        retries=1,
        mode="daily",
        count=1,
        daily_editions_by_type="which_came_first=1,history_mcq_4=1,history_factoid_mcq_4=3,geography_factoid_mcq_4=1",
    )
    monkeypatch.setattr(cli, "parse_args", lambda: daily_args)
    assert cli.main() == 0

    extra_args = argparse.Namespace(
        date=target_date,
        quiz_types="history_mcq_4",
        output_dir=output_dir,
        timeout=1,
        retries=1,
        mode="extra",
        count=2,
        daily_editions_by_type="which_came_first=1,history_mcq_4=1,history_factoid_mcq_4=3,geography_factoid_mcq_4=1",
    )
    monkeypatch.setattr(cli, "parse_args", lambda: extra_args)
    assert cli.main() == 0

    records = list_quiz_records_for_date_type(
        output_dir=output_dir,
        target_date=dt.date.fromisoformat(target_date),
        quiz_type="history_mcq_4",
    )
    assert [record.edition for record in records] == [1, 2, 3]
    question_human_ids = [record.payload["questions"][0]["human_id"] for record in records]
    assert question_human_ids == ["Q1", "Q2", "Q3"]
    for record in records:
        assert all(choice.get("human_id") for choice in record.payload["choices"])
        assert all(answer_fact.get("human_id") for answer_fact in record.payload["answer_facts"])

    lookup_payload = load_json_file(Path(output_dir) / "human_id_lookup.json")
    assert lookup_payload is not None
    assert lookup_payload["metadata"]["version"] == 1
    assert lookup_payload["question_uuid_to_human_id"]
    assert lookup_payload["answer_uuid_to_human_id"]
    assert lookup_payload["questions"]["Q1"]["quiz_type"] == "history_mcq_4"


def test_extra_mode_requires_daily_edition_first(tmp_path) -> None:
    from quiz_forge.cli import _build_generation_plan

    with pytest.raises(ValueError):
        _build_generation_plan(
            output_dir=(tmp_path / "quizzes").as_posix(),
            target_date=dt.date(2026, 2, 26),
            quiz_types=["history_mcq_4"],
            mode="extra",
            count=1,
            daily_editions_by_type={"history_mcq_4": 1},
        )


def test_daily_mode_build_generation_plan_uses_per_type_daily_targets(tmp_path) -> None:
    from quiz_forge.cli import _build_generation_plan

    pending = _build_generation_plan(
        output_dir=(tmp_path / "quizzes").as_posix(),
        target_date=dt.date(2026, 2, 26),
        quiz_types=["which_came_first", "history_factoid_mcq_4"],
        mode="daily",
        count=1,
        daily_editions_by_type={"which_came_first": 1, "history_factoid_mcq_4": 3},
    )

    assert [(quiz_type, edition) for quiz_type, edition, _path in pending] == [
        ("which_came_first", 1),
        ("history_factoid_mcq_4", 1),
        ("history_factoid_mcq_4", 2),
        ("history_factoid_mcq_4", 3),
    ]


def test_extra_mode_requires_full_daily_range_before_extra(tmp_path) -> None:
    from quiz_forge.cli import _build_generation_plan

    quizzes_dir = tmp_path / "quizzes"
    target_date = dt.date(2026, 2, 26)
    write_quiz_file(
        build_output_path(quizzes_dir.as_posix(), target_date, "history_factoid_mcq_4", 1),
        _minimal_existing_factoid_payload(
            target_date=target_date,
            generated_at="2026-02-26T06:00:00Z",
            answer_kind="time",
            prompt_style="when",
        ),
    )

    with pytest.raises(ValueError):
        _build_generation_plan(
            output_dir=quizzes_dir.as_posix(),
            target_date=target_date,
            quiz_types=["history_factoid_mcq_4"],
            mode="extra",
            count=1,
            daily_editions_by_type={"history_factoid_mcq_4": 3},
        )


def test_extra_mode_starts_after_configured_factoid_daily_range(tmp_path) -> None:
    from quiz_forge.cli import _build_generation_plan

    quizzes_dir = tmp_path / "quizzes"
    target_date = dt.date(2026, 2, 26)
    for edition in (1, 2, 3):
        write_quiz_file(
            build_output_path(quizzes_dir.as_posix(), target_date, "history_factoid_mcq_4", edition),
            _minimal_existing_factoid_payload(
                target_date=target_date,
                generated_at=f"2026-02-26T06:0{edition}:00Z",
                answer_kind="time",
                prompt_style="when",
            )
            | {
                "generation": {
                    "mode": "daily",
                    "edition": edition,
                    "generated_at": f"2026-02-26T06:0{edition}:00Z",
                }
            },
        )

    pending = _build_generation_plan(
        output_dir=quizzes_dir.as_posix(),
        target_date=target_date,
        quiz_types=["history_factoid_mcq_4"],
        mode="extra",
        count=2,
        daily_editions_by_type={"history_factoid_mcq_4": 3},
    )

    assert [(quiz_type, edition) for quiz_type, edition, _path in pending] == [
        ("history_factoid_mcq_4", 4),
        ("history_factoid_mcq_4", 5),
    ]


def test_cli_generates_history_factoid_mcq(monkeypatch, tmp_path) -> None:
    from quiz_forge import cli

    target_date = "2026-02-26"
    output_dir = (tmp_path / "quizzes").as_posix()

    monkeypatch.setattr(cli, "fetch_json", lambda *_args, **_kwargs: {"events": []})
    monkeypatch.setattr(cli, "extract_candidates", lambda _payload: _sample_candidates())
    monkeypatch.setenv("AI_MODE", "off")
    monkeypatch.setenv("QUIZ_FORGE_AI_REPORT_PATH", (tmp_path / "ai-report.json").as_posix())

    args = argparse.Namespace(
        date=target_date,
        quiz_types="history_factoid_mcq_4",
        output_dir=output_dir,
        timeout=1,
        retries=1,
        mode="daily",
        count=1,
        daily_editions_by_type="which_came_first=1,history_mcq_4=1,history_factoid_mcq_4=1",
    )
    monkeypatch.setattr(cli, "parse_args", lambda: args)
    assert cli.main() == 0

    records = list_quiz_records_for_date_type(
        output_dir=output_dir,
        target_date=dt.date.fromisoformat(target_date),
        quiz_type="history_factoid_mcq_4",
    )
    assert [record.edition for record in records] == [1]
    payload = records[0].payload
    assert payload["type"] == "history_factoid_mcq_4"
    assert isinstance(payload.get("question"), str) and payload["question"].endswith("?")
    assert len(payload["choices"]) == 4
    assert all("year" not in choice for choice in payload["choices"])
    facets = payload["questions"][0]["facets"]
    assert facets["question_format"] == "factoid"
    assert facets["answer_kind"] == "time"
    assert facets["prompt_style"] == "when"
    assert payload["questions"][0]["human_id"].startswith("Q")
    assert all(choice["human_id"].startswith("A") for choice in payload["choices"])


def test_cli_daily_mode_generates_three_history_factoid_daily_editions(monkeypatch, tmp_path) -> None:
    from quiz_forge import cli

    target_date = "2026-02-26"
    output_dir = (tmp_path / "quizzes").as_posix()

    monkeypatch.setattr(cli, "fetch_json", lambda *_args, **_kwargs: {"events": []})
    monkeypatch.setattr(cli, "extract_candidates", lambda _payload: _sample_candidates())
    monkeypatch.setenv("AI_MODE", "off")
    monkeypatch.setenv("QUIZ_FORGE_AI_REPORT_PATH", (tmp_path / "ai-report.json").as_posix())

    args = argparse.Namespace(
        date=target_date,
        quiz_types="history_factoid_mcq_4",
        output_dir=output_dir,
        timeout=1,
        retries=1,
        mode="daily",
        count=1,
        daily_editions_by_type="which_came_first=1,history_mcq_4=1,history_factoid_mcq_4=3,geography_factoid_mcq_4=1",
    )
    monkeypatch.setattr(cli, "parse_args", lambda: args)
    assert cli.main() == 0

    records = list_quiz_records_for_date_type(
        output_dir=output_dir,
        target_date=dt.date.fromisoformat(target_date),
        quiz_type="history_factoid_mcq_4",
    )

    assert [record.edition for record in records] == [1, 2, 3]
    assert all(record.payload["generation"]["mode"] == "daily" for record in records)


def test_cli_generates_history_factoid_person_mcq_when_person_candidates_exist(monkeypatch, tmp_path) -> None:
    from quiz_forge import cli

    target_date = "2026-02-26"
    output_dir = (tmp_path / "quizzes").as_posix()

    monkeypatch.setattr(cli, "fetch_json", lambda *_args, **_kwargs: {"events": []})
    monkeypatch.setattr(cli, "extract_candidates", lambda _payload: _person_factoid_candidates())
    monkeypatch.setenv("AI_MODE", "off")
    monkeypatch.setenv("QUIZ_FORGE_AI_REPORT_PATH", (tmp_path / "ai-report.json").as_posix())

    args = argparse.Namespace(
        date=target_date,
        quiz_types="history_factoid_mcq_4",
        output_dir=output_dir,
        timeout=1,
        retries=1,
        mode="daily",
        count=1,
        daily_editions_by_type="which_came_first=1,history_mcq_4=1,history_factoid_mcq_4=1",
    )
    monkeypatch.setattr(cli, "parse_args", lambda: args)
    assert cli.main() == 0

    records = list_quiz_records_for_date_type(
        output_dir=output_dir,
        target_date=dt.date.fromisoformat(target_date),
        quiz_type="history_factoid_mcq_4",
    )
    assert [record.edition for record in records] == [1]
    payload = records[0].payload
    assert payload["type"] == "history_factoid_mcq_4"
    assert payload["question"].startswith("Who ")
    assert len(payload["choices"]) == 4
    assert all(any(character.isalpha() for character in choice["label"]) for choice in payload["choices"])
    facets = payload["questions"][0]["facets"]
    assert facets["question_format"] == "factoid"
    assert facets["answer_kind"] == "person"
    assert facets["prompt_style"] == "who"
    assert all(fact["facets"]["entity_type"] == "person" for fact in payload["answer_facts"])
    assert {event["text"] for event in payload["source"]["events_used"]} <= {
        candidate["text"] for candidate in _person_factoid_candidates()
    }


def test_cli_generates_history_factoid_place_mcq_when_place_candidates_exist(monkeypatch, tmp_path) -> None:
    from quiz_forge import cli

    target_date = "2026-02-26"
    output_dir = (tmp_path / "quizzes").as_posix()

    monkeypatch.setattr(cli, "fetch_json", lambda *_args, **_kwargs: {"events": []})
    monkeypatch.setattr(cli, "extract_candidates", lambda _payload: _place_factoid_candidates())
    monkeypatch.setenv("AI_MODE", "off")
    monkeypatch.setenv("QUIZ_FORGE_AI_REPORT_PATH", (tmp_path / "ai-report.json").as_posix())

    args = argparse.Namespace(
        date=target_date,
        quiz_types="history_factoid_mcq_4",
        output_dir=output_dir,
        timeout=1,
        retries=1,
        mode="daily",
        count=1,
        daily_editions_by_type="which_came_first=1,history_mcq_4=1,history_factoid_mcq_4=1",
    )
    monkeypatch.setattr(cli, "parse_args", lambda: args)
    assert cli.main() == 0

    records = list_quiz_records_for_date_type(
        output_dir=output_dir,
        target_date=dt.date.fromisoformat(target_date),
        quiz_type="history_factoid_mcq_4",
    )
    assert [record.edition for record in records] == [1]
    payload = records[0].payload
    assert payload["type"] == "history_factoid_mcq_4"
    assert payload["question"].startswith("Where did this happen: ")
    assert len(payload["choices"]) == 4
    assert all(any(character.isalpha() for character in choice["label"]) for choice in payload["choices"])
    facets = payload["questions"][0]["facets"]
    assert facets["question_format"] == "factoid"
    assert facets["answer_kind"] == "place"
    assert facets["prompt_style"] == "where"
    assert all(fact["facets"]["entity_type"] == "place" for fact in payload["answer_facts"])
    assert {event["text"] for event in payload["source"]["events_used"]} <= {
        candidate["text"] for candidate in _place_factoid_candidates()
    }


def test_cli_generates_history_factoid_place_mcq_for_embedded_place_patterns(monkeypatch, tmp_path) -> None:
    from quiz_forge import cli

    target_date = "2026-02-26"
    output_dir = (tmp_path / "quizzes").as_posix()

    monkeypatch.setattr(cli, "fetch_json", lambda *_args, **_kwargs: {"events": []})
    monkeypatch.setattr(cli, "extract_candidates", lambda _payload: _place_factoid_embedded_candidates())
    monkeypatch.setenv("AI_MODE", "off")
    monkeypatch.setenv("QUIZ_FORGE_AI_REPORT_PATH", (tmp_path / "ai-report.json").as_posix())

    args = argparse.Namespace(
        date=target_date,
        quiz_types="history_factoid_mcq_4",
        output_dir=output_dir,
        timeout=1,
        retries=1,
        mode="daily",
        count=1,
        daily_editions_by_type="which_came_first=1,history_mcq_4=1,history_factoid_mcq_4=1",
    )
    monkeypatch.setattr(cli, "parse_args", lambda: args)
    assert cli.main() == 0

    records = list_quiz_records_for_date_type(
        output_dir=output_dir,
        target_date=dt.date.fromisoformat(target_date),
        quiz_type="history_factoid_mcq_4",
    )
    payload = records[0].payload
    assert payload["question"].startswith("Where did this happen: ")
    assert payload["questions"][0]["facets"]["answer_kind"] == "place"
    assert any(choice["label"] == "Karachi, Pakistan" for choice in payload["choices"])


def test_cli_prefers_less_recent_factoid_kind_when_both_person_and_place_are_available(monkeypatch, tmp_path) -> None:
    from quiz_forge import cli

    output_dir = (tmp_path / "quizzes").as_posix()
    quizzes_dir = Path(output_dir)
    earlier_date = dt.date(2026, 2, 24)
    later_date = dt.date(2026, 2, 25)

    write_quiz_file(
        build_output_path(output_dir, earlier_date, "history_factoid_mcq_4", 1),
        _minimal_existing_factoid_payload(
            target_date=earlier_date,
            generated_at="2026-02-24T06:00:00Z",
            answer_kind="person",
            prompt_style="who",
        ),
    )
    write_quiz_file(
        build_output_path(output_dir, later_date, "history_factoid_mcq_4", 1),
        _minimal_existing_factoid_payload(
            target_date=later_date,
            generated_at="2026-02-25T06:00:00Z",
            answer_kind="person",
            prompt_style="who",
        ),
    )

    target_date = "2026-02-26"
    monkeypatch.setattr(cli, "fetch_json", lambda *_args, **_kwargs: {"events": []})
    monkeypatch.setattr(cli, "extract_candidates", lambda _payload: _mixed_factoid_candidates())
    monkeypatch.setenv("AI_MODE", "off")
    monkeypatch.setenv("QUIZ_FORGE_AI_REPORT_PATH", (tmp_path / "ai-report.json").as_posix())

    args = argparse.Namespace(
        date=target_date,
        quiz_types="history_factoid_mcq_4",
        output_dir=output_dir,
        timeout=1,
        retries=1,
        mode="daily",
        count=1,
        daily_editions_by_type="which_came_first=1,history_mcq_4=1,history_factoid_mcq_4=1",
    )
    monkeypatch.setattr(cli, "parse_args", lambda: args)
    assert cli.main() == 0

    records = list_quiz_records_for_date_type(
        output_dir=output_dir,
        target_date=dt.date.fromisoformat(target_date),
        quiz_type="history_factoid_mcq_4",
    )
    payload = records[0].payload
    assert payload["questions"][0]["facets"]["answer_kind"] == "place"
    assert payload["questions"][0]["facets"]["prompt_style"] == "where"
    assert quizzes_dir.exists()


def test_cli_reuses_existing_human_ids_on_rerun(monkeypatch, tmp_path) -> None:
    from quiz_forge import cli

    target_date = "2026-02-26"
    output_dir = (tmp_path / "quizzes").as_posix()

    monkeypatch.setattr(cli, "fetch_json", lambda *_args, **_kwargs: {"events": []})
    monkeypatch.setattr(cli, "extract_candidates", lambda _payload: _sample_candidates())
    monkeypatch.setenv("AI_MODE", "off")
    monkeypatch.setenv("QUIZ_FORGE_AI_REPORT_PATH", (tmp_path / "ai-report.json").as_posix())

    args = argparse.Namespace(
        date=target_date,
        quiz_types="history_mcq_4",
        output_dir=output_dir,
        timeout=1,
        retries=1,
        mode="daily",
        count=1,
        daily_editions_by_type="which_came_first=1,history_mcq_4=1,history_factoid_mcq_4=1",
    )
    monkeypatch.setattr(cli, "parse_args", lambda: args)
    assert cli.main() == 0

    records = list_quiz_records_for_date_type(
        output_dir=output_dir,
        target_date=dt.date.fromisoformat(target_date),
        quiz_type="history_mcq_4",
    )
    assert len(records) == 1
    first_question_id = records[0].payload["questions"][0]["id"]
    first_question_human_id = records[0].payload["questions"][0]["human_id"]

    lookup_path = Path(output_dir) / "human_id_lookup.json"
    first_lookup = load_json_file(lookup_path)
    assert first_lookup is not None
    first_updated_at = first_lookup["metadata"]["updated_at"]

    # No new quiz should be generated; lookup should not be rewritten.
    assert cli.main() == 0

    second_lookup = load_json_file(lookup_path)
    assert second_lookup is not None
    assert second_lookup["metadata"]["updated_at"] == first_updated_at
    assert second_lookup["question_uuid_to_human_id"][first_question_id] == first_question_human_id


def test_cli_backfills_human_ids_for_existing_quizzes(monkeypatch, tmp_path) -> None:
    from quiz_forge import cli

    target_date = "2026-02-26"
    output_dir = (tmp_path / "quizzes").as_posix()

    monkeypatch.setattr(cli, "fetch_json", lambda *_args, **_kwargs: {"events": []})
    monkeypatch.setattr(cli, "extract_candidates", lambda _payload: _sample_candidates())
    monkeypatch.setenv("AI_MODE", "off")
    monkeypatch.setenv("QUIZ_FORGE_AI_REPORT_PATH", (tmp_path / "ai-report.json").as_posix())

    daily_args = argparse.Namespace(
        date=target_date,
        quiz_types="history_mcq_4",
        output_dir=output_dir,
        timeout=1,
        retries=1,
        mode="daily",
        count=1,
        daily_editions_by_type="which_came_first=1,history_mcq_4=1,history_factoid_mcq_4=1",
        backfill_human_ids=False,
    )
    monkeypatch.setattr(cli, "parse_args", lambda: daily_args)
    assert cli.main() == 0

    records = list_quiz_records_for_date_type(
        output_dir=output_dir,
        target_date=dt.date.fromisoformat(target_date),
        quiz_type="history_mcq_4",
    )
    assert len(records) == 1
    quiz_path = records[0].path
    payload = load_json_file(quiz_path)
    assert payload is not None

    # Simulate legacy files without human ids.
    payload["questions"][0].pop("human_id", None)
    for choice in payload["choices"]:
        choice.pop("human_id", None)
    for answer_fact in payload["answer_facts"]:
        answer_fact.pop("human_id", None)
    write_quiz_file(quiz_path, payload)

    lookup_path = Path(output_dir) / "human_id_lookup.json"
    lookup_path.unlink(missing_ok=True)

    backfill_args = argparse.Namespace(
        output_dir=output_dir,
        backfill_human_ids=True,
    )
    monkeypatch.setattr(cli, "parse_args", lambda: backfill_args)
    assert cli.main() == 0

    backfilled_payload = load_json_file(quiz_path)
    assert backfilled_payload is not None
    assert backfilled_payload["questions"][0]["human_id"].startswith("Q")
    assert all(choice["human_id"].startswith("A") for choice in backfilled_payload["choices"])
    assert all(answer_fact["human_id"].startswith("A") for answer_fact in backfilled_payload["answer_facts"])
    assert lookup_path.exists()


def test_cli_backfills_and_normalizes_legacy_v1_quiz(monkeypatch, tmp_path) -> None:
    from quiz_forge import cli

    target_date = dt.date(2026, 2, 26)
    output_dir = (tmp_path / "quizzes").as_posix()
    quiz_path = build_output_path(output_dir, target_date, "which_came_first", 1)
    write_quiz_file(
        quiz_path,
        _legacy_which_came_first_payload(target_date=target_date),
    )

    backfill_args = argparse.Namespace(
        output_dir=output_dir,
        backfill_human_ids=True,
    )
    monkeypatch.setattr(cli, "parse_args", lambda: backfill_args)
    assert cli.main() == 0

    payload = load_json_file(quiz_path)
    assert payload is not None
    assert payload["metadata"]["version"] == 2
    assert payload["metadata"]["normalized_model"] == "question_answer_facts_v1"
    assert payload["generation"]["edition"] == 1
    assert payload["generation"]["mode"] == "daily"
    assert payload["questions"][0]["human_id"].startswith("Q")
    assert all(choice["human_id"].startswith("A") for choice in payload["choices"])
    assert all(answer_fact["human_id"].startswith("A") for answer_fact in payload["answer_facts"])
    assert all("event_id" in event for event in payload["source"]["events_used"])


def test_cli_applies_factoid_ai_pipeline_when_enabled(monkeypatch, tmp_path, mocker) -> None:
    from quiz_forge import cli

    target_date = "2026-02-26"
    output_dir = (tmp_path / "quizzes").as_posix()

    monkeypatch.setattr(cli, "fetch_json", lambda *_args, **_kwargs: {"events": []})
    monkeypatch.setattr(cli, "extract_candidates", lambda _payload: _sample_candidates())
    monkeypatch.setattr(
        "quiz_forge.factoid_pipeline.fetch_wikipedia_page_summary",
        lambda page_url, **_kwargs: _page_summary_payload_for_url(page_url),
    )
    monkeypatch.setenv("AI_MODE", "on")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_MODEL", "gpt-5-mini")
    monkeypatch.setenv("AI_MAX_CALLS_PER_RUN", "8")
    monkeypatch.setenv("FACTOID_AI_PIPELINE_ENABLED", "true")
    monkeypatch.setenv("QUIZ_FORGE_AI_REPORT_PATH", (tmp_path / "ai-report.json").as_posix())

    def fake_run_json_task(*args, **kwargs) -> AIJsonTaskResponse:  # noqa: ANN002,ANN003
        del args
        user_payload = kwargs["user_payload"]
        task = user_payload.get("task")
        if task == "factoid_page_candidate_generate":
            prompts = {
                "The Beatles": "Which band made Paul McCartney famous worldwide?",
                "Wings": "Which band did Paul McCartney form after the Beatles together with Linda McCartney and Denny Laine?",
                "The Quarrymen": "Which skiffle group did Paul McCartney join in 1957 before it evolved into the Beatles?",
                "The Who": "Which English rock band released the rock opera Tommy?",
            }
            payload = {
                "candidates": [
                    {
                        "page_context_id": page_context["page_context_id"],
                        "question": prompts[page_context["page_title"]],
                        "correct_answer": page_context["page_title"],
                        "answer_kind": "organization",
                        "answer_subtype": "band",
                        "prompt_style": "which",
                        "evidence_text": page_context["page_extract"],
                        "score": 0.95,
                    }
                    for page_context in user_payload["page_contexts"]
                ]
            }
        elif task == "factoid_distractor_select":
            payload = {
                "selected_distractor_ids": [
                    candidate["candidate_id"] for candidate in user_payload["distractor_candidates"][:3]
                ]
            }
        elif task == "factoid_final_judge":
            payload = {"final_score": 0.99, "publishable": True}
        else:
            raise AssertionError(f"Unexpected task: {task}")

        return AIJsonTaskResponse(
            payload=payload,
            provider="openai",
            model="gpt-5-mini",
            usage=AIUsage(input_tokens=20, output_tokens=10, estimated_cost_usd=0.0),
        )

    run_json_mock = mocker.patch(
        "quiz_forge.ai.providers.openai.OpenAIProvider.run_json_task",
        side_effect=fake_run_json_task,
    )

    args = argparse.Namespace(
        date=target_date,
        quiz_types="history_factoid_mcq_4",
        output_dir=output_dir,
        timeout=1,
        retries=1,
        mode="daily",
        count=1,
        daily_editions_by_type="which_came_first=1,history_mcq_4=1,history_factoid_mcq_4=1",
    )
    monkeypatch.setattr(cli, "parse_args", lambda: args)
    assert cli.main() == 0
    assert run_json_mock.call_count == 3

    records = list_quiz_records_for_date_type(
        output_dir=output_dir,
        target_date=dt.date.fromisoformat(target_date),
        quiz_type="history_factoid_mcq_4",
    )
    payload = records[0].payload
    assert payload["question"].startswith("Which ")
    assert payload["metadata"]["generation_method"] == "ai_native_factoid_v1"
    assert payload["questions"][0]["facets"]["answer_kind"] == "organization"
    assert payload["questions"][0]["facets"]["answer_subtype"] == "band"
    assert len(payload["source"]["page_sources"]) == 4


def test_cli_applies_ai_factoid_candidate_for_person_question(monkeypatch, tmp_path, mocker) -> None:
    from quiz_forge import cli

    target_date = "2026-02-26"
    output_dir = (tmp_path / "quizzes").as_posix()

    monkeypatch.setattr(cli, "fetch_json", lambda *_args, **_kwargs: {"events": []})
    monkeypatch.setattr(cli, "extract_candidates", lambda _payload: _person_factoid_candidates())
    monkeypatch.setattr(
        "quiz_forge.factoid_pipeline.fetch_wikipedia_page_summary",
        lambda page_url, **_kwargs: _page_summary_payload_for_url(page_url),
    )
    monkeypatch.setenv("AI_MODE", "on")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_MODEL", "gpt-5-mini")
    monkeypatch.setenv("AI_MAX_CALLS_PER_RUN", "8")
    monkeypatch.setenv("FACTOID_AI_PIPELINE_ENABLED", "true")
    monkeypatch.setenv("QUIZ_FORGE_AI_REPORT_PATH", (tmp_path / "ai-report.json").as_posix())

    def fake_run_json_task(*args, **kwargs) -> AIJsonTaskResponse:  # noqa: ANN002,ANN003
        del args
        user_payload = kwargs["user_payload"]
        task = user_payload.get("task")
        if task == "factoid_page_candidate_generate":
            prompts = {
                "Neil Armstrong": "Who walked on the Moon during Apollo 11?",
                "Napoleon Bonaparte": "Who abdicated as Emperor of the French?",
                "Martin Luther King Jr.": "Who delivered the I've Been to the Mountaintop speech?",
                "Amelia Earhart": "Who departed from Honolulu in an attempt to fly around the world?",
                "Julius Caesar": "Who was assassinated by Roman senators in the Theatre of Pompey?",
            }
            payload = {
                "candidates": [
                    {
                        "page_context_id": page_context["page_context_id"],
                        "question": prompts[page_context["page_title"]],
                        "correct_answer": page_context["page_title"],
                        "answer_kind": "person",
                        "answer_subtype": "historical_figure",
                        "prompt_style": "who",
                        "evidence_text": page_context["page_extract"],
                        "score": 0.95,
                    }
                    for page_context in user_payload["page_contexts"]
                ]
            }
            model = "gpt-5.2"
        elif task == "factoid_distractor_select":
            payload = {
                "selected_distractor_ids": [
                    candidate["candidate_id"] for candidate in user_payload["distractor_candidates"][:3]
                ]
            }
            model = "gpt-5.2"
        elif task == "factoid_final_judge":
            payload = {"final_score": 0.99, "publishable": True}
            model = "gpt-5.2"
        else:
            raise AssertionError(f"Unexpected task: {task}")
        return AIJsonTaskResponse(
            payload=payload,
            provider="openai",
            model=model,
            usage=AIUsage(input_tokens=20, output_tokens=10, estimated_cost_usd=0.0),
        )

    run_json_mock = mocker.patch(
        "quiz_forge.ai.providers.openai.OpenAIProvider.run_json_task",
        side_effect=fake_run_json_task,
    )

    args = argparse.Namespace(
        date=target_date,
        quiz_types="history_factoid_mcq_4",
        output_dir=output_dir,
        timeout=1,
        retries=1,
        mode="daily",
        count=1,
        daily_editions_by_type="which_came_first=1,history_mcq_4=1,history_factoid_mcq_4=1",
    )
    monkeypatch.setattr(cli, "parse_args", lambda: args)
    assert cli.main() == 0
    assert run_json_mock.call_count == 3

    records = list_quiz_records_for_date_type(
        output_dir=output_dir,
        target_date=dt.date.fromisoformat(target_date),
        quiz_type="history_factoid_mcq_4",
    )
    payload = records[0].payload
    assert payload["questions"][0]["facets"]["answer_kind"] == "person"
    assert payload["questions"][0]["facets"]["answer_subtype"] == "historical_figure"
    assert payload["questions"][0]["facets"]["prompt_style"] == "who"
    assert lint_quiz_payload(payload) == ()
    assert len(payload["choices"]) == 4
    expected_labels = {
        "Neil Armstrong",
        "Napoleon Bonaparte",
        "Martin Luther King Jr.",
        "Amelia Earhart",
        "Julius Caesar",
    }
    assert {choice["label"] for choice in payload["choices"]}.issubset(expected_labels)


def test_cli_falls_back_when_ai_typed_distractor_selection_is_invalid(monkeypatch, tmp_path, mocker) -> None:
    from quiz_forge import cli

    target_date = "2026-02-26"
    output_dir = (tmp_path / "quizzes").as_posix()
    report_path = tmp_path / "ai-report.json"

    monkeypatch.setattr(cli, "fetch_json", lambda *_args, **_kwargs: {"events": []})
    monkeypatch.setattr(cli, "extract_candidates", lambda _payload: _person_factoid_candidates())
    monkeypatch.setattr(
        "quiz_forge.factoid_pipeline.fetch_wikipedia_page_summary",
        lambda page_url, **_kwargs: _page_summary_payload_for_url(page_url),
    )
    monkeypatch.setenv("AI_MODE", "on")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_MODEL", "gpt-5-mini")
    monkeypatch.setenv("AI_MAX_CALLS_PER_RUN", "8")
    monkeypatch.setenv("FACTOID_AI_PIPELINE_ENABLED", "true")
    monkeypatch.setenv("QUIZ_FORGE_AI_REPORT_PATH", report_path.as_posix())

    def fake_run_json_task(*args, **kwargs) -> AIJsonTaskResponse:  # noqa: ANN002,ANN003
        del args
        user_payload = kwargs["user_payload"]
        task = user_payload.get("task")
        if task == "factoid_page_candidate_generate":
            payload = {
                "candidates": [
                    {
                        "page_context_id": page_context["page_context_id"],
                        "question": "Who is featured in this historical event?",
                        "correct_answer": page_context["page_title"],
                        "answer_kind": "person",
                        "answer_subtype": "historical_figure",
                        "prompt_style": "who",
                        "evidence_text": page_context["page_extract"],
                        "score": 0.95,
                    }
                    for page_context in user_payload["page_contexts"]
                ]
            }
        elif task == "factoid_distractor_select":
            payload = {"selected_distractor_ids": ["not-a-real-candidate-id", "still-invalid", "also-invalid"]}
        else:
            raise AssertionError(f"Unexpected task: {task}")
        return AIJsonTaskResponse(
            payload=payload,
            provider="openai",
            model="gpt-5.2",
            usage=AIUsage(input_tokens=20, output_tokens=10, estimated_cost_usd=0.0),
        )

    mocker.patch(
        "quiz_forge.ai.providers.openai.OpenAIProvider.run_json_task",
        side_effect=fake_run_json_task,
    )

    args = argparse.Namespace(
        date=target_date,
        quiz_types="history_factoid_mcq_4",
        output_dir=output_dir,
        timeout=1,
        retries=1,
        mode="daily",
        count=1,
        daily_editions_by_type="which_came_first=1,history_mcq_4=1,history_factoid_mcq_4=1",
    )
    monkeypatch.setattr(cli, "parse_args", lambda: args)
    assert cli.main() == 0

    payload = list_quiz_records_for_date_type(
        output_dir=output_dir,
        target_date=dt.date.fromisoformat(target_date),
        quiz_type="history_factoid_mcq_4",
    )[0].payload
    assert lint_quiz_payload(payload) == ()

    report_payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert "history_factoid_mcq_4:ai_native_fallback:1" in report_payload["quality"]["fallback_paths"]
    assert "factoid_distractor_select_invalid_ids:1" in report_payload["quality"]["ai_stage_failures"]


def test_cli_counts_ai_typed_candidate_review_rejections(monkeypatch, tmp_path, mocker) -> None:
    from quiz_forge import cli

    target_date = "2026-02-26"
    output_dir = (tmp_path / "quizzes").as_posix()
    report_path = tmp_path / "ai-report.json"

    monkeypatch.setattr(cli, "fetch_json", lambda *_args, **_kwargs: {"events": []})
    monkeypatch.setattr(cli, "extract_candidates", lambda _payload: _person_factoid_candidates())
    monkeypatch.setattr(
        "quiz_forge.factoid_pipeline.fetch_wikipedia_page_summary",
        lambda page_url, **_kwargs: _page_summary_payload_for_url(page_url),
    )
    monkeypatch.setenv("AI_MODE", "on")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_MODEL", "gpt-5-mini")
    monkeypatch.setenv("AI_MAX_CALLS_PER_RUN", "8")
    monkeypatch.setenv("FACTOID_AI_PIPELINE_ENABLED", "true")
    monkeypatch.setenv("QUIZ_FORGE_AI_REPORT_PATH", report_path.as_posix())

    def fake_run_json_task(*args, **kwargs) -> AIJsonTaskResponse:  # noqa: ANN002,ANN003
        del args
        user_payload = kwargs["user_payload"]
        task = user_payload.get("task")
        if task != "factoid_page_candidate_generate":
            raise AssertionError(f"Unexpected task: {task}")
        return AIJsonTaskResponse(
            payload={
                "candidates": [
                    {
                        "page_context_id": page_context["page_context_id"],
                        "question": f"Who is featured on {page_context['page_title']}?",
                        "correct_answer": "Someone Else",
                        "answer_kind": "person",
                        "answer_subtype": "historical_figure",
                        "prompt_style": "who",
                        "evidence_text": "Ungrounded evidence text",
                        "score": 0.95,
                    }
                    for page_context in user_payload["page_contexts"]
                ]
            },
            provider="openai",
            model="gpt-5.2",
            usage=AIUsage(input_tokens=20, output_tokens=10, estimated_cost_usd=0.0),
        )

    mocker.patch(
        "quiz_forge.ai.providers.openai.OpenAIProvider.run_json_task",
        side_effect=fake_run_json_task,
    )

    args = argparse.Namespace(
        date=target_date,
        quiz_types="history_factoid_mcq_4",
        output_dir=output_dir,
        timeout=1,
        retries=1,
        mode="daily",
        count=1,
        daily_editions_by_type="which_came_first=1,history_mcq_4=1,history_factoid_mcq_4=1",
    )
    monkeypatch.setattr(cli, "parse_args", lambda: args)
    assert cli.main() == 0

    payload = list_quiz_records_for_date_type(
        output_dir=output_dir,
        target_date=dt.date.fromisoformat(target_date),
        quiz_type="history_factoid_mcq_4",
    )[0].payload
    assert lint_quiz_payload(payload) == ()

    report_payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert "candidate_ungrounded:1" in report_payload["quality"]["ai_stage_failures"]


def test_ai_factoid_distractors_exclude_same_source_event_value_copies() -> None:
    from quiz_forge.selection import build_history_factoid_distractors_for_candidate

    original_event = {
        "text": "In Karachi, Pakistan, a bomb blast kills at least 48 people in a predominantly Shia Muslim area.",
        "year": 2013,
        "wikipedia_url": "https://example.com/karachi",
    }
    duplicate_value_event = dict(original_event)
    candidates = [
        original_event,
        duplicate_value_event,
        {
            "text": "In Kyoto, Emperor Komei grants an imperial audience to foreign diplomats for the first time.",
            "year": 1863,
            "wikipedia_url": "https://example.com/kyoto",
        },
        {
            "text": "At Waterloo, Napoleon Bonaparte is defeated by the Seventh Coalition.",
            "year": 1815,
            "wikipedia_url": "https://example.com/waterloo",
        },
        {
            "text": "In Honolulu, Amelia Earhart departs in her attempt to fly around the world.",
            "year": 1937,
            "wikipedia_url": "https://example.com/honolulu",
        },
        {
            "text": "At the Winter Palace, demonstrators demand political reform from the Russian Empire.",
            "year": 1905,
            "wikipedia_url": "https://example.com/winter-palace",
        },
    ]
    correct_candidate = {
        "answer_kind": "place",
        "prompt_style": "where",
        "answer_label": "Karachi",
        "question_text": "Where did this happen: a bomb blast kills at least 48 people in a predominantly Shia Muslim area?",
        "source_event": original_event,
    }

    distractors = build_history_factoid_distractors_for_candidate(
        candidates,
        seed=1,
        correct_candidate=correct_candidate,
    )

    assert len(distractors) == 3
    assert all(
        distractor["source_event"]["text"] != duplicate_value_event["text"]
        or distractor["source_event"]["year"] != duplicate_value_event["year"]
        or distractor["source_event"]["wikipedia_url"] != duplicate_value_event["wikipedia_url"]
        for distractor in distractors
    )


def test_build_history_factoid_quiz_falls_back_when_ai_candidate_produces_duplicate_answer_fact_ids(monkeypatch) -> None:
    import datetime as dt

    from quiz_forge.builders import build_history_factoid_mcq_4_quiz

    correct_candidate = {
        "answer_kind": "place",
        "prompt_style": "where",
        "answer_label": "Karachi, Pakistan",
        "question_text": "Where did this happen: a bomb blast kills at least 48 people in a predominantly Shia Muslim area?",
        "source_event": {
            "text": "In Karachi, Pakistan, a bomb blast kills at least 48 people in a predominantly Shia Muslim area.",
            "year": 2013,
            "wikipedia_url": "https://example.com/karachi",
        },
    }
    duplicate_distractor = {
        "answer_kind": "place",
        "prompt_style": "where",
        "answer_label": "Karachi, Pakistan",
        "question_text": "Where did this happen: a bomb blast kills at least 48 people in a predominantly Shia Muslim area?",
        "source_event": dict(correct_candidate["source_event"]),
    }

    monkeypatch.setattr(
        "quiz_forge.builders.build_history_factoid_distractors_for_candidate",
        lambda *args, **kwargs: [duplicate_distractor, _extract_place_candidate("Kyoto"), _extract_place_candidate("Waterloo")],
    )

    payload = build_history_factoid_mcq_4_quiz(
        dt.date(2026, 3, 15),
        dt.datetime(2026, 3, 15, 6, 0, tzinfo=dt.timezone.utc),
        "https://example.com/source",
        _place_factoid_candidates(),
        seed=1,
        edition=1,
        generation_mode="daily",
        ai_selected_factoid_candidate=correct_candidate,
    )

    assert payload["type"] == "history_factoid_mcq_4"
    assert len(payload["answer_facts"]) == 4
    assert len({fact["id"] for fact in payload["answer_facts"]}) == 4


def test_build_history_factoid_typed_quiz_rejects_duplicate_answer_fact_ids() -> None:
    import datetime as dt

    from quiz_forge.builders import _build_history_factoid_typed_quiz

    correct_candidate = {
        "answer_kind": "place",
        "prompt_style": "where",
        "answer_label": "Karachi, Pakistan",
        "question_text": "Where did this happen: a bomb blast kills at least 48 people in a predominantly Shia Muslim area?",
        "source_event": {
            "text": "In Karachi, Pakistan, a bomb blast kills at least 48 people in a predominantly Shia Muslim area.",
            "year": 2013,
            "wikipedia_url": "https://example.com/karachi",
        },
    }
    duplicate_distractor = {
        "answer_kind": "place",
        "prompt_style": "where",
        "answer_label": "Karachi, Pakistan",
        "question_text": "Where did this happen: a bomb blast kills at least 48 people in a predominantly Shia Muslim area?",
        "source_event": dict(correct_candidate["source_event"]),
    }

    with pytest.raises(ValueError, match="unique answer_fact ids"):
        _build_history_factoid_typed_quiz(
            target_date=dt.date(2026, 3, 15),
            retrieval_time=dt.datetime(2026, 3, 15, 6, 0, tzinfo=dt.timezone.utc),
            source_url="https://example.com/source",
            seed=1,
            edition=1,
            generation_mode="daily",
            correct_factoid=correct_candidate,
            distractor_factoids=[duplicate_distractor, _extract_place_candidate("Kyoto"), _extract_place_candidate("Waterloo")],
        )


def _extract_place_candidate(label: str) -> dict[str, object]:
    candidates_by_label = {
        "Kyoto": _place_factoid_candidates()[0],
        "Waterloo": _place_factoid_candidates()[1],
        "Karachi, Pakistan": _place_factoid_candidates()[2],
    }
    event = candidates_by_label[label]
    return {
        "answer_kind": "place",
        "prompt_style": "where",
        "answer_label": label,
        "question_text": "Where did this happen?",
        "source_event": event,
    }


def test_build_history_mcq_4_quiz_retries_when_first_correct_choice_leaks_target_year() -> None:
    import datetime as dt

    from quiz_forge.builders import build_history_mcq_4_quiz

    candidates = [
        {
            "text": "Economist is sworn in during the 2010 earthquake ceremony.",
            "year": 2010,
            "wikipedia_url": "https://example.com/leaky-2010",
        },
        {
            "text": "A constitution is signed after months of negotiations.",
            "year": 1919,
            "wikipedia_url": "https://example.com/1919",
        },
        {
            "text": "A fleet reaches port after a long voyage.",
            "year": 1888,
            "wikipedia_url": "https://example.com/1888",
        },
        {
            "text": "A treaty is ratified by the senate.",
            "year": 1935,
            "wikipedia_url": "https://example.com/1935",
        },
        {
            "text": "A republic declares independence from a neighboring empire.",
            "year": 1991,
            "wikipedia_url": "https://example.com/1991",
        },
    ]
    quality_stats = QualityRunStats()

    payload = build_history_mcq_4_quiz(
        dt.date(2026, 3, 17),
        dt.datetime(2026, 3, 17, 6, 0, tzinfo=dt.timezone.utc),
        "https://example.com/source",
        candidates,
        seed=4,
        edition=1,
        generation_mode="daily",
        quality_stats=quality_stats,
    )

    assert lint_quiz_payload(payload) == ()
    assert "prompt_leak_year:1" in quality_stats.to_report_payload()["lint_failures"]


def test_build_history_factoid_quiz_rejects_leaky_ai_candidate_and_falls_back(monkeypatch) -> None:
    import datetime as dt

    from quiz_forge.builders import build_history_factoid_mcq_4_quiz

    ai_candidate = {
        "answer_kind": "place",
        "prompt_style": "where",
        "answer_label": "the MCG Stadium",
        "question_text": "Where did this happen: First ever official cricket test match is played: Australia vs England in Melbourne, Australia?",
        "source_event": {
            "text": "First ever official cricket test match is played: Australia vs England in Melbourne, Australia.",
            "year": 1877,
            "wikipedia_url": "https://example.com/mcg",
        },
    }

    monkeypatch.setattr(
        "quiz_forge.builders.build_history_factoid_distractors_for_candidate",
        lambda *args, **kwargs: [
            {
                "answer_kind": "place",
                "prompt_style": "where",
                "answer_label": "Kyoto",
                "question_text": "Where did this happen?",
                "source_event": _place_factoid_candidates()[0],
            },
            {
                "answer_kind": "place",
                "prompt_style": "where",
                "answer_label": "Waterloo",
                "question_text": "Where did this happen?",
                "source_event": _place_factoid_candidates()[1],
            },
            {
                "answer_kind": "place",
                "prompt_style": "where",
                "answer_label": "Karachi, Pakistan",
                "question_text": "Where did this happen?",
                "source_event": _place_factoid_candidates()[2],
            },
        ],
    )
    quality_stats = QualityRunStats()

    payload = build_history_factoid_mcq_4_quiz(
        dt.date(2026, 3, 17),
        dt.datetime(2026, 3, 17, 6, 0, tzinfo=dt.timezone.utc),
        "https://example.com/source",
        _place_factoid_candidates(),
        seed=1,
        edition=1,
        generation_mode="daily",
        ai_selected_factoid_candidate=ai_candidate,
        quality_stats=quality_stats,
    )

    assert lint_quiz_payload(payload) == ()
    assert payload["question"] != ai_candidate["question_text"]
    assert "history_factoid_mcq_4:ai_candidate_rejected:1" in quality_stats.to_report_payload()["fallback_paths"]


def test_cli_discards_ai_time_factoid_update_when_quality_lint_fails(monkeypatch, tmp_path) -> None:
    from quiz_forge import cli

    target_date = "2026-03-17"
    output_dir = (tmp_path / "quizzes").as_posix()

    monkeypatch.setattr(cli, "fetch_json", lambda *_args, **_kwargs: {"events": []})
    monkeypatch.setattr(cli, "extract_candidates", lambda _payload: _sample_candidates())
    monkeypatch.setenv("AI_MODE", "on")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_MODEL", "gpt-5-mini")
    monkeypatch.setenv("QUIZ_FORGE_AI_REPORT_PATH", (tmp_path / "ai-report.json").as_posix())

    class _Settings:
        enabled = True
        model_qgen = "gpt-5-mini"
        model_ranker = "gpt-5-mini"
        model_distractors = "gpt-5-mini"
        model_judge = "gpt-5-mini"
        max_stage_tokens = 200
        min_question_score = 0.5
        min_final_score = 0.5
        max_page_contexts = 4
        max_page_extract_chars = 500

    monkeypatch.setattr(cli, "load_factoid_pipeline_settings", lambda _model: _Settings())

    def _bad_ai_quiz(**_kwargs):
        quiz = {
            "date": target_date,
            "topics": ["history"],
            "type": "history_factoid_mcq_4",
            "questions": [
                {
                    "id": "q1",
                    "type": "history_factoid_mcq_4",
                    "prompt": "Who is Neil Armstrong?",
                    "answer_fact_ids": ["a", "b", "c", "d"],
                    "correct_answer_fact_id": "a",
                    "tags": ["history", "history_factoid_mcq_4"],
                    "facets": {
                        "topic": "history",
                        "difficulty_band": "baseline",
                        "question_format": "factoid",
                        "answer_kind": "person",
                        "answer_subtype": "historical_figure",
                        "prompt_style": "who",
                    },
                    "selection_rules": {"distractor_same_year_allowed": False},
                }
            ],
            "answer_facts": [
                {
                    "id": "a",
                    "label": "Neil Armstrong",
                    "year": 1969,
                    "tags": ["history"],
                    "facets": {"topic": "history", "entity_type": "person", "entity_subtype": "historical_figure"},
                    "match": {"distractor_profile": {"year": 1969}},
                    "vector_metadata": {"text_for_embedding": "Neil Armstrong", "embedding_status": "not_generated"},
                },
                {
                    "id": "b",
                    "label": "Buzz Aldrin",
                    "year": 1969,
                    "tags": ["history"],
                    "facets": {"topic": "history", "entity_type": "person", "entity_subtype": "historical_figure"},
                    "match": {"distractor_profile": {"year": 1969}},
                    "vector_metadata": {"text_for_embedding": "Buzz Aldrin", "embedding_status": "not_generated"},
                },
                {
                    "id": "c",
                    "label": "Yuri Gagarin",
                    "year": 1961,
                    "tags": ["history"],
                    "facets": {"topic": "history", "entity_type": "person", "entity_subtype": "historical_figure"},
                    "match": {"distractor_profile": {"year": 1961}},
                    "vector_metadata": {"text_for_embedding": "Yuri Gagarin", "embedding_status": "not_generated"},
                },
                {
                    "id": "d",
                    "label": "Michael Collins",
                    "year": 1969,
                    "tags": ["history"],
                    "facets": {"topic": "history", "entity_type": "person", "entity_subtype": "historical_figure"},
                    "match": {"distractor_profile": {"year": 1969}},
                    "vector_metadata": {"text_for_embedding": "Michael Collins", "embedding_status": "not_generated"},
                },
            ],
            "question": "Who is Neil Armstrong?",
            "choices": [
                {"id": "A", "label": "Neil Armstrong", "answer_fact_id": "a"},
                {"id": "B", "label": "Buzz Aldrin", "answer_fact_id": "b"},
                {"id": "C", "label": "Yuri Gagarin", "answer_fact_id": "c"},
                {"id": "D", "label": "Michael Collins", "answer_fact_id": "d"},
            ],
            "correct_choice_id": "A",
            "source": {
                "name": "Wikipedia On This Day",
                "url": "https://example.com/source",
                "retrieved_at": "2026-03-17T06:00:00Z",
                "events_used": [
                    {"event_id": "a", "text": "Neil Armstrong walks on the Moon during Apollo 11.", "year": 1969, "wikipedia_url": "https://example.com/neil-armstrong"},
                    {"event_id": "b", "text": "Buzz Aldrin walks on the Moon during Apollo 11.", "year": 1969, "wikipedia_url": "https://example.com/buzz"},
                    {"event_id": "c", "text": "Yuri Gagarin becomes the first human in space.", "year": 1961, "wikipedia_url": "https://example.com/yuri"},
                    {"event_id": "d", "text": "Michael Collins pilots the Apollo 11 command module.", "year": 1969, "wikipedia_url": "https://example.com/collins"},
                ],
                "page_sources": [
                    {"answer_fact_id": "a", "page_url": "https://example.com/neil-armstrong", "page_title": "Neil Armstrong", "retrieved_at": "2026-03-17T06:00:00Z"},
                    {"answer_fact_id": "b", "page_url": "https://example.com/buzz", "page_title": "Buzz Aldrin", "retrieved_at": "2026-03-17T06:00:00Z"},
                    {"answer_fact_id": "c", "page_url": "https://example.com/yuri", "page_title": "Yuri Gagarin", "retrieved_at": "2026-03-17T06:00:00Z"},
                    {"answer_fact_id": "d", "page_url": "https://example.com/collins", "page_title": "Michael Collins", "retrieved_at": "2026-03-17T06:00:00Z"},
                ],
            },
            "generation": {"mode": "daily", "edition": 1, "generated_at": "2026-03-17T06:00:00Z"},
            "metadata": {
                "version": 2,
                "normalized_model": "question_answer_facts_v1",
                "generation_method": "ai_native_factoid_v1",
            },
        }
        return quiz, None

    monkeypatch.setattr(cli, "generate_ai_native_factoid_quiz", _bad_ai_quiz)

    args = argparse.Namespace(
        date=target_date,
        quiz_types="history_factoid_mcq_4",
        output_dir=output_dir,
        timeout=1,
        retries=1,
        mode="daily",
        count=1,
        daily_editions_by_type="which_came_first=1,history_mcq_4=1,history_factoid_mcq_4=1",
    )
    monkeypatch.setattr(cli, "parse_args", lambda: args)
    assert cli.main() == 0

    records = list_quiz_records_for_date_type(
        output_dir=output_dir,
        target_date=dt.date.fromisoformat(target_date),
        quiz_type="history_factoid_mcq_4",
    )
    payload = records[0].payload
    assert lint_quiz_payload(payload) == ()
    assert payload["question"] != "Who is Neil Armstrong?"

    report_payload = json.loads((tmp_path / "ai-report.json").read_text(encoding="utf-8"))
    assert report_payload["quality"]["ai_quality_rejection_count"] == 1
