# Phase 5.5 Specification: AI-Native Factoid Pipeline

## Naming
- Project name: `Mindblast`.
- User-facing app name: `Mindblast`.
- Backend generator service name: `quiz-forge`.

## Objective
Define a production-safe AI workflow for generating `history_factoid_mcq_4` content with stronger models, while preserving strict quality, attribution, and spend guardrails.

## Relationship to Other Phases
- Extends `docs/PHASE5.md` (new factoid quiz type contract).
- Builds on `docs/PHASE5_2.md` for deterministic typed factoid expansion.
- Reuses Phase 3 provider abstraction and budget controls.
- Keeps Phase 4 multi-edition generation behavior compatible.

## Scope (Phase 5.5)
- Add an AI-native multi-step generation workflow for history factoid quizzes.
- Support per-step model selection (strong model where needed, cheaper model elsewhere).
- Add verification gates before publishing generated distractors/questions.
- Use fetched Wikipedia page context as the grounding source for candidate generation.
- Keep published answer choices sourced-only; no synthetic distractors.
- Daily run may fall back to the deterministic builder whenever the AI-native path is not publishable.

## Out of Scope
- Non-history categories.
- Unverified synthetic facts.
- Removing deterministic fallback paths.
- User-personalized generation.

## Pipeline Overview

### Source Page Selection Policy (Deterministic)
Selection must be deterministic and repeatable for `(date, edition, quiz_type)`.

Required policy:
1. Maintain a curated source registry (seed set of approved Wikipedia pages + tags).
2. Build a daily candidate set from:
   - registry pages not on cooldown,
   - optionally a small freshness slice from trusted linked pages.
3. Apply hard filters before AI calls:
   - no disambiguation/list pages,
   - minimum content quality threshold,
   - no blocked/risky pages from compliance policy.
4. Score candidates using non-AI heuristics:
   - recency of use (prefer less recently used),
   - historical acceptance rate,
   - answer-kind balance (`person/place/time`).
5. Pick page(s) using deterministic seeded ordering:
   - seed key: `date + edition + quiz_type`.
6. On repeated low-quality outcomes, apply cooldown and move to next candidate.

Operational notes:
- Page selection should not depend on non-deterministic model output.
- Re-runs for same seed should resolve to same primary candidate ordering unless registry changes.

### Stage 0: Source Ingest
Inputs:
- Deterministically selected linked Wikipedia pages from the daily On This Day candidate pool.

Outputs:
- Normalized source document package:
  - `event_id`
  - event text/year
  - page URL
  - page title
  - page extract
  - retrieval timestamp

### Stage 1: Candidate Q/A Generation (Strong Model)
Goal:
- Generate multiple factoid candidates from each source.

Output contract per candidate:
- `question`
- `correct_answer`
- `answer_kind` (`person` | `place` | `organization` | `work` | `object` | `time`)
- `answer_subtype`
- `prompt_style` (`who` | `where` | `when` | `what` | `which`)
- `evidence_text` (verbatim source span)
- `page_context_id`
- `score`

Rules:
- Candidate must be answerable from source.
- Answer must be short-form (entity/date style, not long sentence).
- `correct_answer` must appear in the page title or page extract.
- `evidence_text` must appear verbatim in the page extract.
- The question prompt must not contain the correct answer.

### Stage 2: Candidate Ranking + Quality Gate (Light Model + Rules)
Goal:
- Keep only high-quality candidates before distractor generation.

Checks:
- clarity (single unambiguous answer)
- answer length bounds
- duplicate/near-duplicate intent removal
- support evidence presence

Outcome:
- Candidate gets `quality_score_1`.
- Candidates below threshold are discarded.
- Typed candidate review must reject vague fragments, wrong entity forms, mixed-type labels, and answers that are not grounded in source text.

### Stage 3: Distractor Generation (Strong Model + Typed Constraints)
Goal:
- Generate plausible distractors for approved candidates.

Constraints:
- exactly 3 distractors
- no duplicates
- no answer leakage
- strongly match `answer_kind`
- distractor IDs must come only from the grounded accepted candidate pool supplied to the model
- distractors must also match `answer_subtype`

Weighting policy:
- `answer_kind = person`: distractors must be real people.
- same profession/class as correct answer: medium preference.
- same era/context: low-medium preference.
- same exact identity/path: forbidden.

### Stage 4: Distractor Verification (Deterministic + Optional Light Model)
Required checks before publish:
- entity exists in trusted source graph (Wikipedia/Wikidata lookup).
- entity type matches expected `answer_kind`.
- distractor is not semantically the same entity as correct answer.
- source attribution for distractors is real and non-fabricated.

