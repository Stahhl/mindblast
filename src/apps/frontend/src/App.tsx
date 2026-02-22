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

  async function refresh(): Promise<void> {
    setStatus("loading");
    setFatalError("");

    try {
      const result = await loadDailyQuizzes();
      setDate(result.date);
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
      setFatalError(error instanceof Error ? error.message : String(error));
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  function onSelectChoice(quizType: QuizType, choiceId: string): void {
    setAnswers((previous) => {
      if (previous[quizType]) {
        return previous;
      }
      return { ...previous, [quizType]: choiceId };
    });
  }

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
        </div>

        <button type="button" className="refresh-button" onClick={refresh} disabled={status === "loading"}>
          {status === "loading" ? "Loading..." : "Retry"}
        </button>
      </header>

      {date ? (
        <section className="scoreboard">
          <p>
            Date: <strong>{date}</strong>
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
