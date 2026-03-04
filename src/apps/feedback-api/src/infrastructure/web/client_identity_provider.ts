import { randomUUID } from "node:crypto";

const COOKIE_NAME = "mindblast_client_id";
const CLIENT_ID_REGEX = /^[a-f0-9-]{36}$/i;

function parseCookieHeader(rawCookieHeader: string | undefined): Record<string, string> {
  if (!rawCookieHeader) {
    return {};
  }

  const parsed: Record<string, string> = {};
  for (const chunk of rawCookieHeader.split(";")) {
    const [name, ...rest] = chunk.split("=");
    const key = name?.trim();
    if (!key) {
      continue;
    }
    parsed[key] = rest.join("=").trim();
  }
  return parsed;
}

function shouldUseSecureCookie(headers: Record<string, string | string[] | undefined>): boolean {
  const forwardedProto = headers["x-forwarded-proto"];
  const proto = Array.isArray(forwardedProto) ? forwardedProto[0] : forwardedProto;
  const first = proto?.split(",")[0]?.trim().toLowerCase();
  if (first === "https") {
    return true;
  }
  return process.env.NODE_ENV === "production";
}

export interface ClientIdentityRequestLike {
  headers: Record<string, string | string[] | undefined>;
}

export interface ClientIdentityResponseLike {
  setHeader(name: string, value: string): void;
}

export function getOrCreateClientId(
  request: ClientIdentityRequestLike,
  response: ClientIdentityResponseLike,
): string {
  const rawCookieHeader = request.headers.cookie;
  const cookie = Array.isArray(rawCookieHeader) ? rawCookieHeader[0] : rawCookieHeader;
  const cookies = parseCookieHeader(cookie);
  const existingClientId = cookies[COOKIE_NAME];
  if (existingClientId && CLIENT_ID_REGEX.test(existingClientId)) {
    return existingClientId;
  }

  const clientId = randomUUID();
  const parts = [
    `${COOKIE_NAME}=${clientId}`,
    "Path=/",
    "HttpOnly",
    "SameSite=Lax",
    "Max-Age=31536000",
  ];
  if (shouldUseSecureCookie(request.headers)) {
    parts.push("Secure");
  }
  response.setHeader("Set-Cookie", parts.join("; "));
  return clientId;
}
