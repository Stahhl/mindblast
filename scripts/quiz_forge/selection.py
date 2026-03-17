"""Deterministic selection logic for quiz events."""

from __future__ import annotations

import hashlib
import datetime as dt
import re
from typing import Any

from .model import build_factoid_answer_fact_id


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
    correct_event: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if max_distractors < 3:
        raise ValueError("max_distractors must be at least 3.")

    if len(candidates) < 4:
        raise ValueError("Not enough valid events to build a 4-option history MCQ.")

    ordered = sorted(candidates, key=lambda item: (item["year"], item["text"]))
    if correct_event is None:
        correct_idx = seed % len(ordered)
        correct = ordered[correct_idx]
    else:
        key = (correct_event["text"], correct_event["year"], correct_event["wikipedia_url"])
        indexed_ordered = {
            (event["text"], event["year"], event["wikipedia_url"]): (index, event)
            for index, event in enumerate(ordered)
        }
        match = indexed_ordered.get(key)
        if match is None:
            raise ValueError("Requested correct event is not present in candidate pool.")
        correct_idx, correct = match

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

    for offset in range(len(ordered)):
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


def iter_history_mcq_correct_events(
    candidates: list[dict[str, Any]],
    seed: int,
) -> list[dict[str, Any]]:
    if len(candidates) < 4:
        raise ValueError("Not enough valid events to build a 4-option history MCQ.")
    ordered = sorted(candidates, key=lambda item: (item["year"], item["text"]))
    first_idx = seed % len(ordered)
    step = (seed % (len(ordered) - 1)) + 1
    indices = [first_idx]
    for offset in range(len(ordered) - 1):
        idx = (first_idx + step + offset) % len(ordered)
        if idx in indices:
            continue
        indices.append(idx)
    return [ordered[index] for index in indices]


_PERSON_CONNECTORS = {
    "al",
    "ap",
    "bin",
    "da",
    "de",
    "del",
    "di",
    "el",
    "ibn",
    "la",
    "le",
    "st.",
    "the",
    "van",
    "von",
}
_PERSON_TITLES = {
    "Archduke",
    "Bishop",
    "Count",
    "Dr.",
    "Emperor",
    "Empress",
    "General",
    "King",
    "Pope",
    "President",
    "Prince",
    "Princess",
    "Queen",
    "Saint",
    "Sir",
    "Sultan",
    "Tsar",
}
_NON_PERSON_KEYWORDS = {
    "Academy",
    "Airlines",
    "Alliance",
    "Apollo",
    "Army",
    "Association",
    "Battle",
    "Bombing",
    "Center",
    "Centre",
    "Company",
    "Congress",
    "Court",
    "Empire",
    "Expedition",
    "Flight",
    "Force",
    "Forces",
    "Kingdom",
    "March",
    "Museum",
    "Order",
    "Parliament",
    "Republic",
    "RMS",
    "Shuttle",
    "Siege",
    "Space",
    "Squadron",
    "STS-",
    "Treaty",
    "University",
    "USS",
    "War",
    "Wildlife",
    "National",
    "Operation",
    "Stadium",
    "Theatre",
    "Theater",
    "Supertanker",
}
_SUBJECT_RE = re.compile(
    r"^(?P<subject>[A-Z][\w'.-]+(?:\s+(?:[A-Z][\w'.-]+|[ivxlcdmIVXLCDM]+|Jr\.|Sr\.|St\.|[a-z]{1,4})){1,6})\s+(?P<rest>.+)$"
)
_PLACE_CONNECTORS = {"and", "de", "del", "du", "la", "le", "of", "st.", "the"}
_PLACE_HINT_TOKENS = {
    "Bay",
    "Beach",
    "Bridge",
    "Canal",
    "Castle",
    "City",
    "Fort",
    "Harbor",
    "Harbour",
    "Hill",
    "Island",
    "Lake",
    "Mountain",
    "Mount",
    "Palace",
    "Park",
    "Port",
    "River",
    "Road",
    "Sea",
    "Square",
    "Station",
    "Temple",
    "Valley",
}
_NON_PLACE_KEYWORDS = {
    "Army",
    "Association",
    "Battle",
    "Bombing",
    "Conference",
    "Court",
    "Day",
    "Dynasty",
    "Expedition",
    "Flight",
    "Forces",
    "Government",
    "King",
    "Law",
    "League",
    "March",
    "Museum",
    "President",
    "Senate",
    "Siege",
    "Speech",
    "Treaty",
    "War",
}
_LEADING_PLACE_RE = re.compile(
    r"^(?P<prefix>In|At|Near|From)\s+(?P<place>(?:the\s+)?[A-Z][^.;:()]{1,70}?)(?:,\s*(?P<place_suffix>[A-Z][^.;:()]{1,40}?))?,\s*(?P<rest>.+)$"
)
_INLINE_PLACE_COMMA_RE = re.compile(
    r"^(?P<prefix>.+?)\s+(?P<prep>in|at|near|from)\s+"
    r"(?P<place>(?:the\s+)?[A-Z][^,.;:()]{1,40})(?:,\s*(?P<place_suffix>[A-Z][^,.;:()]{1,30}))?,\s*"
    r"(?P<suffix>.+)$"
)
_INLINE_PLACE_TRAILING_RE = re.compile(
    r"^(?P<prefix>.+?)\s+(?P<prep>in|at|near|from)\s+"
    r"(?P<place>(?:the\s+)?[A-Z][\w'.-]+(?:\s+(?:[A-Z][\w'.-]+|of|the|de|del|du|la|le|St\.)){0,4})"
    r"(?P<suffix>\s+(?:in|on|during|after|before|while|as|to|for|with|under)\b.+)$"
)


