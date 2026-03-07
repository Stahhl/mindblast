# Phase 6 Rollout and Rollback Runbook

## Scope

Runbook for deploying and operating `quiz_feedback_v1` (`quizFeedbackApi`) across:
- staging project: `mindblast-staging`
- production project: `mindblast-prod`

## Current Deployment Topology

- Frontend app and static quiz files: Firebase Hosting.
- Feedback backend: Firebase Functions v2 (`feedback-api:quizFeedbackApi`) routed by Hosting rewrite:
  - `/api/** -> quizFeedbackApi`
- Storage: Firestore (`quiz_feedback`, `quiz_feedback_rate_limits`) with `firestore.rules` and `firestore.indexes.json`.

## Preconditions

Before production rollout:
- Staging smoke validation is green:
  - first submit returns `mode=created`
  - repeat submit same `(client_id, question_id, day)` returns `mode=updated`
  - repeated burst hits `429 rate_limited`
- Terraform state for target environment reconciles cleanly:
  - `terraform plan` shows no unexpected drift.
- Required secrets exist in GitHub:
  - `FIREBASE_SERVICE_ACCOUNT_STAGING`
  - `FIREBASE_SERVICE_ACCOUNT_PRODUCTION`

## Standard Rollout

### 1) Staging deploy

Use CI workflow:
- `.github/workflows/deploy-feedback-api-staging.yml`

Or manual:

```zsh
cd <repo-root>
npx --yes firebase-tools@13 deploy \
  --only functions:feedback-api:quizFeedbackApi,firestore:rules,firestore:indexes \
  --project mindblast-staging
```

### 2) Staging smoke test

Run a burst against `https://staging.mindblast.app/api/quiz-feedback` and verify:
- `200 created`
- `200 updated`
- `429 rate_limited` with `Retry-After`

Verify logs:

```zsh
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="quizfeedbackapi" AND logName="projects/mindblast-staging/logs/run.googleapis.com%2Frequests"' \
  --project=mindblast-staging --limit=200 --format=json
```

Expected for a passing burst:
- mix of `200` and `429`
- no unexpected `5xx` spike

### 3) Production deploy

Manual command:

```zsh
cd <repo-root>
npx --yes firebase-tools@13 deploy \
  --only functions:feedback-api:quizFeedbackApi,firestore:rules,firestore:indexes \
  --project mindblast-prod
```

If frontend changes are part of release, run production Hosting deploy workflow:
- `.github/workflows/deploy-frontend-production.yml`

### 4) Production verification

- Routing check:
  - `POST https://mindblast.app/api/quiz-feedback` should reach backend route.
- If App Check is enforced in production:
  - unauthenticated curl is expected to return `403 app_check_failed`.
- Verify from real frontend flow on `https://mindblast.app`:
  - user can submit rating/comment
  - repeat submit updates existing feedback for same day

## Rollback Procedure

Choose the smallest rollback that restores stability.

### Level 1: Emergency write stop

Current reliable path in this repo is a hotfix default change + fast redeploy.

1. Create a hotfix commit in `src/apps/feedback-api/src/application/runtime_config.ts`:
   - set `writeEnabled` fallback to `false` for full write stop, or
   - set `commentsEnabled` fallback to `false` to keep ratings and disable comments.
2. Redeploy function:

```zsh
cd <repo-root>
npx --yes firebase-tools@13 deploy \
  --only functions:feedback-api:quizFeedbackApi \
  --project <target-project>
```

3. Verify endpoint behavior:
   - write-stop expected response: `503` with `error:"writes_disabled"`.

Note:
- Direct `gcloud run services update --update-env-vars` is not reliable for this
  Firebase-managed function in current setup (artifact resolution failures observed).

### Level 2: Backend version rollback

Redeploy last known-good commit for backend + Firestore config:

```zsh
cd <repo-root>
git checkout <known-good-sha>
npx --yes firebase-tools@13 deploy \
  --only functions:feedback-api:quizFeedbackApi,firestore:rules,firestore:indexes \
  --project <target-project>
git checkout main
```

### Level 3: Frontend rollback (if release included frontend regression)

- Use Firebase Hosting rollback (console or CLI) for affected site.
- Then confirm `/api/**` rewrite behavior and frontend feedback UI recovery.

## Incident Notes to Capture

For each rollout or rollback, record:
- timestamp (UTC)
- environment (`staging` or `production`)
- deployed commit SHA
- command/workflow used
- smoke-test outcomes
- log summary (status distribution, reject reasons, any 5xx)
- follow-up fixes required
