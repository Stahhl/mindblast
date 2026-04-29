import type { QuizType } from "./types";

export interface PersistUserQuizStateRequest {
  quiz_file: string;
  date: string;
  quiz_type: QuizType;
  edition: number;
  question_id: string;
  question_human_id: string;
  selected_choice_id?: string;
  feedback_draft?: {
    rating?: number;
    comment?: string;
  };
}

export interface UserQuizAnswerState {
  date: string;
  quiz_file: string;
  quiz_type: QuizType;
  edition: number;
  question_id: string;
  question_human_id: string;
  selected_choice_id: string;
  answered_at: string;
  updated_at: string;
}

export interface UserFeedbackDraftState {
  question_id: string;
  rating?: number;
  comment?: string;
  updated_at: string;
}

export interface UserFeedbackSubmissionState {
  question_id: string;
  feedback_id: string;
  rating: number;
  comment?: string;
  submitted_at: string;
  updated_at: string;
}

export interface UserQuizStateResponse {
  ok: true;
  date: string;
  answers: UserQuizAnswerState[];
  feedback_drafts: UserFeedbackDraftState[];
  feedback_submissions: UserFeedbackSubmissionState[];
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

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

export async function loadUserQuizState(
  date: string,
  questionIds: string[],
  authHeaders: Record<string, string>,
): Promise<UserQuizStateResponse> {
  const params = new URLSearchParams({ date });
  if (questionIds.length) {
    params.set("question_ids", questionIds.join(","));
  }

  const response = await fetch(`/api/user-quiz-state?${params.toString()}`, {
    method: "GET",
    headers: authHeaders,
  });
  const payload = await readJson(response);
  if (!response.ok) {
    const errorPayload = (payload && typeof payload === "object" ? payload : {}) as ErrorPayload;
    throw new Error(buildErrorMessage(errorPayload, `Request failed (${response.status})`));
  }

  const parsed = (payload && typeof payload === "object" ? payload : {}) as Partial<UserQuizStateResponse>;
  if (parsed.ok !== true || typeof parsed.date !== "string") {
    throw new Error("Unexpected user state API response");
  }

  return {
    ok: true,
    date: parsed.date,
    answers: Array.isArray(parsed.answers) ? parsed.answers : [],
    feedback_drafts: Array.isArray(parsed.feedback_drafts) ? parsed.feedback_drafts : [],
    feedback_submissions: Array.isArray(parsed.feedback_submissions) ? parsed.feedback_submissions : [],
  };
}

export async function persistUserQuizState(
  request: PersistUserQuizStateRequest,
  authHeaders: Record<string, string>,
): Promise<void> {
  const response = await fetch("/api/user-quiz-state", {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify(request),
  });
  const payload = await readJson(response);
  if (!response.ok) {
    const errorPayload = (payload && typeof payload === "object" ? payload : {}) as ErrorPayload;
    throw new Error(buildErrorMessage(errorPayload, `Request failed (${response.status})`));
  }
  const parsed = (payload && typeof payload === "object" ? payload : {}) as { ok?: unknown };
  if (parsed.ok !== true) {
    throw new Error("Unexpected user state API response");
  }
}
