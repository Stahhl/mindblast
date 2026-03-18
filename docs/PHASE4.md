# Phase 4 Specification: Multi-Generation Quizzes (Same-Day Editions)

## Naming
- Project name: `Mindblast`.
- User-facing app name: `Mindblast`.
- Backend generator service name: `quiz-forge`.

## Objective
Enable `quiz-forge` to generate more than one quiz per type per UTC day so content can be iterated faster, while keeping the scheduled daily run as the default behavior.

## Why Phase 4
- Speed up iteration without waiting for the next UTC day.
- Keep current daily publishing flow stable.
- Make the frontend and discovery layer support both daily and extra same-day quiz editions.

## Dependency
- Phase 4 extends:
  - `docs/PHASE1.md` (generation contract),
  - `docs/PHASE1_5.md` (discovery artifacts),
  - `docs/PHASE2.md` (frontend behavior).

## Scope (Phase 4)
- Keep daily cron generation as default.
- Add support for multiple same-day quiz editions per quiz type.
- Keep Wikipedia On This Day as the default source.
- Update index/latest artifacts for multi-edition discovery.
- Update frontend to browse and play multiple quizzes for a date.

## Out of Scope
- New non-Wikipedia data sources (unless separately documented and approved).
- User accounts or server-side answer persistence.
- Personalization or adaptive recommendation.
- Replacing static hosting with an always-on backend API.

## Core Behavior Changes

### Generation Modes
- `daily` mode:
  - default for scheduled workflow,
  - generates the configured daily edition range per enabled type for the UTC day.
- `extra` mode:
  - used for manual/operational runs,
  - generates one or more additional editions above the configured daily range for the type.

Default scheduled daily targets:
- `which_came_first`: `1`
- `history_mcq_4`: `1`
- `history_factoid_mcq_4`: `3`

### Edition Semantics
- `edition` is a positive integer scoped by `(date, quiz_type)`.
- `edition = 1` must always be `daily`.
- Editions inside the configured daily range for the type are `daily`.
- Extra runs must allocate the next available edition strictly above the configured daily range (no gaps unless historical data already has gaps).

### UUID and File Naming
- Output path remains: `quizzes/<uuid>.json`.
- Deterministic UUIDv5 input must include `date + quiz_type + edition`.
- This allows multiple files per type/day without collisions.

## Data Contract (Additive)

### Quiz Payload Additions
Add fields to each quiz payload:
- `generation.mode`: `daily` | `extra`
- `generation.edition`: integer (`>= 1`)
- `generation.generated_at`: UTC ISO-8601 timestamp (`Z`)

Notes:
- Existing fields in Phase 1 remain valid and required.
- Additions are backward-compatible and additive.

### Discovery Artifact Changes

#### Daily Index (`quizzes/index/YYYY-MM-DD.json`)
Move from one-file-per-type shape to edition-aware shape.

Required fields:
- `date`
- `quizzes_by_type`: map of quiz type to ordered list of edition entries
- `available_types`
- `metadata`

Edition entry shape:
- `edition`
- `mode`
- `quiz_file`
- `generated_at`

Backward compatibility:
- keep `quiz_files` (single file per type) pointing to edition 1 where available, so older clients keep working during migration.

#### Latest Pointer (`quizzes/latest.json`)
Keep existing purpose but add edition-aware fields:
- `date`
- `index_file`
- `available_types`
- `latest_quiz_by_type` (points to latest edition file for each type on `date`)
- `metadata`

## Source and Selection Strategy
- Keep Wikimedia On This Day endpoint as source.
- For each additional same-day edition:
  - avoid repeating the exact same question payload for that `(date, quiz_type)`,
  - prefer unused source events first,
  - fail closed when unique valid output cannot be produced.
- Maintain existing quiz-type validation rules (choice count, one correct answer, etc.).

## Pipeline and CI Changes

### Scheduled Workflow
- Keep cron default unchanged: one daily generation run.
- Scheduled run behavior remains:
  - target mode: `daily`
  - target daily editions by type: `which_came_first=1,history_mcq_4=1,history_factoid_mcq_4=3`

### Manual Workflow Expansion
Add/extend `workflow_dispatch` inputs:
- `quiz_types` (comma-separated)
- `mode` (`daily` | `extra`, default `extra` for manual runs)
- `count` (number of quizzes per selected type, default `1`)
- `daily_editions_by_type` (comma-separated `quiz_type=count` map)
- optional `date` override for backfills

Rules:
- `daily` mode via manual dispatch should ensure the configured daily edition range exists.
- `extra` mode generates next available editions strictly above the configured daily range.
- `extra` mode fails closed when the configured daily range does not yet exist for a date/type.
- Commit/push only when at least one new quiz file is created.

## Frontend Changes (Phase 2 Alignment)
- Keep current default: show latest date quizzes first.
- Add same-day edition awareness:
  - show latest edition by default per type,
  - provide "More quizzes today" access for other editions.
- Add/archive date browsing:
  - list all quizzes for selected date, grouped by type and edition.
- Add stable deep-link route by quiz file UUID so any historical quiz is playable.
- Preserve current source-visibility guardrail (sources hidden by default behind user toggle).

## Validation and Testing Plan

### Unit Tests (`scripts/quiz_forge`)
- Edition allocator for `(date, quiz_type)`.
- UUID determinism with edition included.
- Duplicate payload prevention across same-day editions.
- Mode behavior (`daily` vs `extra`).

### Integration Tests
- Rebuild index/latest with mixed single-edition and multi-edition dates.
- Verify backward compatibility fields remain correct.

### Frontend Tests
- Date screen renders multiple editions.
- Default selection uses latest edition for the date/type.
- Deep-link loading by quiz file UUID.

## Rollout Plan
1. Docs-first contract update (this phase doc + linked contracts).
2. Generator changes:
   - per-type daily target args,
   - edition-aware UUIDs,
   - duplicate guards.
3. Discovery artifact upgrade:
   - `quizzes_by_type`,
   - compatibility `quiz_files`,
   - `latest_quiz_by_type`.
4. Workflow updates:
   - keep cron daily default,
   - add manual `extra` generation controls,
   - record requested daily targets in persisted run reports.
5. Frontend updates for multi-edition and archive UX.
6. Verify staging end-to-end and then promote to production.

## Acceptance Criteria
- Daily cron produces `which_came_first=1`, `history_mcq_4=1`, and `history_factoid_mcq_4=3`.
- Manual extra generation can produce additional editions for the same date/type.
- Index/latest artifacts expose all editions and remain backward-compatible during migration.
- Frontend can discover, browse, and answer historical quizzes with multiple editions per date.
- Validation fails closed on invalid or non-unique extra editions.
