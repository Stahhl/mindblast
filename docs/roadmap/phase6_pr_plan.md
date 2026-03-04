# Phase 6 PR Plan: Quiz Feedback API

## Objective
Deliver Phase 6 (`quiz_feedback_v1`) in small, reviewable pull requests with clear gates.

## PR1: Backend MVP

Scope:
- [x] Add Firebase Functions service with `POST /api/quiz-feedback`.
- [x] Add Hosting rewrite for `/api/**` in `firebase.json` (before SPA catch-all).
- [x] Implement strict payload validation:
  - [x] `rating` integer `1..5`
  - [x] optional `comment` max 500 chars (trimmed)
  - [x] `quiz_type` in supported set
  - [x] `question_human_id` format `Q<integer>`
- [x] Implement server-issued anonymous `client_id` cookie:
  - [x] `HttpOnly`
  - [x] `SameSite=Lax`
  - [x] `Secure` in production
- [x] Implement deterministic upsert key:
  - [x] `(client_id, question_id, feedback_date_utc)`
- [x] Persist `created_at` and `updated_at`.
- [x] Return response shape `{ ok, mode, feedback_id }`.
- [x] Add backend tests for:
  - [x] valid create
  - [x] valid update (upsert path)
  - [x] invalid payload rejection

Exit criteria:
- Endpoint works end-to-end in local/staging with deterministic upsert behavior.

## PR2: Frontend Feedback UX

Scope:
- [x] Add feedback API client wrapper (`POST /api/quiz-feedback`).
- [x] Add quiz-card UI controls:
  - [x] `1..5` stars
  - [x] optional comment textarea
  - [x] submit/update action
- [x] Include quiz identity fields in request payload:
  - [x] `quiz_file`, `date`, `quiz_type`, `edition`
  - [x] `question_id`, `question_human_id`
- [x] Add UX states:
  - [x] saving
  - [x] saved
  - [x] updated
  - [x] retry/error
- [x] Optional local draft persistence per `question_id`.
- [x] Add frontend tests for submit/update/error flows.

Exit criteria:
- Users can submit and update feedback from quiz cards without blocking quiz play.

## PR3: Abuse Controls and Security Hardening

Scope:
- [x] Add layered rate limits:
  - [x] per client (`5/hour`, `20/day` initial)
  - [x] per IP (`60/hour` initial)
  - [x] global circuit breaker (`5000/hour` initial)
- [x] Enforce per `(client_id, question_id, feedback_date_utc)` one-create semantics.
- [x] Add App Check verification for production requests.
- [x] Add strict CORS/origin allowlist (staging + production domains).
- [x] Add Firestore rules:
  - [x] deny direct client writes to `quiz_feedback`
- [x] Add structured rejection logs:
  - [x] `invalid_payload`
  - [x] `rate_limited`
  - [x] `app_check_failed`
- [x] Add feature flags:
  - [x] disable comments
  - [x] disable all feedback writes
- [x] Add backend tests for rate-limited and gated request paths.

Exit criteria:
- Basic scripted spam attempts are throttled and do not cause unbounded write growth.

## PR4: Staging Validation and Operations

Scope:
- [x] Upgrade `mindblast-staging` to Blaze (pay-as-you-go) so backend APIs can be enabled.
- [x] Apply Terraform infra updates in staging (backend APIs + CI IAM roles).
- [x] Deploy `quizFeedbackApi` + Firestore rules/indexes to staging
  (`functions:feedback-api:quizFeedbackApi` codebase selector).
- [x] Run staged load/sanity script for feedback submission bursts.
- [x] Validate:
  - [x] create/update behavior under repeated submits
  - [x] rate-limit enforcement
  - [x] reject reason logging visibility
- [x] Produce rollout notes + rollback procedure.
- [x] Document incident kill-switch usage.

Current status (2026-03-04):
- Blaze/billing blocker resolved; backend APIs required by Functions v2 are enabled.
- Terraform staging reconciliation completed (`terraform plan`: no changes).
- Staging public API route is intentionally disabled after PR4 verification:
  - Hosting rewrite `/api/** -> quizFeedbackApi` removed from staging target,
  - direct function/service URLs return `403` without invoker permission.
- `quizFeedbackApi` is deployed but not publicly invokable (no `allUsers` invoker binding).
- Staging runtime keeps App Check in `off` mode via auto-detection for known staging
  project (`mindblast-staging`) while production stays strict in `auto`.

Validation evidence (2026-03-04 UTC):
- Smoke test requests (same cookie/question/day) returned:
  - `200 created` on first submit
  - `200 updated` on repeated submits
  - `429 rate_limited` on requests `#6` and `#7` with `Retry-After` header
- Firestore document verified:
  - `quiz_feedback/fdbk_c02ba08de8e438b75ce1454990a9012a`
  - `created_at` and later `updated_at` values present, same deterministic ID across updates
- Cloud Logging verification:
  - Request status counts in smoke window: `200 x 5`, `429 x 2`, `5xx x 0`
  - Reject reasons in smoke window: `rate_limited x 2`
- Rollout/rollback runbook:
  - `docs/roadmap/phase6_rollout_runbook.md`

Exit criteria:
- Staging validation evidence is attached and production rollout checklist is approved.

## Merge Order
1. PR1 (backend MVP)
2. PR2 (frontend UX)
3. PR3 (hardening)
4. PR4 (staging validation + operations)

## Definition of Done
- [ ] Feedback can be created/updated from the UI.
- [ ] One logical feedback record per `(client_id, question_id, day)` is enforced.
- [ ] Abuse controls are active and tested.
- [ ] Endpoint failures never block quiz gameplay.
- [x] Staging validation complete and runbook documented.
