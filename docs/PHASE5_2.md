# Phase 5.2 Specification: Deterministic Factoid Expansion

## Naming
- Project name: `Mindblast`.
- User-facing app name: `Mindblast`.
- Backend generator service name: `quiz-forge`.

## Objective
Expand `history_factoid_mcq_4` beyond year-only answers so the generator can publish more varied short-answer history questions using deterministic, rule-based extraction.

Primary target additions:
- `who` questions with `person` answers
- `where` questions with `place` answers
- keep `when` questions with `time` answers as the fallback path

## Relationship to Other Phases
- Extends `docs/PHASE5.md` without replacing its shipped initial implementation record.
- Sits before `docs/PHASE5_5.md`, which remains the AI-native follow-up.
- If there is a conflict for `history_factoid_mcq_4`, this document supersedes the Phase 5 initial restriction that only `when`/`time` is publishable.

## Why This Phase
- Current `history_factoid_mcq_4` output is still answering with years only, which limits perceived variety.
- The existing normalized model already supports typed factoid metadata (`answer_kind`, `prompt_style`, `entity_type`).
- Deterministic extraction is a safer next step than jumping directly to AI-native generation.
- This phase preserves the Phase 1/1.5 operating posture: low-cost, idempotent, fail-closed, and easy to audit.

## Scope (Phase 5.2)
- Expand `history_factoid_mcq_4` publishable question styles from only `when` to `who`, `where`, and `when`.
- Add a deterministic factoid-candidate extraction layer derived from Wikipedia On This Day event text.
- Represent short answers as typed entities instead of always using the source event year as the choice label.
- Add typed distractor selection so person questions get person distractors, place questions get place distractors, and time questions keep time distractors.
- Keep all generation file paths, discovery artifacts, and daily scheduler behavior unchanged.
- Preserve deterministic re-run behavior for the same `(date, quiz_type, edition)` input.

## Out of Scope
- AI-generated question writing or distractor generation.
- Replacing `history_mcq_4`.
- New quiz types beyond `history_factoid_mcq_4`.
- Free-form "thing" or object answers without a reliable typed extractor.
- Non-history categories.
- Publishing ambiguous or weakly supported extracted entities.

## Product Intent
This phase is specifically meant to improve answer variety. Suitable target answers are:
- people
- places
- time answers

Avoid in this phase:
- generic nouns
- long descriptive phrases
- entity types that cannot be validated with simple deterministic rules

## Generation Strategy

### High-Level Flow
1. Fetch and validate Wikipedia On This Day event candidates as today.
2. Derive zero or more factoid candidates from each event:
   - `person` / `who`
   - `place` / `where`
   - `time` / `when`
3. Score candidates using deterministic quality heuristics.
4. Pick one publishable factoid candidate using seeded ordering.
5. Select 3 distractors that match the chosen candidate's `answer_kind`.
6. Validate answer distinctness, source support, and payload contract.
7. If no `person` or `place` candidate passes, fallback to current `time` behavior.

### Deterministic Extraction Policy
Extraction must not depend on nondeterministic model output.

Initial heuristics may include:
- person:
  - detect linked Wikipedia page titles in event text that look like personal names
  - prefer titles with 2 to 4 capitalized tokens
  - reject obvious institutions, battles, ships, laws, months, and dynasties
- place:
  - detect linked page titles or event spans following cues such as `in`, `at`, `near`, `from`
  - prefer recognized place-like strings over generic regions or directions
  - reject overly broad labels such as `Europe` unless no narrower supported place exists
- time:
  - keep current year-based fallback behavior

### Candidate Quality Gates
A factoid candidate is publishable only if:
- it has a short answer label suitable for a choice button
- the answer is explicitly supported by the source event text or closely aligned linked page title
- the prompt is answerable with exactly one intended answer
- the answer label is not just a copy of the full event sentence
- the answer label is not empty, generic, or heavily punctuation-dependent

Fail policy:
- discard weak candidates
- do not degrade to synthetic guesses
- fallback to `when`/`time` if stronger typed extraction fails

## Data Contract Updates

### Quiz Type
- Quiz type remains `history_factoid_mcq_4`.
- No new top-level schema version is required.

### Question Facets
`questions[0].facets.question_format` remains:
- `factoid`

`questions[0].facets.answer_kind` becomes:
- `person`
- `place`
- `time`

`questions[0].facets.prompt_style` becomes:
- `who`
- `where`
- `when`

