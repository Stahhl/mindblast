# Phase 9 Specification: Geography Factoid MCQ (`geography_factoid_mcq_4`)

## Naming
- Project name: `Mindblast`.
- User-facing app name: `Mindblast`.
- Backend generator service name: `quiz-forge`.

## Objective
Add the first non-history quiz category to `quiz-forge` while preserving the current operating posture:
- deterministic selection,
- fail-closed validation,
- low-cost scheduled generation,
- idempotent reruns,
- explicit source attribution.

Phase 9 introduces one new geography quiz type:
- `geography_factoid_mcq_4`

## Why Phase 9
- `history_factoid_mcq_4` proves that short-answer factoid questions feel more varied than year-only prompts.
- Geography is the safest next category for a deterministic v1 because:
  - answers are short and entity-like,
  - distractors can be kept within the same answer kind,
  - structured source data is available from low-risk sources,
  - the frontend can support it without a major payload redesign.

## Relationship To Existing Phases
- Extends `docs/PHASE4.md` for multi-edition generation behavior.
- Extends `docs/PHASE2.md` for frontend rendering of an additional quiz type.
- Must comply with `docs/CONTENT_COMPLIANCE_POLICY.md`.
- Uses the source approval posture documented in `docs/QUIZ_CONTENT_SOURCES.md`.

If there is a conflict:
- `docs/PHASE1.md` remains the source of truth for currently shipped history behavior.
- This document defines the intended contract for `geography_factoid_mcq_4`.

## Scope (Phase 9)
- Add quiz type `geography_factoid_mcq_4`.
- Add one geography topic contract:
  - `topics = ["geography"]`
- Keep exactly 4 choices with exactly 1 correct choice.
- Keep the normalized `questions` + `answer_facts` model.
- Keep deterministic UUID/output path behavior and edition semantics unchanged.
- Use approved structured geography facts derived from Wikidata (CC0) for v1.
- Support one prompt family only in v1:
  - capital-to-country

## Out Of Scope
- Country-to-capital prompts.
- Flags, landmarks, timezones, population, language, or mixed geography formats.
- AI-written geography prompts or synthetic distractors.
- Ambiguous/disputed capital-country pairs.
- Dependencies, territories, or multi-capital states unless they are explicitly approved by later docs.
- Broader category-generalization work beyond what is required to safely support this one new type.

## Source Posture

### Approved V1 Source Direction
- Primary source direction: Wikidata-derived structured facts.
- Licensing posture: CC0 / public-domain dedication.
- Terms URL: `https://www.wikidata.org/wiki/Wikidata:Licensing`
- Risk rating: `Green`

### Operational Obligations
- Record the source URL used for the fetch or query.
- Preserve stable source identifiers for country and capital entities.
- Keep attribution explicit in quiz payload source metadata.
- Do not present synthetic distractors or inferred facts as sourced facts.

## Type Definition

### Quiz Type ID
- `geography_factoid_mcq_4`

### Topic Contract
- `topics` must equal `["geography"]` for this type.

This phase begins the move from a global history-only topic rule to per-type topic validation:
- history quiz types keep `topics = ["history"]`
- geography quiz type uses `topics = ["geography"]`

### Question Style
- V1 prompt format is fixed:
  - `Which country has the capital <Capital>?`
- Prompt must end with `?`.
- Prompt must use a single capital label that maps to one intended country in the approved source set.

Examples:
- `Which country has the capital Lima?`
- `Which country has the capital Ottawa?`

### Choice Rules
- Exactly 4 choices.
- Exactly 1 correct choice.
- Each choice includes:
  - `id`
  - `label`
  - `answer_fact_id`
- Choices for this type must not include `year`.
- Choice labels must be country names only.
- Choice labels must be unique after normalization.

### Correctness Rules
- The correct answer must be the country associated with the capital named in the prompt.
- All distractors must also be countries.
- Distractors must be distinct from the correct country and from each other.
- Fail closed if 3 valid distractors are not available.

## Data Contract

### Top-Level Shape
- Keep the existing quiz payload structure unchanged where possible:
  - `date`
  - `topics`
  - `type`
  - `questions`
  - `answer_facts`
  - `question`
  - `choices`
  - `correct_choice_id`
  - `source`
  - `generation`
  - `metadata`

### Question Facets
For `questions[0]`:
- `type == "geography_factoid_mcq_4"`
- `facets.question_format = "factoid"`
- `facets.answer_kind = "country"`
- `facets.prompt_style = "capital_to_country"`
- `facets.topic = "geography"`

### Answer Facts
For `answer_facts[*]`:
- `facets.entity_type = "country"`
- `label` is the country name shown to users
- `vector_metadata.text_for_embedding` may include both country and capital context

