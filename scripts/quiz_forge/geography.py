"""Deterministic geography source loading and selection."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

GEOGRAPHY_SOURCE_NAME = "Wikidata"
GEOGRAPHY_SOURCE_URL = "https://www.wikidata.org/wiki/Wikidata:Licensing"


def _data_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "geography_country_capitals.json"


def load_geography_records() -> list[dict[str, Any]]:
    payload = json.loads(_data_path().read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Geography source data must be a list.")
    records: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        records.append(dict(item))
    return records


def _normalized(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split()).strip()
    return normalized or None


def iter_eligible_geography_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    eligible: list[dict[str, Any]] = []
    seen_countries: set[str] = set()
    seen_capitals: set[str] = set()

    for record in records:
        country_label = _normalized(record.get("country_label"))
        capital_label = _normalized(record.get("capital_label"))
        country_qid = _normalized(record.get("country_qid"))
        capital_qid = _normalized(record.get("capital_qid"))
        country_url = _normalized(record.get("country_url"))
        capital_url = _normalized(record.get("capital_url"))
        blocked_reason = _normalized(record.get("blocked_reason"))

        if blocked_reason is not None:
            continue
        if None in {country_label, capital_label, country_qid, capital_qid, country_url, capital_url}:
            continue

        country_key = country_label.casefold()
        capital_key = capital_label.casefold()
        if country_key in seen_countries or capital_key in seen_capitals:
            continue

        eligible_record = {
            "country_label": country_label,
            "capital_label": capital_label,
            "country_qid": country_qid,
            "capital_qid": capital_qid,
            "country_url": country_url,
            "capital_url": capital_url,
        }
        eligible.append(eligible_record)
        seen_countries.add(country_key)
        seen_capitals.add(capital_key)

    return eligible


def pick_geography_factoid_records(
    records: list[dict[str, Any]],
    seed: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    eligible = sorted(
        iter_eligible_geography_records(records),
        key=lambda item: (item["capital_label"], item["country_label"], item["country_qid"]),
    )
    if len(eligible) < 4:
        raise ValueError("Not enough valid geography records to build geography_factoid_mcq_4.")

    correct_idx = seed % len(eligible)
    correct = eligible[correct_idx]
    step = (seed % (len(eligible) - 1)) + 1

    distractors: list[dict[str, Any]] = []
    for offset in range(len(eligible)):
        idx = (correct_idx + step + offset) % len(eligible)
        if idx == correct_idx:
            continue
        candidate = eligible[idx]
        if candidate["country_label"] == correct["country_label"]:
            continue
        if candidate["capital_label"] == correct["capital_label"]:
            continue
        distractors.append(candidate)
        if len(distractors) == 3:
            break

    if len(distractors) != 3:
        raise ValueError("Could not pick three valid geography distractors.")

    return correct, distractors


def geography_option_sort_key(seed: int, record: dict[str, Any]) -> str:
    return hashlib.sha256(
        f"{seed}:{record['country_qid']}:{record['capital_qid']}".encode("utf-8")
    ).hexdigest()
