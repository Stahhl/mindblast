import type { FeedbackRecord, SubmitFeedbackMode } from "../domain/feedback";

export interface ClockPort {
  nowIsoUtc(): string;
  todayUtc(): string;
}

export interface IdGeneratorPort {
  buildFeedbackId(input: { clientId: string; questionId: string; feedbackDateUtc: string }): string;
}

export interface FeedbackRepositoryPort {
  upsertById(feedbackId: string, record: FeedbackRecord): Promise<{ mode: SubmitFeedbackMode }>;
}
