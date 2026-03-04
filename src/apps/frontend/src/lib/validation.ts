import type { IndexPayload, LatestPayload, QuizPayload, QuizSource, QuizType } from "./types";

const KNOWN_TYPES = new Set<QuizType>(["which_came_first", "history_mcq_4", "history_factoid_mcq_4"]);

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) {
    throw new Error(message);
  }
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isQuizType(value: unknown): value is QuizType {
  return isNonEmptyString(value) && KNOWN_TYPES.has(value as QuizType);
}

function isHumanId(value: unknown, prefix: "Q" | "A"): value is string {
  if (!isNonEmptyString(value) || !value.startsWith(prefix)) {
    return false;
  }
  const suffix = value.slice(prefix.length);
  return /^\d+$/.test(suffix) && Number.parseInt(suffix, 10) >= 1;
}

function validateSource(source: unknown, expectedLength: number): asserts source is QuizSource {
  assert(source && typeof source === "object", "quiz.source must be an object");

  const sourceValue = source as Record<string, unknown>;
  assert(isNonEmptyString(sourceValue.name), "quiz.source.name must be a non-empty string");
  assert(isNonEmptyString(sourceValue.url), "quiz.source.url must be a non-empty string");
  assert(isNonEmptyString(sourceValue.retrieved_at), "quiz.source.retrieved_at must be a non-empty string");

  assert(Array.isArray(sourceValue.events_used), "quiz.source.events_used must be an array");
  assert(
    sourceValue.events_used.length === expectedLength,
    `quiz.source.events_used must contain exactly ${expectedLength} entries`
  );

  sourceValue.events_used.forEach((event, idx) => {
    assert(event && typeof event === "object", `quiz.source.events_used[${idx}] must be an object`);

    const eventValue = event as Record<string, unknown>;
    assert(isNonEmptyString(eventValue.text), `quiz.source.events_used[${idx}].text must be a non-empty string`);
    assert(Number.isInteger(eventValue.year), `quiz.source.events_used[${idx}].year must be an integer`);
    assert(
      isNonEmptyString(eventValue.wikipedia_url),
      `quiz.source.events_used[${idx}].wikipedia_url must be a non-empty string`
    );
  });
}

function validateCommonQuizShape(quiz: unknown): asserts quiz is QuizPayload {
  assert(quiz && typeof quiz === "object", "quiz must be an object");
  const quizValue = quiz as Record<string, unknown>;

  assert(isNonEmptyString(quizValue.date), "quiz.date must be a non-empty string");
  assert(Array.isArray(quizValue.topics), "quiz.topics must be an array");
  assert(quizValue.topics.length > 0, "quiz.topics must contain at least one topic");
  assert(quizValue.topics.every((entry) => isNonEmptyString(entry)), "quiz.topics entries must be non-empty strings");

  assert(isQuizType(quizValue.type), `quiz.type '${String(quizValue.type)}' is unsupported`);

  assert(isNonEmptyString(quizValue.question), "quiz.question must be a non-empty string");
  assert(Array.isArray(quizValue.choices), "quiz.choices must be an array");
  assert(quizValue.choices.length > 0, "quiz.choices must not be empty");

  quizValue.choices.forEach((choice, idx) => {
    assert(choice && typeof choice === "object", `quiz.choices[${idx}] must be an object`);
    const choiceValue = choice as Record<string, unknown>;
    assert(isNonEmptyString(choiceValue.id), `quiz.choices[${idx}].id must be a non-empty string`);
    assert(isNonEmptyString(choiceValue.label), `quiz.choices[${idx}].label must be a non-empty string`);
    if (choiceValue.human_id !== undefined) {
      assert(
        isHumanId(choiceValue.human_id, "A"),
        `quiz.choices[${idx}].human_id must match A<integer> when present`
      );
    }
  });

  const uniqueIds = new Set(quizValue.choices.map((choice) => (choice as { id: string }).id));
  assert(uniqueIds.size === quizValue.choices.length, "quiz.choices IDs must be unique");
  assert(uniqueIds.has(quizValue.correct_choice_id as string), "quiz.correct_choice_id must match a choice id");

  assert(quizValue.metadata && typeof quizValue.metadata === "object", "quiz.metadata must be an object");
  const metadata = quizValue.metadata as Record<string, unknown>;
  assert(metadata.version === 1 || metadata.version === 2, "quiz.metadata.version must be 1 or 2");

  const generation = quizValue.generation;
  if (generation !== undefined) {
    assert(generation && typeof generation === "object", "quiz.generation must be an object when present");
    const generationValue = generation as Record<string, unknown>;
    assert(isNonEmptyString(generationValue.mode), "quiz.generation.mode must be a non-empty string");
    assert(Number.isInteger(generationValue.edition), "quiz.generation.edition must be an integer");
    assert((generationValue.edition as number) >= 1, "quiz.generation.edition must be >= 1");
    assert(
      isNonEmptyString(generationValue.generated_at),
      "quiz.generation.generated_at must be a non-empty string"
    );
  }

  if (metadata.version === 2) {
    assert(
      isNonEmptyString(metadata.normalized_model),
      "quiz.metadata.normalized_model must be a non-empty string when version is 2"
    );
    validateNormalizedModel(quizValue);
  }
}

