import { describe, expect, test } from "vitest";

import type { FeedbackRepositoryPort } from "../src/application/ports";
import { ValidationError } from "../src/application/errors";
import { submitFeedbackUseCase } from "../src/application/submit_feedback_use_case";
import type { FeedbackRecord, SubmitFeedbackMode } from "../src/domain/feedback";

class FixedClock {
  private readonly values: string[];
  private index = 0;

  constructor(...values: string[]) {
    this.values = values;
  }

  nowIsoUtc(): string {
    const current = this.values[Math.min(this.index, this.values.length - 1)] ?? "2026-03-04T00:00:00.000Z";
    this.index += 1;
    return current;
  }

  todayUtc(): string {
    return this.nowIsoUtc().slice(0, 10);
  }
}

class DeterministicIdGenerator {
  buildFeedbackId(input: { clientId: string; questionId: string; feedbackDateUtc: string }): string {
    return `fdbk_${input.clientId}_${input.questionId}_${input.feedbackDateUtc}`;
  }
}

class InMemoryFeedbackRepository implements FeedbackRepositoryPort {
  records = new Map<string, FeedbackRecord>();

  async upsertById(feedbackId: string, record: FeedbackRecord): Promise<{ mode: SubmitFeedbackMode }> {
    const existing = this.records.get(feedbackId);
    if (!existing) {
      this.records.set(feedbackId, record);
      return { mode: "created" };
    }

    this.records.set(feedbackId, {
      ...record,
      created_at: existing.created_at,
    });
    return { mode: "updated" };
  }
}

function payload(overrides: Partial<Record<string, unknown>> = {}): Record<string, unknown> {
  return {
    quiz_file: "quizzes/abc123.json",
    date: "2026-03-04",
    quiz_type: "history_factoid_mcq_4",
    edition: 1,
    question_id: "123e4567-e89b-42d3-a456-426614174000",
    question_human_id: "Q42",
    rating: 4,
    comment: "  Good question  ",
    ...overrides,
  };
}

describe("submitFeedbackUseCase", () => {
  test("creates feedback on first submission", async () => {
    const repository = new InMemoryFeedbackRepository();
    const result = await submitFeedbackUseCase(
      {
        payload: payload(),
        clientId: "client-1",
      },
      {
        repository,
        clock: new FixedClock("2026-03-04T10:00:00.000Z", "2026-03-04T10:00:00.000Z"),
        idGenerator: new DeterministicIdGenerator(),
      },
    );

    expect(result.ok).toBe(true);
    expect(result.mode).toBe("created");

    const stored = repository.records.get(result.feedback_id);
    expect(stored).toBeDefined();
    expect(stored?.rating).toBe(4);
    expect(stored?.comment).toBe("Good question");
    expect(stored?.created_at).toBe("2026-03-04T10:00:00.000Z");
    expect(stored?.updated_at).toBe("2026-03-04T10:00:00.000Z");
  });

  test("updates existing feedback for same client/question/day", async () => {
    const repository = new InMemoryFeedbackRepository();
    const idGenerator = new DeterministicIdGenerator();

    const first = await submitFeedbackUseCase(
      {
        payload: payload({ rating: 2, comment: "initial" }),
        clientId: "client-1",
      },
      {
        repository,
        clock: new FixedClock("2026-03-04T10:00:00.000Z", "2026-03-04T10:00:00.000Z"),
        idGenerator,
      },
    );
    const second = await submitFeedbackUseCase(
      {
        payload: payload({ rating: 5, comment: "updated" }),
        clientId: "client-1",
      },
      {
        repository,
        clock: new FixedClock("2026-03-04T11:00:00.000Z", "2026-03-04T11:00:00.000Z"),
        idGenerator,
      },
    );

    expect(first.feedback_id).toBe(second.feedback_id);
    expect(second.mode).toBe("updated");

    const stored = repository.records.get(second.feedback_id);
    expect(stored?.rating).toBe(5);
    expect(stored?.comment).toBe("updated");
    expect(stored?.created_at).toBe("2026-03-04T10:00:00.000Z");
    expect(stored?.updated_at).toBe("2026-03-04T11:00:00.000Z");
  });

  test("rejects invalid payload", async () => {
    const repository = new InMemoryFeedbackRepository();

    await expect(
      submitFeedbackUseCase(
        {
          payload: payload({ rating: 6 }),
          clientId: "client-1",
        },
        {
          repository,
          clock: new FixedClock("2026-03-04T10:00:00.000Z", "2026-03-04T10:00:00.000Z"),
          idGenerator: new DeterministicIdGenerator(),
        },
      ),
    ).rejects.toBeInstanceOf(ValidationError);
  });
});
