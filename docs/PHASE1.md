# Phase 1 Specification: quiz-forge (Daily History Quizzes)

## Naming
- Project name: `Mindblast`.
- User-facing app name: `Mindblast`.
- Backend generator service name: `quiz-forge`.

## Objective
Build a minimal `quiz-forge` service for `Mindblast` that generates deterministic daily history quizzes and stores them as JSON in git-backed storage.

## Scope (Phase 1)
- One repository: `quiz-forge`.
- One scheduled CI workflow in GitHub Actions.
- Generate the configured daily edition target per enabled type per UTC day in default `daily` mode.
- Enabled types:
  - `which_came_first`
  - `history_mcq_4`
- Use a normalized question/answer-fact model so answer facts are reusable across question generation.
- Each quiz has exactly **1** correct answer.
- Output is committed and pushed as JSON under `quizzes/` in the private content repository `Stahhl/mindblast-content`.

## Out of Scope (for now)
- User-facing app.
- Leaderboards, achievements, and ratings.
- Non-history categories.
- Non-Wikipedia content sources.

Note:
- Multiple quizzes per type per day are introduced in Phase 4 (`docs/PHASE4.md`) via per-type daily edition targets plus `extra` mode.

## Content Source
- Use Wikipedia via Wikimedia On This Day API:
  - `https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/events/{month}/{day}`
- The generator selects valid events from that payload and builds each enabled quiz type.

## Workflow Requirements
- Primary trigger type: `schedule`.
- Recommended schedule: once daily in UTC (example: `0 6 * * *`).
- Manual dispatch is allowed for operational retries/backfills.

## Output Format
- Store one JSON file per generated edition:
  - `quizzes/<uuid>.json`
- `<uuid>` must be a deterministic UUIDv5 derived from `date + quiz_type + edition`.
- If a file for a date/type/edition already exists, do not create duplicates.
- Commit only when at least one new file is created.

Current scheduled daily targets:
- `which_came_first`: `1`
- `history_mcq_4`: `1`
- `history_factoid_mcq_4`: `3`

### JSON Contract (v2)
Common fields for all types:
- `date`: `YYYY-MM-DD` UTC date.
- `topics`: exactly `['history']`.
- `type`: quiz type identifier.
- `questions`: array containing exactly 1 question object.
- `answer_facts`: non-empty reusable answer-fact array.
- `question`: non-empty string (legacy compatibility mirror of `questions[0].prompt`).
- `choices`: non-empty array (legacy compatibility view).
- `choices[*].human_id` (optional): stable human-facing answer alias in `A<integer>` format.
- `correct_choice_id`: one of the choice ids (legacy compatibility view).
- `source.name`, `source.url`, `source.retrieved_at`: non-empty strings.
- `source.events_used`: array of source events (`event_id`, `text`, `year`, `wikipedia_url`).
- `source.page_sources` (optional): array of page provenance entries for AI-native factoids (`answer_fact_id`, `page_url`, `page_title`, `retrieved_at`).
- `generation.mode`: `daily` for any edition inside the configured daily range for the quiz type.
- `generation.edition`: integer `>= 1`.
- `generation.generated_at`: UTC ISO-8601 timestamp (`Z`).
- `metadata.version`: `2`.
- `metadata.normalized_model`: `question_answer_facts_v1`.

`questions[0]` requirements:
- `id`: non-empty deterministic UUID string.
- `human_id` (optional): stable human-facing question alias in `Q<integer>` format.
- `type`: equals top-level quiz `type`.
- `prompt`: non-empty string and equal to top-level `question`.
- `answer_fact_ids`: ordered list of fact ids used by the question.
- `correct_answer_fact_id`: one entry from `answer_fact_ids`.
- `tags`: non-empty list of strings.
- `facets`: object.
- `selection_rules`: object.
- For `history_factoid_mcq_4`, `facets.answer_subtype` is required and must be a non-empty string.

