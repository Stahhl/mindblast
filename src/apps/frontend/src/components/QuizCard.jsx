function answerTone(isCorrect) {
  return isCorrect ? "correct" : "wrong";
}

function formatQuizType(type) {
  if (type === "which_came_first") {
    return "Which Came First";
  }
  if (type === "history_mcq_4") {
    return "History MCQ";
  }
  return type;
}

export default function QuizCard({ quiz, selectedChoiceId, onSelectChoice }) {
  const hasAnswered = Boolean(selectedChoiceId);
  const correctChoice = quiz.choices.find((choice) => choice.id === quiz.correct_choice_id);
  const isCorrect = selectedChoiceId === quiz.correct_choice_id;

  return (
    <article className="quiz-card">
      <header className="quiz-header">
        <p className="quiz-type">{formatQuizType(quiz.type)}</p>
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
              onClick={() => onSelectChoice(quiz.type, choice.id)}
            >
              <span className="choice-id">{choice.id}</span>
              <span className="choice-label">{choice.label}</span>
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

      <details className="source-details">
        <summary className="source-summary">Show sources ({quiz.source.name})</summary>
        <section className="source-block">
          <ul>
            {quiz.source.events_used.map((event) => (
              <li key={`${event.year}-${event.wikipedia_url}`}>
                <a href={event.wikipedia_url} target="_blank" rel="noreferrer">
                  {event.year}: {event.text}
                </a>
              </li>
            ))}
          </ul>
        </section>
      </details>
    </article>
  );
}
