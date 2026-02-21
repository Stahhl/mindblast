# Phase 1 Specification: quiz-forge ("Which Came First?")

## Naming
- Project name: `Mindblast`.
- User-facing app name: `Mindblast`.
- Backend generator service name: `quiz-forge`.

## Objective
Build a minimal `quiz-forge` service for `Mindblast` that generates **one** daily history "Which came first?" question and stores it as JSON in this same repository.

## Scope (Phase 1)
- One repository: `quiz-forge`.
- One scheduled CI workflow in GitHub Actions.
- Generate exactly **1** history question per day.
- Question type is exactly `which_came_first`.
- Each question has **2** candidate events and exactly **1** correct answer.
- Output is committed and pushed back to the repo as JSON.

## Out of Scope (for now)
- User-facing app.
- Leaderboards, achievements, and ratings.
- Multiple questions per day.
- Non-history categories.
- Non-Wikipedia content sources.

## Content Source
- Use Wikipedia via Wikimedia On This Day API:
  - `https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/events/{month}/{day}`
- The generator selects two valid events and builds one comparison question.

## Workflow Requirements
- Trigger type: `schedule` only.
- No trigger on push, pull request, or manual dispatch in Phase 1.
- Recommended schedule: once daily in UTC (example: `0 6 * * *`).

## Output Format
- Store one JSON file per day:
  - `quizzes/YYYY-MM-DD.json`
- If today's file already exists, do not create duplicates.
- Commit only when a new file is created.

### JSON Contract (v1)
```json
{
  "date": "2026-02-21",
  "topics": ["history"],
  "type": "which_came_first",
  "question": "Which event happened earlier?",
  "choices": [
    {
      "id": "A",
      "label": "Apollo 11 lands on the Moon",
      "year": 1969
    },
    {
      "id": "B",
      "label": "The first modern Olympic Games open in Athens",
      "year": 1896
    }
  ],
  "correct_choice_id": "B",
  "source": {
    "name": "Wikipedia On This Day",
    "url": "https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/events/2/21",
    "retrieved_at": "2026-02-21T06:00:00Z",
    "events_used": [
      {
        "text": "Apollo 11 lands on the Moon.",
        "year": 1969,
        "wikipedia_url": "https://en.wikipedia.org/wiki/Apollo_11"
      },
      {
        "text": "The first modern Olympic Games open in Athens.",
        "year": 1896,
        "wikipedia_url": "https://en.wikipedia.org/wiki/1896_Summer_Olympics"
      }
    ]
  },
  "metadata": {
    "version": 1
  }
}
```

## Validation Rules
- `topics` must be an array with exactly one value in Phase 1: `["history"]`.
- `type` must be `which_came_first`.
- `choices` must contain exactly 2 objects with unique `id` values.
- Each choice must include non-empty `label` and integer `year`.
- `correct_choice_id` must match one of the choice `id` values.
- `year` values must not be equal (no tie questions in Phase 1).
- `question` must be non-empty.
- `date` must match file date (`YYYY-MM-DD`).

## Reliability and Safety
- If generation fails, exit with non-zero status and do not commit partial output.
- If data is invalid, fail the workflow and do not commit.
- Keep logs minimal but clear (source URL used, file path written, commit result).

## Repository Layout (Phase 1)
```text
.
├── .github/workflows/daily-quiz.yml
├── scripts/generate_quiz.py
└── quizzes/
```

## Acceptance Criteria
- A scheduled workflow runs once per day.
- One new file is created at `quizzes/YYYY-MM-DD.json`.
- File contains one valid `which_came_first` history question with exactly two choices and one correct answer.
- Workflow commits and pushes the new file.
- Re-running on the same day does not create a duplicate file or unnecessary commit.
