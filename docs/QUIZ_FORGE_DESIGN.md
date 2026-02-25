# quiz-forge Design Doc

## Purpose
`quiz-forge` is the backend generator that creates daily quiz payloads and commits them to this repository.  
In Phase 1, it produces one history quiz per enabled type (`which_came_first`, `history_mcq_4`).

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
- It writes one file at `quizzes/<uuid>.json` per enabled type using a deterministic UUIDv5 derived from UTC date + quiz type.
- It writes discovery artifacts at `quizzes/index/YYYY-MM-DD.json` and `quizzes/latest.json`.
- The `Mindblast` app consumes this file later.

## Proposed Tech Stack
- Runtime: Python 3.12
- Python project/dependency manager: `uv` (`pyproject.toml` + `uv.lock`)
- CI/Scheduler: GitHub Actions cron
- HTTP client: Python standard library (`urllib`) or `requests`
- Validation: built-in checks in Python (optionally add `jsonschema` later)
- Storage: Git repository JSON files (Phase 1 source of truth)
- Phase 3 AI providers (intended):
  - external: OpenAI API
  - local: Ollama

## Why This Stack
- No dedicated server required.
- Zero baseline hosting cost.
- Easy auditability through git history.
- Fast to evolve and refactor later.

## Execution Flow (Daily Job)
1. Determine current UTC date.
2. Determine enabled quiz types.
3. Build output path `quizzes/<uuid>.json` for each type from deterministic UUIDv5(date + type).
4. Skip only the types whose output file already exists (idempotency).
5. Call Wikimedia On This Day endpoint for current month/day.
6. Filter events to valid candidates:
   - has year
   - has readable text
   - has at least one Wikipedia page URL
7. Generate payloads through a quiz-type registry (one builder per type).
   - payloads include normalized `questions` + `answer_facts` plus compatibility fields.
   - previously selected correct answer-facts are eligible distractors for subsequent quiz types when valid.
   - in Phase 3 for `history_mcq_4`, optionally make one AI rerank call for distractor ordering and fallback deterministically on any failure.
8. Run shared + type-specific contract validation.
9. Write JSON files to disk.
10. Write/update discovery artifacts for static client lookup.
11. Commit and push only when new files are created.

## Data Contract Ownership
- Contract lives in `/Users/stahl/dev/mindblast/docs/PHASE1.md`.
- `quiz-forge` script must enforce all validation rules before commit.
- Current schema version is `metadata.version = 2`.

## Guardrails

### Cost Guardrails
- Phase 1 uses Wikimedia data only and no paid AI calls.
- Expected daily infra cost: $0.
- If paid AI is introduced later, add:
  - hard daily budget env var (`AI_MAX_DAILY_USD`, Phase 3 default `1.00`)
  - hard monthly budget env var (`AI_MAX_MONTHLY_USD`, Phase 3 default `5.00`)
  - max token/request cap per run
  - fail-closed behavior when budget is exceeded
  - deterministic fallback path when AI is unavailable
  - daily pipeline usage reporting (calls/tokens/spend/fallback summary)

### Quality Guardrails
- No tie years in Phase 1 questions.
- No duplicate choice IDs.
- Non-empty text fields only.
- Source attribution must be present in output.
- If input data quality is insufficient, fail job instead of writing weak output.
- Do not fabricate source attributions for generated/synthetic content.
- If synthetic content is introduced later, it must be explicitly labeled and excluded from sourced event attribution.

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
- In Phase 3, provider credentials are required for external AI mode and must be stored in CI secrets (never in repo).
- Human operation should be limited to key generation/rotation, environment config updates, and daily report review.

## CI/CD Design
- Trigger: `schedule` (manual dispatch allowed for operational reruns).
- No push/PR triggers in Phase 1.
- Workflow steps:
  1. checkout
  2. setup python
  3. install `uv` and sync locked environment
  4. run generator with `uv run`
  5. emit operational summary report to Discord (including AI usage when enabled)
  6. git add/commit/push if changes exist
- Bot commit message format:
  - `quiz-forge: add quiz for YYYY-MM-DD`

## Repository Layout
```text
.
├── .github/workflows/daily-quiz.yml
├── pyproject.toml
├── uv.lock
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
1. Stabilize Phase 1 multi-type generation (`which_came_first`, `history_mcq_4`).
2. Add Phase 1.5 discovery artifacts for static clients (`quizzes/latest.json` + daily index files).
3. Ship Phase 2 frontend app that consumes static discovery + quiz files.
4. Add Phase 3 AI-assisted distractor reranking with budget-limited provider abstraction.
5. Add ratings feedback signal from the `Mindblast` app.
6. Add category expansion and difficulty levels.
7. Add leaderboards, achievements, and streak logic.

## Open Decisions
- Keep pure rule-based generation or add optional LLM refinement later.
- When to migrate from git-file storage to database storage.
- Whether to produce one global question/day or per-locale/per-region variants.
