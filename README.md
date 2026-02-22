# Mindblast

Mindblast is a quiz project built to evolve over time.

- `Mindblast app`: the user-facing experience where people play quizzes.
- `quiz-forge`: the backend generator that creates daily quiz content.

## Current Status

Phase 1.5 focuses on `quiz-forge` + static discovery:
- one scheduled GitHub Actions run per day
- one history question per enabled quiz type per day
- enabled types: `which_came_first`, `history_mcq_4`
- discovery artifacts: `quizzes/index/YYYY-MM-DD.json`, `quizzes/latest.json`
- output committed as JSON to this repository

## Repository Structure

```text
.
├── .github/workflows/
│   └── daily-quiz.yml
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
│   ├── HOSTING_ROLLOUT.md
│   ├── QUIZ_FORGE_DESIGN.md
│   ├── FUTURE_FEATURES.md
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
- Hosting rollout plan: `docs/HOSTING_ROLLOUT.md`
- Architecture and guardrails: `docs/QUIZ_FORGE_DESIGN.md`
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
