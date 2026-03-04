import { afterEach, describe, expect, test } from "vitest";

import { loadFeedbackRuntimeConfig } from "../src/application/runtime_config";

const ORIGINAL_ENV = { ...process.env };

afterEach(() => {
  process.env = { ...ORIGINAL_ENV };
});

describe("feedback runtime config", () => {
  test("auto App Check is disabled for known staging project", () => {
    process.env.NODE_ENV = "production";
    process.env.GCLOUD_PROJECT = "mindblast-staging";
    delete process.env.FEEDBACK_APP_CHECK_ENFORCEMENT;

    const config = loadFeedbackRuntimeConfig();
    expect(config.security.requireAppCheck).toBe(false);
  });

  test("auto App Check is enabled for production projects", () => {
    process.env.NODE_ENV = "production";
    process.env.GCLOUD_PROJECT = "mindblast-prod";
    delete process.env.FEEDBACK_APP_CHECK_ENFORCEMENT;

    const config = loadFeedbackRuntimeConfig();
    expect(config.security.requireAppCheck).toBe(true);
  });
});
