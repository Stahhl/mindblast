# Phase 7 Rollout and Rollback Runbook

## Scope

Runbook for `quiz_feedback_v2` (authenticated feedback writes) in:
- staging project: `mindblast-staging`
- production project: `mindblast-prod`

## Preconditions

- Firebase Auth Google provider enabled in target project.
- Web app registered in Firebase project.
- Frontend env vars configured (`FIREBASE_WEB_*`, App Check site key).
- Terraform applied for target env with:
  - `manage_feedback_api_invoker_iam = true`
  - invoker posture explicitly chosen and documented (`feedback_api_allow_public_invoker`)
- Hosting rewrite enabled in `firebase.json`:
  - `/api/** -> quizFeedbackApi`

## Staging Rollout

Phase 7 exception posture:
- `feedback_api_allow_public_invoker = true` (temporary)
- backend app-level controls remain required (`401`/`403`/`429` contract)

1. Deploy feedback backend:

```zsh
gh workflow run "Deploy Feedback API Staging"
gh run watch
```

2. Deploy frontend/hosting config:

```zsh
gh workflow run "Deploy Frontend Staging"
gh run watch
```

## Staging Smoke Checks

### 1) Unauthenticated request is rejected (`401`)

```zsh
curl -i -X POST "https://staging.mindblast.app/api/quiz-feedback" \
  -H "Origin: https://staging.mindblast.app" \
  -H "Content-Type: application/json" \
  --data '{}'
```

Expect:
- `HTTP 401`
- body includes `{"ok":false,"error":"unauthenticated"}`

### 2) Auth without valid App Check is rejected (`403`)

Steps:
1. Sign in on `https://staging.mindblast.app`.
2. In browser devtools Network tab, capture one successful feedback request.
3. Copy its `Authorization: Bearer <id-token>` value.
4. Replay with invalid App Check:

```zsh
curl -i -X POST "https://staging.mindblast.app/api/quiz-feedback" \
  -H "Origin: https://staging.mindblast.app" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <copied-id-token>" \
  -H "X-Firebase-AppCheck: invalid" \
  --data '{}'
```

Expect:
- `HTTP 403`
- body includes `{"ok":false,"error":"app_check_failed"}`

### 3) Authenticated + valid App Check is accepted

From UI on `https://staging.mindblast.app`:
- sign in with Google
- submit feedback once

Expect:
- request returns `200`
- response shape includes `ok: true`, `mode: created|updated`, `feedback_id`

### 4) Rate limits still enforced

Replay authenticated request payload + headers in a short burst (6+ within hour).

Expect:
- some `200`
- then `429` with `error: rate_limited` and `Retry-After`

## Observability Checks

Request status distribution:

```zsh
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="quizfeedbackapi" AND logName="projects/mindblast-staging/logs/run.googleapis.com%2Frequests"' \
  --project=mindblast-staging --limit=200 --format="value(httpRequest.status)"
```

Reject reasons (`quiz_feedback_reject`):

```zsh
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="quizfeedbackapi" AND jsonPayload.event="quiz_feedback_reject"' \
  --project=mindblast-staging --limit=200 --format="value(jsonPayload.reason)"
```

## Telemetry Thresholds (Discord-First)

Channel:
- send operational alerts to Discord using existing `DISCORD_WEBHOOK_URL`.

Window:
- evaluate every 10 minutes (`--freshness=10m`) for fast detection.

Thresholds:
- `5xx` ratio > `1%` over 10m: alert (`high`)
- `429` ratio > `20%` over 10m: alert (`warning`) and inspect edge/backend limits
- request volume > `3x` recent baseline (10m vs typical 10m window): alert (`warning`)
- `writes_disabled` reject seen: alert immediately (`info` / incident marker)

Sampling commands:

```zsh
# Status counts in the last 10 minutes
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="quizfeedbackapi" AND logName:"run.googleapis.com%2Frequests"' \
  --project=mindblast-staging --freshness=10m --limit=1000 --format="value(httpRequest.status)"

# Reject reasons in the last 10 minutes
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="quizfeedbackapi" AND jsonPayload.event="quiz_feedback_reject"' \
  --project=mindblast-staging --freshness=10m --limit=1000 --format="value(jsonPayload.reason)"
```

Discord message template:

```text
mindblast feedback telemetry (staging, 10m)
total: <n>
2xx/4xx/5xx: <..>/<..>/<..>
429 ratio: <x>%
5xx ratio: <y>%
writes_disabled events: <n>
action: <none | monitor | contain>
```

Initial operating guidance:
- if `5xx` threshold breaches, run emergency containment (`Feedback Emergency Toggle`) while investigating.
- if only `429` breaches, verify edge rate-limit behavior before escalating.
- keep Firebase/GCP billing alerts enabled as a cost backstop; telemetry alerts are the earlier signal.

## Known Failure Mode

If `/api/quiz-feedback` returns Google Frontend HTML `403` (not JSON):
- Hosting rewrite reached backend, but Cloud Run invoker IAM denied request.
- In current platform behavior, Hosting rewrite requests arrive unauthenticated at Cloud Run.
- To allow rewrite traffic, set `feedback_api_allow_public_invoker = true` (and rely on app-level auth/app-check/rate limits),
  or keep invoker private and disable `/api/**` rewrite.

Production note:
- production must remain `feedback_api_allow_public_invoker = false` until Phase 7.5 hardening (`docs/PHASE7_5.md`) is complete.

## Rollback

1. Emergency write stop:
  - trigger workflow `Feedback Emergency Toggle` with:
    - `environment`: `staging` or `production`
    - `write_enabled`: `false`
    - `confirmation`: `SHORT_CIRCUIT`
  - this redeploys `quizFeedbackApi` with `FEEDBACK_WRITE_ENABLED=false` and keeps auth/app-check enforcement required.
2. Route rollback:
  - remove `/api/**` rewrite from target Hosting block in `firebase.json`, redeploy hosting.
3. Access rollback:
  - keep `feedback_api_allow_public_invoker = false` and (if needed) disable hosting invoker grants via Terraform.

## Phone-Only Containment Flow

Use GitHub mobile/web UI:
1. Open Actions -> `Feedback Emergency Toggle`.
2. Click `Run workflow`.
3. Select `environment`.
4. Set `write_enabled=false`.
5. Enter confirmation phrase: `SHORT_CIRCUIT`.
6. Run workflow and wait for green completion.
7. Verify `/api/quiz-feedback` returns `503` with `error: writes_disabled`.

Recovery:
1. Run `Feedback Emergency Toggle` again.
2. Keep same `environment`.
3. Set `write_enabled=true`.
4. Enter `SHORT_CIRCUIT`.
5. Verify normal signed-in feedback submit returns `200`.

## Incident Notes

Record:
- UTC timestamp
- environment
- commit SHA
- workflow run URLs
- smoke-test outcomes
- request status counts and reject reasons
- rollback actions (if any)
