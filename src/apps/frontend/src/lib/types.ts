export type QuizType = "which_came_first" | "history_mcq_4";

export interface LatestPayload {
  date: string;
  index_file: string;
  available_types: QuizType[];
  metadata: {
    version: 1;
    updated_at: string;
  };
}

export interface IndexPayload {
  date: string;
  quiz_files: Record<QuizType, string> | Record<string, string>;
  available_types: QuizType[];
  metadata: {
    version: 1;
    generated_at: string;
  };
}

export interface QuizSourceEvent {
  event_id?: string;
  text: string;
  year: number;
  wikipedia_url: string;
}

export interface QuizSource {
  name: string;
  url: string;
  retrieved_at: string;
  events_used: QuizSourceEvent[];
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
  questions?: QuizQuestionModel[];
  answer_facts?: QuizAnswerFact[];
}

export interface QuizQuestionModel {
  id: string;
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
  label: string;
  year: number;
}

export interface HistoryMcqChoice {
  id: string;
  label: string;
}

export interface WhichCameFirstQuiz extends QuizBase {
  type: "which_came_first";
  choices: WhichCameFirstChoice[];
}

export interface HistoryMcqQuiz extends QuizBase {
  type: "history_mcq_4";
  choices: HistoryMcqChoice[];
}

export type QuizPayload = WhichCameFirstQuiz | HistoryMcqQuiz;

export interface DailyQuizLoadResult {
  date: string;
  latestDate: string;
  availableTypes: QuizType[];
  quizzes: QuizPayload[];
  errorsByType: Map<string, string>;
}
