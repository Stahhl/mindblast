# Phase 10 Specification: Signed-In Cross-Device Persistence

## Naming
- Project name: `Mindblast`.
- User-facing app name: `Mindblast`.
- Backend generator service name: `quiz-forge`.

## Objective
Persist signed-in user progress and feedback draft state across devices while keeping public quiz content static and preserving the existing authenticated backend write boundary.

## Scope
- Sync quiz answer/progress state per authenticated user, quiz date, and question.
- Sync feedback draft state per authenticated user and question.
- Read back a user's existing submitted feedback state from `quiz_feedback`.
- Keep Firestore direct client access denied; browser clients use authenticated `/api/**` routes only.

## Data Minimization Contract
User-state records store identifiers and state only:
- `auth_uid`
- `date`
- `quiz_file`
- `quiz_type`
- `edition`
- `question_id`
- `question_human_id`
- `selected_choice_id`
- timestamps
- feedback draft `rating` and optional `comment`

User-state records must not copy question text, answer labels, Wikipedia event text, source URLs, generated/synthetic content, or source attribution payloads. The source of truth for quiz content remains the static quiz JSON artifact referenced by `quiz_file`.

## API Contract
Routes are served by the existing Firebase Function behind Firebase Hosting rewrites.

### `GET /api/user-quiz-state?date=YYYY-MM-DD&question_ids=<csv>`
Returns signed-in state for the authenticated user only:
```json
{
  "ok": true,
  "date": "2026-03-04",
  "answers": [],
  "feedback_drafts": [],
  "feedback_submissions": []
}
```

### `PUT /api/user-quiz-state`
Upserts answer state and/or feedback draft state:
```json
{
  "quiz_file": "quizzes/abc123.json",
  "date": "2026-03-04",
  "quiz_type": "history_mcq_4",
  "edition": 1,
  "question_id": "123e4567-e89b-42d3-a456-426614174000",
  "question_human_id": "Q42",
  "selected_choice_id": "A",
  "feedback_draft": {
    "rating": 4,
    "comment": "Nice question"
  }
}
```

Both routes require:
- `X-Firebase-ID-Token`
- `X-Firebase-AppCheck`
- allowed origin
- existing per-user, per-IP, and global rate limits

## Storage
- Answer state: `user_quiz_state/{auth_uid}/dates/{date}/items/{question_id}`
- Draft state: `user_feedback_drafts/{auth_uid}/questions/{question_id}`
- Submitted feedback readback: existing `quiz_feedback` records filtered by authenticated user and question IDs.

All collections are backend-only in Firestore rules.

## Privacy And Compliance
- Feedback comments are user-provided content and must remain private.
- No public feed, client-side Firestore reads, or raw comment export with `auth_uid`.
- User-state deletion by `auth_uid` is required before shipping account deletion/self-service privacy tooling.
- This phase does not add new content sources and does not alter source licensing obligations.

## Acceptance Criteria
- Signed-out users retain local-only progress behavior.
- Signed-in users can reload another device and see saved answers, feedback drafts, and prior submitted feedback state.
- Persistence failures do not block quiz play.
- Direct Firestore client access remains denied.
- Backend and frontend tests/builds pass.
