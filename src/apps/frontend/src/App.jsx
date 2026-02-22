import { useEffect, useMemo, useState } from "react";

import QuizCard from "./components/QuizCard.jsx";
import { loadDailyQuizzes } from "./lib/quizApi.js";

const STATUS = {
  LOADING: "loading",
  READY: "ready",
  ERROR: "error"
};

function makeStorageKey(date) {
  return `mindblast:answers:${date}`;
}

export default function App() {
  const [status, setStatus] = useState(STATUS.LOADING);
  const [date, setDate] = useState("");
  const [quizzes, setQuizzes] = useState([]);
  const [errorsByType, setErrorsByType] = useState(new Map());
  const [fatalError, setFatalError] = useState("");
  const [answers, setAnswers] = useState({});

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
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== "object") {
        setAnswers({});
        return;
      }
      setAnswers(parsed);
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

  async function refresh() {
    setStatus(STATUS.LOADING);
    setFatalError("");

    try {
      const result = await loadDailyQuizzes();
      setDate(result.date);
      setQuizzes(result.quizzes);
      setErrorsByType(result.errorsByType);

      if (!result.quizzes.length) {
        setStatus(STATUS.ERROR);
        setFatalError("No valid quizzes were loaded for this date.");
        return;
      }

      setStatus(STATUS.READY);
    } catch (error) {
      setStatus(STATUS.ERROR);
      setFatalError(error instanceof Error ? error.message : String(error));
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  function onSelectChoice(quizType, choiceId) {
    setAnswers((previous) => {
      if (previous[quizType]) {
        return previous;
      }
      return { ...previous, [quizType]: choiceId };
    });
  }

  return (
    <main className="page-shell">
      <div className="background-orb orb-one" aria-hidden="true" />
      <div className="background-orb orb-two" aria-hidden="true" />

      <header className="top-bar">
        <div>
          <p className="eyebrow">Mindblast Daily</p>
          <h1>History Challenge</h1>
          <p className="subtitle">Load order: latest -> daily index -> quiz payloads.</p>
        </div>

        <button type="button" className="refresh-button" onClick={refresh} disabled={status === STATUS.LOADING}>
          {status === STATUS.LOADING ? "Loading..." : "Retry"}
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

      {status === STATUS.LOADING ? <p className="state-banner">Fetching quizzes...</p> : null}

      {status === STATUS.ERROR ? (
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
          <div className="quiz-wrap" key={quiz.type} style={{ "--stagger": `${idx * 80}ms` }}>
            <QuizCard quiz={quiz} selectedChoiceId={answers[quiz.type]} onSelectChoice={onSelectChoice} />
          </div>
        ))}
      </section>
    </main>
  );
}
