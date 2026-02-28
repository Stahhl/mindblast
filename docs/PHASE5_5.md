# Phase 5.5 Specification: AI-Native Factoid Pipeline

## Naming
- Project name: `Mindblast`.
- User-facing app name: `Mindblast`.
- Backend generator service name: `quiz-forge`.

## Objective
Define a production-safe AI workflow for generating `history_factoid_mcq_4` content with stronger models, while preserving strict quality, attribution, and spend guardrails.

## Relationship to Other Phases
- Extends `docs/PHASE5.md` (new factoid quiz type contract).
- Reuses Phase 3 provider abstraction and budget controls.
- Keeps Phase 4 multi-edition generation behavior compatible.

## Scope (Phase 5.5)
- Add an AI-native multi-step generation workflow for history factoid quizzes.
- Support per-step model selection (strong model where needed, cheaper model elsewhere).
- Add verification gates before publishing generated distractors/questions.
- Persist approved question assets in a reusable question bank.
- Daily run must publish at least 1 valid factoid quiz when sufficient approved content exists.

## Out of Scope
- Non-history categories.
- Unverified synthetic facts.
- Removing deterministic fallback paths.
- User-personalized generation.

## Pipeline Overview

### Stage 0: Source Ingest
Inputs:
- Curated source URL list (initially Wikipedia pages with clear attribution trail).

Outputs:
- Normalized source document package:
  - URL
  - title
  - extracted spans/sentences
  - detected entities
  - retrieval timestamp

### Stage 1: Candidate Q/A Generation (Strong Model)
Goal:
- Generate multiple factoid candidates from each source.

Output contract per candidate:
- `question`
- `correct_answer`
- `answer_kind` (`person` | `place` | `time`)
- `prompt_style` (`who` | `where` | `when`)
- `supporting_span` (verbatim or pointer to exact source text)
- `source_url`

Rules:
- Candidate must be answerable from source.
- Answer must be short-form (entity/date style, not long sentence).

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

### Stage 3: Distractor Generation (Strong Model + Typed Constraints)
Goal:
- Generate plausible distractors for approved candidates.

Constraints:
- exactly 3 distractors
- no duplicates
- no answer leakage
- strongly match `answer_kind`

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

## Model Strategy
- Stage 1 and Stage 3: stronger model tier allowed.
- Stage 2 and Stage 5: cheaper model tier preferred.
- Verification stages should remain deterministic-first.

Provider-agnostic configuration:
- `AI_MODEL_QA_GEN`
- `AI_MODEL_DISTRACTOR_GEN`
- `AI_MODEL_RANKER`
- `AI_MODEL_JUDGE`

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
