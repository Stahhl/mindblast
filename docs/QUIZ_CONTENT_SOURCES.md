# Quiz Content Source Scan (Commercial Safety Pass)

Last reviewed: 2026-03-19 (UTC)

Policy anchor: `docs/CONTENT_COMPLIANCE_POLICY.md`

## Purpose
Identify quiz datasets/APIs (trivia + board-game-relevant content) that Mindblast could:
- use directly in product content,
- use as reference material, or
- use for model training/fine-tuning.

This document focuses on licensing and terms risk, not content quality.

## Risk Legend
- Green: typically workable for commercial use with low licensing friction.
- Yellow: usable, but with obligations or unclear edge cases that need review.
- Red: high risk or explicit restrictions for our planned use.

## Source Matrix

| Source | Content Type | Cost Model | Key License / Terms Signal | Direct Commercial Use | Model Training | Risk |
|---|---|---|---|---|---|---|
| [Wikidata](https://www.wikidata.org/wiki/Wikidata:Licensing) | Structured facts (including board games, history, people, places) | Free | Data is dedicated to public domain via CC0 | Yes | Yes | Green |
| [Open Trivia DB](https://opentdb.com/api_config.php) | Trivia MCQs (includes `Entertainment: Board Games`) | Free | States questions are licensed under CC BY-SA 4.0 | Yes, with attribution/share-alike obligations | Usually yes, with attribution/share-alike obligations | Yellow |
| [Wikimedia content license](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use/en#7._Licensing_of_Content) | Wikipedia text/media used to derive trivia | Free | Text is generally under CC BY-SA 4.0 and GFDL | Yes, with attribution/share-alike obligations | Usually yes, but share-alike obligations should be reviewed | Yellow |
| [The Trivia API](https://the-trivia-api.com/license/) | Trivia Q/A API | Free + paid | Free content is CC BY-NC 4.0; commercial use requires subscription | Yes, but paid plan required for commercial | Yes for paid/commercial plan; free tier is non-commercial | Yellow |
| [TriviaDatabase](https://www.triviadatabase.com/licensing) | Large trivia packs/API | Paid licensing available | Offers separate licenses (personal/non-profit, app/web, full use) | Yes, via paid license | Potentially yes only if explicitly granted in contract | Yellow |
| [QuizAPI Terms](https://quizapi.io/terms) | API quizzes (mostly technical) | Free + paid | Terms state no commercial use on free plan and note third-party content may have separate rights | Paid plan may allow product use | Unclear; requires explicit provider confirmation | Yellow |
| [QANTA / Quizbowl](https://pinafore.github.io/qanta-leaderboard/) | Quizbowl long-form questions | Free | Distributed under CC BY-SA 4.0 (per dataset page) | Yes, with attribution/share-alike obligations | Usually yes with same obligations | Yellow |
| [OpenTriviaQA](https://github.com/uberspot/OpenTriviaQA) | Open trivia corpus | Free | Repo is CC BY-SA 4.0 but notes source-rights uncertainty for portions (OpenTDB/JService) | Risky for product without legal review | Risky for same reason | Red |
| [BoardGameGeek XML API Terms](https://boardgamegeek.com/wiki/page/XML_API_Terms_of_Use) + [usage policy](https://boardgamegeek.com/using_the_xml_api) | Board game metadata + community data | Free non-commercial; commercial license by agreement | Terms restrict to non-commercial unless licensed and usage policy explicitly prohibits AI/LLM training | Commercial only with explicit license | No (explicit AI/LLM training prohibition) | Red |

## Recommended Shortlist For Mindblast

1. Primary base facts: **Wikidata (CC0)** for low-friction commercial safety.
2. Supplemental trivia set: **Open Trivia DB** if we can meet CC BY-SA attribution/share-alike obligations.
3. Board-game enrichment:
   - Prefer **Wikidata board-game entities** first.
   - Treat **BoardGameGeek** as contract-only for commercial app usage and never for model training unless policy changes in writing.
4. Paid expansion path: **The Trivia API commercial plan** or **TriviaDatabase app/full-use license** once we need larger volume/variety.

## Phase 9 Selected Source Direction

Selected next category:
- `geography_factoid_mcq_4` (capital-to-country only in v1)

Selected source posture:
- **Wikidata-derived structured geography facts**

Terms / license:
- Terms URL: https://www.wikidata.org/wiki/Wikidata:Licensing
- Review date: 2026-03-19 (UTC)
- License signal: CC0 / public-domain dedication

Operational obligations for Phase 9:
- preserve source query URL or dataset reference in quiz metadata
- preserve stable country/capital entity identifiers
- keep source attribution explicit in payloads
- reject ambiguous/disputed capital-country pairs in v1
- do not mix synthetic distractors into sourced geography payloads

Risk rating:
- `Green`

Why this was selected:
- structured facts are a better fit for deterministic geography generation than free-form text sources
- CC0 posture is the lowest-friction option in the current source scan
- country/capital records support short-answer factoid prompts cleanly

## Practical Use Guidance

- Best low-risk path for training data today: **CC0-only corpus (Wikidata-derived)**.
- Best low-risk path for direct question delivery:
  - CC0/contracted sources first,
  - CC BY-SA sources only if we implement attribution and downstream compliance.
- Best near-term category expansion path:
  - geography factoids from Wikidata-derived country/capital records
- AI-generated content is not a source:
  - never attach fabricated citations to generated items,
  - keep generated items explicitly labeled as synthetic when/if introduced.
- Avoid using scraped/redistributed trivia dumps with unclear provenance for production or model training.

## Validation Checklist Before Integrating Any New Source

1. Confirm license/terms page URL and capture date reviewed.
2. Confirm whether commercial app use is allowed.
3. Confirm whether model training/fine-tuning is allowed.
4. Confirm attribution/share-alike/non-commercial restrictions.
5. Record operational limits (rate limits, redistribution limits, API key requirements).
6. Add source-specific validation and attribution fields before shipping content.
