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
- [ ] Add report-side production feedback reader for Firestore `quiz_feedback`.
- [ ] Add weekly UTC window resolution for the previous 7 completed days.
- [ ] Load quiz context from `mindblast-content/quizzes/*.json` using `quiz_file`.
- [ ] Exclude sensitive fields from all report/LLM payload shapes:
  - [ ] `auth_uid`
  - [ ] `client_id`
  - [ ] `user_agent_hash`
- [ ] Implement comment sanitization:
  - [ ] strip emails
  - [ ] strip URLs
  - [ ] strip likely identifiers / long numeric strings
  - [ ] normalize whitespace
  - [ ] cap excerpt length
- [ ] Build deterministic aggregates:
  - [ ] total submissions
  - [ ] ratings histogram
  - [ ] total commented submissions
  - [ ] per-question submission count
  - [ ] per-question average rating
  - [ ] per-question latest feedback timestamp
- [ ] Implement deterministic ordering:
  - [ ] lowest average rating
  - [ ] then highest submission count
  - [ ] then latest update timestamp
- [ ] Add tests for:
  - [ ] weekly window filtering
  - [ ] context join by `quiz_file`
  - [ ] sanitization
  - [ ] aggregate ordering

Exit criteria:
- A deterministic in-memory weekly review payload can be built from production-style feedback records and quiz artifacts without any LLM dependency.

## PR2: LLM Summary Contract and Report Rendering

Maps to Phase 8 sections:
- `Report Outputs`
- `LLM Role and Constraints`
- `Provider and Budget Posture`

Scope:
- [ ] Add a structured LLM task contract for weekly feedback review output:
  - [ ] `executive_summary`
  - [ ] `themes`
  - [ ] `positive_signals`
  - [ ] `questions_to_review`
  - [ ] `action_items`
- [ ] Reuse the existing provider abstraction for report summarization.
- [ ] Keep report AI settings budget-limited and low-call-count.
- [ ] Implement fail-closed fallback:
  - [ ] deterministic report still renders when AI fails
  - [ ] markdown includes `AI summary unavailable`
- [ ] Render committed report outputs:
  - [ ] `reports/feedback/weekly/YYYY/YYYY-Www.md`
  - [ ] `reports/feedback/weekly/YYYY/YYYY-Www.json`
- [ ] Ensure markdown includes:
  - [ ] date range
  - [ ] aggregate metrics
  - [ ] recurring themes
  - [ ] action items
  - [ ] sanitized excerpts
  - [ ] per-question references
- [ ] Add tests for:
  - [ ] LLM output parsing/validation
  - [ ] markdown rendering
  - [ ] JSON companion rendering
  - [ ] AI fallback behavior

Exit criteria:
- Weekly review reports render deterministically, with optional LLM summary content, and never expose raw sensitive fields.

## PR3: Weekly Workflow and Content Repo Write Path

Maps to Phase 8 sections:
- `Workflow Behavior`
- `Secrets and Config`

Scope:
- [ ] Add a weekly GitHub Actions workflow in `mindblast`.
- [ ] Check out:
  - [ ] `mindblast`
  - [ ] `mindblast-content`
- [ ] Add production Firestore read-only credential wiring.
- [ ] Add report-specific workflow config:
  - [ ] provider/model
  - [ ] per-run call limit
  - [ ] token/budget limits
- [ ] Generate reports and commit them to `mindblast-content` only when changed.
- [ ] Exit cleanly without commit when:
  - [ ] no feedback exists in the weekly window
  - [ ] rendered report content is unchanged
- [ ] Document required secrets/variables for operations.

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
