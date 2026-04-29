import { ValidationError } from "./errors";
import type { ClockPort, UserStateRepositoryPort } from "./ports";
import type { QuizType } from "../domain/feedback";
import type { UserQuizStateSnapshot } from "../domain/user_state";

const QUIZ_FILE_REGEX = /^quizzes\/[A-Za-z0-9._-]+\.json$/;
const DATE_REGEX = /^\d{4}-\d{2}-\d{2}$/;
const UUID_REGEX =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const QUESTION_HUMAN_ID_REGEX = /^Q[1-9]\d*$/;
const CHOICE_ID_REGEX = /^[A-Z][A-Z0-9_-]{0,15}$/;
const SUPPORTED_TYPES = new Set<QuizType>([
  "which_came_first",
  "history_mcq_4",
  "history_factoid_mcq_4",
  "geography_factoid_mcq_4",
]);
const ALLOWED_PUT_FIELDS = new Set([
  "date",
  "quiz_file",
  "quiz_type",
  "edition",
  "question_id",
  "question_human_id",
  "selected_choice_id",
  "feedback_draft",
]);

export interface UserStateUseCaseDependencies {
  repository: UserStateRepositoryPort;
  clock: ClockPort;
  featureFlags: {
    commentsEnabled: boolean;
  };
}

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

function validateDate(date: string): void {
  if (!DATE_REGEX.test(date)) {
    throw new ValidationError("date must match YYYY-MM-DD");
  }
}

function validateQuestionId(questionId: string): void {
  if (!UUID_REGEX.test(questionId)) {
    throw new ValidationError("question_id must be a UUID");
  }
}

function parseQuestionIds(raw: string | undefined): string[] {
  if (!raw || !raw.trim()) {
    return [];
  }
  const ids = raw
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean);
  if (ids.length > 20) {
    throw new ValidationError("question_ids must include at most 20 entries");
  }
  ids.forEach(validateQuestionId);
  return Array.from(new Set(ids));
}

export async function getUserQuizStateUseCase(
  input: { authUid: string; date: string; questionIdsRaw?: string },
  deps: UserStateUseCaseDependencies,
): Promise<UserQuizStateSnapshot> {
  validateDate(input.date);
  const questionIds = parseQuestionIds(input.questionIdsRaw);
  const answers = await deps.repository.listQuizAnswers({ authUid: input.authUid, date: input.date });
  const effectiveQuestionIds = questionIds.length ? questionIds : answers.map((answer) => answer.question_id);
  const [feedbackDrafts, feedbackSubmissions] = await Promise.all([
    deps.repository.listFeedbackDrafts({ authUid: input.authUid, questionIds: effectiveQuestionIds }),
    deps.repository.listFeedbackSubmissions({ authUid: input.authUid, questionIds: effectiveQuestionIds }),
  ]);

  return {
    ok: true,
    date: input.date,
    answers,
    feedback_drafts: feedbackDrafts,
    feedback_submissions: feedbackSubmissions,
  };
}

export async function putUserQuizStateUseCase(
  input: { authUid: string; payload: unknown },
  deps: UserStateUseCaseDependencies,
): Promise<{ ok: true }> {
  assertObject(input.payload);
  for (const key of Object.keys(input.payload)) {
    if (!ALLOWED_PUT_FIELDS.has(key)) {
      throw new ValidationError(`unsupported field: ${key}`);
    }
  }

  const date = requireString(input.payload, "date");
  validateDate(date);
  const quizFile = requireString(input.payload, "quiz_file");
  if (!QUIZ_FILE_REGEX.test(quizFile)) {
    throw new ValidationError("quiz_file must match quizzes/*.json");
  }
  const quizType = requireString(input.payload, "quiz_type");
  if (!SUPPORTED_TYPES.has(quizType as QuizType)) {
    throw new ValidationError("quiz_type is not supported");
  }
  const edition = requireInteger(input.payload, "edition");
  if (edition < 1) {
    throw new ValidationError("edition must be >= 1");
  }
  const questionId = requireString(input.payload, "question_id");
  validateQuestionId(questionId);
  const questionHumanId = requireString(input.payload, "question_human_id");
  if (!QUESTION_HUMAN_ID_REGEX.test(questionHumanId)) {
    throw new ValidationError("question_human_id must match Q<integer>");
  }

  const nowIso = deps.clock.nowIsoUtc();
  const selectedChoiceId = input.payload.selected_choice_id;
  if (selectedChoiceId !== undefined) {
    if (typeof selectedChoiceId !== "string" || !CHOICE_ID_REGEX.test(selectedChoiceId.trim())) {
      throw new ValidationError("selected_choice_id is invalid");
    }
    await deps.repository.upsertQuizAnswer({
      schema_version: 1,
      auth_uid: input.authUid,
      date,
      quiz_file: quizFile,
      quiz_type: quizType as QuizType,
      edition,
      question_id: questionId,
      question_human_id: questionHumanId,
      selected_choice_id: selectedChoiceId.trim(),
      answered_at: nowIso,
      updated_at: nowIso,
    });
  }

  if (input.payload.feedback_draft !== undefined) {
    assertObject(input.payload.feedback_draft);
    const draft = input.payload.feedback_draft;
    const ratingRaw = draft.rating;
    const commentRaw = draft.comment;
    let rating: number | undefined;
    let comment: string | undefined;
    if (ratingRaw !== undefined) {
      if (!Number.isInteger(ratingRaw) || (ratingRaw as number) < 1 || (ratingRaw as number) > 5) {
        throw new ValidationError("feedback_draft.rating must be an integer from 1 to 5");
      }
      rating = ratingRaw as number;
    }
    if (commentRaw !== undefined && deps.featureFlags.commentsEnabled) {
      if (typeof commentRaw !== "string") {
        throw new ValidationError("feedback_draft.comment must be a string");
      }
      const trimmed = commentRaw.trim();
      if (trimmed.length > 500) {
        throw new ValidationError("feedback_draft.comment must be at most 500 characters");
      }
      if (trimmed) {
        comment = trimmed;
      }
    }
    await deps.repository.upsertFeedbackDraft({
      schema_version: 1,
      auth_uid: input.authUid,
      question_id: questionId,
      ...(rating !== undefined ? { rating } : {}),
      ...(comment ? { comment } : {}),
      updated_at: nowIso,
    });
  }

  if (selectedChoiceId === undefined && input.payload.feedback_draft === undefined) {
    throw new ValidationError("selected_choice_id or feedback_draft is required");
  }

  return { ok: true };
}
