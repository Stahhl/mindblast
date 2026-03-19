import { ValidationError } from "./errors";
import type { QuizType, SubmitFeedbackPayload } from "../domain/feedback";

const QUIZ_FILE_REGEX = /^quizzes\/[A-Za-z0-9._-]+\.json$/;
const DATE_REGEX = /^\d{4}-\d{2}-\d{2}$/;
const UUID_REGEX =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const QUESTION_HUMAN_ID_REGEX = /^Q[1-9]\d*$/;
const SUPPORTED_TYPES = new Set<QuizType>([
  "which_came_first",
  "history_mcq_4",
  "history_factoid_mcq_4",
  "geography_factoid_mcq_4",
]);
const ALLOWED_FIELDS = new Set([
  "quiz_file",
  "date",
  "quiz_type",
  "edition",
  "question_id",
  "question_human_id",
  "rating",
  "comment",
]);

function assertObject(payload: unknown): asserts payload is Record<string, unknown> {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new ValidationError("payload must be a JSON object");
  }
}

function requireString(payload: Record<string, unknown>, field: string): string {
  const value = payload[field];
  if (typeof value !== "string") {
    throw new ValidationError(`${field} must be a string`);
  }
  const trimmed = value.trim();
  if (!trimmed) {
    throw new ValidationError(`${field} must be non-empty`);
  }
  return trimmed;
}

function requireInteger(payload: Record<string, unknown>, field: string): number {
  const value = payload[field];
  if (!Number.isInteger(value)) {
    throw new ValidationError(`${field} must be an integer`);
  }
  return value as number;
}

export function validateSubmitFeedbackPayload(payload: unknown): SubmitFeedbackPayload {
  return validateSubmitFeedbackPayloadWithOptions(payload, { commentsEnabled: true });
}

export interface SubmitFeedbackValidationOptions {
  commentsEnabled: boolean;
}

export function validateSubmitFeedbackPayloadWithOptions(
  payload: unknown,
  options: SubmitFeedbackValidationOptions,
): SubmitFeedbackPayload {
  assertObject(payload);

  for (const key of Object.keys(payload)) {
    if (!ALLOWED_FIELDS.has(key)) {
      throw new ValidationError(`unsupported field: ${key}`);
    }
  }

  const quizFile = requireString(payload, "quiz_file");
  if (!QUIZ_FILE_REGEX.test(quizFile)) {
    throw new ValidationError("quiz_file must match quizzes/*.json");
  }

  const date = requireString(payload, "date");
  if (!DATE_REGEX.test(date)) {
    throw new ValidationError("date must match YYYY-MM-DD");
  }

  const quizType = requireString(payload, "quiz_type");
  if (!SUPPORTED_TYPES.has(quizType as QuizType)) {
    throw new ValidationError("quiz_type is not supported");
  }

  const edition = requireInteger(payload, "edition");
  if (edition < 1) {
    throw new ValidationError("edition must be >= 1");
  }

  const questionId = requireString(payload, "question_id");
  if (!UUID_REGEX.test(questionId)) {
    throw new ValidationError("question_id must be a UUID");
  }

  const questionHumanId = requireString(payload, "question_human_id");
  if (!QUESTION_HUMAN_ID_REGEX.test(questionHumanId)) {
    throw new ValidationError("question_human_id must match Q<integer>");
  }

  const rating = requireInteger(payload, "rating");
  if (rating < 1 || rating > 5) {
    throw new ValidationError("rating must be an integer from 1 to 5");
  }

  const commentRaw = payload.comment;
  let comment: string | undefined;
  if (commentRaw !== undefined) {
    if (!options.commentsEnabled) {
      comment = undefined;
    } else {
      if (typeof commentRaw !== "string") {
        throw new ValidationError("comment must be a string");
      }
      const trimmed = commentRaw.trim();
      if (trimmed.length > 500) {
        throw new ValidationError("comment must be at most 500 characters");
      }
      if (trimmed.length > 0) {
        comment = trimmed;
      }
    }
  }

  return {
    quiz_file: quizFile,
    date,
    quiz_type: quizType as QuizType,
    edition,
    question_id: questionId,
    question_human_id: questionHumanId,
    rating,
    comment,
  };
}
