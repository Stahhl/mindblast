# AGENTS.md

## Project Context

- Project name: `Mindblast`
- User-facing app name: `Mindblast`
- Backend generator service: `quiz-forge`
- Current active phase: Phase 1.5 (daily quiz generation + static discovery artifacts)

## Source of Truth

- Phase scope and contract: `docs/PHASE1.md`
- Next phase planning: `docs/PHASE1_5.md`, `docs/PHASE2.md`
- System design and guardrails: `docs/QUIZ_FORGE_DESIGN.md`
- Planned future features: `docs/FUTURE_FEATURES.md`
- Domain and naming checklist: `docs/DOMAIN_PREPURCHASE_CHECKLIST.md`

If there is any conflict, follow `docs/PHASE1.md` for current implementation behavior.

## Agent Goals

1. Keep Phase 1 implementation minimal and reliable.
2. Prefer deterministic, rule-based generation in Phase 1.
3. Avoid introducing paid AI API dependencies unless explicitly requested.
4. Preserve idempotency and safe re-runs in scheduled jobs.

## Phase 1 Functional Contract

- Generate exactly 1 quiz file per enabled quiz type per UTC day.
- Output path must be `quizzes/<uuid>.json` (deterministic UUIDv5 derived from UTC date + quiz type).
- Enabled quiz types are currently `which_came_first` and `history_mcq_4`.
- `which_came_first` must have exactly 2 choices with distinct years.
- `history_mcq_4` must have exactly 4 choices with exactly 1 correct answer.
- Exactly 1 correct choice.
- Use Wikipedia On This Day endpoint as source.
- Commit/push only when a new daily file is created.

## Non-Goals in Phase 1

- No user-facing app implementation.
- No leaderboards, achievements, ratings, or streak systems.
- No extra categories beyond history.
- No always-on service hosting.

## Implementation Conventions

- Keep files and formats simple (JSON + Python + GitHub Actions).
- Add clear validation before writing output.
- Fail closed on invalid data (no partial or malformed commits).
- Keep logs concise and operationally useful.

## Change Management

- Make incremental, reviewable changes.
- Update docs when behavior or contracts change.
- Do not silently change JSON contract fields used in `docs/PHASE1.md`.
- If you need to change the contract, update docs first in the same PR.