def _normalize_ws(value: str) -> str:
    return " ".join(value.split())


def _strip_leading_context(text: str) -> list[str]:
    segments = [segment.strip() for segment in text.split(",")]
    variants: list[str] = []
    for start in range(min(3, len(segments))):
        variant = _normalize_ws(", ".join(segments[start:]))
        if variant and variant not in variants:
            variants.append(variant)
    return variants or [_normalize_ws(text)]


def _looks_like_person_name(subject: str) -> bool:
    tokens = subject.split()
    if len(tokens) < 2:
        return False
    if subject.startswith("The "):
        return False
    if any(any(char.isdigit() for char in token) for token in tokens if token.upper() != token):
        return False
    if any(token.endswith("'s") or token.endswith("’s") for token in tokens):
        return False

    non_title_tokens = [token for token in tokens if token not in _PERSON_TITLES]
    if len(non_title_tokens) < 2:
        return False

    first = non_title_tokens[0]
    if first in _NON_PERSON_KEYWORDS or any(keyword in subject for keyword in _NON_PERSON_KEYWORDS):
        return False
    if any(token.rstrip(".,") in _PLACE_HINT_TOKENS for token in non_title_tokens):
        return False

    capitalized_token_count = 0
    for token in non_title_tokens:
        normalized = token.rstrip(".,")
        if normalized.lower() in _PERSON_CONNECTORS:
            continue
        if normalized in {"Jr", "Jr.", "Sr", "Sr.", "II", "III", "IV", "V"}:
            continue
        if normalized and normalized[0].isupper():
            capitalized_token_count += 1
            continue
        return False

    return capitalized_token_count >= 2


def looks_like_person_label(label: str) -> bool:
    return _looks_like_person_name(_normalize_ws(label.strip()))


def _extract_person_factoid_candidate(event: dict[str, Any]) -> dict[str, Any] | None:
    raw_text = event.get("text")
    if not isinstance(raw_text, str):
        return None

    for candidate_text in _strip_leading_context(raw_text):
        match = _SUBJECT_RE.match(candidate_text)
        if match is None:
            continue
        subject = _normalize_ws(match.group("subject").strip(" ,"))
        rest = _normalize_ws(match.group("rest").rstrip(" .!?"))
        if not rest or not _looks_like_person_name(subject):
            continue
        if rest.lower().startswith(("and ", "or ", "but ")):
            continue
        question = f"Who {rest}?"
        if len(question) > 180:
            continue
        return {
            "answer_kind": "person",
            "prompt_style": "who",
            "answer_label": subject,
            "question_text": question,
            "source_event": event,
        }

    return None


