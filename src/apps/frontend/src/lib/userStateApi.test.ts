import { beforeEach, describe, expect, test, vi } from "vitest";

import { loadUserQuizState, persistUserQuizState } from "./userStateApi";

describe("userStateApi", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  test("loads signed-in quiz state with auth headers", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          ok: true,
          date: "2026-03-04",
          answers: [
            {
              date: "2026-03-04",
              quiz_file: "quizzes/abc123.json",
              quiz_type: "history_mcq_4",
              edition: 1,
              question_id: "123e4567-e89b-42d3-a456-426614174000",
              question_human_id: "Q42",
              selected_choice_id: "A",
              answered_at: "2026-03-04T10:00:00.000Z",
              updated_at: "2026-03-04T10:00:00.000Z",
            },
          ],
          feedback_drafts: [],
          feedback_submissions: [],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await loadUserQuizState("2026-03-04", ["123e4567-e89b-42d3-a456-426614174000"], {
      "X-Firebase-ID-Token": "id-token",
      "X-Firebase-AppCheck": "app-check",
    });

    expect(result.answers[0]?.selected_choice_id).toBe("A");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/user-quiz-state?date=2026-03-04&question_ids=123e4567-e89b-42d3-a456-426614174000",
      {
        method: "GET",
        headers: {
          "X-Firebase-ID-Token": "id-token",
          "X-Firebase-AppCheck": "app-check",
        },
      },
    );
  });

  test("persists signed-in quiz state", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await persistUserQuizState(
      {
        quiz_file: "quizzes/abc123.json",
        date: "2026-03-04",
        quiz_type: "history_mcq_4",
        edition: 1,
        question_id: "123e4567-e89b-42d3-a456-426614174000",
        question_human_id: "Q42",
        selected_choice_id: "A",
      },
      {
        "X-Firebase-ID-Token": "id-token",
        "X-Firebase-AppCheck": "app-check",
      },
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/user-quiz-state",
      expect.objectContaining({
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "X-Firebase-ID-Token": "id-token",
          "X-Firebase-AppCheck": "app-check",
        },
      }),
    );
  });
});
