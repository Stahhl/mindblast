import { afterEach, describe, expect, test } from "vitest";

import { loadFeedbackRuntimeConfig } from "../src/application/runtime_config";

const ORIGINAL_ENV = { ...process.env };

afterEach(() => {
  process.env = { ...ORIGINAL_ENV };
});

describe("feedback runtime config", () => {
  test("uses the updated default rate limits", () => {
    delete process.env.FEEDBACK_RATE_LIMIT_CLIENT_HOURLY;
    delete process.env.FEEDBACK_RATE_LIMIT_CLIENT_DAILY;
    delete process.env.FEEDBACK_RATE_LIMIT_IP_HOURLY;
    delete process.env.FEEDBACK_RATE_LIMIT_GLOBAL_HOURLY;

    const config = loadFeedbackRuntimeConfig();
    expect(config.rateLimits.clientHourly).toBe(12);
    expect(config.rateLimits.clientDaily).toBe(60);
    expect(config.rateLimits.ipHourly).toBe(120);
    expect(config.rateLimits.globalHourly).toBe(5000);
  });

  test("auto App Check is enabled in production environments including staging project ids", () => {
    process.env.NODE_ENV = "production";
    process.env.GCLOUD_PROJECT = "mindblast-staging";
    delete process.env.FEEDBACK_APP_CHECK_ENFORCEMENT;

    const config = loadFeedbackRuntimeConfig();
    expect(config.security.requireAppCheck).toBe(true);
  });

  test("auto App Check is enabled for production projects", () => {
    process.env.NODE_ENV = "production";
    process.env.GCLOUD_PROJECT = "mindblast-prod";
    delete process.env.FEEDBACK_APP_CHECK_ENFORCEMENT;

    const config = loadFeedbackRuntimeConfig();
    expect(config.security.requireAppCheck).toBe(true);
  });

  test("auto auth enforcement is enabled in production environments", () => {
    process.env.NODE_ENV = "production";
    delete process.env.FEEDBACK_AUTH_ENFORCEMENT;

    const config = loadFeedbackRuntimeConfig();
    expect(config.security.requireAuth).toBe(true);
  });

  test("auto auth enforcement is disabled outside production environments", () => {
    process.env.NODE_ENV = "development";
    delete process.env.FEEDBACK_AUTH_ENFORCEMENT;

    const config = loadFeedbackRuntimeConfig();
    expect(config.security.requireAuth).toBe(false);
  });

  test("auto enforcement is enabled in managed runtime even when NODE_ENV is not production", () => {
    process.env.NODE_ENV = "development";
    process.env.K_SERVICE = "quizfeedbackapi";
    delete process.env.FEEDBACK_AUTH_ENFORCEMENT;
    delete process.env.FEEDBACK_APP_CHECK_ENFORCEMENT;

    const config = loadFeedbackRuntimeConfig();
    expect(config.security.requireAuth).toBe(true);
    expect(config.security.requireAppCheck).toBe(true);
  });

  test("auto enforcement stays disabled in emulator runtime", () => {
    process.env.NODE_ENV = "development";
    process.env.K_SERVICE = "quizfeedbackapi";
    process.env.FUNCTIONS_EMULATOR = "true";
    delete process.env.FEEDBACK_AUTH_ENFORCEMENT;
    delete process.env.FEEDBACK_APP_CHECK_ENFORCEMENT;

    const config = loadFeedbackRuntimeConfig();
    expect(config.security.requireAuth).toBe(false);
    expect(config.security.requireAppCheck).toBe(false);
  });
});