`answer_facts` requirements:
- Each fact includes `id`, `label`, integer `year`, `tags`, `facets`, `match`, `vector_metadata`.
- `answer_facts[*].human_id` (optional) must use `A<integer>` and align with linked choice `human_id`.
- `vector_metadata.text_for_embedding` and `vector_metadata.embedding_status` must be non-empty strings.
- Fact ids must be unique.
- `questions[0].answer_fact_ids` must reference existing fact ids.
- For AI-native `history_factoid_mcq_4`, `answer_facts[*].facets.entity_subtype` is required and must align with the question subtype.

### JSON Contract Example (v2)
```json
{
  "date": "2026-02-25",
  "topics": ["history"],
  "type": "which_came_first",
  "questions": [
    {
      "id": "33b21f44-4fab-5a57-88dd-c7ed41b5126f",
      "human_id": "Q412",
      "type": "which_came_first",
      "prompt": "Which event happened earlier?",
      "answer_fact_ids": [
        "3cdde5a2-a6b1-5df8-a804-2c0502a2ef5d",
        "5f9bc15e-1614-5278-b166-6d4f2964f823"
      ],
      "correct_answer_fact_id": "3cdde5a2-a6b1-5df8-a804-2c0502a2ef5d",
      "tags": ["history", "which_came_first"],
      "facets": { "topic": "history", "difficulty_band": "baseline" },
      "selection_rules": { "distractor_same_year_allowed": false }
    }
  ],
  "answer_facts": [
    {
      "id": "3cdde5a2-a6b1-5df8-a804-2c0502a2ef5d",
      "human_id": "A991",
      "label": "The RMS Titanic sinks in the Atlantic Ocean.",
      "year": 1912,
      "tags": ["history", "history_mcq_4", "role:correct", "20th-century", "1910s"],
      "facets": {
        "topic": "history",
        "temporal_century": "20th-century",
        "temporal_decade": "1910s",
        "source": "wikipedia_on_this_day"
      },
      "match": {
        "distractor_profile": {
          "year": 1912,
          "temporal_century": "20th-century",
          "temporal_decade": "1910s"
        }
      },
      "vector_metadata": {
        "text_for_embedding": "The RMS Titanic sinks in the Atlantic Ocean.",
        "embedding_status": "not_generated"
      }
    },
    {
      "id": "5f9bc15e-1614-5278-b166-6d4f2964f823",
      "human_id": "A992",
      "label": "Apollo 11 lands on the Moon.",
      "year": 1969,
      "tags": ["history", "which_came_first", "role:distractor", "20th-century", "1960s"],
      "facets": {
        "topic": "history",
        "temporal_century": "20th-century",
        "temporal_decade": "1960s",
        "source": "wikipedia_on_this_day"
      },
      "match": {
        "distractor_profile": {
          "year": 1969,
          "temporal_century": "20th-century",
          "temporal_decade": "1960s"
        }
      },
      "vector_metadata": {
        "text_for_embedding": "Apollo 11 lands on the Moon.",
        "embedding_status": "not_generated"
      }
    }
  ],
  "question": "Which event happened earlier?",
  "choices": [
    { "id": "A", "human_id": "A991", "label": "The RMS Titanic sinks in the Atlantic Ocean.", "year": 1912, "answer_fact_id": "3cdde5a2-a6b1-5df8-a804-2c0502a2ef5d" },
    { "id": "B", "human_id": "A992", "label": "Apollo 11 lands on the Moon.", "year": 1969, "answer_fact_id": "5f9bc15e-1614-5278-b166-6d4f2964f823" }
  ],
  "correct_choice_id": "A",
  "source": {
    "name": "Wikipedia On This Day",
    "url": "https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/events/2/25",
    "retrieved_at": "2026-02-25T06:00:00Z",
    "events_used": [
      {
        "event_id": "3cdde5a2-a6b1-5df8-a804-2c0502a2ef5d",
        "text": "The RMS Titanic sinks in the Atlantic Ocean.",
        "year": 1912,
        "wikipedia_url": "https://en.wikipedia.org/wiki/RMS_Titanic"
      },
      {
        "event_id": "5f9bc15e-1614-5278-b166-6d4f2964f823",
        "text": "Apollo 11 lands on the Moon.",
        "year": 1969,
        "wikipedia_url": "https://en.wikipedia.org/wiki/Apollo_11"
      }
    ]
  },
  "generation": {
    "mode": "daily",
    "edition": 1,
    "generated_at": "2026-02-25T06:00:00Z"
  },
  "metadata": {
    "version": 2,
    "normalized_model": "question_answer_facts_v1"
  }
}
```

