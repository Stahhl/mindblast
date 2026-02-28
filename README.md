# Mindblast

Mindblast is a quiz project built to evolve over time.

- `Mindblast app`: the user-facing experience where people play quizzes.
- `quiz-forge`: the backend generator that creates daily quiz content.

## Current Status

Phase 1.5 focuses on `quiz-forge` + static discovery:
- one scheduled GitHub Actions run per day
- default daily generation: one history quiz per enabled type per UTC day (`edition = 1`)
- optional manual extra generation: additional same-day editions (`edition > 1`)
- default enabled types: `which_came_first`, `history_mcq_4`
- supported additional type: `history_factoid_mcq_4` (Phase 5, manual rollout first)
- quiz payload schema: `metadata.version = 2` with normalized `questions` + `answer_facts` and legacy compatibility fields
- discovery artifacts: `quizzes/index/YYYY-MM-DD.json`, `quizzes/latest.json`
- output committed as JSON to this repository

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
│   ├── HOSTING_ROLLOUT.md
│   ├── QUIZ_FORGE_DESIGN.md
│   ├── FUTURE_FEATURES.md
│   ├── api_contracts/
│   └── DOMAIN_PREPURCHASE_CHECKLIST.md
├── scripts/
│   ├── generate_quiz.py
│   └── quiz_forge/
└── quizzes/
```

## Key Docs

- Phase 1 scope: `docs/PHASE1.md`
- Phase 1.5 discovery layer: `docs/PHASE1_5.md`
- Phase 2 frontend scope: `docs/PHASE2.md`
- Phase 3 AI workflow scope: `docs/PHASE3.md`
- Phase 4 multi-generation scope: `docs/PHASE4.md`
- Phase 5 history factoid MCQ scope: `docs/PHASE5.md`
- Phase 5.5 AI-native factoid pipeline: `docs/PHASE5_5.md`
- Hosting rollout plan: `docs/HOSTING_ROLLOUT.md`
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
2. Backfill discovery artifacts for any legacy quiz dates that predate Phase 1.5.
3. Re-evaluate backend API need after Phase 2 against the decision gate in `docs/PHASE2.md`.

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
pnpm dev
```

## Local quiz-forge Run (uv)

```zsh
cd /Users/stahl/dev/mindblast
uv sync --locked --no-dev --python 3.12
uv run --python 3.12 python scripts/generate_quiz.py --quiz-types "which_came_first,history_mcq_4"
```

## Python Tests (uv)

```zsh
cd /Users/stahl/dev/mindblast
uv sync --locked --dev --python 3.12
uv run --python 3.12 pytest tests/quiz_forge
```

## Staging Deploy (GitHub Actions)

- Workflow: `.github/workflows/deploy-frontend-staging.yml`
- Trigger: push to `main` when frontend, Firebase config, or `quizzes/` content changes
- Target project/site: `mindblast-staging` (via `.firebaserc` hosting target `staging`)

Required repository secrets:
- `FIREBASE_SERVICE_ACCOUNT_STAGING`: service account JSON for Firebase Hosting deploy

## Production Deploy (GitHub Actions)

- Workflow: `.github/workflows/deploy-frontend-production.yml`
- Trigger: push to `main` when frontend, Firebase config, or `quizzes/` content changes
- Target project/site: `mindblast-prod` (via `.firebaserc` hosting target `production`)

Required repository secrets:
- `FIREBASE_SERVICE_ACCOUNT_PRODUCTION`: service account JSON for Firebase Hosting deploy

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

Review guardrail:
- Code owners file: `.github/CODEOWNERS`
- Enable branch protection in GitHub and require:
  - at least 1 pull-request review
  - code owner review
  - required status check: `Secret Scan / Gitleaks`
