# Phase 6 PR Plan: Quiz Feedback API

## Objective
Deliver Phase 6 (`quiz_feedback_v1`) in small, reviewable pull requests with clear gates.

## PR1: Backend MVP

Scope:
- [ ] Add Firebase Functions service with `POST /api/quiz-feedback`.
- [ ] Add Hosting rewrite for `/api/**` in `firebase.json` (before SPA catch-all).
- [ ] Implement strict payload validation:
  - [ ] `rating` integer `1..5`
  - [ ] optional `comment` max 500 chars (trimmed)
  - [ ] `quiz_type` in supported set
  - [ ] `question_human_id` format `Q<integer>`
- [ ] Implement server-issued anonymous `client_id` cookie:
  - [ ] `HttpOnly`
  - [ ] `SameSite=Lax`
  - [ ] `Secure` in production
- [ ] Implement deterministic upsert key:
  - [ ] `(client_id, question_id, feedback_date_utc)`
- [ ] Persist `created_at` and `updated_at`.
- [ ] Return response shape `{ ok, mode, feedback_id }`.
- [ ] Add backend tests for:
  - [ ] valid create
  - [ ] valid update (upsert path)
  - [ ] invalid payload rejection

Exit criteria:
- Endpoint works end-to-end in local/staging with deterministic upsert behavior.

## PR2: Frontend Feedback UX

Scope:
- [ ] Add feedback API client wrapper (`POST /api/quiz-feedback`).
- [ ] Add quiz-card UI controls:
  - [ ] `1..5` stars
  - [ ] optional comment textarea
  - [ ] submit/update action
- [ ] Include quiz identity fields in request payload:
  - [ ] `quiz_file`, `date`, `quiz_type`, `edition`
  - [ ] `question_id`, `question_human_id`
- [ ] Add UX states:
  - [ ] saving
  - [ ] saved
  - [ ] updated
  - [ ] retry/error
- [ ] Optional local draft persistence per `question_id`.
- [ ] Add frontend tests for submit/update/error flows.

Exit criteria:
- Users can submit and update feedback from quiz cards without blocking quiz play.

## PR3: Abuse Controls and Security Hardening

Scope:
- [ ] Add layered rate limits:
  - [ ] per client (`5/hour`, `20/day` initial)
  - [ ] per IP (`60/hour` initial)
  - [ ] global circuit breaker (`5000/hour` initial)
- [ ] Enforce per `(client_id, question_id, feedback_date_utc)` one-create semantics.
- [ ] Add App Check verification for production requests.
- [ ] Add strict CORS/origin allowlist (staging + production domains).
- [ ] Add Firestore rules:
  - [ ] deny direct client writes to `quiz_feedback`
- [ ] Add structured rejection logs:
  - [ ] `invalid_payload`
  - [ ] `rate_limited`
  - [ ] `app_check_failed`
- [ ] Add feature flags:
  - [ ] disable comments
  - [ ] disable all feedback writes
- [ ] Add backend tests for rate-limited and gated request paths.

Exit criteria:
- Basic scripted spam attempts are throttled and do not cause unbounded write growth.

## PR4: Staging Validation and Operations

Scope:
- [ ] Run staged load/sanity script for feedback submission bursts.
- [ ] Validate:
  - [ ] create/update behavior under repeated submits
  - [ ] rate-limit enforcement
  - [ ] reject reason logging visibility
- [ ] Produce rollout notes + rollback procedure.
- [ ] Document incident kill-switch usage.

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
- [ ] Staging validation complete and runbook documented.
