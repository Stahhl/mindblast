# Mindblast

Mindblast is a quiz project built to evolve over time.

- `Mindblast app`: the user-facing experience where people play quizzes.
- `quiz-forge`: the backend generator that creates daily quiz content.

## Current Status

Phase 1.5 focuses on `quiz-forge` + static discovery:
- one scheduled GitHub Actions run per day
- default daily generation targets: `which_came_first=1`, `history_mcq_4=1`, `history_factoid_mcq_4=3`
- optional manual extra generation: additional same-day editions above the configured daily range
- default enabled types: `which_came_first`, `history_mcq_4`, `history_factoid_mcq_4`
- `history_factoid_mcq_4` AI-native rewrite path is behind `FACTOID_AI_PIPELINE_ENABLED` (disabled by default)
- quiz payload schema: `metadata.version = 2` with normalized `questions` + `answer_facts` and legacy compatibility fields
- discovery artifacts: `quizzes/index/YYYY-MM-DD.json`, `quizzes/latest.json`
- support artifact: `quizzes/human_id_lookup.json` (`Q...`/`A...` alias lookup)
- internal run reports: `reports/quiz-forge/daily/YYYY/MM/DD/<timestamp>-run-<github_run_id>.json`
- output stored in the private content repository `Stahhl/mindblast-content`

## Repository Structure

```text
.
├── .github/workflows/
│   └── daily-quiz.yml
├── pyproject.toml
├── uv.lock
├── infra/
│   └── terraform/
│       ├── modules/
│       └── envs/
│           ├── staging/
│           └── production/
├── src/
│   └── apps/
│       ├── feedback-api/
│       │   ├── src/
│       │   ├── tests/
│       │   ├── package.json
│       │   └── tsconfig.json
│       └── frontend/
│           ├── src/
│           │   ├── components/
│           │   ├── lib/
│           │   ├── App.tsx
│           │   ├── main.tsx
│           │   └── styles.css
│           ├── package.json
│           ├── vite.config.ts
│           ├── tsconfig.json
│           └── index.html
├── docs/
│   ├── PHASE1.md
│   ├── PHASE1_5.md
│   ├── PHASE2.md
│   ├── PHASE3.md
│   ├── PHASE4.md
│   ├── PHASE5.md
│   ├── PHASE5_5.md
│   ├── PHASE6.md
│   ├── PHASE6_5.md
│   ├── PHASE7.md
│   ├── PHASE7_5.md
│   ├── HOSTING_ROLLOUT.md
│   ├── ENVIRONMENTS.md
│   ├── QUIZ_FORGE_DESIGN.md
│   ├── FUTURE_FEATURES.md
│   ├── api_contracts/
│   └── DOMAIN_PREPURCHASE_CHECKLIST.md
├── scripts/
│   ├── generate_quiz.py
│   └── quiz_forge/
```

## Key Docs

- Phase 1 scope: `docs/PHASE1.md`
- Phase 1.5 discovery layer: `docs/PHASE1_5.md`
- Phase 2 frontend scope: `docs/PHASE2.md`
- Phase 3 AI workflow scope: `docs/PHASE3.md`
- Phase 4 multi-generation scope: `docs/PHASE4.md`
- Phase 5 history factoid MCQ scope: `docs/PHASE5.md`
- Phase 5.5 AI-native factoid pipeline: `docs/PHASE5_5.md`
- Phase 6 feedback API scope: `docs/PHASE6.md`
- Phase 6.5 Terraform access/IAM parameterization: `docs/PHASE6_5.md`
- Phase 7 auth scope: `docs/PHASE7.md`
- Phase 7.5 edge hardening scope: `docs/PHASE7_5.md`
- Phase 8 weekly feedback review scope: `docs/PHASE8.md`
- Hosting rollout plan: `docs/HOSTING_ROLLOUT.md`
- Environment posture and risk model: `docs/ENVIRONMENTS.md`
- Backend service architecture: `docs/BACKEND_SERVICE_DESIGN.md`
- Terraform IaC setup: `infra/terraform/README.md`
- Architecture and guardrails: `docs/QUIZ_FORGE_DESIGN.md`
- Provider API contract snapshots: `docs/api_contracts/`
- Future roadmap ideas: `docs/FUTURE_FEATURES.md`
- Domain/brand pre-purchase checks: `docs/DOMAIN_PREPURCHASE_CHECKLIST.md`

