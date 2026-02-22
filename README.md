# Mindblast

Mindblast is a quiz project built to evolve over time.

- `Mindblast app`: the user-facing experience where people play quizzes.
- `quiz-forge`: the backend generator that creates daily quiz content.

## Current Status

Phase 1 focuses only on `quiz-forge`:
- one scheduled GitHub Actions run per day
- one history question per day
- question type: `which_came_first`
- output committed as JSON to this repository

## Repository Structure

```text
.
├── .github/workflows/
│   └── daily-quiz.yml
├── docs/
│   ├── PHASE1.md
│   ├── QUIZ_FORGE_DESIGN.md
│   ├── FUTURE_FEATURES.md
│   └── DOMAIN_PREPURCHASE_CHECKLIST.md
├── scripts/
│   └── generate_quiz.py
└── quizzes/
    └── .gitkeep
```

## Key Docs

- Phase 1 scope: `docs/PHASE1.md`
- Architecture and guardrails: `docs/QUIZ_FORGE_DESIGN.md`
- Future roadmap ideas: `docs/FUTURE_FEATURES.md`
- Domain/brand pre-purchase checks: `docs/DOMAIN_PREPURCHASE_CHECKLIST.md`

## Naming

- Project name: `Mindblast`
- User-facing app name: `Mindblast`
- Backend generator service: `quiz-forge`

## Next Steps

1. Push this repository to GitHub and enable Actions for the repo.
2. Add repository secret `DISCORD_WEBHOOK_URL` for workflow status notifications.
3. Confirm the scheduled workflow runs and creates `quizzes/<uuid>.json`.
4. Review the first generated quiz file and tune prompt wording or selection rules if needed.
