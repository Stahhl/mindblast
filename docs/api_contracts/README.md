# API Contract Snapshots

This directory stores provider-specific API contract snapshots used by `quiz-forge`.

## Purpose
- Keep request/response assumptions explicit and reviewable.
- Prevent schema drift in provider client code.
- Tie CI tests to a known contract snapshot.

## Current Scope
- OpenAI Chat Completions contract for `history_mcq_4` rerank calls.

## Maintenance Rules
1. Source links must be official provider docs.
2. Every snapshot must include:
   - `last_reviewed_utc`
   - source URLs
   - request profile(s)
   - response parsing rules
3. Provider code under `scripts/quiz_forge/ai/providers/` must reference these rules.
4. Contract tests under `tests/quiz_forge/` must fail when code drifts from snapshot.

## Review Trigger
- Review snapshots whenever:
  - model family changes (for example GPT-5.x behavior changes),
  - provider returns new unsupported/invalid parameter errors,
  - API docs update relevant request/response fields.