## Naming

- Project name: `Mindblast`
- User-facing app name: `Mindblast`
- Backend generator service: `quiz-forge`

## Next Steps

1. Run the local frontend and validate quiz UX on desktop/mobile.
2. Integrate Phase 6 feedback UI in quiz cards and wire it to `POST /api/quiz-feedback`.
3. Add Phase 6 abuse controls (rate limits, App Check, kill-switch flags).

## Local Frontend Run

Use your Node + pnpm bootstrap in this shell:

```zsh
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
nvm use default
export PATH="$HOME/Library/pnpm:$PATH"
```

Then install and run:

```zsh
cd src/apps/frontend
pnpm install
pnpm test
pnpm dev
```

Expected local layout:

```text
../mindblast
../mindblast-content
```

Local quiz content is served from the sibling checkout `../mindblast-content/quizzes` by default.
Override that path when needed:

```zsh
export MINDBLAST_CONTENT_DIR="../mindblast-content/quizzes"
```

## Local quiz-forge Run (uv)

```zsh
cd <repo-root>
uv sync --locked --no-dev --python 3.12
uv run --python 3.12 python scripts/generate_quiz.py \
  --quiz-types "which_came_first,history_mcq_4,history_factoid_mcq_4" \
  --output-dir ../mindblast-content/quizzes
```

Backfill human-friendly IDs for already generated quiz files:

```zsh
uv run --python 3.12 python scripts/generate_quiz.py --backfill-human-ids --output-dir ../mindblast-content/quizzes
```

This backfill mode can also normalize legacy schema v1 quiz payloads to v2.

## Python Tests (uv)

```zsh
cd <repo-root>
uv sync --locked --dev --python 3.12
uv run --python 3.12 pytest tests/quiz_forge
```

## Weekly Feedback Review Run (uv)

```zsh
cd <repo-root>
uv sync --locked --no-dev --python 3.12
uv run --python 3.12 python scripts/generate_weekly_feedback_report.py \
  --content-repo-root ../mindblast-content \
  --feedback-json /path/to/feedback_fixture.json \
  --run-date 2026-03-16 \
  --disable-ai
```

The fixture file should contain production-shaped feedback records whose `quiz_file` values exist under `../mindblast-content/quizzes`.

Production workflow prerequisites:
- `FEEDBACK_REPORT_FIREBASE_SERVICE_ACCOUNT_PRODUCTION`: read-only Firestore service account JSON for `mindblast-prod`
- `OPENAI_API_KEY`: reused for the optional AI summary step

Recommended repository variables:
- `FEEDBACK_REPORT_AI_MODE`: `on`
- `FEEDBACK_REPORT_AI_PROVIDER`: `openai`
- `FEEDBACK_REPORT_AI_MODEL`: `gpt-5-mini`
- `FEEDBACK_REPORT_AI_MAX_CALLS_PER_RUN`: `3`
- `FEEDBACK_REPORT_AI_MAX_INPUT_TOKENS`: `12000`
- `FEEDBACK_REPORT_AI_MAX_OUTPUT_TOKENS`: `800`
- `FEEDBACK_REPORT_AI_MAX_DAILY_USD`: `1`
- `FEEDBACK_REPORT_AI_MAX_MONTHLY_USD`: `5`

## Content Repo Workflow Prerequisites

Repository variable:
- `QUIZ_CONTENT_REPO`: `Stahhl/mindblast-content`

Repository secrets:
- `CONTENT_REPO_WRITE_TOKEN`: fine-grained PAT with read/write access to `Stahhl/mindblast-content`
- `CONTENT_REPO_READ_TOKEN`: fine-grained PAT with read access to `Stahhl/mindblast-content`

Artifact families stored in `Stahhl/mindblast-content`:
- public client-facing quiz artifacts under `quizzes/**`
- internal operational/debug artifacts under `reports/**`

Frontend deploy workflows must continue to copy only `quizzes/**`.

## Feedback API Build + Tests (pnpm)

```zsh
cd src/apps/feedback-api
pnpm install
pnpm test
pnpm build
```

Deploy feedback function manually:

