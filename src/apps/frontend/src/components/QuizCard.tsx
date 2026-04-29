import { useEffect, useMemo, useState } from "react";

import { submitQuizFeedback } from "../lib/feedbackApi";
import type { UserFeedbackDraftState, UserFeedbackSubmissionState } from "../lib/userStateApi";
import type { QuizPayload, QuizType } from "../lib/types";

interface QuizCardProps {
  quiz: QuizPayload;
  quizKey: string;
  quizFile: string;
  edition: number;
  feedbackEnabled: boolean;
  feedbackBlockedMessage?: string;
  getFeedbackRequestHeaders: () => Promise<Record<string, string>>;
  initialFeedbackDraft?: UserFeedbackDraftState;
  initialFeedbackSubmission?: UserFeedbackSubmissionState;
  onFeedbackDraftChange?: (input: {
    quiz: QuizPayload;
    quizFile: string;
    edition: number;
    questionId: string;
    questionHumanId: string;
    rating?: number;
    comment: string;
  }) => void;
  selectedChoiceId: string | undefined;
  onSelectChoice: (quizKey: string, choiceId: string) => void;
}

type FeedbackStatus = "idle" | "saving" | "saved" | "updated" | "error";

const COMMENT_MAX_LENGTH = 500;

function answerTone(isCorrect: boolean): "correct" | "wrong" {
  return isCorrect ? "correct" : "wrong";
}

function formatQuizType(type: QuizType): string {
  if (type === "which_came_first") {
    return "Which Came First";
  }
  if (type === "history_mcq_4") {
    return "History MCQ";
  }
  if (type === "history_factoid_mcq_4") {
    return "History Factoid";
  }
  if (type === "geography_factoid_mcq_4") {
    return "Geography Factoid";
  }
  return type;
}

function feedbackDraftKey(questionId: string): string {
  return `mindblast:feedback-draft:${questionId}`;
}

interface FeedbackDraft {
  rating?: number;
  comment?: string;
}

function readDraft(questionId: string): FeedbackDraft {
  if (!questionId) {
    return {};
  }
  try {
    const raw = localStorage.getItem(feedbackDraftKey(questionId));
    if (!raw) {
      return {};
    }
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object") {
      return {};
    }
    const asRecord = parsed as Record<string, unknown>;
    const rating = Number.isInteger(asRecord.rating) ? (asRecord.rating as number) : undefined;
    const comment = typeof asRecord.comment === "string" ? asRecord.comment : undefined;
    if (rating !== undefined && (rating < 1 || rating > 5)) {
      return { comment };
    }
    return { rating, comment };
  } catch {
    return {};
  }
}

function writeDraft(questionId: string, draft: FeedbackDraft): void {
  if (!questionId) {
    return;
  }
  if (draft.rating === undefined && (!draft.comment || !draft.comment.trim())) {
    localStorage.removeItem(feedbackDraftKey(questionId));
    return;
  }
  localStorage.setItem(
    feedbackDraftKey(questionId),
    JSON.stringify({
      rating: draft.rating,
      comment: draft.comment ?? "",
    }),
  );
}