Migration note:
- Existing historical files may still have `metadata.version = 1`.
- New generation output must use the v2 contract above.
- Running the human-id backfill mode may normalize legacy v1 payloads to v2.

`which_came_first` requirements:
- Exactly 2 choices.
- Each choice includes `id`, `label`, integer `year`, and `answer_fact_id`; optional `human_id` uses `A<integer>`.
- Choice years must be distinct.
- `question` must be: `Which event happened earlier?`
- `source.events_used` must contain exactly 2 entries.

`history_mcq_4` requirements:
- Exactly 4 choices.
- Each choice includes `id`, `label`, and `answer_fact_id`; optional `human_id` uses `A<integer>`.
- Choices must not include `year`.
- `question` must follow: `Which event happened in <year>?`
- `source.events_used` must contain exactly 4 entries.

`history_factoid_mcq_4` requirements:
- Exactly 4 choices.
- Each choice includes `id`, `label`, and `answer_fact_id`; optional `human_id` uses `A<integer>`.
- Choices must not include `year`.
- `question` must end with `?`.
- `questions[0].facets.question_format` must be `factoid`.
- `questions[0].facets.answer_kind` must be one of `person|place|organization|work|object|time`.
- `questions[0].facets.answer_subtype` must be a non-empty string.
- `questions[0].facets.prompt_style` must be one of `who|where|when|what|which` and align with `answer_kind`.
- `source.events_used` must contain exactly 4 entries.
- If present, `source.page_sources` must contain exactly 4 entries aligned by `answer_fact_id` with `source.events_used`.

## Validation Rules
- `date` must match the target UTC generation date (`YYYY-MM-DD`).
- `topics` must equal `['history']`.
- `type` must be one of enabled supported types.
- Choice ids must be unique and non-empty.
- Choice labels must be non-empty.
- `correct_choice_id` must match one of the choice ids.
- `choices[*].answer_fact_id` must be non-empty and aligned with `questions[0].answer_fact_ids` order.
- If present, `questions[0].human_id` must match `Q<integer>`.
- If present, `choices[*].human_id` and `answer_facts[*].human_id` must match `A<integer>` and align per `answer_fact_id`.
- Source attribution must be present and non-empty.
- `source.events_used` entries must include non-empty `event_id`, `text`, integer `year`, and non-empty `wikipedia_url`.
- If present, `source.page_sources` entries must include non-empty `answer_fact_id`, `page_url`, `page_title`, and `retrieved_at`.
- `generation.mode` must be `daily` when `generation.edition` is `1`.
- `generation.edition` must be integer `>= 1`.
- `generation.generated_at` must be UTC ISO-8601 with `Z`.
- `questions[0].correct_answer_fact_id` must match the fact linked by `correct_choice_id`.

## Reliability and Safety
- If generation fails, exit with non-zero status and do not commit partial output.
- If data is invalid, fail the workflow and do not commit.
- Keep logs minimal but clear (source URL used, file paths written, commit result).

## Repository Layout (Phase 1)
```text
.
├── .github/workflows/daily-quiz.yml
├── pyproject.toml
├── uv.lock
├── scripts/generate_quiz.py
└── quizzes/
```

## Acceptance Criteria
- A scheduled workflow runs once per day.
- One new file is created at `quizzes/<uuid>.json` per enabled quiz type when missing.
- Each file contains a valid supported history quiz with exactly one correct answer.
- Workflow commits and pushes new files.
- Re-running on the same day does not create duplicate files for existing date/type pairs.
