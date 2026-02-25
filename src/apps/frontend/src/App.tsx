import { useEffect, useMemo, useState } from "react";

import QuizCard from "./components/QuizCard";
import { loadDailyQuizzes } from "./lib/quizApi";
import type { QuizPayload, QuizType } from "./lib/types";

type Status = "loading" | "ready" | "error";
type AnswerMap = Partial<Record<QuizType, string>>;
type AppEnvironment = "staging" | "production" | "local" | "unknown";

function makeStorageKey(date: string): string {
  return `mindblast:answers:${date}`;
}

function shiftIsoDate(date: string, days: number): string {
  const parsed = new Date(`${date}T00:00:00Z`);
  parsed.setUTCDate(parsed.getUTCDate() + days);
  return parsed.toISOString().slice(0, 10);
}

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  const tagName = target.tagName.toLowerCase();
  return tagName === "input" || tagName === "textarea" || tagName === "select" || target.isContentEditable;
}

function detectEnvironment(): AppEnvironment {
  const raw = String(import.meta.env.VITE_APP_ENV ?? "")
    .trim()
    .toLowerCase();

  if (!raw) {
    return "local";
  }

  if (raw === "prod" || raw === "production") {
    return "production";
  }

  if (raw === "staging" || raw === "stage") {
    return "staging";
  }

  return "unknown";
}

function environmentLabel(environment: AppEnvironment): string {
  if (environment === "production") {
    return "Production";
  }
  if (environment === "staging") {
    return "Staging";
  }
  if (environment === "local") {
    return "Local";
  }
  return "Unknown";
}

