import { describe, expect, test } from "vitest";

import type {
  AuditLoggerPort,
  AuthIdentityDecision,
  AuthIdentityVerifierPort,
  RateLimitCheck,
  RateLimitDecision,
  RateLimiterPort,
  RequestAttestationDecision,
  RequestAttestationVerifierPort,
} from "../src/application/ports";
import type { FeedbackRuntimeConfig } from "../src/application/runtime_config";
import type { FeedbackRepositoryPort } from "../src/application/ports";
import type { FeedbackRecord, SubmitFeedbackMode } from "../src/domain/feedback";
import type {
  UserFeedbackDraftRecord,
  UserFeedbackSubmissionState,
  UserQuizAnswerRecord,
} from "../src/domain/user_state";
import { createQuizFeedbackHttpHandler } from "../src/infrastructure/http/quiz_feedback_http_handler";

class FixedClock {
  nowIsoUtc(): string {
    return "2026-03-04T10:00:00.000Z";
  }

  todayUtc(): string {
    return "2026-03-04";
  }
}

class DeterministicIdGenerator {
  buildFeedbackId(input: { authUid: string; questionId: string; feedbackDateUtc: string }): string {
    return `fdbk_${input.authUid}_${input.questionId}_${input.feedbackDateUtc}`;
  }
}

class InMemoryFeedbackRepository implements FeedbackRepositoryPort {
  records = new Map<string, FeedbackRecord>();

  async upsertById(feedbackId: string, record: FeedbackRecord): Promise<{ mode: SubmitFeedbackMode }> {
    const existing = this.records.get(feedbackId);
    if (!existing) {
      this.records.set(feedbackId, record);
      return { mode: "created" };
    }
    this.records.set(feedbackId, {
      ...record,
      created_at: existing.created_at,
    });
    return { mode: "updated" };
  }
}

class InMemoryUserStateRepository {
  answers = new Map<string, UserQuizAnswerRecord>();
  drafts = new Map<string, UserFeedbackDraftRecord>();
  submissions: UserFeedbackSubmissionState[] = [];

  async listQuizAnswers(input: { authUid: string; date: string }): Promise<UserQuizAnswerRecord[]> {
    return Array.from(this.answers.values()).filter(
      (record) => record.auth_uid === input.authUid && record.date === input.date,
    );
  }

  async upsertQuizAnswer(record: UserQuizAnswerRecord): Promise<void> {
    this.answers.set(`${record.auth_uid}:${record.date}:${record.question_id}`, record);
  }

  async listFeedbackDrafts(input: { authUid: string; questionIds: string[] }): Promise<UserFeedbackDraftRecord[]> {
    const allowed = new Set(input.questionIds);
    return Array.from(this.drafts.values()).filter(
      (record) => record.auth_uid === input.authUid && allowed.has(record.question_id),
    );
  }

  async upsertFeedbackDraft(record: UserFeedbackDraftRecord): Promise<void> {
    this.drafts.set(`${record.auth_uid}:${record.question_id}`, record);
  }

  async listFeedbackSubmissions(input: { authUid: string; questionIds: string[] }): Promise<UserFeedbackSubmissionState[]> {
    const allowed = new Set(input.questionIds);
    return this.submissions.filter((record) => allowed.has(record.question_id) && input.authUid === "uid-1");
  }
}

class StubRateLimiter implements RateLimiterPort {
  calls = 0;
  decision: RateLimitDecision = { allowed: true };

  async checkAndConsume(_checks: RateLimitCheck[]): Promise<RateLimitDecision> {
    this.calls += 1;
    return this.decision;
  }
}

class StubAppCheckVerifier implements RequestAttestationVerifierPort {
  decision: RequestAttestationDecision = { ok: true };
  calls = 0;

  async verifyToken(_token: string | undefined): Promise<RequestAttestationDecision> {
    this.calls += 1;
    return this.decision;
  }
}

class StubAuthVerifier implements AuthIdentityVerifierPort {
  decision: AuthIdentityDecision = {
    ok: true,
    identity: {
      uid: "uid-1",
      providerId: "google.com",
    },
  };
  calls = 0;
  lastToken: string | undefined = undefined;

  async verifyIdToken(token: string | undefined): Promise<AuthIdentityDecision> {
    this.calls += 1;
    this.lastToken = token;
    return this.decision;
  }
}

