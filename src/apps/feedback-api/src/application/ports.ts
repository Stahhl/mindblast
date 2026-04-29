import type { FeedbackRecord, SubmitFeedbackMode } from "../domain/feedback";
import type {
  UserFeedbackDraftRecord,
  UserFeedbackSubmissionState,
  UserQuizAnswerRecord,
} from "../domain/user_state";

export interface ClockPort {
  nowIsoUtc(): string;
  todayUtc(): string;
}

export interface IdGeneratorPort {
  buildFeedbackId(input: { authUid: string; questionId: string; feedbackDateUtc: string }): string;
}

export interface FeedbackRepositoryPort {
  upsertById(feedbackId: string, record: FeedbackRecord): Promise<{ mode: SubmitFeedbackMode }>;
}

export interface UserStateRepositoryPort {
  listQuizAnswers(input: { authUid: string; date: string }): Promise<UserQuizAnswerRecord[]>;
  upsertQuizAnswer(record: UserQuizAnswerRecord): Promise<void>;
  listFeedbackDrafts(input: { authUid: string; questionIds: string[] }): Promise<UserFeedbackDraftRecord[]>;
  upsertFeedbackDraft(record: UserFeedbackDraftRecord): Promise<void>;
  listFeedbackSubmissions(input: { authUid: string; questionIds: string[] }): Promise<UserFeedbackSubmissionState[]>;
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

export interface VerifiedAuthIdentity {
  uid: string;
  providerId: string;
}

export interface AuthIdentityDecision {
  ok: boolean;
  identity?: VerifiedAuthIdentity;
  reason?: string;
}

export interface AuthIdentityVerifierPort {
  verifyIdToken(token: string | undefined): Promise<AuthIdentityDecision>;
}

export interface AuditLoggerPort {
  reject(reason: string, context?: Record<string, unknown>): void;
}
