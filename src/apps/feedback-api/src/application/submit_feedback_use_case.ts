import type { FeedbackRecord, SubmitFeedbackResult } from "../domain/feedback";
import type { ClockPort, FeedbackRepositoryPort, IdGeneratorPort } from "./ports";
import { validateSubmitFeedbackPayload } from "./validation";

export interface SubmitFeedbackUseCaseDependencies {
  repository: FeedbackRepositoryPort;
  clock: ClockPort;
  idGenerator: IdGeneratorPort;
}

export interface SubmitFeedbackUseCaseInput {
  payload: unknown;
  clientId: string;
}

export async function submitFeedbackUseCase(
  input: SubmitFeedbackUseCaseInput,
  deps: SubmitFeedbackUseCaseDependencies,
): Promise<SubmitFeedbackResult> {
  const normalized = validateSubmitFeedbackPayload(input.payload);

  const nowIso = deps.clock.nowIsoUtc();
  const feedbackDateUtc = nowIso.slice(0, 10);
  const feedbackId = deps.idGenerator.buildFeedbackId({
    clientId: input.clientId,
    questionId: normalized.question_id,
    feedbackDateUtc,
  });

  const record: FeedbackRecord = {
    schema_version: 1,
    feedback_id: feedbackId,
    quiz_file: normalized.quiz_file,
    date: normalized.date,
    quiz_type: normalized.quiz_type,
    edition: normalized.edition,
    question_id: normalized.question_id,
    question_human_id: normalized.question_human_id,
    rating: normalized.rating,
    feedback_date_utc: feedbackDateUtc,
    client_id: input.clientId,
    created_at: nowIso,
    updated_at: nowIso,
    source: "web",
    ...(normalized.comment ? { comment: normalized.comment } : {}),
  };

  const upsert = await deps.repository.upsertById(feedbackId, record);
  return {
    ok: true,
    mode: upsert.mode,
    feedback_id: feedbackId,
  };
}
