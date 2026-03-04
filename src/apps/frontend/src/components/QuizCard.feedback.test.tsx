import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, test, vi } from "vitest";

import QuizCard from "./QuizCard";
import type { HistoryMcqQuiz } from "../lib/types";
import { submitQuizFeedback } from "../lib/feedbackApi";

vi.mock("../lib/feedbackApi", () => ({
  submitQuizFeedback: vi.fn(),
}));

function sampleQuiz(): HistoryMcqQuiz {
  return {
    date: "2026-03-04",
    topics: ["history"],
    type: "history_mcq_4",
    question: "Which event happened in 1901?",
    correct_choice_id: "A",
    source: {
      name: "Wikipedia On This Day",
      url: "https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/events/3/4",
      retrieved_at: "2026-03-04T06:00:00Z",
      events_used: [
        {
          event_id: "evt-1",
          text: "Event A",
          year: 1901,
          wikipedia_url: "https://example.com/a",
        },
        {
          event_id: "evt-2",
          text: "Event B",
          year: 1902,
          wikipedia_url: "https://example.com/b",
        },
        {
          event_id: "evt-3",
          text: "Event C",
          year: 1903,
          wikipedia_url: "https://example.com/c",
        },
        {
          event_id: "evt-4",
          text: "Event D",
          year: 1904,
          wikipedia_url: "https://example.com/d",
        },
      ],
    },
    metadata: {
      version: 2,
      normalized_model: "question_answer_facts_v1",
    },
    generation: {
      mode: "daily",
      edition: 1,
      generated_at: "2026-03-04T06:00:00Z",
    },
    choices: [
      { id: "A", label: "Event A", answer_fact_id: "fact-a", human_id: "A1" },
      { id: "B", label: "Event B", answer_fact_id: "fact-b", human_id: "A2" },
      { id: "C", label: "Event C", answer_fact_id: "fact-c", human_id: "A3" },
      { id: "D", label: "Event D", answer_fact_id: "fact-d", human_id: "A4" },
    ],
    questions: [
      {
        id: "123e4567-e89b-42d3-a456-426614174000",
        human_id: "Q42",
        type: "history_mcq_4",
        prompt: "Which event happened in 1901?",
        answer_fact_ids: ["fact-a", "fact-b", "fact-c", "fact-d"],
        correct_answer_fact_id: "fact-a",
        tags: ["history", "history_mcq_4"],
        facets: { topic: "history", difficulty_band: "baseline" },
        selection_rules: { distractor_same_year_allowed: false, target_year: 1901 },
      },
    ],
    answer_facts: [
      {
        id: "fact-a",
        human_id: "A1",
        label: "Event A",
        year: 1901,
        tags: ["history"],
        facets: { topic: "history" },
        match: {},
        vector_metadata: { text_for_embedding: "Event A", embedding_status: "not_generated" },
      },
      {
        id: "fact-b",
        human_id: "A2",
        label: "Event B",
        year: 1902,
        tags: ["history"],
        facets: { topic: "history" },
        match: {},
        vector_metadata: { text_for_embedding: "Event B", embedding_status: "not_generated" },
      },
      {
        id: "fact-c",
        human_id: "A3",
        label: "Event C",
        year: 1903,
        tags: ["history"],
        facets: { topic: "history" },
        match: {},
        vector_metadata: { text_for_embedding: "Event C", embedding_status: "not_generated" },
      },
      {
        id: "fact-d",
        human_id: "A4",
        label: "Event D",
        year: 1904,
        tags: ["history"],
        facets: { topic: "history" },
        match: {},
        vector_metadata: { text_for_embedding: "Event D", embedding_status: "not_generated" },
      },
    ],
  };
}

const submitFeedbackMock = vi.mocked(submitQuizFeedback);

describe("QuizCard feedback", () => {
  beforeEach(() => {
    submitFeedbackMock.mockReset();
    localStorage.clear();
  });

  test("submits feedback and shows saved state", async () => {
    submitFeedbackMock.mockResolvedValue({ ok: true, mode: "created", feedback_id: "fdbk_1" });

    const user = userEvent.setup();
    render(
      <QuizCard
        quiz={sampleQuiz()}
        quizKey="history_mcq_4:1:quizzes/abc123.json"
        quizFile="quizzes/abc123.json"
        edition={1}
        selectedChoiceId={undefined}
        onSelectChoice={() => {}}
      />,
    );

    await user.click(screen.getByRole("button", { name: "4 stars" }));
    await user.type(screen.getByLabelText("Optional comment"), "Useful question");
    await user.click(screen.getByRole("button", { name: "Submit feedback" }));

    await waitFor(() => {
      expect(submitFeedbackMock).toHaveBeenCalledTimes(1);
    });

    expect(submitFeedbackMock).toHaveBeenCalledWith({
      quiz_file: "quizzes/abc123.json",
      date: "2026-03-04",
      quiz_type: "history_mcq_4",
      edition: 1,
      question_id: "123e4567-e89b-42d3-a456-426614174000",
      question_human_id: "Q42",
      rating: 4,
      comment: "Useful question",
    });

    expect(await screen.findByText("Feedback saved.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Saved" })).toBeInTheDocument();
  });

  test("submits feedback and shows updated state", async () => {
    submitFeedbackMock.mockResolvedValue({ ok: true, mode: "updated", feedback_id: "fdbk_1" });

    const user = userEvent.setup();
    render(
      <QuizCard
        quiz={sampleQuiz()}
        quizKey="history_mcq_4:1:quizzes/abc123.json"
        quizFile="quizzes/abc123.json"
        edition={1}
        selectedChoiceId={undefined}
        onSelectChoice={() => {}}
      />,
    );

    await user.click(screen.getByRole("button", { name: "5 stars" }));
    await user.click(screen.getByRole("button", { name: "Submit feedback" }));

    expect(await screen.findByText("Feedback updated.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Updated" })).toBeInTheDocument();
  });

  test("shows retry state when submit fails", async () => {
    submitFeedbackMock.mockRejectedValue(new Error("rate_limited"));

    const user = userEvent.setup();
    render(
      <QuizCard
        quiz={sampleQuiz()}
        quizKey="history_mcq_4:1:quizzes/abc123.json"
        quizFile="quizzes/abc123.json"
        edition={1}
        selectedChoiceId={undefined}
        onSelectChoice={() => {}}
      />,
    );

    await user.click(screen.getByRole("button", { name: "3 stars" }));
    await user.click(screen.getByRole("button", { name: "Submit feedback" }));

    expect(await screen.findByText("Could not submit feedback: rate_limited")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry submit" })).toBeInTheDocument();
  });
});
