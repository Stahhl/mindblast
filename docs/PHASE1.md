# Phase 1 Specification: quiz-forge (Daily History Quizzes)

## Naming
- Project name: `Mindblast`.
- User-facing app name: `Mindblast`.
- Backend generator service name: `quiz-forge`.

## Objective
Build a minimal `quiz-forge` service for `Mindblast` that generates deterministic daily history quizzes and stores them as JSON in this repository.

## Scope (Phase 1)
- One repository: `quiz-forge`.
- One scheduled CI workflow in GitHub Actions.
- Generate exactly **1** quiz per enabled type per UTC day.
- Enabled types:
  - `which_came_first`
  - `history_mcq_4`
- Each quiz has exactly **1** correct answer.
- Output is committed and pushed back to the repo as JSON.

## Out of Scope (for now)
- User-facing app.
- Leaderboards, achievements, and ratings.
- Multiple quizzes per type per day.
- Non-history categories.
- Non-Wikipedia content sources.

## Content Source
- Use Wikipedia via Wikimedia On This Day API:
  - `https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/events/{month}/{day}`
- The generator selects valid events from that payload and builds each enabled quiz type.

## Workflow Requirements
- Primary trigger type: `schedule`.
- Recommended schedule: once daily in UTC (example: `0 6 * * *`).
- Manual dispatch is allowed for operational retries/backfills.

## Output Format
- Store one JSON file per enabled quiz type per UTC day:
  - `quizzes/<uuid>.json`
- `<uuid>` must be a deterministic UUIDv5 derived from `date + quiz_type`.
- If a file for a date/type already exists, do not create duplicates.
- Commit only when at least one new file is created.

### JSON Contract (v1)
Common fields for all types:
- `date`: `YYYY-MM-DD` UTC date.
- `topics`: exactly `['history']`.
- `type`: quiz type identifier.
- `question`: non-empty string.
- `choices`: non-empty array.
- `correct_choice_id`: one of the choice ids.
- `source.name`, `source.url`, `source.retrieved_at`: non-empty strings.
- `source.events_used`: array of source events (`text`, `year`, `wikipedia_url`).
- `metadata.version`: `1`.

`which_came_first` requirements:
- Exactly 2 choices.
- Each choice includes `id`, `label`, and integer `year`.
- Choice years must be distinct.
- `question` must be: `Which event happened earlier?`
- `source.events_used` must contain exactly 2 entries.

`history_mcq_4` requirements:
- Exactly 4 choices.
- Each choice includes `id` and `label`.
- Choices must not include `year`.
- `question` must follow: `Which event happened in <year>?`
- `source.events_used` must contain exactly 4 entries.

## Validation Rules
- `date` must match the target UTC generation date (`YYYY-MM-DD`).
- `topics` must equal `['history']`.
- `type` must be one of enabled supported types.
- Choice ids must be unique and non-empty.
- Choice labels must be non-empty.
- `correct_choice_id` must match one of the choice ids.
- Source attribution must be present and non-empty.
- `source.events_used` entries must include non-empty `text`, integer `year`, and non-empty `wikipedia_url`.

## Reliability and Safety
- If generation fails, exit with non-zero status and do not commit partial output.
- If data is invalid, fail the workflow and do not commit.
- Keep logs minimal but clear (source URL used, file paths written, commit result).

## Repository Layout (Phase 1)
```text
.
├── .github/workflows/daily-quiz.yml
├── scripts/generate_quiz.py
└── quizzes/
```

## Acceptance Criteria
- A scheduled workflow runs once per day.
- One new file is created at `quizzes/<uuid>.json` per enabled quiz type when missing.
- Each file contains a valid supported history quiz with exactly one correct answer.
- Workflow commits and pushes new files.
- Re-running on the same day does not create duplicate files for existing date/type pairs.
