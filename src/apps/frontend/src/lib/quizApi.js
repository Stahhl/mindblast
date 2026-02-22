import { validateIndexPayload, validateLatestPayload, validateQuizPayload } from "./validation.js";

function toAbsolutePath(path) {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  if (path.startsWith("/")) {
    return path;
  }
  return `/${path}`;
}

async function fetchJson(path) {
  const response = await fetch(toAbsolutePath(path));
  if (!response.ok) {
    throw new Error(`Request failed (${response.status}) for ${path}`);
  }
  return response.json();
}

export async function loadDailyQuizzes() {
  const latest = validateLatestPayload(await fetchJson("/quizzes/latest.json"));
  const index = validateIndexPayload(await fetchJson(latest.index_file));

  const quizResults = await Promise.allSettled(
    Object.entries(index.quiz_files).map(async ([quizType, quizPath]) => {
      const quiz = validateQuizPayload(await fetchJson(quizPath));
      if (quiz.type !== quizType) {
        throw new Error(`Quiz type mismatch for ${quizType}`);
      }
      return [quizType, quiz];
    })
  );

  const quizzesByType = new Map();
  const errorsByType = new Map();

  quizResults.forEach((result, idx) => {
    const quizType = index.available_types[idx];
    if (result.status === "fulfilled") {
      const [type, quiz] = result.value;
      quizzesByType.set(type, quiz);
      return;
    }

    const message = result.reason instanceof Error ? result.reason.message : String(result.reason);
    errorsByType.set(quizType, message);
  });

  const quizzes = index.available_types
    .map((quizType) => quizzesByType.get(quizType))
    .filter(Boolean);

  return {
    date: index.date,
    availableTypes: index.available_types,
    quizzes,
    errorsByType
  };
}
