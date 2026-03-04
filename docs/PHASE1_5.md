# Phase 1.5 Specification: Discovery Layer for Static Clients

## Naming
- Project name: `Mindblast`.
- User-facing app name: `Mindblast`.
- Backend generator service name: `quiz-forge`.

## Objective
Add a lightweight discovery/index layer so clients can find daily quiz files without needing to know UUID filenames.

## Scope (Phase 1.5)
- Keep current quiz generation behavior from `docs/PHASE1.md`.
- Add deterministic index artifacts after successful daily generation.
- Keep everything file-based in this repository (no always-on backend API).

## Out of Scope
- User authentication.
- Score persistence beyond local client state.
- Leaderboards, achievements, and streaks.
- Personalized quiz feeds.

## Discovery Artifacts

### Daily Index
- Path: `quizzes/index/YYYY-MM-DD.json`
- Exactly one index file per UTC date that has generated quizzes.
- Contains pointers to quiz files for that date, including multiple same-day editions.
- `quiz_files` remains as a compatibility map for clients that only support one file per type.

Example:
```json
{
  "date": "2026-02-22",
  "quizzes_by_type": {
    "which_came_first": [
      {
        "edition": 1,
        "mode": "daily",
        "quiz_file": "quizzes/23a13cb0-49ae-594b-b85b-fe17817dbd33.json",
        "generated_at": "2026-02-22T06:00:00Z"
      }
    ],
    "history_mcq_4": [
      {
        "edition": 1,
        "mode": "daily",
        "quiz_file": "quizzes/137b933b-c96b-5794-b985-4e60a04f1b8d.json",
        "generated_at": "2026-02-22T06:00:00Z"
      },
      {
        "edition": 2,
        "mode": "extra",
        "quiz_file": "quizzes/8de3029a-38ec-5ed0-a530-3a8e3d1f00b2.json",
        "generated_at": "2026-02-22T12:00:00Z"
      }
    ]
  },
  "quiz_files": {
    "which_came_first": "quizzes/23a13cb0-49ae-594b-b85b-fe17817dbd33.json",
    "history_mcq_4": "quizzes/137b933b-c96b-5794-b985-4e60a04f1b8d.json"
  },
  "available_types": ["which_came_first", "history_mcq_4"],
  "metadata": {
    "version": 2,
    "generated_at": "2026-02-22T06:00:00Z"
  }
}
```

### Latest Pointer
- Path: `quizzes/latest.json`
- Points to the newest available UTC date index.

Example:
```json
{
  "date": "2026-02-22",
  "index_file": "quizzes/index/2026-02-22.json",
  "available_types": ["which_came_first", "history_mcq_4"],
  "latest_quiz_by_type": {
    "which_came_first": "quizzes/23a13cb0-49ae-594b-b85b-fe17817dbd33.json",
    "history_mcq_4": "quizzes/8de3029a-38ec-5ed0-a530-3a8e3d1f00b2.json"
  },
  "metadata": {
    "version": 2,
    "updated_at": "2026-02-22T06:00:00Z"
  }
}
```

### Human ID Lookup
- Path: `quizzes/human_id_lookup.json`
- Append-only lookup for support/debugging aliases:
  - question aliases: `Q<integer>` -> question UUID + quiz file path
  - answer aliases: `A<integer>` -> answer-fact UUID
- Counters only advance when a new quiz file is generated.
- No rewrite on no-op reruns.

Example:
```json
{
  "metadata": {
    "version": 1,
    "updated_at": "2026-02-22T06:00:00Z"
  },
  "counters": {
    "question": 412,
    "answer": 992
  },
  "question_uuid_to_human_id": {
    "33b21f44-4fab-5a57-88dd-c7ed41b5126f": "Q412"
  },
  "answer_uuid_to_human_id": {
    "3cdde5a2-a6b1-5df8-a804-2c0502a2ef5d": "A991",
    "5f9bc15e-1614-5278-b166-6d4f2964f823": "A992"
  },
  "questions": {
    "Q412": {
      "question_id": "33b21f44-4fab-5a57-88dd-c7ed41b5126f",
      "quiz_file": "quizzes/23a13cb0-49ae-594b-b85b-fe17817dbd33.json",
      "date": "2026-02-22",
      "quiz_type": "which_came_first",
      "edition": 1
    }
  },
  "answers": {
    "A991": {
      "answer_fact_id": "3cdde5a2-a6b1-5df8-a804-2c0502a2ef5d",
      "label": "The RMS Titanic sinks in the Atlantic Ocean.",
      "year": 1912
    }
  }
}
```

## Generation Rules
- Write/update the date index for the target date only after quiz payload validation succeeds.
- Update `quizzes/latest.json` only when the target date is newer than the currently referenced date.
- Update `quizzes/human_id_lookup.json` only when at least one new quiz file is created.
- Backfill mode (`--backfill-human-ids`) may normalize legacy `metadata.version = 1` quiz payloads to v2 before assigning human IDs.
- If a rerun is for the same date and content is unchanged, do not create an unnecessary commit.
- Fail closed if index files would reference missing quiz files.
- During schema migration, index files may reference a mix of quiz payload versions (`metadata.version` 1 and 2).

## CI/CD Behavior
- Continue using the current scheduled GitHub Actions workflow.
- Commit/push only when quiz or discovery files changed.
- Commit message may stay date-based (same as current Phase 1 behavior).

## Validation Rules
- `date` fields must be valid UTC dates in `YYYY-MM-DD`.
- `quizzes_by_type` keys must be known enabled types.
- `quiz_files` keys must be known enabled types (compatibility view).
- Every `quiz_files` path must exist in the repository at generation time.
- Every `quizzes_by_type[*][*].quiz_file` path must exist in the repository at generation time.
- `available_types` must match `quizzes_by_type` keys.
- Metadata timestamps must be UTC ISO-8601 strings with `Z`.

## Acceptance Criteria
- For each generated UTC date, `quizzes/index/YYYY-MM-DD.json` exists and correctly references all generated quiz types for that date.
- `quizzes/latest.json` always points to the newest indexed UTC date.
- A static client can discover and load today's quizzes by fetching:
  1. `quizzes/latest.json`
  2. the referenced daily index
  3. referenced quiz files
