import { ValidationError } from "../../application/errors";
import type { FeedbackRuntimeConfig } from "../../application/runtime_config";
import {
  submitFeedbackUseCase,
  type SubmitFeedbackUseCaseDependencies,
} from "../../application/submit_feedback_use_case";
import type {
  AuditLoggerPort,
  AuthIdentityVerifierPort,
  RateLimitDecision,
  RateLimiterPort,
  RequestAttestationVerifierPort,
} from "../../application/ports";

const QUIZ_FEEDBACK_PATHS = new Set(["/api/quiz-feedback", "/quiz-feedback"]);
const ALLOWED_METHODS = "POST, OPTIONS";
const ALLOWED_HEADERS = "Content-Type, Authorization, X-Firebase-ID-Token, X-Firebase-AppCheck";

interface RequestLike {
  method: string;
  path: string;
  body: unknown;
  headers: Record<string, string | string[] | undefined>;
  get(name: string): string | undefined;
}

interface ResponseLike {
  status(code: number): ResponseLike;
  json(payload: unknown): void;
  setHeader(name: string, value: string): void;
}

export interface QuizFeedbackHttpHandlerDependencies {
  useCase: SubmitFeedbackUseCaseDependencies;
  rateLimiter: RateLimiterPort;
  authVerifier: AuthIdentityVerifierPort;
  appCheckVerifier: RequestAttestationVerifierPort;
  auditLogger: AuditLoggerPort;
  runtimeConfig: FeedbackRuntimeConfig;
}

function isJsonContentType(contentType: string | undefined): boolean {
  return typeof contentType === "string" && contentType.toLowerCase().includes("application/json");
}

function normalizePath(path: string): string {
  if (path.endsWith("/")) {
    return path.slice(0, -1);
  }
  return path;
}

function normalizeHeader(value: string | string[] | undefined): string | undefined {
  if (Array.isArray(value)) {
    return value[0];
  }
  return value;
}

function parseBearerToken(authorizationHeader: string | undefined): string | undefined {
  if (!authorizationHeader || !authorizationHeader.trim()) {
    return undefined;
  }

  const [scheme, token] = authorizationHeader.trim().split(/\s+/, 2);
  if (!scheme || !token || scheme.toLowerCase() !== "bearer") {
    return undefined;
  }
  return token;
}

function parseIdToken(idTokenHeader: string | undefined, authorizationHeader: string | undefined): string | undefined {
  if (idTokenHeader && idTokenHeader.trim()) {
    return idTokenHeader.trim();
  }
  return parseBearerToken(authorizationHeader);
}

function readLegacyClientIdFromCookie(request: RequestLike): string | undefined {
  const cookie = normalizeHeader(request.headers.cookie);
  if (!cookie || !cookie.trim()) {
    return undefined;
  }
  const parts = cookie.split(";").map((entry) => entry.trim());
  const clientCookie = parts.find((entry) => entry.startsWith("mindblast_client_id="));
  if (!clientCookie) {
    return undefined;
  }
  const value = clientCookie.slice("mindblast_client_id=".length).trim();
  return value || undefined;
}

function parseIpAddress(request: RequestLike): string {
  const forwardedFor = normalizeHeader(request.headers["x-forwarded-for"]);
  if (typeof forwardedFor === "string" && forwardedFor.trim()) {
    return forwardedFor.split(",")[0]?.trim() || "unknown";
  }

  const realIp = normalizeHeader(request.headers["x-real-ip"]);
  if (typeof realIp === "string" && realIp.trim()) {
    return realIp.trim();
  }

  const cfIp = normalizeHeader(request.headers["cf-connecting-ip"]);
  if (typeof cfIp === "string" && cfIp.trim()) {
    return cfIp.trim();
  }

  return "unknown";
}

function extractBody(request: RequestLike): unknown {
  if (request.body && typeof request.body === "object") {
    return request.body as unknown;
  }
  if (typeof request.body === "string") {
    return JSON.parse(request.body) as unknown;
  }
  return {};
}

function extractContentLength(request: RequestLike): number {
  const raw = normalizeHeader(request.headers["content-length"]);
  if (!raw || !raw.trim()) {
    return 0;
  }
  const parsed = Number.parseInt(raw, 10);
  if (!Number.isInteger(parsed) || parsed < 0) {
    return 0;
  }
  return parsed;
}

function isOriginAllowed(origin: string | undefined, runtimeConfig: FeedbackRuntimeConfig): boolean {
  if (!origin || !origin.trim()) {
    return !runtimeConfig.security.requireOrigin;
  }
  return runtimeConfig.security.allowedOrigins.includes(origin);
}

function applyCorsHeaders(response: ResponseLike, origin: string | undefined): void {
  if (!origin) {
    return;
  }
  response.setHeader("Access-Control-Allow-Origin", origin);
  response.setHeader("Vary", "Origin");
  response.setHeader("Access-Control-Allow-Methods", ALLOWED_METHODS);
  response.setHeader("Access-Control-Allow-Headers", ALLOWED_HEADERS);
  response.setHeader("Access-Control-Max-Age", "3600");
}

function reject(
  response: ResponseLike,
  auditLogger: AuditLoggerPort,
  statusCode: number,
  reason: string,
  payload: Record<string, unknown>,
  context: Record<string, unknown> = {},
): void {
  auditLogger.reject(reason, {
    status_code: statusCode,
    ...context,
  });
  response.status(statusCode).json(payload);
}

