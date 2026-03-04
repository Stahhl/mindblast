import { getApps, initializeApp } from "firebase-admin/app";
import { getFirestore } from "firebase-admin/firestore";

import type { SubmitFeedbackUseCaseDependencies } from "../application/submit_feedback_use_case";
import { FirestoreFeedbackRepository } from "../infrastructure/firebase/firestore_feedback_repository";
import { SystemClock } from "../infrastructure/system/clock";
import { Sha256IdGenerator } from "../infrastructure/system/id_generator";

export function buildRuntimeDependencies(): SubmitFeedbackUseCaseDependencies {
  if (getApps().length === 0) {
    initializeApp();
  }

  return {
    repository: new FirestoreFeedbackRepository(getFirestore()),
    clock: new SystemClock(),
    idGenerator: new Sha256IdGenerator(),
  };
}