```zsh
# Firebase Functions v2 requires Blaze (pay-as-you-go) in each project.
# Apply backend API + IAM infra changes first:
# cd infra/terraform/envs/staging && terraform plan && terraform apply

firebase deploy --only functions:feedback-api:quizFeedbackApi,firestore:rules,firestore:indexes --project mindblast-staging
firebase deploy --only functions:feedback-api:quizFeedbackApi,firestore:rules,firestore:indexes --project mindblast-prod
```

## Staging Deploy (GitHub Actions)

- Workflow: `.github/workflows/deploy-frontend-staging.yml`
- Trigger: push to `main` when frontend or Firebase config changes, and after successful `Daily Quiz Generation` runs
- Target project/site: `mindblast-staging` (via `.firebaserc` hosting target `staging`)

Required repository secrets:
- `FIREBASE_SERVICE_ACCOUNT_STAGING`: service account JSON for Firebase Hosting deploy
- `CONTENT_REPO_READ_TOKEN`: fine-grained PAT with read access to `Stahhl/mindblast-content`

## Feedback API Staging Deploy (GitHub Actions)

- Workflow: `.github/workflows/deploy-feedback-api-staging.yml`
- Trigger: push to `main` when feedback-api source, Firestore config, or Firebase config changes
- Deploy target: `mindblast-staging`
- Deploy command:
  - `functions:feedback-api:quizFeedbackApi`
  - `firestore:rules`
  - `firestore:indexes`

Required repository secrets:
- `FIREBASE_SERVICE_ACCOUNT_STAGING`: service account JSON for Firebase deploy auth

Operational runbook:
- `docs/roadmap/phase6_rollout_runbook.md`

## Production Deploy (GitHub Actions)

- Workflow: `.github/workflows/deploy-frontend-production.yml`
- Trigger: push to `main` when frontend or Firebase config changes, and after successful `Daily Quiz Generation` runs
- Target project/site: `mindblast-prod` (via `.firebaserc` hosting target `production`)

Required repository secrets:
- `FIREBASE_SERVICE_ACCOUNT_PRODUCTION`: service account JSON for Firebase Hosting deploy
- `CONTENT_REPO_READ_TOKEN`: fine-grained PAT with read access to `Stahhl/mindblast-content`

## Weekly Feedback Review (GitHub Actions)

- Workflow: `.github/workflows/weekly-feedback-review.yml`
- Trigger: every Monday at `07:00 UTC` and manual dispatch
- Data source: production Firestore `quiz_feedback`
- Output: `reports/feedback/weekly/YYYY/YYYY-Www.{md,json}` in `Stahhl/mindblast-content`

Required repository secrets:
- `FEEDBACK_REPORT_FIREBASE_SERVICE_ACCOUNT_PRODUCTION`: read-only Firestore service account JSON for `mindblast-prod`
- `CONTENT_REPO_WRITE_TOKEN`: fine-grained PAT with read/write access to `Stahhl/mindblast-content`
- `OPENAI_API_KEY`: optional for AI summary; deterministic report still works with `disable_ai`

## Daily Quiz Run Reports (GitHub Actions)

- Workflow: `.github/workflows/daily-quiz.yml`
- Trigger: daily schedule and manual dispatch
- Output: `reports/quiz-forge/daily/YYYY/MM/DD/<timestamp>-run-<github_run_id>.json` in `Stahhl/mindblast-content`
- Retention: append-only, one JSON report per run including reruns and failures
- Discord notification: rendered from the persisted JSON report rather than treated as the sole copy of debugging data

## Secret Guardrails

Local guardrails:
- Git hooks: `.githooks/pre-commit` and `.githooks/pre-push`
- Hook bootstrap: `scripts/setup_git_hooks.sh`

Setup:

```zsh
brew install gitleaks
./scripts/setup_git_hooks.sh
```

CI guardrail:
- Workflow: `.github/workflows/secret-scan.yml` (gitleaks scan on PRs and `main` pushes)
- Workflow: `.github/workflows/feedback-api-security.yml` (dependency audit + CodeQL for feedback backend changes)

Review guardrail:
- Code owners file: `.github/CODEOWNERS`
- Enable branch protection in GitHub and require:
  - at least 1 pull-request review
  - code owner review
  - required status check: `Secret Scan / Gitleaks`
