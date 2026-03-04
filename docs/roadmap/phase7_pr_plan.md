# Phase 7 PR Plan: Authenticated Feedback API (`quiz_feedback_v2`)

## Objective
Deliver Phase 7 in small, reviewable PRs that align directly with `docs/PHASE7.md` and keep abuse/cost risk bounded during rollout.

## Dependency
- Phase 6 feedback endpoint is live.
- Phase 6.5 Terraform IAM/invoker parameterization is in place.

## PR1: Infra Prerequisites and Access Baseline

Maps to Phase 7 sections:
- `Infra Prerequisites`
- `Architecture`

Scope:
- [ ] Ensure Firebase Auth prerequisites are enabled per environment (including Identity Toolkit API where required).
- [ ] Verify Terraform-driven invoker posture remains private by default (no public direct backend URL access).
- [ ] Confirm environment config explicitly captures:
  - [ ] App Check enforcement intent
  - [ ] `/api/**` Hosting rewrite exposure intent
  - [ ] auth-required mode intent
- [ ] Update infra docs/examples to reflect Phase 7 auth-era baseline.

Exit criteria:
- Auth and access prerequisites are source-controlled, documented, and reproducible via Terraform + environment config.

## PR2: Backend Identity and Access Contract

Maps to Phase 7 sections:
- `Identity and Access Contract`
- `Validation Rules`
- `Abuse and Cost Controls (Required)`

Scope:
- [ ] Add Firebase ID token verification for `POST /api/quiz-feedback`.
- [ ] Enforce App Check verification on write path per environment policy.
- [ ] Keep allowed-origin checks and existing rate limits in the request path.
- [ ] Return contract-specific status codes:
  - [ ] missing/invalid ID token -> `401`
  - [ ] missing/invalid App Check -> `403`
  - [ ] disallowed origin -> `403`
- [ ] Add backend tests for auth/app-check failure and success paths.

Exit criteria:
- Backend write path accepts only authenticated + attested requests, with contract-accurate error behavior.

## PR3: Data Model Migration to `quiz_feedback_v2`

Maps to Phase 7 sections:
- `Data Model (quiz_feedback_v2)`
- `Validation Rules`

Scope:
- [ ] Add `schema_version = 2` to new/updated feedback writes.
- [ ] Store authenticated identity fields:
  - [ ] `auth_uid`
  - [ ] `auth_provider`
  - [ ] `auth_verified_at`
- [ ] Switch upsert uniqueness key to `(auth_uid, question_id, feedback_date_utc)`.
- [ ] Keep legacy `client_id` as compatibility-only during migration window.
- [ ] Add tests for deterministic update semantics under authenticated identity.

Exit criteria:
- Feedback uniqueness and update behavior are keyed by authenticated user identity.

## PR4: Frontend Auth Integration

Maps to Phase 7 sections:
- `Frontend Behavior`

Scope:
- [ ] Add Firebase Auth client bootstrap for web.
- [ ] Add minimal Google sign-in/sign-out UX for feedback actions.
- [ ] Attach ID token + App Check token to feedback write requests.
- [ ] Handle auth-required UX states:
  - [ ] signed-out prompt
  - [ ] token fetch failure
  - [ ] expired session retry
- [ ] Preserve quiz play when auth/feedback path is unavailable.

Exit criteria:
- Signed-in users can submit/update feedback; signed-out users get clear guidance without breaking gameplay.

## PR5: Staging Rollout and Validation

Maps to Phase 7 sections:
- `Rollout Plan`

Scope:
- [ ] Re-enable staging Hosting rewrite `/api/** -> quizFeedbackApi`.
- [ ] Verify direct backend URLs remain non-public.
- [ ] Run staging smoke tests:
  - [ ] unauthenticated request rejected (`401`)
  - [ ] auth without valid App Check rejected (`403`)
  - [ ] authenticated + valid App Check request accepted
  - [ ] rate limits still enforced
- [ ] Capture log evidence for reject reasons and response-code distribution.
- [ ] Update runbook with Phase 7 operational checks.

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
- [ ] Feedback upsert uniqueness is `(auth_uid, question_id, feedback_date_utc)`.
- [ ] Direct backend URLs remain non-public.
- [ ] Routing and IAM posture are source-controlled and reproducible.
- [ ] Runbook/docs reflect auth-era operations and rollback controls.
