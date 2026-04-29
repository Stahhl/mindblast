import type { QuizType } from "./feedback";

export interface UserQuizAnswerRecord {
  schema_version: 1;
  auth_uid: string;
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

export interface UserFeedbackDraftRecord {
  schema_version: 1;
  auth_uid: string;
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

export interface UserQuizStateSnapshot {
  ok: true;
  date: string;
  answers: UserQuizAnswerRecord[];
  feedback_drafts: UserFeedbackDraftRecord[];
  feedback_submissions: UserFeedbackSubmissionState[];
}