Fail policy:
- If verification fails, discard AI distractor set.
- Retry once with adjusted constraints; if still invalid, fallback to deterministic distractor selector.
- Deterministic linting remains the final publish gate even if the AI distractor set is schema-valid.

### Stage 5: Final Ranking/Judging
Goal:
- Score end-to-end quiz quality after distractors are attached.

Scoring dimensions:
- question clarity
- distractor plausibility
- uniqueness
- source support confidence

Outcome:
- `quality_score_final`
- `publishable` boolean

### Stage 6: Publish to Question Bank and Daily Quiz Selection
If `publishable`:
- persist candidate to reusable question bank
- mark provenance + generation metadata

Daily scheduler behavior:
- select at least 1 approved factoid item per day when available
- if none available, fail closed to existing supported types/fallback behavior (no malformed publish)

## Data Contracts

### Question Bank Entry (new internal artifact)
Path suggestion:
- `quizzes/bank/history_factoid/<id>.json`

Required fields:
- `id`
- `question`
- `correct_answer`
- `answer_kind`
- `prompt_style`
- `distractors`
- `source` metadata
- `quality_score_1`
- `quality_score_final`
- `verification` details
- `ai_lineage` (provider/model/step summaries)

### Published Quiz Payload
- Must remain compatible with `docs/PHASE5.md`.
- Additive metadata allowed:
  - `metadata.pipeline_version`
  - `metadata.generation_method = "ai_native_factoid_v1"`
- Additive source provenance allowed:
  - `source.page_sources[*].answer_fact_id`
  - `source.page_sources[*].page_url`
  - `source.page_sources[*].page_title`
  - `source.page_sources[*].retrieved_at`

## Model Strategy
- Stage 1 and Stage 3: stronger model tier allowed.
- Stage 2 and Stage 5: cheaper model tier preferred.
- Verification stages should remain deterministic-first.

Provider-agnostic configuration:
- `FACTOID_AI_MODEL_QA_GEN`
- `FACTOID_AI_MODEL_DISTRACTOR_GEN`
- `FACTOID_AI_MODEL_RANKER`
- `FACTOID_AI_MODEL_JUDGE`
- `FACTOID_AI_PIPELINE_ENABLED` (feature flag, default `false`)

## Budget Guardrails
- Keep existing hard caps:
  - `AI_MAX_DAILY_USD = 1.00`
  - `AI_MAX_MONTHLY_USD = 5.00`
- Add per-stage caps:
  - `AI_MAX_CALLS_QA_GEN_PER_RUN`
  - `AI_MAX_CALLS_DISTRACTOR_PER_RUN`
  - `AI_MAX_CALLS_JUDGE_PER_RUN`
- Hard stop behavior:
  - if cap exceeded, skip remaining AI stages and fallback deterministically.

## Compliance Guardrails
- Never fabricate citations.
- Never claim distractors are sourced if verification failed.
- If synthetic content is ever allowed in future, it must be explicitly tagged and excluded from sourced fact lists unless truly sourced.

## Observability
Per run report must include:
- calls/tokens/cost by stage
- accepted vs rejected candidates per stage
- fallback reasons by stage
- published count and rejected count

Discord daily summary extension:
- include stage-level call/cost summary
- include publishability funnel (`generated -> passed_q1 -> passed_verify -> published`)

## Human Intervention
Expected ongoing intervention:
- none for normal daily operations.

Required one-time setup:
1. Configure per-stage model env vars.
2. Ensure provider credentials and budget vars are present.
3. Enable question-bank artifact path in workflow commits.

Manual triggers:
- recurring low-quality scores
- verification failure spikes
- budget cap breaches

## Rollout Plan
1. Docs + contracts first (this phase).
2. Implement question-bank storage + schemas.
3. Implement Stage 1/2 generation and gate.
4. Implement Stage 3/4 distractor generation + verification.
5. Implement Stage 5 judge and publishability thresholds.
6. Enable staged rollout in `shadow` publication mode first.
7. Promote to default publication after acceptance metrics are stable.

## Acceptance Criteria
- End-to-end pipeline produces valid `history_factoid_mcq_4` quizzes with short-answer style.
- Published items pass all verification gates.
- Stage-level spend and usage are reported daily.
- Hard budget limits are never exceeded without deterministic fallback.
- Daily pipeline remains reliable and idempotent.