def _looks_like_place_label(label: str) -> bool:
    normalized_label = _normalize_ws(label.strip(" ,"))
    if not normalized_label:
        return False
    if any(char.isdigit() for char in normalized_label):
        return False
    if normalized_label.lower() in {"the world", "world", "earth"}:
        return False
    if _looks_like_person_name(normalized_label):
        place_hint_present = (
            "," in normalized_label
            or normalized_label.lower().startswith("the ")
            or any(token.rstrip(".,") in _PLACE_HINT_TOKENS for token in normalized_label.split())
        )
        if not place_hint_present:
            return False

    segments = [segment.strip() for segment in normalized_label.split(",")]
    if len(segments) > 3:
        return False

    capitalized_token_count = 0
    for segment in segments:
        if not segment:
            return False
        for token in segment.split():
            bare = token.rstrip(".,")
            if not bare:
                continue
            if bare.lower() in _PLACE_CONNECTORS:
                continue
            if bare[0].isupper():
                capitalized_token_count += 1
                if bare in _NON_PLACE_KEYWORDS:
                    return False
                continue
            return False

    return capitalized_token_count >= 1


def looks_like_place_label(label: str) -> bool:
    return _looks_like_place_label(label)


def _split_place_segments(text: str, *, prefix: str) -> tuple[str, str] | None:
    remainder = _normalize_ws(text[len(prefix) :].strip())
    if not remainder:
        return None
    segments = [segment.strip() for segment in remainder.split(",")]
    if len(segments) < 2 or not segments[0]:
        return None

    place_segments = [segments[0]]
    rest_segments = segments[1:]
    if len(rest_segments) >= 2 and _looks_like_place_label(rest_segments[0]):
        place_segments.append(rest_segments[0])
        rest_segments = rest_segments[1:]

    place = _normalize_ws(", ".join(segment for segment in place_segments if segment))
    rest = _normalize_ws(", ".join(segment for segment in rest_segments if segment).rstrip(" .!?"))
    if not place or not rest:
        return None
    return place, rest


def _extract_place_factoid_candidate(event: dict[str, Any]) -> dict[str, Any] | None:
    raw_text = event.get("text")
    if not isinstance(raw_text, str):
        return None

    text = _normalize_ws(raw_text)
    for place_prefix in ("In ", "At ", "Near ", "From "):
        if text.startswith(place_prefix):
            split_result = _split_place_segments(text, prefix=place_prefix)
            if split_result is not None:
                place, rest = split_result
                if _looks_like_place_label(place):
                    question = f"Where did this happen: {rest}?"
                    if len(question) <= 220:
                        return {
                            "answer_kind": "place",
                            "prompt_style": "where",
                            "answer_label": place,
                            "question_text": question,
                            "source_event": event,
                        }

    match = _INLINE_PLACE_COMMA_RE.match(text)
    if match is not None:
        place_parts = [match.group("place"), match.group("place_suffix")]
        place = _normalize_ws(", ".join(part.strip(" ,") for part in place_parts if isinstance(part, str) and part.strip()))
        prefix = _normalize_ws(match.group("prefix").rstrip(" ,"))
        suffix = _normalize_ws(match.group("suffix").rstrip(" .!?"))
        rest = _normalize_ws(f"{prefix} {suffix}".strip())
        if rest and _looks_like_place_label(place):
            question = f"Where did this happen: {rest}?"
            if len(question) <= 220:
                return {
                    "answer_kind": "place",
                    "prompt_style": "where",
                    "answer_label": place,
                    "question_text": question,
                    "source_event": event,
                }

    match = _INLINE_PLACE_TRAILING_RE.match(text)
    if match is not None:
        place = _normalize_ws(match.group("place").strip(" ,"))
        prefix = _normalize_ws(match.group("prefix").rstrip(" ,"))
        suffix = _normalize_ws(match.group("suffix").rstrip(" .!?"))
        rest = _normalize_ws(f"{prefix} {suffix}".strip())
        if rest and _looks_like_place_label(place):
            question = f"Where did this happen: {rest}?"
            if len(question) <= 220:
                return {
                    "answer_kind": "place",
                    "prompt_style": "where",
                    "answer_label": place,
                    "question_text": question,
                    "source_event": event,
                }

    return None


