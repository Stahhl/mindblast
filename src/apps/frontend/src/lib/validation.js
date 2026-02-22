const KNOWN_TYPES = new Set(["which_came_first", "history_mcq_4"]);

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function isNonEmptyString(value) {
  return typeof value === "string" && value.trim().length > 0;
}

function validateSource(source, expectedLength) {
  assert(source && typeof source === "object", "quiz.source must be an object");
  assert(isNonEmptyString(source.name), "quiz.source.name must be a non-empty string");
  assert(isNonEmptyString(source.url), "quiz.source.url must be a non-empty string");
  assert(isNonEmptyString(source.retrieved_at), "quiz.source.retrieved_at must be a non-empty string");

  assert(Array.isArray(source.events_used), "quiz.source.events_used must be an array");
  assert(source.events_used.length === expectedLength, `quiz.source.events_used must contain exactly ${expectedLength} entries`);

  source.events_used.forEach((event, idx) => {
    assert(event && typeof event === "object", `quiz.source.events_used[${idx}] must be an object`);
    assert(isNonEmptyString(event.text), `quiz.source.events_used[${idx}].text must be a non-empty string`);
    assert(Number.isInteger(event.year), `quiz.source.events_used[${idx}].year must be an integer`);
    assert(isNonEmptyString(event.wikipedia_url), `quiz.source.events_used[${idx}].wikipedia_url must be a non-empty string`);
  });
}

function validateCommonQuizShape(quiz) {
  assert(quiz && typeof quiz === "object", "quiz must be an object");
  assert(isNonEmptyString(quiz.date), "quiz.date must be a non-empty string");
  assert(Array.isArray(quiz.topics), "quiz.topics must be an array");
  assert(quiz.topics.length > 0, "quiz.topics must contain at least one topic");
  assert(quiz.topics.every(isNonEmptyString), "quiz.topics entries must be non-empty strings");

  assert(isNonEmptyString(quiz.type), "quiz.type must be a non-empty string");
  assert(KNOWN_TYPES.has(quiz.type), `quiz.type '${quiz.type}' is unsupported`);

  assert(isNonEmptyString(quiz.question), "quiz.question must be a non-empty string");
  assert(Array.isArray(quiz.choices), "quiz.choices must be an array");
  assert(quiz.choices.length > 0, "quiz.choices must not be empty");

  quiz.choices.forEach((choice, idx) => {
    assert(choice && typeof choice === "object", `quiz.choices[${idx}] must be an object`);
    assert(isNonEmptyString(choice.id), `quiz.choices[${idx}].id must be a non-empty string`);
    assert(isNonEmptyString(choice.label), `quiz.choices[${idx}].label must be a non-empty string`);
  });

  const uniqueIds = new Set(quiz.choices.map((choice) => choice.id));
  assert(uniqueIds.size === quiz.choices.length, "quiz.choices IDs must be unique");
  assert(uniqueIds.has(quiz.correct_choice_id), "quiz.correct_choice_id must match a choice id");

  assert(quiz.metadata && typeof quiz.metadata === "object", "quiz.metadata must be an object");
  assert(quiz.metadata.version === 1, "quiz.metadata.version must be 1");
}

function validateWhichCameFirst(quiz) {
  assert(quiz.choices.length === 2, "which_came_first must have exactly 2 choices");

  const years = quiz.choices.map((choice, idx) => {
    assert(Number.isInteger(choice.year), `which_came_first choice ${idx + 1} must include integer year`);
    return choice.year;
  });

  assert(years[0] !== years[1], "which_came_first choice years must be distinct");
  validateSource(quiz.source, 2);
}

function validateHistoryMcq4(quiz) {
  assert(quiz.choices.length === 4, "history_mcq_4 must have exactly 4 choices");

  quiz.choices.forEach((choice, idx) => {
    assert(choice.year === undefined, `history_mcq_4 choice ${idx + 1} must not include year`);
  });

  validateSource(quiz.source, 4);
}

export function validateLatestPayload(payload) {
  assert(payload && typeof payload === "object", "latest payload must be an object");
  assert(isNonEmptyString(payload.date), "latest.date must be a non-empty string");
  assert(isNonEmptyString(payload.index_file), "latest.index_file must be a non-empty string");

  assert(Array.isArray(payload.available_types), "latest.available_types must be an array");
  assert(payload.available_types.length > 0, "latest.available_types must not be empty");
  payload.available_types.forEach((quizType, idx) => {
    assert(isNonEmptyString(quizType), `latest.available_types[${idx}] must be a non-empty string`);
  });

  assert(payload.metadata && typeof payload.metadata === "object", "latest.metadata must be an object");
  assert(payload.metadata.version === 1, "latest.metadata.version must be 1");
  return payload;
}

export function validateIndexPayload(payload) {
  assert(payload && typeof payload === "object", "index payload must be an object");
  assert(isNonEmptyString(payload.date), "index.date must be a non-empty string");

  assert(payload.quiz_files && typeof payload.quiz_files === "object", "index.quiz_files must be an object");
  const entries = Object.entries(payload.quiz_files);
  assert(entries.length > 0, "index.quiz_files must not be empty");

  entries.forEach(([quizType, quizPath]) => {
    assert(isNonEmptyString(quizType), "index.quiz_files key must be non-empty");
    assert(isNonEmptyString(quizPath), `index.quiz_files['${quizType}'] must be a non-empty string`);
  });

  assert(Array.isArray(payload.available_types), "index.available_types must be an array");
  assert(payload.available_types.length > 0, "index.available_types must not be empty");

  const fileKeys = entries.map(([quizType]) => quizType);
  assert(
    JSON.stringify(fileKeys) === JSON.stringify(payload.available_types),
    "index.available_types must match index.quiz_files keys order"
  );

  assert(payload.metadata && typeof payload.metadata === "object", "index.metadata must be an object");
  assert(payload.metadata.version === 1, "index.metadata.version must be 1");
  return payload;
}

export function validateQuizPayload(payload) {
  validateCommonQuizShape(payload);

  if (payload.type === "which_came_first") {
    validateWhichCameFirst(payload);
  } else if (payload.type === "history_mcq_4") {
    validateHistoryMcq4(payload);
  }

  return payload;
}