class CapturingAuditLogger implements AuditLoggerPort {
  events: Array<{ reason: string; context: Record<string, unknown> }> = [];

  reject(reason: string, context: Record<string, unknown> = {}): void {
    this.events.push({ reason, context });
  }
}

interface FakeRequest {
  method: string;
  path: string;
  body: unknown;
  headers: Record<string, string | string[] | undefined>;
  get(name: string): string | undefined;
}

class FakeResponse {
  statusCode = 200;
  body: unknown = null;
  headers: Record<string, string> = {};

  status(code: number): FakeResponse {
    this.statusCode = code;
    return this;
  }

  json(payload: unknown): void {
    this.body = payload;
  }

  setHeader(name: string, value: string): void {
    this.headers[name.toLowerCase()] = value;
  }
}

function buildRuntimeConfig(overrides: Partial<FeedbackRuntimeConfig> = {}): FeedbackRuntimeConfig {
  const base: FeedbackRuntimeConfig = {
    featureFlags: {
      writeEnabled: true,
      commentsEnabled: true,
    },
    rateLimits: {
      clientHourly: 5,
      clientDaily: 20,
      ipHourly: 60,
      globalHourly: 5000,
    },
    security: {
      requireAuth: true,
      requireAppCheck: false,
      requireOrigin: false,
      allowedOrigins: ["https://mindblast.app", "https://staging.mindblast.app"],
      maxRequestBytes: 8192,
    },
  };

  return {
    ...base,
    ...overrides,
    featureFlags: {
      ...base.featureFlags,
      ...(overrides.featureFlags || {}),
    },
    rateLimits: {
      ...base.rateLimits,
      ...(overrides.rateLimits || {}),
    },
    security: {
      ...base.security,
      ...(overrides.security || {}),
    },
  };
}

function buildValidPayload(overrides: Partial<Record<string, unknown>> = {}): Record<string, unknown> {
  return {
    quiz_file: "quizzes/abc123.json",
    date: "2026-03-04",
    quiz_type: "history_mcq_4",
    edition: 1,
    question_id: "123e4567-e89b-42d3-a456-426614174000",
    question_human_id: "Q42",
    rating: 4,
    comment: "Looks good",
    ...overrides,
  };
}

function buildRequest(overrides: Partial<FakeRequest> = {}): FakeRequest {
  const headers = {
    "content-type": "application/json",
    authorization: "Bearer token-123",
    cookie: "mindblast_client_id=703e4c47-9040-4a17-bde9-fa4d40da7d3a",
    ...overrides.headers,
  };

  return {
    method: "POST",
    path: "/api/quiz-feedback",
    body: buildValidPayload(),
    headers,
    get(name: string): string | undefined {
      const value = this.headers[name.toLowerCase()];
      return Array.isArray(value) ? value[0] : value;
    },
    ...overrides,
  };
}

function createHandlerDeps(runtimeConfig: FeedbackRuntimeConfig) {
  const repository = new InMemoryFeedbackRepository();
  const userStateRepository = new InMemoryUserStateRepository();
  const rateLimiter = new StubRateLimiter();
  const authVerifier = new StubAuthVerifier();
  const appCheckVerifier = new StubAppCheckVerifier();
  const auditLogger = new CapturingAuditLogger();

  const handler = createQuizFeedbackHttpHandler({
    useCase: {
      repository,
      clock: new FixedClock(),
      idGenerator: new DeterministicIdGenerator(),
      featureFlags: {
        commentsEnabled: runtimeConfig.featureFlags.commentsEnabled,
      },
    },
    userStateUseCase: {
      repository: userStateRepository,
      clock: new FixedClock(),
      featureFlags: {
        commentsEnabled: runtimeConfig.featureFlags.commentsEnabled,
      },
    },
    rateLimiter,
    authVerifier,
    appCheckVerifier,
    auditLogger,
    runtimeConfig,
  });

  return {
    handler,
    repository,
    userStateRepository,
    rateLimiter,
    authVerifier,
    appCheckVerifier,
    auditLogger,
  };
}