function validateNormalizedModel(quizValue: Record<string, unknown>): void {
  assert(Array.isArray(quizValue.answer_facts), "quiz.answer_facts must be an array for schema v2");
  assert(quizValue.answer_facts.length > 0, "quiz.answer_facts must not be empty for schema v2");

  const answerFacts = quizValue.answer_facts as Array<Record<string, unknown>>;
  const factIds = new Set<string>();
  answerFacts.forEach((fact, idx) => {
    assert(fact && typeof fact === "object", `quiz.answer_facts[${idx}] must be an object`);
    assert(isNonEmptyString(fact.id), `quiz.answer_facts[${idx}].id must be a non-empty string`);
    if (fact.human_id !== undefined) {
      assert(
        isHumanId(fact.human_id, "A"),
        `quiz.answer_facts[${idx}].human_id must match A<integer> when present`
      );
    }
    assert(isNonEmptyString(fact.label), `quiz.answer_facts[${idx}].label must be a non-empty string`);
    assert(Number.isInteger(fact.year), `quiz.answer_facts[${idx}].year must be an integer`);
    assert(Array.isArray(fact.tags), `quiz.answer_facts[${idx}].tags must be an array`);
    assert(fact.tags.length > 0, `quiz.answer_facts[${idx}].tags must not be empty`);
    assert(
      fact.tags.every((tag) => isNonEmptyString(tag)),
      `quiz.answer_facts[${idx}].tags entries must be non-empty strings`
    );
    assert(fact.facets && typeof fact.facets === "object", `quiz.answer_facts[${idx}].facets must be an object`);
    assert(fact.match && typeof fact.match === "object", `quiz.answer_facts[${idx}].match must be an object`);
    assert(
      fact.vector_metadata && typeof fact.vector_metadata === "object",
      `quiz.answer_facts[${idx}].vector_metadata must be an object`
    );
    const vectorMetadata = fact.vector_metadata as Record<string, unknown>;
    assert(
      isNonEmptyString(vectorMetadata.text_for_embedding),
      `quiz.answer_facts[${idx}].vector_metadata.text_for_embedding must be a non-empty string`
    );
    assert(
      isNonEmptyString(vectorMetadata.embedding_status),
      `quiz.answer_facts[${idx}].vector_metadata.embedding_status must be a non-empty string`
    );
    factIds.add(fact.id as string);
  });

  assert(Array.isArray(quizValue.questions), "quiz.questions must be an array for schema v2");
  assert(quizValue.questions.length === 1, "quiz.questions must contain exactly one item for schema v2");

  const question = quizValue.questions[0] as Record<string, unknown>;
  assert(question && typeof question === "object", "quiz.questions[0] must be an object");
  assert(isNonEmptyString(question.id), "quiz.questions[0].id must be a non-empty string");
  if (question.human_id !== undefined) {
    assert(
      isHumanId(question.human_id, "Q"),
      "quiz.questions[0].human_id must match Q<integer> when present"
    );
  }
  assert(isQuizType(question.type), "quiz.questions[0].type must be a known quiz type");
  assert(isNonEmptyString(question.prompt), "quiz.questions[0].prompt must be a non-empty string");
  assert(
    question.prompt === quizValue.question,
    "quiz.questions[0].prompt must match the legacy quiz.question field"
  );
  assert(Array.isArray(question.answer_fact_ids), "quiz.questions[0].answer_fact_ids must be an array");
  assert(question.answer_fact_ids.length > 0, "quiz.questions[0].answer_fact_ids must not be empty");
  assert(
    question.answer_fact_ids.every((value) => isNonEmptyString(value)),
    "quiz.questions[0].answer_fact_ids entries must be non-empty strings"
  );
  question.answer_fact_ids.forEach((factId, idx) => {
    assert(factIds.has(factId as string), `quiz.questions[0].answer_fact_ids[${idx}] must reference answer_facts`);
  });
  assert(
    isNonEmptyString(question.correct_answer_fact_id),
    "quiz.questions[0].correct_answer_fact_id must be a non-empty string"
  );
  assert(
    (question.answer_fact_ids as string[]).includes(question.correct_answer_fact_id as string),
    "quiz.questions[0].correct_answer_fact_id must be in answer_fact_ids"
  );
  assert(Array.isArray(question.tags), "quiz.questions[0].tags must be an array");
  assert(question.tags.length > 0, "quiz.questions[0].tags must not be empty");
  assert(
    question.tags.every((tag) => isNonEmptyString(tag)),
    "quiz.questions[0].tags entries must be non-empty strings"
  );
  assert(question.facets && typeof question.facets === "object", "quiz.questions[0].facets must be an object");
  assert(
    question.selection_rules && typeof question.selection_rules === "object",
    "quiz.questions[0].selection_rules must be an object"
  );

  const choiceAnswerFactIds = (quizValue.choices as Array<Record<string, unknown>>).map((choice, idx) => {
    assert(
      isNonEmptyString(choice.answer_fact_id),
      `quiz.choices[${idx}].answer_fact_id must be a non-empty string for schema v2`
    );
    return choice.answer_fact_id as string;
  });

  assert(
    JSON.stringify(choiceAnswerFactIds) === JSON.stringify(question.answer_fact_ids),
    "quiz.choices[*].answer_fact_id order must match quiz.questions[0].answer_fact_ids"
  );

  const factHumanIdById = new Map<string, string | undefined>();
  answerFacts.forEach((fact) => {
    factHumanIdById.set(fact.id as string, fact.human_id as string | undefined);
  });

  const choiceHumanIds = (quizValue.choices as Array<Record<string, unknown>>).map((choice) => choice.human_id);
  const hasChoiceHumanIds = choiceHumanIds.some((value) => value !== undefined);
  const hasFactHumanIds = answerFacts.some((fact) => fact.human_id !== undefined);
  assert(
    hasChoiceHumanIds === hasFactHumanIds,
    "quiz.choices[*].human_id and quiz.answer_facts[*].human_id must either both be present or both absent"
  );
  if (hasChoiceHumanIds && hasFactHumanIds) {
    (quizValue.choices as Array<Record<string, unknown>>).forEach((choice, idx) => {
      const expectedHumanId = factHumanIdById.get(choice.answer_fact_id as string);
      assert(
        choice.human_id === expectedHumanId,
        `quiz.choices[${idx}].human_id must match the linked answer_fact human_id`
      );
    });
  }
}

