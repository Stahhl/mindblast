# Phase 6 Specification: Quiz Feedback API (`quiz_feedback_v1`)

## Naming
- Project name: `Mindblast`.
- User-facing app name: `Mindblast`.
- Backend generator service name: `quiz-forge`.

## Objective
Ship a minimal feedback loop where users can rate a quiz card (question + answers together) using:
- a required `1..5` star rating,
- an optional text comment.

The goal is to collect useful quality signals tied to stable quiz identifiers (`quiz_file`, `question_id`, `question_human_id`) without requiring user auth in this phase.

## Why This Phase
- We need fast quality feedback from real users to improve quiz generation quality.
- Human-friendly IDs (`Q...`, `A...`) now support direct triage ("`Q1324` looked wrong").
- Existing static-only architecture has no write path, so feedback requires a small backend endpoint.

## Scope (Phase 6)
- Add one backend write endpoint:
  - `POST /api/quiz-feedback`
- Persist feedback records in Firebase-backed storage (Firestore).
- Add frontend UI controls on each quiz card:
  - `1..5` stars,
  - optional comment,
  - submit/update status.
- Enforce abuse controls suitable for unauthenticated clients.
- Keep endpoint and schema intentionally small and deterministic.

## Out of Scope
- User accounts/login.
- Public comments feed.
- Complex moderation tooling.
- Recommendation/personalization logic.
- Analytics dashboards beyond raw stored feedback.

## Architecture
- Hosting remains Firebase Hosting.
- Add HTTP backend via Firebase Functions (or Cloud Run behind Hosting rewrite).
- Route API via same origin:
  - `/api/**` -> backend
- Continue serving quiz payloads statically from `/quizzes/**`.
- Follow backend portability guardrails in `docs/BACKEND_SERVICE_DESIGN.md` (ports/adapters, Firebase as infrastructure adapter only).

## Infra Prerequisites
- Enable backend APIs in each environment project:
  - `cloudfunctions.googleapis.com`
  - `run.googleapis.com`
  - `cloudbuild.googleapis.com`
  - `artifactregistry.googleapis.com`
  - `eventarc.googleapis.com`
  - `firestore.googleapis.com`
- Ensure each Firebase project is on Blaze (pay-as-you-go), otherwise
  `run/cloudbuild/artifactregistry` cannot be enabled and Functions v2 deploy is blocked.
- Ensure CI deploy service account has:
  - `roles/cloudfunctions.admin`
  - `roles/iam.serviceAccountUser`
  - existing Hosting roles from prior phases.
- Apply Terraform for staging/production before first backend deploy.

## Data Model (`quiz_feedback_v1`)

One logical feedback record per `(client_id, question_id, feedback_date_utc)`.

Required fields:
- `schema_version`: `1`
- `quiz_file`: repository path to quiz payload (`quizzes/<uuid>.json`)
- `date`: quiz date (`YYYY-MM-DD`)
- `quiz_type`: one of supported quiz types
- `edition`: integer `>= 1`
- `question_id`: UUID from `questions[0].id`
- `question_human_id`: `Q<integer>`
- `rating`: integer `1..5`
- `feedback_date_utc`: `YYYY-MM-DD` date bucket used for uniqueness/rate limiting
- `client_id`: server-derived anonymous identifier
- `created_at`: UTC ISO-8601
- `updated_at`: UTC ISO-8601

Optional fields:
- `comment`: string, trimmed, max 500 chars
- `source`: `"web"` (default in this phase)
- `user_agent_hash`: optional hash for abuse diagnostics

## Endpoint Contract

### `POST /api/quiz-feedback`

Request body:
```json
{
  "quiz_file": "quizzes/23a13cb0-49ae-594b-b85b-fe17817dbd33.json",
  "date": "2026-02-22",
  "quiz_type": "which_came_first",
  "edition": 1,
  "question_id": "bcdf8161-5029-578f-970c-54e87cfe0085",
  "question_human_id": "Q1",
  "rating": 4,
  "comment": "Nice question, but distractor B was too obvious."
}
```

Success response:
```json
{
  "ok": true,
  "mode": "created",
  "feedback_id": "fdbk_..."
}
```

Upsert response when same `(client_id, question_id, feedback_date_utc)` exists:
```json
{
  "ok": true,
  "mode": "updated",
  "feedback_id": "fdbk_..."
}
```

Validation error response:
```json
{
  "ok": false,
  "error": "invalid_payload",
  "details": "rating must be an integer from 1 to 5"
}
```

