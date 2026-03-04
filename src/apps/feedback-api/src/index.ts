import { onRequest } from "firebase-functions/v2/https";

import { buildRuntimeDependencies } from "./composition/firebase_runtime";
import { createQuizFeedbackHttpHandler } from "./infrastructure/http/quiz_feedback_http_handler";

const dependencies = buildRuntimeDependencies();

export const quizFeedbackApi = onRequest({ cors: false }, createQuizFeedbackHttpHandler(dependencies));