function validateWhichCameFirst(quiz: QuizPayload): void {
  assert(quiz.type === "which_came_first", "quiz.type mismatch for which_came_first validation");
  assert(quiz.choices.length === 2, "which_came_first must have exactly 2 choices");

  const years = quiz.choices.map((choice, idx) => {
    assert(Number.isInteger(choice.year), `which_came_first choice ${idx + 1} must include integer year`);
    return choice.year;
  });

  assert(years[0] !== years[1], "which_came_first choice years must be distinct");
  validateSource(quiz.source, 2);
}

function validateHistoryMcq4(quiz: QuizPayload): void {
  assert(quiz.type === "history_mcq_4", "quiz.type mismatch for history_mcq_4 validation");
  assert(quiz.choices.length === 4, "history_mcq_4 must have exactly 4 choices");

  quiz.choices.forEach((choice, idx) => {
    const choiceWithYear = choice as { year?: unknown };
    assert(choiceWithYear.year === undefined, `history_mcq_4 choice ${idx + 1} must not include year`);
  });

  validateSource(quiz.source, 4);
}

function validateHistoryFactoidMcq4(quiz: QuizPayload): void {
  assert(quiz.type === "history_factoid_mcq_4", "quiz.type mismatch for history_factoid_mcq_4 validation");
  assert(quiz.choices.length === 4, "history_factoid_mcq_4 must have exactly 4 choices");

  quiz.choices.forEach((choice, idx) => {
    const choiceWithYear = choice as { year?: unknown };
    assert(choiceWithYear.year === undefined, `history_factoid_mcq_4 choice ${idx + 1} must not include year`);
  });

  assert(quiz.question.trim().endsWith("?"), "history_factoid_mcq_4 question must end with '?'");
  validateSource(quiz.source, 4);
}

export function validateLatestPayload(payload: unknown): LatestPayload {
  assert(payload && typeof payload === "object", "latest payload must be an object");
  const latest = payload as Record<string, unknown>;

  assert(isNonEmptyString(latest.date), "latest.date must be a non-empty string");
  assert(isNonEmptyString(latest.index_file), "latest.index_file must be a non-empty string");

  assert(Array.isArray(latest.available_types), "latest.available_types must be an array");
  assert(latest.available_types.length > 0, "latest.available_types must not be empty");
  latest.available_types.forEach((quizType, idx) => {
    assert(isQuizType(quizType), `latest.available_types[${idx}] must be a known quiz type`);
  });

  assert(latest.metadata && typeof latest.metadata === "object", "latest.metadata must be an object");
  const metadata = latest.metadata as Record<string, unknown>;
  assert(metadata.version === 1 || metadata.version === 2, "latest.metadata.version must be 1 or 2");

  if (latest.latest_quiz_by_type !== undefined) {
    assert(
      latest.latest_quiz_by_type && typeof latest.latest_quiz_by_type === "object",
      "latest.latest_quiz_by_type must be an object when present"
    );
    Object.entries(latest.latest_quiz_by_type as Record<string, unknown>).forEach(([quizType, quizPath]) => {
      assert(isQuizType(quizType), `latest.latest_quiz_by_type key '${quizType}' must be a known quiz type`);
      assert(
        isNonEmptyString(quizPath),
        `latest.latest_quiz_by_type['${quizType}'] must be a non-empty string`
      );
    });
  }

  return latest as unknown as LatestPayload;
}