async function checkRateLimits(
  request: RequestLike,
  deps: QuizFeedbackHttpHandlerDependencies,
  authUid: string,
): Promise<RateLimitDecision> {
  const ipAddress = parseIpAddress(request);
  return deps.rateLimiter.checkAndConsume([
    {
      key: `user:${authUid}`,
      label: "user_hourly",
      limit: deps.runtimeConfig.rateLimits.clientHourly,
      windowSeconds: 3600,
    },
    {
      key: `user:${authUid}`,
      label: "user_daily",
      limit: deps.runtimeConfig.rateLimits.clientDaily,
      windowSeconds: 86400,
    },
    {
      key: `ip:${ipAddress}`,
      label: "ip_hourly",
      limit: deps.runtimeConfig.rateLimits.ipHourly,
      windowSeconds: 3600,
    },
    {
      key: "global",
      label: "global_hourly",
      limit: deps.runtimeConfig.rateLimits.globalHourly,
      windowSeconds: 3600,
    },
  ]);
}

export function createQuizFeedbackHttpHandler(deps: QuizFeedbackHttpHandlerDependencies) {
  return async (request: RequestLike, response: ResponseLike): Promise<void> => {
    const path = normalizePath(request.path);
    const origin = normalizeHeader(request.headers.origin);

    if (!QUIZ_FEEDBACK_PATHS.has(path)) {
      response.status(404).json({ ok: false, error: "not_found" });
      return;
    }

    if (request.method === "OPTIONS") {
      if (!isOriginAllowed(origin, deps.runtimeConfig)) {
        reject(response, deps.auditLogger, 403, "forbidden_origin", { ok: false, error: "forbidden_origin" }, { origin });
        return;
      }
      applyCorsHeaders(response, origin);
      response.status(204).json({});
      return;
    }

    if (request.method !== "POST") {
      reject(response, deps.auditLogger, 405, "method_not_allowed", { ok: false, error: "method_not_allowed" }, { method: request.method });
      return;
    }

    if (!isOriginAllowed(origin, deps.runtimeConfig)) {
      reject(response, deps.auditLogger, 403, "forbidden_origin", { ok: false, error: "forbidden_origin" }, { origin });
      return;
    }
    applyCorsHeaders(response, origin);

    if (!deps.runtimeConfig.featureFlags.writeEnabled) {
      reject(response, deps.auditLogger, 503, "writes_disabled", { ok: false, error: "writes_disabled" });
      return;
    }

    const idTokenHeader = request.get("x-firebase-id-token") || normalizeHeader(request.headers["x-firebase-id-token"]);
    const authHeader = request.get("authorization") || normalizeHeader(request.headers.authorization);
    const idToken = parseIdToken(idTokenHeader, authHeader);
    const authDecision = await deps.authVerifier.verifyIdToken(idToken);
    if (!authDecision.ok || !authDecision.identity) {
      reject(
        response,
        deps.auditLogger,
        401,
        "unauthenticated",
        { ok: false, error: "unauthenticated" },
        { auth_reason: authDecision.reason || "unknown" },
      );
      return;
    }

    const appCheckToken = request.get("x-firebase-appcheck") || normalizeHeader(request.headers["x-firebase-appcheck"]);
    const appCheckDecision = await deps.appCheckVerifier.verifyToken(appCheckToken);
    if (!appCheckDecision.ok) {
      reject(
        response,
        deps.auditLogger,
        403,
        "app_check_failed",
        { ok: false, error: "app_check_failed" },
        { app_check_reason: appCheckDecision.reason || "unknown" },
      );
      return;
    }

    const contentLength = extractContentLength(request);
    if (contentLength > deps.runtimeConfig.security.maxRequestBytes) {
      reject(
        response,
        deps.auditLogger,
        413,
        "invalid_payload",
        { ok: false, error: "invalid_payload", details: "payload too large" },
        { content_length: contentLength },
      );
      return;
    }

    if (!isJsonContentType(request.get("content-type"))) {
      reject(
        response,
        deps.auditLogger,
        400,
        "invalid_payload",
        { ok: false, error: "invalid_payload", details: "content-type must be application/json" },
      );
      return;
    }

    try {
      const payload = extractBody(request);
      const legacyClientId = readLegacyClientIdFromCookie(request);

      const rateLimitDecision = await checkRateLimits(request, deps, authDecision.identity.uid);
      if (!rateLimitDecision.allowed) {
        if (rateLimitDecision.retryAfterSeconds) {
          response.setHeader("Retry-After", String(rateLimitDecision.retryAfterSeconds));
        }
        reject(
          response,
          deps.auditLogger,
          429,
          "rate_limited",
          { ok: false, error: "rate_limited" },
          {
            limit_reason: rateLimitDecision.reason || "unknown",
            retry_after_seconds: rateLimitDecision.retryAfterSeconds || 0,
          },
        );
        return;
      }

      const result = await submitFeedbackUseCase(
        {
          payload,
          authUid: authDecision.identity.uid,
          authProvider: authDecision.identity.providerId,
          legacyClientId,
        },
        deps.useCase,
      );

      response.status(200).json(result);
    } catch (error) {
      if (error instanceof SyntaxError) {
        reject(
          response,
          deps.auditLogger,
          400,
          "invalid_payload",
          { ok: false, error: "invalid_payload", details: "body must be valid JSON" },
        );
        return;
      }
      if (error instanceof ValidationError) {
        reject(
          response,
          deps.auditLogger,
          400,
          "invalid_payload",
          { ok: false, error: "invalid_payload", details: error.message },
        );
        return;
      }

      console.error("quiz feedback write failed", error);
      response.status(500).json({ ok: false, error: "storage_error" });
    }
  };
}
