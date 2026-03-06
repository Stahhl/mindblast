import { afterEach, describe, expect, test } from "vitest";

import { loadFeedbackRuntimeConfig } from "../src/application/runtime_config";

const ORIGINAL_ENV = { ...process.env };

afterEach(() => {
  process.env = { ...ORIGINAL_ENV };
});

describe("feedback runtime config", () => {
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
});