Required alignment:
- `answer_kind = person` must pair with `prompt_style = who`
- `answer_kind = place` must pair with `prompt_style = where`
- `answer_kind = time` must pair with `prompt_style = when`

### Answer Facts
For `history_factoid_mcq_4`, `answer_facts[*]` remain required and should describe the short answer entity used by the choice, not just the full source event.

Required additions/expectations:
- `answer_facts[*].facets.entity_type` must align with `questions[0].facets.answer_kind`
- `answer_facts[*].label` should be the short answer label shown to users
- `answer_facts[*].vector_metadata.text_for_embedding` may include the short answer label and supporting event text

### Source Attribution
`source.events_used` remains required and attributable to Wikipedia On This Day source events.

For this phase:
- each choice must still map back to a real source event
- the short answer label may be normalized from the source text
- normalization must preserve factual identity

## Prompt Rules

### Allowed Prompt Forms
- `Who ...?`
- `Where ...?`
- `When ...?`

### Prompt Requirements
- Must end with `?`
- Must match `questions[0].facets.prompt_style`
- Must be concise and natural
- Must be answerable from the linked source event without outside inference beyond simple normalization

### Choice Requirements
- Exactly 4 choices
- Exactly 1 correct choice
- Choices must not include `year`
- Choice labels should be short and entity-like where possible
- Distractors should match the correct answer's `answer_kind`

## Distractor Selection Rules

### Person
- distractors must be people
- prefer similar era/context when deterministic rules can support it
- reject duplicate surnames when they create ambiguity with the correct answer
- reject labels that are clearly not person names

### Place
- distractors must be places
- prefer similar geographic scale when possible
- reject vague regions when the correct answer is a specific city/site
- reject labels that are clearly organizations or events

### Time
- keep current distinct-time-answer behavior
- maintain existing no-year-field-on-choice rule

### Shared Rules
- no duplicate labels
- no semantically identical aliases of the correct answer
- no distractor that leaks the answer in the question text
- fail closed if 3 valid distractors cannot be found

## Implementation Plan

### Workstream 1: Contract and Validation
- update generator validation so `history_factoid_mcq_4` accepts `person|place|time` and `who|where|when`
- keep strict alignment checks between `answer_kind` and `prompt_style`
- add validation for `answer_facts[*].facets.entity_type`

### Workstream 2: Extraction Layer
- add a deterministic factoid candidate model separate from raw source events
- extract candidate `question`, `answer_label`, `answer_kind`, `prompt_style`, and `supporting_event`
- seed-order candidates so reruns stay deterministic

### Workstream 3: Typed Builder
- update the factoid builder to build choices from typed short answers
- preserve current `when` implementation as the fallback path
- keep normalized question/answer-fact payload shape compatible with existing clients

### Workstream 4: Distractor Matching
- add typed distractor pools for `person` and `place`
- reuse deterministic ordering and fail-closed behavior
- prefer a smaller, high-confidence distractor set over broad fuzzy matching

### Workstream 5: Tests
- add unit tests for candidate extraction heuristics
- add payload validation tests for each supported prompt style
- add generation tests that confirm fallback to `when/time` when `who` or `where` extraction is insufficient
- add regression tests to ensure daily file naming/idempotency behavior does not change

## Rollout Plan
1. Docs first: approve this phase contract.
2. Implement validator and internal candidate model behind current factoid type.
3. Ship deterministic `who` support first.
4. Ship deterministic `where` support second.
5. Keep `when/time` fallback enabled throughout rollout.
6. Observe generated output quality over several days before broadening heuristics.
7. Revisit `docs/PHASE5_5.md` only after deterministic typed factoids are stable.

## Acceptance Criteria
- The generator can publish valid `history_factoid_mcq_4` quizzes with `who`, `where`, or `when` prompts.
- Published factoid choices are no longer always years.
- `person` questions use person distractors, `place` questions use place distractors, and `time` questions use time distractors.
- The pipeline remains deterministic and idempotent for the same run inputs.
- Weak extraction falls back to safe `when/time` output instead of publishing ambiguous questions.
- Existing clients continue to load quiz payloads without structural breaking changes.

## Open Decisions
- Whether deterministic place extraction is strong enough to ship at the same time as person extraction, or should remain second.
- Whether answer-fact IDs for typed factoids should be derived from the short answer entity alone or from entity plus supporting event identity.
- How aggressively to normalize answer labels when source page titles differ from the best user-facing short answer.