describe("quiz feedback HTTP handler hardening", () => {
  test("rejects with rate_limited when limiter blocks request", async () => {
    const runtimeConfig = buildRuntimeConfig();
    const deps = createHandlerDeps(runtimeConfig);
    deps.rateLimiter.decision = {
      allowed: false,
      reason: "client_hourly",
      retryAfterSeconds: 42,
    };

    const request = buildRequest();
    const response = new FakeResponse();

    await deps.handler(request, response);

    expect(response.statusCode).toBe(429);
    expect(response.headers["retry-after"]).toBe("42");
    expect(response.body).toEqual({ ok: false, error: "rate_limited" });
    expect(deps.auditLogger.events[0]?.reason).toBe("rate_limited");
  });

  test("rejects with app_check_failed when verifier denies", async () => {
    const runtimeConfig = buildRuntimeConfig();
    const deps = createHandlerDeps(runtimeConfig);
    deps.appCheckVerifier.decision = { ok: false, reason: "invalid_app_check_token" };

    const request = buildRequest();
    const response = new FakeResponse();

    await deps.handler(request, response);

    expect(response.statusCode).toBe(403);
    expect(response.body).toEqual({ ok: false, error: "app_check_failed" });
    expect(deps.auditLogger.events[0]?.reason).toBe("app_check_failed");
  });

  test("rejects with unauthenticated when auth verifier denies", async () => {
    const runtimeConfig = buildRuntimeConfig();
    const deps = createHandlerDeps(runtimeConfig);
    deps.authVerifier.decision = { ok: false, reason: "missing_id_token" };

    const request = buildRequest({
      headers: {
        "content-type": "application/json",
      },
    });
    const response = new FakeResponse();

    await deps.handler(request, response);

    expect(response.statusCode).toBe(401);
    expect(response.body).toEqual({ ok: false, error: "unauthenticated" });
    expect(deps.auditLogger.events[0]?.reason).toBe("unauthenticated");
  });

  test("rejects request from forbidden origin", async () => {
    const runtimeConfig = buildRuntimeConfig({
      security: {
        requireOrigin: true,
        allowedOrigins: ["https://mindblast.app"],
      },
    });
    const deps = createHandlerDeps(runtimeConfig);

    const request = buildRequest({
      headers: {
        "content-type": "application/json",
        origin: "https://evil.example",
      },
    });
    const response = new FakeResponse();

    await deps.handler(request, response);

    expect(response.statusCode).toBe(403);
    expect(response.body).toEqual({ ok: false, error: "forbidden_origin" });
    expect(deps.auditLogger.events[0]?.reason).toBe("forbidden_origin");
  });

  test("rejects when writes are disabled", async () => {
    const runtimeConfig = buildRuntimeConfig({
      featureFlags: {
        writeEnabled: false,
      },
    });
    const deps = createHandlerDeps(runtimeConfig);

    const request = buildRequest();
    const response = new FakeResponse();

    await deps.handler(request, response);

    expect(response.statusCode).toBe(503);
    expect(response.body).toEqual({ ok: false, error: "writes_disabled" });
    expect(deps.auditLogger.events[0]?.reason).toBe("writes_disabled");
  });

  test("accepts preflight request for allowed origin", async () => {
    const runtimeConfig = buildRuntimeConfig({
      security: {
        requireOrigin: true,
      },
    });
    const deps = createHandlerDeps(runtimeConfig);

    const request = buildRequest({
      method: "OPTIONS",
      body: {},
      headers: {
        origin: "https://mindblast.app",
      },
    });
    const response = new FakeResponse();

    await deps.handler(request, response);

    expect(response.statusCode).toBe(204);
    expect(response.headers["access-control-allow-origin"]).toBe("https://mindblast.app");
    expect(response.headers["access-control-allow-methods"]).toBe("GET, PUT, POST, OPTIONS");
  });

  test("stores rating while dropping comment when comments are disabled", async () => {
    const runtimeConfig = buildRuntimeConfig({
      featureFlags: {
        commentsEnabled: false,
      },
    });
    const deps = createHandlerDeps(runtimeConfig);

    const request = buildRequest();
    const response = new FakeResponse();

    await deps.handler(request, response);

    expect(response.statusCode).toBe(200);
    expect(response.body).toEqual({
      ok: true,
      mode: "created",
      feedback_id: "fdbk_uid-1_123e4567-e89b-42d3-a456-426614174000_2026-03-04",
    });
    const record = Array.from(deps.repository.records.values())[0];
    expect(record?.rating).toBe(4);
    expect(record?.comment).toBeUndefined();
    expect(record?.auth_uid).toBe("uid-1");
  });

  test("prefers x-firebase-id-token over authorization bearer", async () => {
    const runtimeConfig = buildRuntimeConfig();
    const deps = createHandlerDeps(runtimeConfig);

    const request = buildRequest({
      headers: {
        "content-type": "application/json",
        authorization: "Bearer fallback-token",
        "x-firebase-id-token": "header-token",
      },
    });
    const response = new FakeResponse();

    await deps.handler(request, response);

    expect(response.statusCode).toBe(200);
    expect(deps.authVerifier.lastToken).toBe("header-token");
  });

  test("uses authorization bearer token when x-firebase-id-token is absent", async () => {
    const runtimeConfig = buildRuntimeConfig();
    const deps = createHandlerDeps(runtimeConfig);

    const request = buildRequest({
      headers: {
        "content-type": "application/json",
        authorization: "Bearer fallback-token",
      },
    });
    const response = new FakeResponse();

    await deps.handler(request, response);

    expect(response.statusCode).toBe(200);
    expect(deps.authVerifier.lastToken).toBe("fallback-token");
  });

  test("logs invalid_payload for malformed body", async () => {
    const runtimeConfig = buildRuntimeConfig();
    const deps = createHandlerDeps(runtimeConfig);

    const request = buildRequest({
      body: "{",
    });
    const response = new FakeResponse();

    await deps.handler(request, response);

    expect(response.statusCode).toBe(400);
    expect(response.body).toEqual({ ok: false, error: "invalid_payload", details: "body must be valid JSON" });
    expect(deps.auditLogger.events[0]?.reason).toBe("invalid_payload");
  });

  test("stores and reads signed-in user quiz state", async () => {
    const runtimeConfig = buildRuntimeConfig();
    const deps = createHandlerDeps(runtimeConfig);
    const putRequest = buildRequest({
      method: "PUT",
      path: "/api/user-quiz-state",
      body: {
        quiz_file: "quizzes/abc123.json",
        date: "2026-03-04",
        quiz_type: "history_mcq_4",
        edition: 1,
        question_id: "123e4567-e89b-42d3-a456-426614174000",
        question_human_id: "Q42",
        selected_choice_id: "A",
        feedback_draft: {
          rating: 5,
          comment: "Draft note",
        },
      },
    });
    const putResponse = new FakeResponse();

    await deps.handler(putRequest, putResponse);

    expect(putResponse.statusCode).toBe(200);
    expect(putResponse.body).toEqual({ ok: true });

    const getRequest = buildRequest({
      method: "GET",
      path: "/api/user-quiz-state",
      url: "/api/user-quiz-state?date=2026-03-04&question_ids=123e4567-e89b-42d3-a456-426614174000",
      body: {},
    });
    const getResponse = new FakeResponse();

    await deps.handler(getRequest, getResponse);

    expect(getResponse.statusCode).toBe(200);
    expect(getResponse.body).toMatchObject({
      ok: true,
      date: "2026-03-04",
      answers: [
        {
          auth_uid: "uid-1",
          question_id: "123e4567-e89b-42d3-a456-426614174000",
          selected_choice_id: "A",
        },
      ],
      feedback_drafts: [
        {
          auth_uid: "uid-1",
          question_id: "123e4567-e89b-42d3-a456-426614174000",
          rating: 5,
          comment: "Draft note",
        },
      ],
    });
  });

  test("rejects oversized user feedback draft comment", async () => {
    const runtimeConfig = buildRuntimeConfig();
    const deps = createHandlerDeps(runtimeConfig);
    const request = buildRequest({
      method: "PUT",
      path: "/api/user-quiz-state",
      body: {
        quiz_file: "quizzes/abc123.json",
        date: "2026-03-04",
        quiz_type: "history_mcq_4",
        edition: 1,
        question_id: "123e4567-e89b-42d3-a456-426614174000",
        question_human_id: "Q42",
        feedback_draft: {
          comment: "x".repeat(501),
        },
      },
    });
    const response = new FakeResponse();

    await deps.handler(request, response);

    expect(response.statusCode).toBe(400);
    expect(response.body).toEqual({
      ok: false,
      error: "invalid_payload",
      details: "feedback_draft.comment must be at most 500 characters",
    });
  });
});