export default function QuizCard({
  quiz,
  quizKey,
  quizFile,
  edition,
  feedbackEnabled,
  feedbackBlockedMessage,
  getFeedbackRequestHeaders,
  initialFeedbackDraft,
  initialFeedbackSubmission,
  onFeedbackDraftChange,
  selectedChoiceId,
  onSelectChoice,
}: QuizCardProps) {
  const hasAnswered = Boolean(selectedChoiceId);
  const correctChoice = quiz.choices.find((choice) => choice.id === quiz.correct_choice_id);
  const isCorrect = selectedChoiceId === quiz.correct_choice_id;
  const questionHumanId = quiz.questions?.[0]?.human_id;
  const questionId = quiz.questions?.[0]?.id ?? "";
  const hasFeedbackMetadata = Boolean(questionId && questionHumanId);
  const canSubmitFeedback = hasFeedbackMetadata && feedbackEnabled;
  const [rating, setRating] = useState<number | undefined>(undefined);
  const [comment, setComment] = useState<string>("");
  const [feedbackStatus, setFeedbackStatus] = useState<FeedbackStatus>("idle");
  const [feedbackMessage, setFeedbackMessage] = useState<string>("");
  const [draftEdited, setDraftEdited] = useState(false);

  useEffect(() => {
    const draft = readDraft(questionId);
    const remoteDraft = initialFeedbackDraft ?? initialFeedbackSubmission;
    setRating(remoteDraft?.rating ?? draft.rating);
    setComment(remoteDraft?.comment ?? draft.comment ?? "");
    if (initialFeedbackSubmission) {
      setFeedbackStatus("updated");
      setFeedbackMessage("Feedback previously saved.");
    } else {
      setFeedbackStatus("idle");
      setFeedbackMessage("");
    }
    setDraftEdited(false);
  }, [initialFeedbackDraft, initialFeedbackSubmission, questionId]);

  useEffect(() => {
    writeDraft(questionId, { rating, comment });
  }, [questionId, rating, comment]);

  useEffect(() => {
    if (!draftEdited || !onFeedbackDraftChange || !questionId || !questionHumanId) {
      return;
    }
    if (rating === undefined && !comment.trim()) {
      return;
    }
    const timeoutId = window.setTimeout(() => {
      onFeedbackDraftChange({
        quiz,
        quizFile,
        edition,
        questionId,
        questionHumanId,
        rating,
        comment,
      });
    }, 600);
    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [comment, draftEdited, edition, onFeedbackDraftChange, questionHumanId, questionId, quiz, quizFile, rating]);

  const remainingCommentCharacters = useMemo(() => COMMENT_MAX_LENGTH - comment.length, [comment.length]);

  function onRatingSelect(nextRating: number): void {
    setRating(nextRating);
    setDraftEdited(true);
    if (feedbackStatus !== "saving") {
      setFeedbackStatus("idle");
      setFeedbackMessage("");
    }
  }

  function onCommentChange(value: string): void {
    setComment(value);
    setDraftEdited(true);
    if (feedbackStatus !== "saving") {
      setFeedbackStatus("idle");
      setFeedbackMessage("");
    }
  }

  async function onSubmitFeedback(): Promise<void> {
    if (feedbackStatus === "saving") {
      return;
    }
    if (!hasFeedbackMetadata) {
      setFeedbackStatus("error");
      setFeedbackMessage("Feedback is unavailable for this quiz payload.");
      return;
    }
    if (!feedbackEnabled) {
      setFeedbackStatus("error");
      setFeedbackMessage(feedbackBlockedMessage || "Sign in to submit feedback.");
      return;
    }
    if (!rating) {
      setFeedbackStatus("error");
      setFeedbackMessage("Select a star rating before submitting.");
      return;
    }

    setFeedbackStatus("saving");
    setFeedbackMessage("");
    try {
      const feedbackRequestHeaders = await getFeedbackRequestHeaders();
      const response = await submitQuizFeedback({
        quiz_file: quizFile,
        date: quiz.date,
        quiz_type: quiz.type,
        edition,
        question_id: questionId,
        question_human_id: questionHumanId as string,
        rating,
        ...(comment.trim() ? { comment: comment.trim() } : {}),
      }, feedbackRequestHeaders);

      if (response.mode === "created") {
        setFeedbackStatus("saved");
        setFeedbackMessage("Feedback saved.");
      } else {
        setFeedbackStatus("updated");
        setFeedbackMessage("Feedback updated.");
      }
      onFeedbackDraftChange?.({
        quiz,
        quizFile,
        edition,
        questionId,
        questionHumanId: questionHumanId as string,
        rating,
        comment,
      });
      setDraftEdited(false);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setFeedbackStatus("error");
      setFeedbackMessage(`Could not submit feedback: ${message}`);
    }
  }

  const submitButtonLabel =
    feedbackStatus === "saving"
      ? "Saving..."
      : feedbackStatus === "updated"
        ? "Updated"
        : feedbackStatus === "saved"
          ? "Saved"
          : feedbackStatus === "error"
            ? "Retry submit"
            : "Submit feedback";

  return (
    <article className="quiz-card">
      <header className="quiz-header">
        <p className="quiz-type">{formatQuizType(quiz.type)}</p>
        <p className="quiz-type">Edition {edition}</p>
        {questionHumanId ? <p className="quiz-human-id">#{questionHumanId}</p> : null}
        <h2>{quiz.question}</h2>
      </header>

      <div className="choice-grid">
        {quiz.choices.map((choice) => {
          const selected = selectedChoiceId === choice.id;
          const isCorrectChoice = quiz.correct_choice_id === choice.id;
          const classes = ["choice"];

          if (selected) {
            classes.push("selected");
          }

          if (hasAnswered && isCorrectChoice) {
            classes.push("answer-correct");
          }

          if (hasAnswered && selected && !isCorrectChoice) {
            classes.push("answer-wrong");
          }

          return (
            <button
              key={choice.id}
              type="button"
              className={classes.join(" ")}
              disabled={hasAnswered}
              onClick={() => onSelectChoice(quizKey, choice.id)}
            >
              <span className="choice-id">{choice.id}</span>
              <span className="choice-body">
                {choice.human_id ? <span className="choice-human-id">#{choice.human_id}</span> : null}
                <span className="choice-label">{choice.label}</span>
              </span>
            </button>
          );
        })}
      </div>

      {hasAnswered ? (
        <p className={`result-pill ${answerTone(isCorrect)}`}>
          {isCorrect ? "Correct" : `Not quite. Correct answer: ${correctChoice?.id}`}
        </p>
      ) : (
        <p className="result-pill pending">Choose one answer to lock this quiz.</p>
      )}

      <section className="feedback-panel">
        <p className="feedback-title">Rate this quiz card</p>
        <div className="feedback-stars" role="group" aria-label="Quiz rating">
          {[1, 2, 3, 4, 5].map((star) => (
            <button
              key={star}
              type="button"
              className={`feedback-star ${rating !== undefined && star <= rating ? "active" : ""}`}
              onClick={() => onRatingSelect(star)}
              disabled={feedbackStatus === "saving" || !canSubmitFeedback}
              aria-label={`${star} star${star === 1 ? "" : "s"}`}
              aria-pressed={rating === star}
            >
              {star}
            </button>
          ))}
        </div>

        <label className="feedback-comment-label" htmlFor={`${quizKey}-feedback-comment`}>
          Optional comment
        </label>
        <textarea
          id={`${quizKey}-feedback-comment`}
          className="feedback-comment"
          value={comment}
          onChange={(event) => onCommentChange(event.target.value.slice(0, COMMENT_MAX_LENGTH))}
          placeholder="What should we improve?"
          maxLength={COMMENT_MAX_LENGTH}
          disabled={feedbackStatus === "saving" || !canSubmitFeedback}
        />
        <p className="feedback-comment-count">{remainingCommentCharacters} characters left</p>

        <div className="feedback-actions">
          <button
            type="button"
            className="feedback-submit"
            disabled={!canSubmitFeedback || !rating || feedbackStatus === "saving"}
            onClick={() => void onSubmitFeedback()}
          >
            {submitButtonLabel}
          </button>
          {feedbackMessage ? (
            <p className={`feedback-message ${feedbackStatus === "error" ? "error" : "ok"}`}>{feedbackMessage}</p>
          ) : null}
          {!hasFeedbackMetadata ? (
            <p className="feedback-message error">Feedback is unavailable for this quiz payload.</p>
          ) : null}
          {hasFeedbackMetadata && !feedbackEnabled && feedbackBlockedMessage ? (
            <p className="feedback-message error">{feedbackBlockedMessage}</p>
          ) : null}
        </div>
      </section>

      <details className="source-details">
        <summary className="source-summary">Show sources ({quiz.source.name})</summary>
        <section className="source-block">
          <ul>
            {quiz.source.events_used?.map((event) => (
              <li key={`${event.year}-${event.wikipedia_url}`}>
                <a href={event.wikipedia_url} target="_blank" rel="noreferrer">
                  {event.year}: {event.text}
                </a>
              </li>
            ))}
            {quiz.source.records_used?.map((record) => (
              <li key={record.record_id}>
                <a href={record.country_url} target="_blank" rel="noreferrer">
                  {record.capital_label}
                  {" -> "}
                  {record.country_label}
                </a>
              </li>
            ))}
          </ul>
        </section>
      </details>
    </article>
  );
}
