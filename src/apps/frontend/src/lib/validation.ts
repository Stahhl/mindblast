import type { IndexPayload, LatestPayload, QuizPayload, QuizSource, QuizType } from "./types";

const KNOWN_TYPES = new Set<QuizType>(["which_came_first", "history_mcq_4"]);

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
  });

  const uniqueIds = new Set(quizValue.choices.map((choice) => (choice as { id: string }).id));
  assert(uniqueIds.size === quizValue.choices.length, "quiz.choices IDs must be unique");
  assert(uniqueIds.has(quizValue.correct_choice_id as string), "quiz.correct_choice_id must match a choice id");

  assert(quizValue.metadata && typeof quizValue.metadata === "object", "quiz.metadata must be an object");
  const metadata = quizValue.metadata as Record<string, unknown>;
  assert(metadata.version === 1, "quiz.metadata.version must be 1");
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
  assert(metadata.version === 1, "latest.metadata.version must be 1");

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
  assert(
    JSON.stringify(fileKeys) === JSON.stringify(index.available_types),
    "index.available_types must match index.quiz_files keys order"
  );

  assert(index.metadata && typeof index.metadata === "object", "index.metadata must be an object");
  const metadata = index.metadata as Record<string, unknown>;
  assert(metadata.version === 1, "index.metadata.version must be 1");

  return index as unknown as IndexPayload;
}

export function validateQuizPayload(payload: unknown): QuizPayload {
  validateCommonQuizShape(payload);
  const quiz = payload as QuizPayload;

  if (quiz.type === "which_came_first") {
    validateWhichCameFirst(quiz);
  } else {
    validateHistoryMcq4(quiz);
  }

  return quiz;
}