def _factoid_candidate_sort_key(candidate: dict[str, Any]) -> tuple[str, int, str]:
    source_event = candidate["source_event"]
    return (
        candidate["answer_label"].casefold(),
        int(source_event["year"]),
        str(source_event["text"]),
    )


def _source_event_key(event: dict[str, Any]) -> tuple[int, str, str]:
    return (
        int(event["year"]),
        str(event["text"]),
        str(event["wikipedia_url"]),
    )


def _factoid_candidate_id(candidate: dict[str, Any]) -> str:
    return build_factoid_answer_fact_id(
        candidate["source_event"],
        answer_label=str(candidate["answer_label"]),
        entity_type=str(candidate["answer_kind"]),
    )


def _pick_factoid_candidates_of_kind(
    extracted_candidates: list[dict[str, Any]],
    seed: int,
    *,
    correct_index_offset: int = 0,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    ordered = sorted(extracted_candidates, key=_factoid_candidate_sort_key)
    unique_ordered: list[dict[str, Any]] = []
    seen_candidate_ids: set[str] = set()
    for candidate in ordered:
        candidate_id = _factoid_candidate_id(candidate)
        if candidate_id in seen_candidate_ids:
            continue
        unique_ordered.append(candidate)
        seen_candidate_ids.add(candidate_id)

    ordered = unique_ordered
    if not ordered:
        raise ValueError("No eligible factoid candidates found.")

    correct_idx = (seed + correct_index_offset) % len(ordered)
    correct = ordered[correct_idx]

    step = (seed % (len(ordered) - 1)) + 1
    distractors: list[dict[str, Any]] = []
    seen_labels = {correct["answer_label"].casefold()}
    seen_candidate_ids = {_factoid_candidate_id(correct)}

    for offset in range(len(ordered)):
        idx = (correct_idx + step + offset) % len(ordered)
        if idx == correct_idx:
            continue
        candidate = ordered[idx]
        candidate_id = _factoid_candidate_id(candidate)
        answer_label = candidate["answer_label"].casefold()
        if answer_label in seen_labels or candidate_id in seen_candidate_ids:
            continue
        distractors.append(candidate)
        seen_labels.add(answer_label)
        seen_candidate_ids.add(candidate_id)
        if len(distractors) == 3:
            break

    return correct, distractors


def build_history_factoid_distractors_for_candidate(
    candidates: list[dict[str, Any]],
    *,
    seed: int,
    correct_candidate: dict[str, Any],
) -> list[dict[str, Any]]:
    answer_kind = correct_candidate.get("answer_kind")
    if answer_kind not in {"person", "place"}:
        raise ValueError("Typed factoid distractor builder only supports person/place candidates.")

    extractor = _extract_person_factoid_candidate if answer_kind == "person" else _extract_place_factoid_candidate
    extracted_candidates = [
        candidate
        for event in candidates
        if (candidate := extractor(event)) is not None
    ]
    source_event = correct_candidate.get("source_event")
    if not isinstance(source_event, dict):
        raise ValueError("Typed factoid correct candidate is missing source_event.")
    source_event_key = _source_event_key(source_event)
    correct_candidate_id = _factoid_candidate_id(correct_candidate)
    correct_answer_label = str(correct_candidate.get("answer_label", "")).casefold()
    distractor_pool = [
        candidate
        for candidate in extracted_candidates
        if isinstance(candidate.get("source_event"), dict)
        and _source_event_key(candidate["source_event"]) != source_event_key
        and candidate.get("answer_label", "").casefold() != correct_answer_label
        and _factoid_candidate_id(candidate) != correct_candidate_id
    ]
    if len({candidate["answer_label"].casefold() for candidate in distractor_pool}) < 3:
        raise ValueError(f"Not enough valid {answer_kind} distractors for history_factoid_mcq_4.")

    _, distractors = _pick_factoid_candidates_of_kind([correct_candidate, *distractor_pool], seed)
    if len(distractors) < 3:
        raise ValueError(f"Could not pick three distinct {answer_kind} distractors for history_factoid_mcq_4.")
    return distractors[:3]


def pick_history_factoid_typed_candidates(
    candidates: list[dict[str, Any]],
    seed: int,
    preferred_distractor_events: list[dict[str, Any]] | None = None,
    preferred_answer_kind: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    del preferred_distractor_events

    by_kind = {
        "person": [
            candidate
            for event in candidates
            if (candidate := _extract_person_factoid_candidate(event)) is not None
        ],
        "place": [
            candidate
            for event in candidates
            if (candidate := _extract_place_factoid_candidate(event)) is not None
        ],
    }
    eligible_kinds = [
        answer_kind
        for answer_kind in ("person", "place")
        if len({candidate["answer_label"].casefold() for candidate in by_kind[answer_kind]}) >= 4
    ]
    if not eligible_kinds:
        raise ValueError("Not enough typed factoid candidates to build a 4-option history factoid MCQ.")

    if preferred_answer_kind in eligible_kinds:
        selected_kind = preferred_answer_kind
    else:
        selected_kind = eligible_kinds[seed % len(eligible_kinds)]
    correct, distractors = _pick_factoid_candidates_of_kind(by_kind[selected_kind], seed)
    if len(distractors) < 3:
        raise ValueError(f"Could not pick three distinct {selected_kind} distractors for history_factoid_mcq_4.")

    return correct, distractors


def iter_history_factoid_typed_candidate_sets(
    candidates: list[dict[str, Any]],
    seed: int,
    *,
    preferred_answer_kind: str | None = None,
) -> list[tuple[dict[str, Any], list[dict[str, Any]], str]]:
    by_kind = {
        "person": [
            candidate
            for event in candidates
            if (candidate := _extract_person_factoid_candidate(event)) is not None
        ],
        "place": [
            candidate
            for event in candidates
            if (candidate := _extract_place_factoid_candidate(event)) is not None
        ],
    }
    eligible_kinds = [
        answer_kind
        for answer_kind in ("person", "place")
        if len({candidate["answer_label"].casefold() for candidate in by_kind[answer_kind]}) >= 4
    ]
    if not eligible_kinds:
        raise ValueError("Not enough typed factoid candidates to build a 4-option history factoid MCQ.")

    if preferred_answer_kind in eligible_kinds:
        primary_kind = preferred_answer_kind
    else:
        primary_kind = eligible_kinds[seed % len(eligible_kinds)]
    kind_order = [primary_kind, *[kind for kind in eligible_kinds if kind != primary_kind]]

    candidate_sets: list[tuple[dict[str, Any], list[dict[str, Any]], str]] = []
    for kind in kind_order:
        unique_candidate_count = len({_factoid_candidate_id(candidate) for candidate in by_kind[kind]})
        for offset in range(unique_candidate_count):
            correct, distractors = _pick_factoid_candidates_of_kind(
                by_kind[kind],
                seed,
                correct_index_offset=offset,
            )
            if len(distractors) < 3:
                continue
            candidate_sets.append((correct, distractors[:3], kind))

    if not candidate_sets:
        raise ValueError(f"Could not pick typed factoid candidates for eligible kinds: {eligible_kinds}.")
    return candidate_sets
