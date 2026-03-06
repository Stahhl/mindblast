export interface SubmitQuizFeedbackRequest {
  quiz_file: string;
  date: string;
  quiz_type: "which_came_first" | "history_mcq_4" | "history_factoid_mcq_4";
  edition: number;
  question_id: string;
  question_human_id: string;
  rating: number;
  comment?: string;
}

export interface SubmitQuizFeedbackSuccess {
  ok: true;
  mode: "created" | "updated";
  feedback_id: string;
}

interface ErrorPayload {
  ok?: boolean;
  error?: string;
  details?: string;
}

function buildErrorMessage(payload: ErrorPayload, fallback: string): string {
  if (typeof payload.details === "string" && payload.details.trim()) {
    return payload.details;
  }
  if (typeof payload.error === "string" && payload.error.trim()) {
    return payload.error;
  }
  return fallback;
}

export async function submitQuizFeedback(
  request: SubmitQuizFeedbackRequest,
  authHeaders: Record<string, string> = {},
): Promise<SubmitQuizFeedbackSuccess> {
  const response = await fetch("/api/quiz-feedback", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify(request),
  });

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const errorPayload = (payload && typeof payload === "object" ? payload : {}) as ErrorPayload;
    throw new Error(buildErrorMessage(errorPayload, `Request failed (${response.status})`));
  }

  const successPayload = (payload && typeof payload === "object" ? payload : {}) as Partial<SubmitQuizFeedbackSuccess>;
  if (successPayload.ok !== true) {
    throw new Error("Unexpected feedback API response");
  }
  if (successPayload.mode !== "created" && successPayload.mode !== "updated") {
    throw new Error("Unexpected feedback API mode");
  }
  if (typeof successPayload.feedback_id !== "string" || !successPayload.feedback_id.trim()) {
    throw new Error("Missing feedback_id in feedback API response");
  }

  return {
    ok: true,
    mode: successPayload.mode,
    feedback_id: successPayload.feedback_id,
  };
}
