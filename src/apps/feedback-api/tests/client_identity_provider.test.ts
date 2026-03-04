import { describe, expect, test } from "vitest";

import { getOrCreateClientId } from "../src/infrastructure/web/client_identity_provider";

describe("getOrCreateClientId", () => {
  test("reuses existing cookie value", () => {
    const setHeaders: string[] = [];
    const clientId = getOrCreateClientId(
      {
        headers: {
          cookie: "mindblast_client_id=123e4567-e89b-42d3-a456-426614174001; theme=dark",
        },
      },
      {
        setHeader: (_name, value) => {
          setHeaders.push(value);
        },
      },
    );

    expect(clientId).toBe("123e4567-e89b-42d3-a456-426614174001");
    expect(setHeaders).toHaveLength(0);
  });

  test("issues new secure cookie when missing", () => {
    const setHeaders: string[] = [];
    const clientId = getOrCreateClientId(
      {
        headers: {
          "x-forwarded-proto": "https",
        },
      },
      {
        setHeader: (_name, value) => {
          setHeaders.push(value);
        },
      },
    );

    expect(clientId).toHaveLength(36);
    expect(setHeaders).toHaveLength(1);
    expect(setHeaders[0]).toContain("mindblast_client_id=");
    expect(setHeaders[0]).toContain("HttpOnly");
    expect(setHeaders[0]).toContain("SameSite=Lax");
    expect(setHeaders[0]).toContain("Secure");
  });
});
