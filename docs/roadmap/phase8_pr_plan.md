# Phase 8 PR Plan: Weekly Feedback Review

## Objective
Deliver Phase 8 in small, reviewable PRs that align directly with `docs/PHASE8.md` and keep the first version internal-only, human-reviewed, and operationally low-risk.

## Dependency
- Phase 7 feedback collection is live in production.
- `mindblast-content` is the source of truth for generated quiz payloads and internal report artifacts.
- Existing AI provider abstraction and budget guardrails remain available for reuse.

## PR1: Data Access and Deterministic Aggregation

Maps to Phase 8 sections:
- `Inputs and Data Model Usage`
- `Weekly Window Definition`
- `Deterministic Aggregation Rules`
- `Comment Sanitization Rules`

Scope:
- [x] Add report-side production feedback reader for Firestore `quiz_feedback`.
- [x] Add weekly UTC window resolution for the previous 7 completed days.
- [x] Load quiz context from `mindblast-content/quizzes/*.json` using `quiz_file`.
- [x] Exclude sensitive fields from all report/LLM payload shapes:
  - [x] `auth_uid`
  - [x] `client_id`
  - [x] `user_agent_hash`
- [x] Implement comment sanitization:
  - [x] strip emails
  - [x] strip URLs
  - [x] strip likely identifiers / long numeric strings
  - [x] normalize whitespace
  - [x] cap excerpt length
- [x] Build deterministic aggregates:
  - [x] total submissions
  - [x] ratings histogram
  - [x] total commented submissions
  - [x] per-question submission count
  - [x] per-question average rating
  - [x] per-question latest feedback timestamp
- [x] Implement deterministic ordering:
  - [x] lowest average rating
  - [x] then highest submission count
  - [x] then latest update timestamp
- [x] Add tests for:
  - [x] weekly window filtering
  - [x] context join by `quiz_file`
  - [x] sanitization
  - [x] aggregate ordering

Exit criteria:
- A deterministic in-memory weekly review payload can be built from production-style feedback records and quiz artifacts without any LLM dependency.

## PR2: LLM Summary Contract and Report Rendering

Maps to Phase 8 sections:
- `Report Outputs`
- `LLM Role and Constraints`
- `Provider and Budget Posture`

Scope:
- [x] Add a structured LLM task contract for weekly feedback review output:
  - [x] `executive_summary`
  - [x] `themes`
  - [x] `positive_signals`
  - [x] `questions_to_review`
  - [x] `action_items`
- [x] Reuse the existing provider abstraction for report summarization.
- [x] Keep report AI settings budget-limited and low-call-count.
- [x] Implement fail-closed fallback:
  - [x] deterministic report still renders when AI fails
  - [x] markdown includes `AI summary unavailable`
- [x] Render committed report outputs:
  - [x] `reports/feedback/weekly/YYYY/YYYY-Www.md`
  - [x] `reports/feedback/weekly/YYYY/YYYY-Www.json`
- [x] Ensure markdown includes:
  - [x] date range
  - [x] aggregate metrics
  - [x] recurring themes
  - [x] action items
  - [x] sanitized excerpts
  - [x] per-question references
- [x] Add tests for:
  - [x] LLM output parsing/validation
  - [x] markdown rendering
  - [x] JSON companion rendering
  - [x] AI fallback behavior

Exit criteria:
- Weekly review reports render deterministically, with optional LLM summary content, and never expose raw sensitive fields.

## PR3: Weekly Workflow and Content Repo Write Path

Maps to Phase 8 sections:
- `Workflow Behavior`
- `Secrets and Config`

Scope:
- [x] Add a weekly GitHub Actions workflow in `mindblast`.
- [x] Check out:
  - [x] `mindblast`
  - [x] `mindblast-content`
- [x] Add production Firestore read-only credential wiring.
- [x] Add report-specific workflow config:
  - [x] provider/model
  - [x] per-run call limit
  - [x] token/budget limits
- [x] Generate reports and commit them to `mindblast-content` only when changed.
- [x] Exit cleanly without commit when:
  - [x] no feedback exists in the weekly window
  - [x] rendered report content is unchanged
- [x] Document required secrets/variables for operations.

Exit criteria:
- A weekly run can produce and commit report artifacts into `mindblast-content` without mutating `mindblast`.

## PR4: Production Validation and Operations

Maps to Phase 8 sections:
- `Acceptance Criteria`
- `Known Limitations`

Scope:
- [ ] Validate one end-to-end non-empty weekly run against production feedback.
- [ ] Validate one zero-feedback/no-op run path.
- [ ] Confirm report artifacts are committed to the expected path in `mindblast-content`.
- [ ] Confirm no raw identifiers or unsanitized comment text appear in outputs.
- [ ] Add short operating notes:
  - [ ] where the report lives
  - [ ] how to rerun manually
  - [ ] what to do when AI summary is unavailable
  - [ ] how humans should triage suggested action items

Exit criteria:
- Weekly reporting is operational, reviewable, and safe to rerun without side effects outside report generation.

## Merge Order

1. PR1 (data access and deterministic aggregation)
2. PR2 (LLM summary contract and report rendering)
3. PR3 (weekly workflow and content repo write path)
4. PR4 (production validation and operations)

## Definition of Done

- [ ] Weekly report reads production feedback and referenced quiz payloads successfully.
- [ ] Reports are written only to `mindblast-content`.
- [ ] Deterministic metrics are present even when AI is unavailable.
- [ ] Report content includes sanitized excerpts only.
- [ ] No user identifiers are exposed.
- [ ] No automatic quiz/config/content changes are performed.
