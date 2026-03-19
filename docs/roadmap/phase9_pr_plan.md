# Phase 9 PR Plan: Geography Factoid Expansion

## Objective
Deliver Phase 9 in small, reviewable PRs that align directly with `docs/PHASE9.md` and keep the first non-history category deterministic, compliant, and easy to roll back.

## Dependency
- Current history generation and discovery flow remains stable.
- `docs/CONTENT_COMPLIANCE_POLICY.md` remains the legal guardrail.
- `docs/QUIZ_CONTENT_SOURCES.md` records the approved geography source posture before rollout.
- Existing frontend and feedback systems already support additive quiz-type expansion.

## PR1: Docs And Source Approval Baseline

Maps to Phase 9 sections:
- `Source Posture`
- `Type Definition`
- `Workflow And Rollout`

Scope:
- [ ] Add `docs/PHASE9.md`.
- [ ] Update `docs/QUIZ_CONTENT_SOURCES.md` with the selected geography source direction and obligations.
- [ ] Update `docs/FUTURE_FEATURES.md` to mark geography as the selected next category.
- [ ] Update `docs/QUIZ_FORGE_DESIGN.md` where it still implies history-only expansion.
- [ ] Capture the v1 scope boundary clearly:
  - [ ] capital-to-country only
  - [ ] no flags/landmarks/timezones
  - [ ] no disputed or ambiguous capitals

Exit criteria:
- The repo has an implementation-ready Phase 9 spec and source/compliance posture before code changes begin.

## PR2: Shared Contract And Validator Generalization

Maps to Phase 9 sections:
- `Topic Contract`
- `Data Contract`
- `Validation Rules`

Scope:
- [ ] Replace hardcoded global history-only topic validation with per-type topic expectations.
- [ ] Add `geography_factoid_mcq_4` across backend/frontend/feedback quiz-type unions.
- [ ] Add validation for:
  - [ ] `topics = ["geography"]`
  - [ ] `answer_kind = "country"`
  - [ ] `prompt_style = "capital_to_country"`
  - [ ] `entity_type = "country"`
- [ ] Add geography-specific source metadata validation for `source.records_used`.
- [ ] Keep existing history payload validation behavior unchanged.

Exit criteria:
- Shared validators and typed unions can accept the new geography type without weakening existing history checks.

## PR3: Geography Source Adapter And Builder

Maps to Phase 9 sections:
- `Source Posture`
- `Generation Strategy`

Scope:
- [ ] Add deterministic geography source loading for approved country-capital records.
- [ ] Add eligibility filtering for:
  - [ ] non-empty country/capital labels
  - [ ] one-country-one-capital pairs
  - [ ] blocked ambiguous/disputed records
- [ ] Add deterministic correct-answer selection.
- [ ] Add deterministic country distractor selection.
- [ ] Map source records into the existing payload plus additive `source.records_used`.
- [ ] Fail closed when 3 clean distractors cannot be produced.

Exit criteria:
- `quiz-forge` can build valid geography quizzes from approved structured facts with deterministic behavior.

## PR4: Workflow And Discovery Integration

Maps to Phase 9 sections:
- `Workflow And Rollout`
- `Acceptance Criteria`

Scope:
- [ ] Add the new type to generator arguments and internal type registries behind a controlled rollout path.
- [ ] Update workflow/report surfaces that enumerate known quiz types.
- [ ] Verify discovery artifact generation remains correct with mixed history + geography outputs.
- [ ] Ensure commit/no-op behavior remains unchanged when no new geography quiz is generated.

Exit criteria:
- The generation workflow can include the geography type without breaking discovery or operational reporting.

## PR5: Frontend Support

Maps to Phase 9 sections:
- `Frontend Impact`

Scope:
- [ ] Add frontend type support for `geography_factoid_mcq_4`.
- [ ] Render geography prompts and country choices cleanly.
- [ ] Preserve answer locking, correctness feedback, and source attribution behavior.
- [ ] Verify archive/latest flows work when a date includes both history and geography quizzes.

Exit criteria:
- The static app can load and play geography quizzes alongside history quizzes without UI regressions.

## PR6: Rollout And Quality Verification

Maps to Phase 9 sections:
- `Workflow And Rollout`
- `Tests Required`
- `Acceptance Criteria`

Scope:
- [ ] Run limited manual or shadow generation first.
- [ ] Review several days of generated geography output for ambiguity and distractor quality.
- [ ] Confirm fail-closed behavior when the source set is insufficient.
- [ ] Promote to normal daily enablement only after quality review passes.
- [ ] Add short runbook notes for:
  - [ ] how to shadow-run the new type
  - [ ] what to inspect in generated payloads
  - [ ] when to keep the type disabled

Exit criteria:
- Geography generation is reviewable, safe to rerun, and only promoted after output quality is acceptable.

## Merge Order

1. PR1 (docs and source approval baseline)
2. PR2 (shared contract and validator generalization)
3. PR3 (geography source adapter and builder)
4. PR4 (workflow and discovery integration)
5. PR5 (frontend support)
6. PR6 (rollout and quality verification)

## Definition Of Done

- [ ] `docs/PHASE9.md` and source/compliance docs are merged first.
- [ ] `geography_factoid_mcq_4` exists across validators and type unions.
- [ ] Geography payloads use `topics = ["geography"]` and `country` / `capital_to_country` facets.
- [ ] Discovery and frontend flows work with mixed topic sets.
- [ ] Controlled rollout evidence shows acceptable quality before daily enablement.
- [ ] No synthetic or ambiguous geography facts are shipped as sourced content.
