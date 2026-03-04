export interface FeedbackFeatureFlags {
  writeEnabled: boolean;
  commentsEnabled: boolean;
}

export interface FeedbackRateLimitConfig {
  clientHourly: number;
  clientDaily: number;
  ipHourly: number;
  globalHourly: number;
}

export interface FeedbackSecurityConfig {
  requireAppCheck: boolean;
  requireOrigin: boolean;
  allowedOrigins: string[];
  maxRequestBytes: number;
}

export interface FeedbackRuntimeConfig {
  featureFlags: FeedbackFeatureFlags;
  rateLimits: FeedbackRateLimitConfig;
  security: FeedbackSecurityConfig;
}

function envBool(name: string, fallback: boolean): boolean {
  const raw = process.env[name];
  if (raw === undefined) {
    return fallback;
  }
  const normalized = raw.trim().toLowerCase();
  if (["1", "true", "yes", "on"].includes(normalized)) {
    return true;
  }
  if (["0", "false", "no", "off"].includes(normalized)) {
    return false;
  }
  throw new Error(`${name} must be a boolean-like value`);
}

function envInt(name: string, fallback: number): number {
  const raw = process.env[name];
  if (raw === undefined || !raw.trim()) {
    return fallback;
  }
  const parsed = Number.parseInt(raw, 10);
  if (!Number.isInteger(parsed) || parsed < 0) {
    throw new Error(`${name} must be a non-negative integer`);
  }
  return parsed;
}

function parseAllowedOrigins(nodeEnv: string): string[] {
  const raw = process.env.FEEDBACK_ALLOWED_ORIGINS;
  if (raw && raw.trim()) {
    return raw
      .split(",")
      .map((entry) => entry.trim())
      .filter(Boolean);
  }

  const base = ["https://mindblast.app", "https://staging.mindblast.app", "https://www.mindblast.app"];
  if (nodeEnv !== "production") {
    base.push("http://localhost:5173", "http://127.0.0.1:5173");
  }
  return base;
}

function parseAppCheckRequired(nodeEnv: string): boolean {
  const mode = (process.env.FEEDBACK_APP_CHECK_ENFORCEMENT || "auto").trim().toLowerCase();
  if (mode === "required") {
    return true;
  }
  if (mode === "off") {
    return false;
  }
  if (mode === "auto") {
    return nodeEnv === "production";
  }
  throw new Error("FEEDBACK_APP_CHECK_ENFORCEMENT must be one of: auto|required|off");
}

export function loadFeedbackRuntimeConfig(): FeedbackRuntimeConfig {
  const nodeEnv = (process.env.NODE_ENV || "development").trim().toLowerCase();
  const isProduction = nodeEnv === "production";

  return {
    featureFlags: {
      writeEnabled: envBool("FEEDBACK_WRITE_ENABLED", true),
      commentsEnabled: envBool("FEEDBACK_COMMENTS_ENABLED", true),
    },
    rateLimits: {
      clientHourly: envInt("FEEDBACK_RATE_LIMIT_CLIENT_HOURLY", 5),
      clientDaily: envInt("FEEDBACK_RATE_LIMIT_CLIENT_DAILY", 20),
      ipHourly: envInt("FEEDBACK_RATE_LIMIT_IP_HOURLY", 60),
      globalHourly: envInt("FEEDBACK_RATE_LIMIT_GLOBAL_HOURLY", 5000),
    },
    security: {
      requireAppCheck: parseAppCheckRequired(nodeEnv),
      requireOrigin: envBool("FEEDBACK_REQUIRE_ORIGIN", isProduction),
      allowedOrigins: parseAllowedOrigins(nodeEnv),
      maxRequestBytes: envInt("FEEDBACK_MAX_REQUEST_BYTES", 8 * 1024),
    },
  };
}
