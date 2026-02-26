"""Deterministic selection logic for quiz events."""

from __future__ import annotations

import hashlib
import datetime as dt
from typing import Any


def build_seed(target_date: dt.date, quiz_type: str, edition: int) -> int:
    key = f"{target_date.isoformat()}:{quiz_type}:{edition}"
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest(), 16)


def pick_two_events(candidates: list[dict[str, Any]], seed: int) -> tuple[dict[str, Any], dict[str, Any]]:
    if len(candidates) < 2:
        raise ValueError("Not enough valid events to build a question.")

    ordered = sorted(candidates, key=lambda item: (item["year"], item["text"]))
    first_idx = seed % len(ordered)
    step = (seed % (len(ordered) - 1)) + 1

    for offset in range(len(ordered) - 1):
        second_idx = (first_idx + step + offset) % len(ordered)
        if second_idx == first_idx:
            continue
        first = ordered[first_idx]
        second = ordered[second_idx]
        if first["year"] != second["year"]:
            return first, second

    raise ValueError("Could not pick two events with distinct years.")


def pick_history_mcq_events(
    candidates: list[dict[str, Any]],
    seed: int,
    preferred_distractor_events: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    correct, distractor_pool = pick_history_mcq_distractor_pool(
        candidates,
        seed,
        preferred_distractor_events=preferred_distractor_events,
        max_distractors=3,
    )
    distractors = distractor_pool[:3]

    options = [correct, *distractors]
    options.sort(
        key=lambda item: hashlib.sha256(
            f"{seed}:{item['year']}:{item['text']}".encode("utf-8")
        ).hexdigest()
    )

    return correct, distractors, options


def pick_history_mcq_distractor_pool(
    candidates: list[dict[str, Any]],
    seed: int,
    preferred_distractor_events: list[dict[str, Any]] | None = None,
    *,
    max_distractors: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if max_distractors < 3:
        raise ValueError("max_distractors must be at least 3.")

    if len(candidates) < 4:
        raise ValueError("Not enough valid events to build a 4-option history MCQ.")

    ordered = sorted(candidates, key=lambda item: (item["year"], item["text"]))
    correct_idx = seed % len(ordered)
    correct = ordered[correct_idx]

    step = (seed % (len(ordered) - 1)) + 1
    distractors: list[dict[str, Any]] = []
    distractor_years: set[int] = set()
    by_key = {
        (event["text"], event["year"], event["wikipedia_url"]): event
        for event in ordered
    }

    if preferred_distractor_events:
        preferred_ordered = sorted(
            preferred_distractor_events,
            key=lambda item: (item["year"], item["text"], item["wikipedia_url"]),
        )
        for preferred in preferred_ordered:
            candidate = by_key.get((preferred["text"], preferred["year"], preferred["wikipedia_url"]))
            if candidate is None:
                continue
            if candidate["year"] == correct["year"]:
                continue
            if candidate["year"] in distractor_years:
                continue
            if candidate is correct:
                continue

            distractors.append(candidate)
            distractor_years.add(candidate["year"])
            if len(distractors) == max_distractors:
                break

    for offset in range(len(ordered) - 1):
        idx = (correct_idx + step + offset) % len(ordered)
        if idx == correct_idx:
            continue

        event = ordered[idx]
        if event in distractors:
            continue
        if event["year"] == correct["year"]:
            continue
        if event["year"] in distractor_years:
            continue

        distractors.append(event)
        distractor_years.add(event["year"])
        if len(distractors) == max_distractors:
            break

    if len(distractors) < 3:
        raise ValueError("Could not pick three distinct-year distractors for history_mcq_4.")

    return correct, distractors
