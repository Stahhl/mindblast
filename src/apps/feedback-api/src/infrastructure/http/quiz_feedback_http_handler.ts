import { ValidationError } from "../../application/errors";
import {
  submitFeedbackUseCase,
  type SubmitFeedbackUseCaseDependencies,
} from "../../application/submit_feedback_use_case";
import { getOrCreateClientId } from "../web/client_identity_provider";

const QUIZ_FEEDBACK_PATHS = new Set(["/api/quiz-feedback", "/quiz-feedback"]);

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

function isJsonContentType(contentType: string | undefined): boolean {
  return typeof contentType === "string" && contentType.toLowerCase().includes("application/json");
}

function normalizePath(path: string): string {
  if (path.endsWith("/")) {
    return path.slice(0, -1);
  }
  return path;
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

export function createQuizFeedbackHttpHandler(deps: SubmitFeedbackUseCaseDependencies) {
  return async (request: RequestLike, response: ResponseLike): Promise<void> => {
    if (request.method !== "POST") {
      response.status(405).json({ ok: false, error: "method_not_allowed" });
      return;
    }

    if (!QUIZ_FEEDBACK_PATHS.has(normalizePath(request.path))) {
      response.status(404).json({ ok: false, error: "not_found" });
      return;
    }

    if (!isJsonContentType(request.get("content-type"))) {
      response.status(400).json({ ok: false, error: "invalid_payload", details: "content-type must be application/json" });
      return;
    }

    try {
      const payload = extractBody(request);
      const clientId = getOrCreateClientId(
        {
          headers: request.headers,
        },
        {
          setHeader: (name, value) => response.setHeader(name, value),
        },
      );

      const result = await submitFeedbackUseCase(
        {
          payload,
          clientId,
        },
        deps,
      );

      response.status(200).json(result);
    } catch (error) {
      if (error instanceof SyntaxError) {
        response.status(400).json({ ok: false, error: "invalid_payload", details: "body must be valid JSON" });
        return;
      }
      if (error instanceof ValidationError) {
        response.status(400).json({ ok: false, error: "invalid_payload", details: error.message });
        return;
      }

      console.error("quiz feedback write failed", error);
      response.status(500).json({ ok: false, error: "storage_error" });
    }
  };
}
