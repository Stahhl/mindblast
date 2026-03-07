# Phase 7 Specification: Authenticated Feedback API (`quiz_feedback_v2`)

## Naming
- Project name: `Mindblast`.
- User-facing app name: `Mindblast`.
- Backend generator service name: `quiz-forge`.

## Objective
Upgrade feedback writes from anonymous identity to authenticated user identity and enforce a strict backend write contract (`quiz_feedback_v2`).

## Dependency
- Phase 6 (`docs/PHASE6.md`) feedback endpoint is implemented.
- Phase 6.5 (`docs/PHASE6_5.md`) Terraform IAM/invoker toggles are available.

## Follow-On Phase
- Phase 7.5 (`docs/PHASE7_5.md`) defines edge hardening and cost-risk controls before production exposure.

## Why This Phase
As of `2026-03-04`, staging feedback infrastructure exists, but internet-facing write endpoints need stronger abuse and spend controls than cookie-based anonymous identity. Phase 7 introduces authenticated identity + attestation while preserving the existing feedback product flow.

## Scope (Phase 7)
- Require Firebase Auth identity for feedback writes.
- Require Firebase App Check for feedback writes.
- Expose feedback API via Hosting rewrite only:
  - `/api/**` -> `quizFeedbackApi`
- Switch feedback upsert identity from `client_id` to `auth_uid`.
- Keep frontend gameplay functional even if auth/feedback is unavailable.
- Validate end-to-end write behavior in staging.

## Out of Scope
- Profile pages or account management depth.
- Social features or public feedback feeds.
- Recommendation/personalization logic.
- Mobile-specific auth implementation details.

## Architecture
- Continue serving quiz payloads statically from `/quizzes/**`.
- Continue same-origin API routing from Hosting to backend.
- Authentication and attestation are enforced at backend write boundary.
- Edge hardening and production exposure model are handled in Phase 7.5 (`docs/PHASE7_5.md`).

## Identity and Access Contract

### Required write request headers
- `Authorization: Bearer <Firebase ID token>`
- `X-Firebase-AppCheck: <App Check token>`

### Required backend behavior (`POST /api/quiz-feedback`)
- `401 unauthenticated` when ID token is missing/invalid.
- `403 app_check_failed` when App Check is missing/invalid.
- `403 forbidden_origin` for disallowed origin.
- Existing `400 invalid_payload` and `429 rate_limited` remain.

## Data Model (`quiz_feedback_v2`)

One logical feedback record per `(auth_uid, question_id, feedback_date_utc)`.

Required fields:
- `schema_version`: `2`
- `quiz_file`
- `date`
- `quiz_type`
- `edition`
- `question_id`
- `question_human_id`
- `rating`
- `feedback_date_utc`
- `auth_uid`
- `auth_provider` (example: `google.com`)
- `auth_verified_at` (UTC ISO-8601)
- `created_at`
- `updated_at`

Optional fields:
- `comment` (trimmed, max 500 chars)
- legacy `client_id` during migration window only

## Abuse and Cost Controls (Required)
- Keep per-user, per-IP, and global rate limits.
- Keep strict schema allowlist and payload size constraints.
- Keep same-origin/CORS allowlist for deployed domains only.
- Keep feature flags for `writeEnabled` and `commentsEnabled`.
- If invoker is public for rewrite compatibility, treat traffic as internet-exposed and billable and rely on auth/app-check/rate-limit rejection until Phase 7.5 edge controls are in place.

## Infra Prerequisites
- Firebase Auth enabled in each environment.
- Required API enabled where needed:
  - `identitytoolkit.googleapis.com`
- Existing backend APIs from Phase 6 remain enabled.
- Invoker and related IAM state managed via Terraform toggles from Phase 6.5.

### Runtime Config (Current Implementation)

Backend runtime flags:
- `FEEDBACK_AUTH_ENFORCEMENT` (`auto|required|off`, default `auto`)
- `FEEDBACK_APP_CHECK_ENFORCEMENT` (`auto|required|off`, default `auto`)

Frontend runtime variables (Vite):
- `VITE_FIREBASE_API_KEY`
- `VITE_FIREBASE_AUTH_DOMAIN`
- `VITE_FIREBASE_PROJECT_ID`
- `VITE_FIREBASE_APP_ID`
- `VITE_FIREBASE_STORAGE_BUCKET` (optional)
- `VITE_FIREBASE_APPCHECK_SITE_KEY`
- `VITE_FIREBASE_APPCHECK_DEBUG_TOKEN` (optional, local-only)

GitHub Actions variable names wired in frontend deploy workflows:
- Staging:
  - `FIREBASE_WEB_API_KEY_STAGING`
  - `FIREBASE_AUTH_DOMAIN_STAGING`
  - `FIREBASE_WEB_APP_ID_STAGING`
  - `FIREBASE_STORAGE_BUCKET_STAGING`
  - `FIREBASE_APPCHECK_SITE_KEY_STAGING`
  - `FIREBASE_APPCHECK_DEBUG_TOKEN_STAGING` (optional)
- Production:
  - `FIREBASE_WEB_API_KEY_PRODUCTION`
  - `FIREBASE_AUTH_DOMAIN_PRODUCTION`
  - `FIREBASE_WEB_APP_ID_PRODUCTION`
  - `FIREBASE_STORAGE_BUCKET_PRODUCTION`
  - `FIREBASE_APPCHECK_SITE_KEY_PRODUCTION`

## Frontend Behavior
- Add minimal sign-in/sign-out UX (Google provider MVP).
- Attach ID token and App Check token to feedback writes.
- If user is signed out, show clear sign-in requirement for feedback actions.
- Quiz play remains available when feedback/auth is unavailable.

## Validation Rules
- All Phase 6 payload validation rules still apply.
- `auth_uid` must be present for every accepted write.
- Upsert uniqueness is `(auth_uid, question_id, feedback_date_utc)`.
- App Check token must pass verification in staging and production.

## Rollout Plan
1. Implement backend auth enforcement behind config flags.
2. Implement frontend auth token acquisition + request wiring.
3. Validate end-to-end in staging with Hosting `/api/**` route enabled.
4. Record invoker posture and risk acceptance in docs (`docs/ENVIRONMENTS.md`, runbook).
5. Complete Phase 7.5 edge hardening before production exposure decisions.
6. Remove legacy anonymous identity write path after confidence window.

Operational runbook:
- `docs/roadmap/phase7_rollout_runbook.md`

## Rollback Plan
- Disable writes using `writeEnabled` and redeploy.
- Disable `/api/**` Hosting rewrite if needed.
- Revert invoker posture through Terraform if exposure changes are part of incident response.

## Acceptance Criteria
- Unauthenticated requests cannot create/update feedback.
- Authenticated + App Check verified requests can create/update feedback.
- Feedback upsert behavior is keyed by authenticated user identity.
- Routing/IAM posture is source-controlled and reproducible.
- Frontend remains playable even when feedback path is unavailable.

## Known Limitations
- One-provider MVP (`google.com`) before adding more identity providers.
- Auth improves abuse resistance but does not eliminate all abusive traffic.
- Rejected traffic can still incur billable load until edge protection is introduced (Phase 7.5).
