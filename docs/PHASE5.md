# Phase 5 Specification: History Factoid MCQ (`history_factoid_mcq_4`)

## Naming
- Project name: `Mindblast`.
- User-facing app name: `Mindblast`.
- Backend generator service name: `quiz-forge`.

## Objective
Add a second history MCQ format where questions are more specific and answers are shorter (person, place, or time), for example:

- Question: `Who killed Abraham Lincoln?`
- Choices:
  - `John Wilkes Booth` (correct)
  - `Lee Harvey Oswald`
  - `Brutus`
  - `Mark David Chapman`

## Why This Phase
- Current `history_mcq_4` prompts are mostly `Which event happened in <year>?`.
- Variety improves playability and perceived quiz quality.
- Existing normalized model already supports this with additive metadata.

## Scope (Phase 5)
- Introduce new quiz type: `history_factoid_mcq_4`.
- Keep `topics: ["history"]`.
- Keep exactly 4 choices with exactly 1 correct choice.
- Keep normalized `questions` + `answer_facts` model.
- Keep discovery/index flow unchanged (Phase 4 multi-edition compatible).
- Initial implementation target: `when`/`time` prompts first, with `who`/`where` expansion in follow-up work.

## Out of Scope
- Replacing `history_mcq_4`.
- Non-history categories.
- User-personalized prompt generation.
- Fabricated facts without verifiable attribution.

## Type Definition

### Quiz Type ID
- `history_factoid_mcq_4`

### Question Style
- More elaborate prompt, shorter answer labels.
- Supported answer kinds:
  - `person`
  - `place`
  - `organization`
  - `work`
  - `object`
  - `time`
- Supported prompt styles:
  - `who`
  - `where`
  - `when`
  - `what`
  - `which`
- AI-native generation is page-grounded:
  - answers must be supported by fetched Wikipedia page context
  - distractors must come from other grounded page-backed candidates of the same `answer_kind` and `answer_subtype`

Examples:
- `Who assassinated Julius Caesar?`
- `Where did the Battle of Waterloo take place?`
- `When did the Berlin Wall fall?`

### Choice Rules
- Exactly 4 choices.
- Each choice includes:
  - `id`
  - `label`
  - `answer_fact_id`
- Choices for this type must not include `year`.
- Labels should be concise and entity-like where possible.

### Correctness Rules
- Exactly 1 correct choice.
- Correct choice must map to `questions[0].correct_answer_fact_id`.
- All `questions[0].answer_fact_ids` must align with `choices[*].answer_fact_id` order.

## Data Contract (Additive)

No new top-level schema version is required. Use current v2 schema with additive facets/tags.

`questions[0]` required additions for this type:
- `facets.question_format = "factoid"`
- `facets.answer_kind` in `person|place|organization|work|object|time`
- `facets.answer_subtype` as a short non-empty string such as `band`, `song`, `album`, `instrument`, or `city`
- `facets.prompt_style` in `who|where|when|what|which`

`answer_facts[*]` recommended additions:
- `facets.entity_type` aligned with `questions[0].facets.answer_kind`
- `facets.entity_subtype` aligned with `questions[0].facets.answer_subtype`
- existing `vector_metadata` stays required for future embedding workflows

## Source and Attribution
- Source attribution requirements remain identical to Phase 1:
  - `source.name`, `source.url`, `source.retrieved_at`
  - `source.events_used` must be real attributable events/facts.
- AI-native page-grounded factoids may add:
  - `source.page_sources[*].answer_fact_id`
  - `source.page_sources[*].page_url`
  - `source.page_sources[*].page_title`
  - `source.page_sources[*].retrieved_at`
- No fabricated source links.
- If source text is long, answer labels may be normalized/shortened, but must preserve factual identity.

## Generation Strategy

High-level builder behavior:
1. Deterministically select a bounded set of linked Wikipedia pages from the daily On This Day pool.
2. Fetch normalized page context (`title` + grounded extract) for those pages.
3. Generate 1-3 grounded factoid candidates per page with answer kind, subtype, prompt style, answer, and evidence span.
4. Reject any candidate whose answer or evidence is not locally grounded in the fetched page context.
5. Select 3 distractors from other accepted candidates with the same `answer_kind` and `answer_subtype`.
6. Judge the final assembled quiz, then build normalized payload and run standard validation.

Failure policy:
- Fail closed when short-answer extraction quality is insufficient.
- Do not publish weak/ambiguous questions just to satisfy count.

## Frontend Impact
- Existing frontend can render this type without structural payload changes.
- Optional UI enhancement:
  - display subtype badge using `questions[0].facets.prompt_style` (`Who`/`Where`/`When`).

## Validation Rules (Type-Specific)
- `type == "history_factoid_mcq_4"`.
- `choices.length == 4`.
- `choices[*].year` is forbidden.
- `question` must end with `?`.
- `questions[0].facets.question_format == "factoid"`.
- `questions[0].facets.answer_kind` must be one of the supported factoid answer kinds.
- `questions[0].facets.answer_subtype` must be present and non-empty.
- `questions[0].facets.prompt_style` must be one of the supported prompt styles and align with `answer_kind`.
- `answer_facts[*].facets.entity_type` must align with `questions[0].facets.answer_kind`.
- `answer_facts[*].facets.entity_subtype` must align with `questions[0].facets.answer_subtype`.
- Exactly one correct choice.

## Rollout Plan
1. Docs-first: introduce this Phase 5 contract.
2. Add new builder + validator for `history_factoid_mcq_4`.
3. Add generation tests for:
   - shape/contract validity,
   - one-correct-choice guarantee,
   - short-answer quality checks.
4. Enable type in workflow in `shadow` style generation first (no removal of existing type).
5. Observe quality in staging and adjust selector heuristics.

## Acceptance Criteria
- Generator can create valid `history_factoid_mcq_4` payloads.
- Payload passes shared + type-specific validation.
- Discovery/index/frontend load works without breaking existing quiz types.
- Questions are materially different in style from `history_mcq_4` and follow short-answer factoid format.
