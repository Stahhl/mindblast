# Phase 8 Specification: Weekly Feedback Review

## Naming
- Project name: `Mindblast`.
- User-facing app name: `Mindblast`.
- Backend generator service name: `quiz-forge`.

## Objective
Add an internal weekly feedback review workflow that combines deterministic analysis with an LLM summary layer.

The goal is to turn submitted quiz feedback into:
- weekly summaries,
- recurring themes,
- prioritized review targets,
- concrete suggested action items.

## Why This Phase
- Feedback is now being collected in Firestore.
- Raw records are useful, but not efficient to review manually over time.
- Current expected volume is low enough that a weekly batch review is sufficient.
- LLM assistance is useful for summarization, theme synthesis, and drafting action items.
- Human review must remain the final decision-maker for any follow-up changes.

## Scope (Phase 8)
- Read production feedback records from Firestore.
- Join feedback to quiz card context using `quiz_file`.
- Generate one weekly internal report.
- Write markdown + JSON report files to `Stahhl/mindblast-content`.
- Include deterministic aggregates plus LLM-generated summary content.
- Keep provider usage budget-limited and fail closed on AI/provider failures.

## Out of Scope
- Public dashboards or public report publishing.
- Automatic quiz edits.
- Automatic prompt or config tuning.
- Moderation tooling beyond basic comment sanitization.
- Staging feedback analysis.
- User-facing exposure of feedback summaries.
- Automatic GitHub issue creation or task assignment.

## Inputs and Data Model Usage

### Data Sources
- Firestore collection: `quiz_feedback`.
- Quiz context from `Stahhl/mindblast-content/quizzes/*.json`.

### Fields Consumed
The workflow consumes existing feedback fields only, including:
- `quiz_file`
- `date`
- `quiz_type`
- `edition`
- `question_id`
- `question_human_id`
- `rating`
- `comment`
- `feedback_date_utc`
- `created_at`
- `updated_at`

### Fields Excluded From LLM and Report Output
The following fields must never be sent to the LLM or surfaced in report content:
- `auth_uid`
- `client_id`
- `user_agent_hash`
- raw auth/provider metadata not needed for review

## Weekly Window Definition
- Run once per week on Monday in UTC.
- Cover the previous 7 completed UTC days.
- Example: a Monday run reports on Monday-Sunday ending the day before the run.
- If no production feedback exists in the window, the workflow exits successfully and writes nothing.

## Report Outputs

### File Paths
Commit two files to `Stahhl/mindblast-content`:
- `reports/feedback/weekly/YYYY/YYYY-Www.md`
- `reports/feedback/weekly/YYYY/YYYY-Www.json`

### Markdown Report Contents
The markdown report must include:
- date range
- overall submission counts
- rating distribution
- number of comments
- strongest positive signals
- weakest questions to review
- recurring themes
- suggested action items
- sanitized excerpts
- per-question references using `question_human_id`, `question_id`, and `quiz_file`

### JSON Companion Contents
The JSON report must include:
- metadata
- date window
- aggregate metrics
- per-question summaries
- LLM output fields
- sanitized excerpts
- action items

## Deterministic Aggregation Rules
Deterministic analysis must run before any LLM call.

Required aggregates:
- total submissions
- ratings histogram
- total commented submissions
- per-question submission count
- per-question average rating
- per-question latest feedback timestamp

Deterministic ordering:
- lowest average rating first
- then highest submission count
- then latest update timestamp

The LLM must receive only the deterministic summary package plus quiz context and sanitized excerpts.

## Comment Sanitization Rules
Comment text may appear only as sanitized excerpts.

Required sanitization behavior:
- strip emails
- strip URLs
- strip long number strings and likely identifiers
- normalize whitespace
- cap excerpt length
- drop or redact obviously sensitive text
- never include raw unfiltered comments in the report or LLM payload

## LLM Role and Constraints

### Allowed LLM Tasks
The LLM is used only for:
- executive summary
- theme synthesis
- positive signal summary
- question review prioritization
- action item drafting

### Disallowed LLM Behavior
The LLM must not:
- invent user feedback
- invent quiz content
- claim certainty beyond provided evidence
- suggest automatic changes as if already approved
- rewrite source facts or quiz payloads directly

### Required Structured Output
The LLM output must be structured with these fields:
- `executive_summary`
- `themes`
- `positive_signals`
- `questions_to_review`
- `action_items`

## Provider and Budget Posture
- Provider abstraction: reuse the existing provider abstraction.
- Intended first provider: `OpenAI`.
- Intended first model: `gpt-5-mini`.
- Use provider-enforced structured outputs with a strict response schema for weekly summary generation when supported by the chosen provider.
- Do not rely on prompt-only `return JSON` instructions as the primary contract for weekly summary output.

Hard constraints:
- low call count per weekly run
- low token budget
- fail closed on provider error or budget overrun
- if AI fails, still allow deterministic report generation with an explicit `AI summary unavailable` section

## Workflow Behavior
Planned GitHub Actions flow:
1. Check out `mindblast`.
2. Check out `mindblast-content`.
3. Authenticate to production Firestore with read-only credentials.
4. Load weekly feedback data.
5. Load referenced quiz files from `mindblast-content`.
6. Build deterministic aggregates.
7. Run LLM summarization.
8. Render markdown + JSON files.
9. Commit report files to `mindblast-content` if changed.

`mindblast` remains the orchestration repository only. Report artifacts live in `mindblast-content`.

## Secrets and Config
Required secrets/config for implementation:
- production Firestore read-only service account secret
- existing `OPENAI_API_KEY`
- `QUIZ_CONTENT_REPO`
- report-specific config values for model and limits

Credential posture:
- Firestore credentials must be read-only.
- Report generation credentials must not grant write access to feedback data.

## Acceptance Criteria
- Weekly workflow can read production feedback and referenced quiz payloads.
- Markdown + JSON report files are generated for a non-empty week.
- Report contains deterministic metrics plus LLM summary output.
- No user identifiers are exposed.
- Sanitized excerpts only are included.
- No automatic content or config changes occur.
- Zero-feedback week exits cleanly without a commit.

## Known Limitations
- Low feedback volume may make weekly themes sparse.
- Summaries are advisory, not ground truth.
- Sanitized comments may lose nuance.
- No long-term trend analysis exists in v1.
- No auto-triage into GitHub issues exists in v1.
