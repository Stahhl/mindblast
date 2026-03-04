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