export function validateIndexPayload(payload: unknown): IndexPayload {
  assert(payload && typeof payload === "object", "index payload must be an object");
  const index = payload as Record<string, unknown>;
  assert(isNonEmptyString(index.date), "index.date must be a non-empty string");

  assert(index.quiz_files && typeof index.quiz_files === "object", "index.quiz_files must be an object");
  const entries = Object.entries(index.quiz_files as Record<string, unknown>);
  assert(entries.length > 0, "index.quiz_files must not be empty");

  entries.forEach(([quizType, quizPath]) => {
    assert(isQuizType(quizType), `index.quiz_files key '${quizType}' must be a known quiz type`);
    assert(isNonEmptyString(quizPath), `index.quiz_files['${quizType}'] must be a non-empty string`);
  });

  assert(Array.isArray(index.available_types), "index.available_types must be an array");
  assert(index.available_types.length > 0, "index.available_types must not be empty");
  index.available_types.forEach((quizType, idx) => {
    assert(isQuizType(quizType), `index.available_types[${idx}] must be a known quiz type`);
  });

  const fileKeys = entries.map(([quizType]) => quizType);

  assert(index.metadata && typeof index.metadata === "object", "index.metadata must be an object");
  const metadata = index.metadata as Record<string, unknown>;
  assert(metadata.version === 1 || metadata.version === 2, "index.metadata.version must be 1 or 2");

  if (index.quizzes_by_type !== undefined) {
    assert(index.quizzes_by_type && typeof index.quizzes_by_type === "object", "index.quizzes_by_type must be an object");
    const typeEntries = Object.entries(index.quizzes_by_type as Record<string, unknown>);
    assert(typeEntries.length > 0, "index.quizzes_by_type must not be empty");

    typeEntries.forEach(([quizType, editions]) => {
      assert(isQuizType(quizType), `index.quizzes_by_type key '${quizType}' must be a known quiz type`);
      assert(Array.isArray(editions), `index.quizzes_by_type['${quizType}'] must be an array`);
      assert(editions.length > 0, `index.quizzes_by_type['${quizType}'] must not be empty`);
      let previousEdition = 0;
      editions.forEach((entry, idx) => {
        assert(entry && typeof entry === "object", `index.quizzes_by_type['${quizType}'][${idx}] must be an object`);
        const entryValue = entry as Record<string, unknown>;
        assert(
          Number.isInteger(entryValue.edition) && (entryValue.edition as number) >= 1,
          `index.quizzes_by_type['${quizType}'][${idx}].edition must be an integer >= 1`
        );
        const edition = entryValue.edition as number;
        assert(
          edition > previousEdition,
          `index.quizzes_by_type['${quizType}'][${idx}].edition must be strictly ascending`
        );
        previousEdition = edition;
        assert(
          isNonEmptyString(entryValue.mode),
          `index.quizzes_by_type['${quizType}'][${idx}].mode must be a non-empty string`
        );
        assert(
          isNonEmptyString(entryValue.quiz_file),
          `index.quizzes_by_type['${quizType}'][${idx}].quiz_file must be a non-empty string`
        );
        assert(
          isNonEmptyString(entryValue.generated_at),
          `index.quizzes_by_type['${quizType}'][${idx}].generated_at must be a non-empty string`
        );
      });
    });

    const typeKeys = typeEntries.map(([quizType]) => quizType);
    assert(
      JSON.stringify(typeKeys) === JSON.stringify(index.available_types),
      "index.available_types must match index.quizzes_by_type keys order"
    );
  } else {
    assert(
      JSON.stringify(fileKeys) === JSON.stringify(index.available_types),
      "index.available_types must match index.quiz_files keys order"
    );
  }

  return index as unknown as IndexPayload;
}

export function validateQuizPayload(payload: unknown): QuizPayload {
  validateCommonQuizShape(payload);
  const quiz = payload as QuizPayload;

  if (quiz.type === "which_came_first") {
    validateWhichCameFirst(quiz);
  } else if (quiz.type === "history_mcq_4") {
    validateHistoryMcq4(quiz);
  } else {
    validateHistoryFactoidMcq4(quiz);
  }

  return quiz;
}