### Source Metadata
The current history-oriented `source.events_used` shape is insufficient for clean geography attribution.

Phase 9 therefore adds additive geography-specific source metadata:
- `source.records_used`

For `geography_factoid_mcq_4`, `source.records_used` must contain exactly 4 entries aligned with `choices[*]`.

Each record must include:
- `record_id`
- `country_label`
- `capital_label`
- `country_qid`
- `capital_qid`
- `country_url`
- `capital_url`

Notes:
- Keep `source.name`, `source.url`, and `source.retrieved_at` required.
- Existing history quiz types keep using `source.events_used`.
- This is additive source metadata, not a breaking top-level schema redesign.

## Generation Strategy

### Eligibility Rules
A source record is eligible only if:
- it represents one country with one approved capital label,
- the capital label is non-empty and suitable for prompt text,
- the country label is non-empty and suitable for a choice button,
- the pair is not in a blocked ambiguous/disputed set,
- the country label normalizes distinctly from the other selected choices.

### V1 Rejection Rules
Reject in v1:
- countries with multiple current capitals in the approved source set,
- capitals shared by multiple accepted countries,
- disputed capitals,
- labels that require long explanatory qualifiers to be unambiguous,
- records that would force non-country distractors.

### Deterministic Selection
High-level flow:
1. Resolve the target UTC date and quiz edition as usual.
2. Fetch the approved geography source snapshot/query result.
3. Filter to eligible country-capital records.
4. Select one correct capital-country pair using deterministic seeded ordering.
5. Select 3 deterministic country distractors from the same eligible pool.
6. Build normalized payload + geography source metadata.
7. Run shared and type-specific validation.
8. Fail closed on any ambiguity, duplicate, or insufficient distractor case.

Determinism requirements:
- selection order must be reproducible for the same `(date, quiz_type, edition, source snapshot)`
- UUID/output path derivation remains based on `date + quiz_type + edition`
- reruns must not create duplicate files

## Validation Rules
- `type == "geography_factoid_mcq_4"`
- `topics == ["geography"]`
- `choices.length == 4`
- exactly 1 correct choice
- `choices[*].year` is forbidden
- `question == questions[0].prompt`
- `question` must match the form `Which country has the capital <Capital>?`
- `questions[0].facets.question_format == "factoid"`
- `questions[0].facets.answer_kind == "country"`
- `questions[0].facets.prompt_style == "capital_to_country"`
- every `answer_facts[*].facets.entity_type == "country"`
- all choice labels are unique normalized country labels
- `source.records_used.length == 4`
- each `source.records_used[*]` entry must map cleanly to one choice / answer fact

## Frontend Impact
- Existing quiz-card rendering can remain structurally similar.
- Frontend must expand known quiz-type unions to include `geography_factoid_mcq_4`.
- Frontend must display the geography prompt and country choices cleanly.
- Source attribution remains visible via the existing payload source fields.
- Archive/latest discovery flows must continue to support mixed-topic dates.

## Workflow And Rollout
- Implement behind a controlled rollout rather than enabling it broadly on day one.
- Recommended rollout path:
  1. docs and source approval
  2. validator/type-union support
  3. builder + source adapter
  4. shadow or limited manual generation
  5. several days of output review
  6. daily target enablement only after quality is acceptable

## Tests Required

### Validation Tests
- accept a well-formed geography payload
- reject non-`["geography"]` topics
- reject prompts that do not match `capital_to_country`
- reject non-country answer labels
- reject duplicate countries
- reject multiple correct answers

### Builder / Generation Tests
- deterministic UUID/output path behavior
- deterministic capital selection for a fixed source snapshot
- fail-closed behavior when distractors are insufficient
- rejection of ambiguous/disputed capitals in v1

### Discovery / Frontend Tests
- mixed dates containing history and geography types
- `latest.json` and daily index loading with the new type present
- answer flow and attribution rendering for the new type

## Acceptance Criteria
- `quiz-forge` can generate valid `geography_factoid_mcq_4` payloads.
- Payloads pass shared and type-specific validation.
- Discovery artifacts include the new type without breaking history quiz loading.
- Frontend can load, render, answer, and attribute the new type.
- Scheduled/manual generation remains safe to rerun and commits only when new files are created.
- Weak or ambiguous geography candidates are rejected rather than published.

## Open Decisions For Implementation
- Whether the geography source fetch should use a checked-in snapshot, a remote query, or a build-time derived artifact.
- Whether distractors should prefer regional proximity or stay purely deterministic by stable ordering in v1.
- Whether `source.records_used` alone is sufficient, or whether geography answer facts should also carry `country_qid` / `capital_qid` facets for downstream use.
