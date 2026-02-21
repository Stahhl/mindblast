# quiz-forge Design Doc

## Purpose
`quiz-forge` is the backend generator that creates one daily quiz payload and commits it to this repository.  
In Phase 1, it produces one history question of type `which_came_first`.

## Naming
- Project name: `Mindblast`.
- User-facing app name: `Mindblast`.
- Backend generator service name: `quiz-forge`.

## Goals
- Keep operations simple and nearly zero-maintenance.
- Keep infrastructure cost at or near $0 in Phase 1.
- Produce deterministic, valid JSON output once per day.
- Support incremental expansion to new quiz modes and categories.

## Non-Goals (Phase 1)
- Running an always-on backend service.
- Managing users, scores, leaderboards, or achievements.
- Serving API traffic directly to clients.

## System Context
- `quiz-forge` runs on GitHub Actions using a daily schedule.
- It fetches source data from Wikimedia On This Day.
- It writes one file at `quizzes/YYYY-MM-DD.json`.
- The `Mindblast` app consumes this file later.

## Proposed Tech Stack
- Runtime: Python 3.12
- CI/Scheduler: GitHub Actions cron
- HTTP client: Python standard library (`urllib`) or `requests`
- Validation: built-in checks in Python (optionally add `jsonschema` later)
- Storage: Git repository JSON files (Phase 1 source of truth)

## Why This Stack
- No dedicated server required.
- Zero baseline hosting cost.
- Easy auditability through git history.
- Fast to evolve and refactor later.

## Execution Flow (Daily Job)
1. Determine current UTC date.
2. Build output path `quizzes/YYYY-MM-DD.json`.
3. Exit early if file already exists (idempotency).
4. Call Wikimedia On This Day endpoint for current month/day.
5. Filter events to valid candidates:
   - has year
   - has readable text
   - has at least one Wikipedia page URL
6. Pick two events with distinct years.
7. Construct `which_came_first` JSON payload.
8. Run contract validation.
9. Write JSON to disk.
10. Commit and push only when a new file is created.

## Data Contract Ownership
- Contract lives in `/Users/stahl/dev/vajb_engine/docs/PHASE1.md`.
- `quiz-forge` script must enforce all validation rules before commit.
- Schema version starts at `metadata.version = 1`.

## Guardrails

### Cost Guardrails
- Phase 1 uses Wikimedia data only and no paid AI calls.
- Expected daily infra cost: $0.
- If paid AI is introduced later, add:
  - hard daily budget env var (example: `MAX_DAILY_SPEND_USD=5`)
  - max token/request cap per run
  - fail-closed behavior when budget is exceeded

### Quality Guardrails
- No tie years in Phase 1 questions.
- No duplicate choice IDs.
- Non-empty text fields only.
- Source attribution must be present in output.
- If input data quality is insufficient, fail job instead of writing weak output.

### Reliability Guardrails
- Single-run concurrency group in GitHub Actions (avoid duplicate runs).
- Network timeouts and small retry policy for source fetch.
- Atomic write pattern (write temp file then move).
- No partial commits on failure.

### Security Guardrails
- Minimal GitHub permissions in workflow:
  - `contents: write` only (needed for commit/push)
- No secrets required in Phase 1.
- Sanitize/log only non-sensitive data.

## CI/CD Design
- Trigger: `schedule` only.
- No push/PR/manual triggers in Phase 1.
- Workflow steps:
  1. checkout
  2. setup python
  3. run generator
  4. git add/commit/push if changes exist
- Bot commit message format:
  - `quiz-forge: add quiz for YYYY-MM-DD`

## Repository Layout
```text
.
├── .github/workflows/daily-quiz.yml
├── scripts/generate_quiz.py
├── quizzes/
└── docs/
    ├── PHASE1.md
    ├── FUTURE_FEATURES.md
    └── QUIZ_FORGE_DESIGN.md
```

## Operational Notes
- Schedule should run at a fixed UTC time to avoid timezone drift.
- If job fails on a day, no file is created for that day; this is acceptable for Phase 1.
- Optional later improvement: backfill command for missing dates.

## Evolution Path
1. Stabilize Phase 1 (`which_came_first`, one question/day).
2. Add ratings feedback signal from the `Mindblast` app.
3. Add MCQ mode (original 4-option plan).
4. Add category expansion and difficulty levels.
5. Add leaderboards, achievements, and streak logic.

## Open Decisions
- Keep pure rule-based generation or add optional LLM refinement later.
- When to migrate from git-file storage to database storage.
- Whether to produce one global question/day or per-locale/per-region variants.
