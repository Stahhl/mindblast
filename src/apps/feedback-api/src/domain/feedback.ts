export type QuizType = "which_came_first" | "history_mcq_4" | "history_factoid_mcq_4";

export interface SubmitFeedbackPayload {
  quiz_file: string;
  date: string;
  quiz_type: QuizType;
  edition: number;
  question_id: string;
  question_human_id: string;
  rating: number;
  comment?: string;
}

export interface FeedbackRecord {
  schema_version: 1;
  feedback_id: string;
  quiz_file: string;
  date: string;
  quiz_type: QuizType;
  edition: number;
  question_id: string;
  question_human_id: string;
  rating: number;
  feedback_date_utc: string;
  client_id: string;
  created_at: string;
  updated_at: string;
  comment?: string;
  source: "web";
  user_agent_hash?: string;
}

export type SubmitFeedbackMode = "created" | "updated";

export interface SubmitFeedbackResult {
  ok: true;
  mode: SubmitFeedbackMode;
  feedback_id: string;
}
