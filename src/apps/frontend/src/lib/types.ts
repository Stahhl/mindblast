export type QuizType =
  | "which_came_first"
  | "history_mcq_4"
  | "history_factoid_mcq_4"
  | "geography_factoid_mcq_4";

export interface IndexQuizEdition {
  edition: number;
  mode: "daily" | "extra" | string;
  quiz_file: string;
  generated_at: string;
}

export interface LatestPayload {
  date: string;
  index_file: string;
  available_types: QuizType[];
  latest_quiz_by_type?: Record<QuizType, string> | Record<string, string>;
  metadata: {
    version: 1 | 2;
    updated_at: string;
  };
}

export interface IndexPayload {
  date: string;
  quiz_files: Record<QuizType, string> | Record<string, string>;
  quizzes_by_type?: Record<QuizType, IndexQuizEdition[]> | Record<string, IndexQuizEdition[]>;
  available_types: QuizType[];
  metadata: {
    version: 1 | 2;
    generated_at: string;
  };
}

export interface QuizSourceEvent {
  event_id?: string;
  text: string;
  year: number;
  wikipedia_url: string;
}

export interface QuizSourceRecord {
  record_id: string;
  country_label: string;
  capital_label: string;
  country_qid: string;
  capital_qid: string;
  country_url: string;
  capital_url: string;
}

export interface QuizSource {
  name: string;
  url: string;
  retrieved_at: string;
  events_used?: QuizSourceEvent[];
  records_used?: QuizSourceRecord[];
}

interface QuizBase {
  date: string;
  topics: string[];
  type: QuizType;
  question: string;
  correct_choice_id: string;
  source: QuizSource;
  metadata: {
    version: 1 | 2;
    normalized_model?: string;
  };
  generation?: {
    mode: "daily" | "extra" | string;
    edition: number;
    generated_at: string;
  };
  questions?: QuizQuestionModel[];
  answer_facts?: QuizAnswerFact[];
}

export interface QuizQuestionModel {
  id: string;
  human_id?: string;
  type: QuizType;
  prompt: string;
  answer_fact_ids: string[];
  correct_answer_fact_id: string;
  tags: string[];
  facets: Record<string, string>;
  selection_rules: Record<string, unknown>;
}

export interface QuizAnswerFact {
  id: string;
  human_id?: string;
  label: string;
  year: number;
  tags: string[];
  facets: Record<string, string>;
  match: Record<string, unknown>;
  vector_metadata: {
    text_for_embedding: string;
    embedding_status: string;
  };
}

export interface WhichCameFirstChoice {
  id: string;
  human_id?: string;
  label: string;
  year: number;
  answer_fact_id?: string;
}

export interface HistoryMcqChoice {
  id: string;
  human_id?: string;
  label: string;
  answer_fact_id?: string;
}

export interface WhichCameFirstQuiz extends QuizBase {
  type: "which_came_first";
  choices: WhichCameFirstChoice[];
}

export interface HistoryMcqQuiz extends QuizBase {
  type: "history_mcq_4";
  choices: HistoryMcqChoice[];
}

export interface HistoryFactoidMcqQuiz extends QuizBase {
  type: "history_factoid_mcq_4";
  choices: HistoryMcqChoice[];
}

export interface GeographyFactoidMcqQuiz extends QuizBase {
  type: "geography_factoid_mcq_4";
  choices: HistoryMcqChoice[];
}

export type QuizPayload =
  | WhichCameFirstQuiz
  | HistoryMcqQuiz
  | HistoryFactoidMcqQuiz
  | GeographyFactoidMcqQuiz;

export interface LoadedQuiz {
  key: string;
  type: QuizType;
  edition: number;
  sourcePath: string;
  payload: QuizPayload;
}

export interface DailyQuizLoadResult {
  date: string;
  latestDate: string;
  availableTypes: QuizType[];
  quizzes: LoadedQuiz[];
  errorsByType: Map<string, string>;
}
