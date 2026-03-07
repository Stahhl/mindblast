# Phase 7 PR Plan: Authenticated Feedback API (`quiz_feedback_v2`)

## Objective
Deliver Phase 7 in small, reviewable PRs that align directly with `docs/PHASE7.md` and keep abuse/cost risk bounded during rollout.

Status snapshot (as of 2026-03-06):
- Checked items are implemented and validated locally.
- Unchecked items are pending environment rollout/verification.

## Dependency
- Phase 6 feedback endpoint is live.
- Phase 6.5 Terraform IAM/invoker parameterization is in place.
- Phase 7.5 (`docs/PHASE7_5.md`) handles edge hardening before production exposure.

## PR1: Infra Prerequisites and Access Baseline

Maps to Phase 7 sections:
- `Infra Prerequisites`
- `Architecture`

Scope:
- [x] Ensure Firebase Auth prerequisites are enabled per environment (including Identity Toolkit API where required).
- [x] Verify Terraform-driven invoker posture remains private by default (no public direct backend URL access).
- [x] Confirm environment config explicitly captures:
  - [x] App Check enforcement intent
  - [x] `/api/**` Hosting rewrite exposure intent
  - [x] auth-required mode intent
- [x] Update infra docs/examples to reflect Phase 7 auth-era baseline.
- [x] Verify Firebase Auth Google provider is enabled in staging (manual console step).
- [x] Verify Firebase Auth Google provider is enabled in production (manual console step).

Exit criteria:
- Auth and access prerequisites are source-controlled, documented, and reproducible via Terraform + environment config.

## PR2: Backend Identity and Access Contract

Maps to Phase 7 sections:
- `Identity and Access Contract`
- `Validation Rules`
- `Abuse and Cost Controls (Required)`

Scope:
- [x] Add Firebase ID token verification for `POST /api/quiz-feedback`.
- [x] Enforce App Check verification on write path per environment policy.
- [x] Keep allowed-origin checks and existing rate limits in the request path.
- [x] Return contract-specific status codes:
  - [x] missing/invalid ID token -> `401`
  - [x] missing/invalid App Check -> `403`
  - [x] disallowed origin -> `403`
- [x] Add backend tests for auth/app-check failure and success paths.

Exit criteria:
- Backend write path accepts only authenticated + attested requests, with contract-accurate error behavior.

## PR3: Data Model Migration to `quiz_feedback_v2`

Maps to Phase 7 sections:
- `Data Model (quiz_feedback_v2)`
- `Validation Rules`

Scope:
- [x] Add `schema_version = 2` to new/updated feedback writes.
- [x] Store authenticated identity fields:
  - [x] `auth_uid`
  - [x] `auth_provider`
  - [x] `auth_verified_at`
- [x] Switch upsert uniqueness key to `(auth_uid, question_id, feedback_date_utc)`.
- [x] Keep legacy `client_id` as compatibility-only during migration window.
- [x] Add tests for deterministic update semantics under authenticated identity.

Exit criteria:
- Feedback uniqueness and update behavior are keyed by authenticated user identity.

## PR4: Frontend Auth Integration

Maps to Phase 7 sections:
- `Frontend Behavior`

Scope:
- [x] Add Firebase Auth client bootstrap for web.
- [x] Add minimal Google sign-in/sign-out UX for feedback actions.
- [x] Attach ID token + App Check token to feedback write requests.
- [x] Handle auth-required UX states:
  - [x] signed-out prompt
  - [x] token fetch failure
  - [ ] expired session retry
- [x] Preserve quiz play when auth/feedback path is unavailable.

Exit criteria:
- Signed-in users can submit/update feedback; signed-out users get clear guidance without breaking gameplay.

## PR5: Staging Rollout and Validation

Maps to Phase 7 sections:
- `Rollout Plan`

Scope:
- [x] Re-enable staging Hosting rewrite `/api/** -> quizFeedbackApi`.
- [x] Verify direct backend URLs remain non-public.
- [ ] Run staging smoke tests:
  - [ ] unauthenticated request rejected (`401`)
  - [ ] auth without valid App Check rejected (`403`)
  - [ ] authenticated + valid App Check request accepted
  - [ ] rate limits still enforced
- [ ] Capture log evidence for reject reasons and response-code distribution.
- [x] Update runbook with Phase 7 operational checks.

Current blocker:
- With private Cloud Run invoker IAM, Firebase Hosting rewrite requests are denied upstream (`403` HTML from Google Frontend) before app-level auth checks run.
- Decision required for staging completion:
  - allow public invoker (then enforce auth/app-check/rate-limits in app), or
  - keep private invoker and disable `/api/**` Hosting route.

Exit criteria:
- Staging confirms contract-correct behavior and bounded write surface.

## PR6: Production Rollout and Rollback Readiness

Maps to Phase 7 sections:
- `Rollout Plan`
- `Rollback Plan`
- `Known Limitations`

Scope:
- [ ] Enable production `/api/**` route for authenticated feedback flow.
- [ ] Verify production App Check enforcement is active.
- [ ] Confirm Phase 7.5 edge hardening controls are active before production exposure.
- [ ] Validate post-deploy behavior:
  - [ ] auth-required response behavior
  - [ ] create/update semantics with `auth_uid` identity
  - [ ] no unexpected 5xx or spend spikes
- [ ] Validate rollback levers:
  - [ ] `writeEnabled` disable path
  - [ ] route-disable path
- [ ] Finalize legacy anonymous-path deprecation checkpoint.

Exit criteria:
- Production authenticated feedback flow is stable, observable, and quickly reversible.

## Merge Order

1. PR1 (infra prerequisites and private access baseline)
2. PR2 (backend identity/access contract)
3. PR3 (data model migration to `quiz_feedback_v2`)
4. PR4 (frontend auth integration)
5. PR5 (staging rollout and validation)
6. PR6 (production rollout and rollback readiness)

## Definition of Done

- [ ] Unauthenticated feedback writes are rejected in staging and production.
- [ ] Authenticated + App Check verified users can create/update feedback.
- [x] Feedback upsert uniqueness is `(auth_uid, question_id, feedback_date_utc)`.
- [x] Routing and IAM posture are source-controlled and reproducible.
- [ ] Runbook/docs reflect auth-era operations and rollback controls.
- [ ] Production exposure decision is aligned with Phase 7.5 edge hardening policy.
