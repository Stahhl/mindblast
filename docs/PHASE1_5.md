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
- Contains pointers to the quiz files for that date.

Example:
```json
{
  "date": "2026-02-22",
  "quiz_files": {
    "which_came_first": "quizzes/23a13cb0-49ae-594b-b85b-fe17817dbd33.json",
    "history_mcq_4": "quizzes/137b933b-c96b-5794-b985-4e60a04f1b8d.json"
  },
  "available_types": ["which_came_first", "history_mcq_4"],
  "metadata": {
    "version": 1,
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
  "metadata": {
    "version": 1,
    "updated_at": "2026-02-22T06:00:00Z"
  }
}
```

## Generation Rules
- Write/update the date index for the target date only after quiz payload validation succeeds.
- Update `quizzes/latest.json` only when the target date is newer than the currently referenced date.
- If a rerun is for the same date and content is unchanged, do not create an unnecessary commit.
- Fail closed if index files would reference missing quiz files.
- During schema migration, index files may reference a mix of quiz payload versions (`metadata.version` 1 and 2).

## CI/CD Behavior
- Continue using the current scheduled GitHub Actions workflow.
- Commit/push only when quiz or discovery files changed.
- Commit message may stay date-based (same as current Phase 1 behavior).

## Validation Rules
- `date` fields must be valid UTC dates in `YYYY-MM-DD`.
- `quiz_files` keys must be known enabled types.
- Every `quiz_files` path must exist in the repository at generation time.
- `available_types` must match `quiz_files` keys.
- Metadata timestamps must be UTC ISO-8601 strings with `Z`.

## Acceptance Criteria
- For each generated UTC date, `quizzes/index/YYYY-MM-DD.json` exists and correctly references all generated quiz types for that date.
- `quizzes/latest.json` always points to the newest indexed UTC date.
- A static client can discover and load today's quizzes by fetching:
  1. `quizzes/latest.json`
  2. the referenced daily index
  3. referenced quiz files
