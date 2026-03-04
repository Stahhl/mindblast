# Mindblast Feedback API

Phase 6 backend MVP service for `POST /api/quiz-feedback`.

## Run tests

```zsh
pnpm --dir src/apps/feedback-api install
pnpm --dir src/apps/feedback-api test
```

## Build

```zsh
pnpm --dir src/apps/feedback-api build
```

## Deploy notes

Firebase Hosting rewrites `/api/**` to function `quizFeedbackApi`.
Function source path in `firebase.json`:
- `src/apps/feedback-api`
- Function deploy options explicitly set `invoker: "public"` for web access.

## Security + Abuse Control Flags

- `FEEDBACK_WRITE_ENABLED` (default: `true`)
- `FEEDBACK_COMMENTS_ENABLED` (default: `true`)
- `FEEDBACK_APP_CHECK_ENFORCEMENT` (`auto|required|off`, default: `auto`)
- In `auto`, App Check is required in production but disabled for the known
  staging project (`mindblast-staging`) to allow staging smoke tests.
- `FEEDBACK_REQUIRE_ORIGIN` (default: `true` in production, else `false`)
- `FEEDBACK_ALLOWED_ORIGINS` (comma-separated; defaults include `mindblast.app` + `staging.mindblast.app`)
- `FEEDBACK_MAX_REQUEST_BYTES` (default: `8192`)
- `FEEDBACK_RATE_LIMIT_CLIENT_HOURLY` (default: `5`)
- `FEEDBACK_RATE_LIMIT_CLIENT_DAILY` (default: `20`)
- `FEEDBACK_RATE_LIMIT_IP_HOURLY` (default: `60`)
- `FEEDBACK_RATE_LIMIT_GLOBAL_HOURLY` (default: `5000`)

Operational note:
- The current deployment setup does not provide a stable runtime env-var toggle path
  for `FEEDBACK_*` in Firebase-managed Cloud Run revisions.
- Use a hotfix fallback change in
  `src/application/runtime_config.ts` + function redeploy for emergency kill-switches.
