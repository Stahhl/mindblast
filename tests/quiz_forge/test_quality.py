from __future__ import annotations

from quiz_forge.quality import (
    ISSUE_MIXED_ENTITY_TYPES,
    ISSUE_PROMPT_LEAK_LOCATION,
    ISSUE_PROMPT_LEAK_YEAR,
    ISSUE_WEAK_DISTRACTOR_PLAUSIBILITY,
    lint_quiz_payload,
)


def test_lint_history_factoid_person_flags_mixed_entity_types() -> None:
    payload = {
        "type": "history_factoid_mcq_4",
        "question": "Who becomes the first American astronaut to ride to space on board a Russian launch vehicle?",
        "questions": [{"facets": {"answer_kind": "person", "prompt_style": "who"}}],
        "choices": [
            {"id": "A", "label": "Norman Thagard"},
            {"id": "B", "label": "Pelican Island National Wildlife"},
            {"id": "C", "label": "Rossini's Petite"},
            {"id": "D", "label": "The South African"},
        ],
        "correct_choice_id": "A",
    }

    issues = lint_quiz_payload(payload)

    assert ISSUE_MIXED_ENTITY_TYPES in issues
    assert ISSUE_WEAK_DISTRACTOR_PLAUSIBILITY in issues


def test_lint_history_factoid_person_flags_weekly_report_style_fragment_labels() -> None:
    payload = {
        "type": "history_factoid_mcq_4",
        "question": "Who was involved in this event?",
        "questions": [{"facets": {"answer_kind": "person", "prompt_style": "who"}}],
        "choices": [
            {"id": "A", "label": "Norman Thagard"},
            {"id": "B", "label": "During the Algerian Civil"},
            {"id": "C", "label": "American Civil"},
            {"id": "D", "label": "In New York"},
        ],
        "correct_choice_id": "A",
    }

    issues = lint_quiz_payload(payload)

    assert ISSUE_MIXED_ENTITY_TYPES in issues
    assert ISSUE_WEAK_DISTRACTOR_PLAUSIBILITY in issues


def test_lint_history_factoid_person_flags_non_person_objects() -> None:
    payload = {
        "type": "history_factoid_mcq_4",
        "question": "Who was central to this event?",
        "questions": [{"facets": {"answer_kind": "person", "prompt_style": "who"}}],
        "choices": [
            {"id": "A", "label": "Neil Armstrong"},
            {"id": "B", "label": "An EF4 tornado"},
            {"id": "C", "label": "The South African"},
            {"id": "D", "label": "Pelican Island National Wildlife"},
        ],
        "correct_choice_id": "A",
    }

    issues = lint_quiz_payload(payload)

    assert ISSUE_MIXED_ENTITY_TYPES in issues
    assert ISSUE_WEAK_DISTRACTOR_PLAUSIBILITY in issues


def test_lint_history_factoid_place_flags_prompt_location_leak() -> None:
    payload = {
        "type": "history_factoid_mcq_4",
        "question": "Where did this happen: First ever official cricket test match is played: Australia vs England in Melbourne, Australia?",
        "questions": [{"facets": {"answer_kind": "place", "prompt_style": "where"}}],
        "choices": [
            {"id": "A", "label": "Newburgh, New York"},
            {"id": "B", "label": "the MCG Stadium"},
            {"id": "C", "label": "Hungary"},
            {"id": "D", "label": "the United Kingdom"},
        ],
        "correct_choice_id": "B",
    }

    issues = lint_quiz_payload(payload)

    assert ISSUE_PROMPT_LEAK_LOCATION in issues


def test_lint_history_factoid_time_flags_prompt_year_leak() -> None:
    payload = {
        "type": "history_factoid_mcq_4",
        "question": "When did the March 2016 Ankara bombing kill at least 37 people?",
        "questions": [{"facets": {"answer_kind": "time", "prompt_style": "when"}}],
        "choices": [
            {"id": "A", "label": "1930"},
            {"id": "B", "label": "1741"},
            {"id": "C", "label": "2016"},
            {"id": "D", "label": "2020"},
        ],
        "correct_choice_id": "C",
    }

    issues = lint_quiz_payload(payload)

    assert issues == (ISSUE_PROMPT_LEAK_YEAR,)


def test_lint_history_mcq_flags_correct_choice_year_leak() -> None:
    payload = {
        "type": "history_mcq_4",
        "question": "Which event happened in 2010?",
        "questions": [{"selection_rules": {"target_year": 2010}}],
        "choices": [
            {"id": "A", "label": "Event in 1928."},
            {"id": "B", "label": "Economist is sworn in during the 2010 earthquake ceremony."},
            {"id": "C", "label": "Event in 1990."},
            {"id": "D", "label": "Event in 1985."},
        ],
        "correct_choice_id": "B",
    }

    issues = lint_quiz_payload(payload)

    assert issues == (ISSUE_PROMPT_LEAK_YEAR,)