export default function App() {
  const [status, setStatus] = useState<Status>("loading");
  const [date, setDate] = useState<string>("");
  const [latestDate, setLatestDate] = useState<string>("");
  const [dateInput, setDateInput] = useState<string>("");
  const [quizzes, setQuizzes] = useState<QuizPayload[]>([]);
  const [errorsByType, setErrorsByType] = useState<Map<string, string>>(new Map());
  const [fatalError, setFatalError] = useState<string>("");
  const [answers, setAnswers] = useState<AnswerMap>({});
  const appEnvironment = useMemo(() => detectEnvironment(), []);
  const envLabel = useMemo(() => environmentLabel(appEnvironment), [appEnvironment]);
  const envClass = `env-${appEnvironment}`;

  const score = useMemo(() => {
    if (!quizzes.length) {
      return { correct: 0, total: 0 };
    }

    let correct = 0;
    quizzes.forEach((quiz) => {
      if (answers[quiz.type] === quiz.correct_choice_id) {
        correct += 1;
      }
    });

    return { correct, total: quizzes.length };
  }, [answers, quizzes]);

  useEffect(() => {
    if (!date) {
      return;
    }

    const raw = localStorage.getItem(makeStorageKey(date));
    if (!raw) {
      setAnswers({});
      return;
    }

    try {
      const parsed = JSON.parse(raw) as unknown;
      if (!parsed || typeof parsed !== "object") {
        setAnswers({});
        return;
      }

      const answerEntries = Object.entries(parsed as Record<string, unknown>).filter(
        ([quizType, choiceId]) =>
          (quizType === "which_came_first" || quizType === "history_mcq_4") && typeof choiceId === "string"
      ) as Array<[QuizType, string]>;

      setAnswers(Object.fromEntries(answerEntries) as AnswerMap);
    } catch {
      setAnswers({});
    }
  }, [date]);

  useEffect(() => {
    if (!date) {
      return;
    }
    localStorage.setItem(makeStorageKey(date), JSON.stringify(answers));
  }, [answers, date]);

  async function refresh(targetDate?: string): Promise<void> {
    setStatus("loading");
    setFatalError("");

    try {
      const result = await loadDailyQuizzes(targetDate);
      setDate(result.date);
      setLatestDate(result.latestDate);
      setDateInput(result.date);
      setQuizzes(result.quizzes);
      setErrorsByType(result.errorsByType);

      if (!result.quizzes.length) {
        setStatus("error");
        setFatalError("No valid quizzes were loaded for this date.");
        return;
      }

      setStatus("ready");
    } catch (error) {
      setStatus("error");
      setQuizzes([]);
      setErrorsByType(new Map());
      if (targetDate) {
        setDate(targetDate);
      }
      const rawMessage = error instanceof Error ? error.message : String(error);
      if (targetDate && rawMessage.includes("Request failed (404)")) {
        setFatalError(`No published quiz index exists for ${targetDate}.`);
      } else {
        setFatalError(rawMessage);
      }
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent): void {
      if (event.defaultPrevented || event.repeat) {
        return;
      }
      if (event.key.toLowerCase() !== "t") {
        return;
      }
      if (event.metaKey || event.ctrlKey || event.altKey) {
        return;
      }
      if (isTypingTarget(event.target)) {
        return;
      }
      event.preventDefault();
      void refresh();
    }

    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
    };
  }, []);

  function onSelectChoice(quizType: QuizType, choiceId: string): void {
    setAnswers((previous) => {
      if (previous[quizType]) {
        return previous;
      }
      return { ...previous, [quizType]: choiceId };
    });
  }

  function onLoadDate(): void {
    if (!dateInput) {
      return;
    }
    void refresh(dateInput);
  }

  function onShiftDate(days: number): void {
    if (!date) {
      return;
    }
    const nextDate = shiftIsoDate(date, days);
    setDateInput(nextDate);
    void refresh(nextDate);
  }

  const inArchiveMode = Boolean(date && latestDate && date !== latestDate);
  const disableNextDay = status === "loading" || !date || (Boolean(latestDate) && date >= latestDate);
  const disableLatest = status === "loading" || !latestDate || date === latestDate;
  const missingArchiveDate = fatalError.match(/^No published quiz index exists for (\d{4}-\d{2}-\d{2})\.$/)?.[1] ?? "";

  return (
    <main className={`page-shell ${envClass}`}>
      <div className="background-orb orb-one" aria-hidden="true" />
      <div className="background-orb orb-two" aria-hidden="true" />

      <header className="top-bar">
        <div>
          <p className="eyebrow">Mindblast Daily</p>
          <p className={`environment-pill ${envClass}`}>Environment: {envLabel}</p>
          <h1>History Challenge</h1>
          <p className="subtitle">Load order: latest -&gt; daily index -&gt; quiz payloads.</p>

          <div className="date-controls">
            <label htmlFor="quiz-date">Browse date</label>
            <div className="date-input-row">
              <input
                id="quiz-date"
                type="date"
                value={dateInput}
                onChange={(event) => setDateInput(event.target.value)}
                max={latestDate || undefined}
              />
              <button
                type="button"
                className="refresh-button secondary"
                onClick={onLoadDate}
                disabled={status === "loading" || !dateInput}
              >
                Load date
              </button>
            </div>
            <div className="history-nav">
              <button
                type="button"
                className="refresh-button secondary"
                onClick={() => onShiftDate(-1)}
                disabled={status === "loading" || !date}
              >
                Previous day
              </button>
              <button
                type="button"
                className="refresh-button secondary"
                onClick={() => onShiftDate(1)}
                disabled={disableNextDay}
              >
                Next day
              </button>
              <button type="button" className="refresh-button secondary" onClick={() => void refresh()} disabled={disableLatest}>
                Latest
              </button>
            </div>
            <p className="shortcut-hint">Shortcut: press T to jump to latest.</p>
          </div>
        </div>

        <button type="button" className="refresh-button" onClick={() => void refresh(date)} disabled={status === "loading"}>
          {status === "loading" ? "Loading..." : "Retry"}
        </button>
      </header>

      {date ? (
        <section className="scoreboard">
          <p>
            Date: <strong>{date}</strong>
          </p>
          <p>
            Mode: <strong>{inArchiveMode ? "Archive" : "Latest"}</strong>
          </p>
          <p>
            Score: <strong>{score.correct}</strong> / {score.total}
          </p>
        </section>
      ) : null}

      {status === "loading" ? <p className="state-banner">Fetching quizzes...</p> : null}

      {status === "error" ? (
        <section className="state-banner error">
          <p>Could not load quizzes.</p>
          {fatalError ? <p className="error-detail">{fatalError}</p> : null}
        </section>
      ) : null}

      {status === "error" && missingArchiveDate ? (
        <section className="archive-empty-state">
          <h2>No quiz published for {missingArchiveDate}</h2>
          <p>Try another date or jump back to the latest available quiz day.</p>
          <div className="archive-empty-actions">
            <button
              type="button"
              className="refresh-button secondary"
              onClick={() => {
                const previousDate = shiftIsoDate(missingArchiveDate, -1);
                setDateInput(previousDate);
                void refresh(previousDate);
              }}
            >
              Try previous day
            </button>
            <button type="button" className="refresh-button secondary" onClick={() => void refresh()}>
              Go to latest
            </button>
          </div>
        </section>
      ) : null}

      {errorsByType.size > 0 ? (
        <section className="state-banner warning">
          <p>Some quiz types failed to load:</p>
          <ul>
            {Array.from(errorsByType.entries()).map(([quizType, message]) => (
              <li key={quizType}>
                <strong>{quizType}</strong>: {message}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="quiz-grid">
        {quizzes.map((quiz, idx) => (
          <div
            className="quiz-wrap"
            key={quiz.type}
            style={{ "--stagger": `${idx * 80}ms` } as Record<string, string>}
          >
            <QuizCard quiz={quiz} selectedChoiceId={answers[quiz.type]} onSelectChoice={onSelectChoice} />
          </div>
        ))}
      </section>
    </main>
  );
}
