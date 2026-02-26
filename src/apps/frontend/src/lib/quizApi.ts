import { validateIndexPayload, validateLatestPayload, validateQuizPayload } from "./validation";
import type { DailyQuizLoadResult, LoadedQuiz, QuizType } from "./types";

function toAbsolutePath(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  if (path.startsWith("/")) {
    return path;
  }
  return `/${path}`;
}

async function fetchJson(path: string): Promise<unknown> {
  const response = await fetch(toAbsolutePath(path));
  if (!response.ok) {
    throw new Error(`Request failed (${response.status}) for ${path}`);
  }
  return response.json();
}

async function loadQuizzesFromIndex(indexPath: string): Promise<{
  date: string;
  availableTypes: QuizType[];
  quizzes: LoadedQuiz[];
  errorsByType: Map<string, string>;
}> {
  const index = validateIndexPayload(await fetchJson(indexPath));

  const targets: Array<{
    quizType: QuizType;
    quizPath: string;
    edition: number;
  }> = [];
  if (index.quizzes_by_type) {
    index.available_types.forEach((quizType) => {
      const editions = index.quizzes_by_type?.[quizType];
      if (!editions) {
        return;
      }
      editions.forEach((entry) => {
        targets.push({
          quizType,
          quizPath: entry.quiz_file,
          edition: entry.edition
        });
      });
    });
  } else {
    Object.entries(index.quiz_files).forEach(([quizType, quizPath]) => {
      targets.push({
        quizType: quizType as QuizType,
        quizPath,
        edition: 1
      });
    });
  }

  const quizResults = await Promise.allSettled(
    targets.map(async (target) => {
      const quiz = validateQuizPayload(await fetchJson(target.quizPath));
      if (quiz.type !== target.quizType) {
        throw new Error(`Quiz type mismatch for ${target.quizType}`);
      }
      const quizEdition = quiz.generation?.edition ?? target.edition;
      const quizKey = `${target.quizType}:${quizEdition}:${target.quizPath}`;
      return {
        key: quizKey,
        type: target.quizType,
        edition: quizEdition,
        sourcePath: target.quizPath,
        payload: quiz
      } satisfies LoadedQuiz;
    })
  );

  const quizzes: LoadedQuiz[] = [];
  const errorsByType = new Map<string, string>();

  quizResults.forEach((result, idx) => {
    const target = targets[idx];
    const errorKey = `${target.quizType} (edition ${target.edition})`;
    if (result.status === "fulfilled") {
      quizzes.push(result.value);
      return;
    }

    const message = result.reason instanceof Error ? result.reason.message : String(result.reason);
    errorsByType.set(errorKey, message);
  });

  quizzes.sort((a, b) => {
    const typeOrder = index.available_types.indexOf(a.type) - index.available_types.indexOf(b.type);
    if (typeOrder !== 0) {
      return typeOrder;
    }
    return a.edition - b.edition;
  });

  return {
    date: index.date,
    availableTypes: index.available_types,
    quizzes,
    errorsByType
  };
}

export async function loadDailyQuizzes(date?: string): Promise<DailyQuizLoadResult> {
  const latest = validateLatestPayload(await fetchJson("/quizzes/latest.json"));
  const indexPath = date ? `/quizzes/index/${date}.json` : latest.index_file;
  const result = await loadQuizzesFromIndex(indexPath);

  return {
    ...result,
    latestDate: latest.date
  };
}
