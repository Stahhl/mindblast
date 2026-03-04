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

export interface RateLimitCheck {
  key: string;
  label: string;
  limit: number;
  windowSeconds: number;
}

export interface RateLimitDecision {
  allowed: boolean;
  reason?: string;
  retryAfterSeconds?: number;
}

export interface RateLimiterPort {
  checkAndConsume(checks: RateLimitCheck[]): Promise<RateLimitDecision>;
}

export interface RequestAttestationDecision {
  ok: boolean;
  reason?: string;
}

export interface RequestAttestationVerifierPort {
  verifyToken(token: string | undefined): Promise<RequestAttestationDecision>;
}

export interface AuditLoggerPort {
  reject(reason: string, context?: Record<string, unknown>): void;
}