Rate-limited response:
```json
{
  "ok": false,
  "error": "rate_limited"
}
```

## Unauthenticated Abuse Controls (Required)

No-auth endpoints are spammable by default. Phase 6 must include all controls below.

### 1) Server-derived client identity
- Do not trust client-provided identity fields.
- Server issues and reads anonymous `client_id` from secure cookie.
- Cookie policy:
  - `HttpOnly`
  - `SameSite=Lax`
  - `Secure` in production

### 2) Idempotent write shape
- Use upsert, not append:
  - one document per `(client_id, question_id, feedback_date_utc)`.
- Re-submission updates rating/comment instead of creating a new row.

### 3) Layered rate limits
- Per client: e.g. `5/hour`, `20/day`.
- Per IP: e.g. `60/hour`.
- Global circuit breaker: e.g. `5000/hour` to protect cost and stability.
- Per question/client/day uniqueness:
  - max `1 create`; updates allowed.

### 4) Request gating
- Require App Check verification for web requests in production.
- Enforce same-origin policy/CORS allowlist for deployed domains only.
- Reject requests with invalid/missing content type or oversized payload.

### 5) Input hardening
- Strict JSON allowlist for accepted fields.
- `rating`: integer only, `1..5`.
- `comment`: optional, trimmed, max 500 chars.
- Ignore/strip unsupported fields.

### 6) Monitoring + kill switch
- Log reject reasons (`invalid_payload`, `rate_limited`, `app_check_failed`).
- Alert on sudden spikes.
- Feature flags:
  - disable comments while keeping star ratings.
  - disable feedback writes globally if incident occurs.
- Operational use (staging/production):
  - current reliable path is hotfix default toggles in
    `src/apps/feedback-api/src/application/runtime_config.ts` plus redeploy.
  - write stop: set `writeEnabled` fallback to `false`, redeploy.
  - comments-only stop: set `commentsEnabled` fallback to `false`, redeploy.

## Storage and Indexing
- Collection: `quiz_feedback`.
- Deterministic `feedback_id`:
  - hash of `(client_id + question_id + feedback_date_utc)`.
- Suggested indexes:
  - `(question_id, updated_at desc)`
  - `(quiz_file, updated_at desc)`
  - `(rating, updated_at desc)` for coarse quality scans.

## Frontend Behavior
- Render star selector and optional comment input on each quiz card.
- Submit button sends `POST /api/quiz-feedback`.
- Show status:
  - `Saved`
  - `Updated`
  - `Retry` on transient failure
- Optional local draft persistence (per `question_id`) is allowed.
- Do not block quiz play if feedback endpoint fails.

## Validation Rules
- `quiz_file` must match `quizzes/*.json`.
- `date` must match `YYYY-MM-DD`.
- `quiz_type` must be a known supported type.
- `edition` must be integer `>= 1`.
- `question_id` must be non-empty UUID string.
- `question_human_id` must match `Q<integer>`.
- `rating` must be integer `1..5`.
- `comment` max length 500 after trim.

## Security Rules and Access
- Direct client writes to Firestore feedback collection are disallowed.
- Backend service account writes feedback documents.
- Read policy for feedback data remains internal-only in Phase 6.

## Rollout Plan
1. Docs-first: approve this Phase 6 contract.
2. Add backend endpoint with strict validation and rate limiting.
3. Add Hosting rewrite for `/api/**`.
4. Add frontend rating/comment UI and submission flow.
5. Add backend tests:
   - validation failures,
   - upsert behavior,
   - rate-limit enforcement.
6. Add frontend tests for submit/update/error states.
7. Ensure staging Firebase project billing is enabled (Blaze).
8. Apply infra updates (APIs + IAM) in staging.
9. Deploy function + Firestore rules/indexes to staging and monitor reject/error rates.
10. Promote to production with comments enabled behind feature flag.

## Acceptance Criteria
- Users can submit `1..5` rating and optional comment per quiz card.
- Re-submission on same day updates existing feedback instead of duplicating.
- Feedback records store quiz/question identifiers, including `question_human_id`.
- Abuse controls are active (client, IP, and global rate limits).
- Endpoint remains operational under basic spam attempts without unbounded write growth.
- Frontend remains functional when feedback endpoint is unavailable.

## Known Limitations
- Without user auth, one-person-one-vote cannot be guaranteed.
- Controls are deterrence and containment, not perfect prevention.
- Stronger guarantees require authenticated identities in a future phase.
