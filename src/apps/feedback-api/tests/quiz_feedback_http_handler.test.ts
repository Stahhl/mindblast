import { describe, expect, test } from "vitest";

import type {
  AuditLoggerPort,
  RateLimitCheck,
  RateLimitDecision,
  RateLimiterPort,
  RequestAttestationDecision,
  RequestAttestationVerifierPort,
} from "../src/application/ports";
import type { FeedbackRuntimeConfig } from "../src/application/runtime_config";
import type { FeedbackRepositoryPort } from "../src/application/ports";
import type { FeedbackRecord, SubmitFeedbackMode } from "../src/domain/feedback";
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
  buildFeedbackId(input: { clientId: string; questionId: string; feedbackDateUtc: string }): string {
    return `fdbk_${input.clientId}_${input.questionId}_${input.feedbackDateUtc}`;
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
  const rateLimiter = new StubRateLimiter();
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
    rateLimiter,
    appCheckVerifier,
    auditLogger,
    runtimeConfig,
  });

  return {
    handler,
    repository,
    rateLimiter,
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
    expect(response.headers["access-control-allow-methods"]).toBe("POST, OPTIONS");
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
      feedback_id: "fdbk_703e4c47-9040-4a17-bde9-fa4d40da7d3a_123e4567-e89b-42d3-a456-426614174000_2026-03-04",
    });
    const record = Array.from(deps.repository.records.values())[0];
    expect(record?.rating).toBe(4);
    expect(record?.comment).toBeUndefined();
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
});
