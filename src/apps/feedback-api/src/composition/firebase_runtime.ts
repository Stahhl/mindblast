import { getApps, initializeApp } from "firebase-admin/app";
import { getFirestore } from "firebase-admin/firestore";

import type {
  AuditLoggerPort,
  AuthIdentityVerifierPort,
  RateLimiterPort,
  RequestAttestationVerifierPort,
} from "../application/ports";
import { loadFeedbackRuntimeConfig, type FeedbackRuntimeConfig } from "../application/runtime_config";
import type { SubmitFeedbackUseCaseDependencies } from "../application/submit_feedback_use_case";
import type { UserStateUseCaseDependencies } from "../application/user_state_use_case";
import { FirestoreFeedbackRepository } from "../infrastructure/firebase/firestore_feedback_repository";
import { FirestoreRateLimiter } from "../infrastructure/firebase/firestore_rate_limiter";
import { FirestoreUserStateRepository } from "../infrastructure/firebase/firestore_user_state_repository";
import { FirebaseAppCheckVerifier } from "../infrastructure/firebase/firebase_app_check_verifier";
import { FirebaseAuthIdentityVerifier } from "../infrastructure/firebase/firebase_auth_identity_verifier";
import { SystemClock } from "../infrastructure/system/clock";
import { ConsoleAuditLogger } from "../infrastructure/system/console_audit_logger";
import { Sha256IdGenerator } from "../infrastructure/system/id_generator";

export interface QuizFeedbackRuntimeDependencies {
  useCase: SubmitFeedbackUseCaseDependencies;
  userStateUseCase: UserStateUseCaseDependencies;
  rateLimiter: RateLimiterPort;
  authVerifier: AuthIdentityVerifierPort;
  appCheckVerifier: RequestAttestationVerifierPort;
  auditLogger: AuditLoggerPort;
  runtimeConfig: FeedbackRuntimeConfig;
}

export function buildRuntimeDependencies(): QuizFeedbackRuntimeDependencies {
  if (getApps().length === 0) {
    initializeApp();
  }
  const runtimeConfig = loadFeedbackRuntimeConfig();
  const firestore = getFirestore();
  const clock = new SystemClock();
  const userStateRepository = new FirestoreUserStateRepository(firestore);

  return {
    useCase: {
      repository: new FirestoreFeedbackRepository(firestore),
      clock,
      idGenerator: new Sha256IdGenerator(),
      featureFlags: {
        commentsEnabled: runtimeConfig.featureFlags.commentsEnabled,
      },
    },
    userStateUseCase: {
      repository: userStateRepository,
      clock,
      featureFlags: {
        commentsEnabled: runtimeConfig.featureFlags.commentsEnabled,
      },
    },
    rateLimiter: new FirestoreRateLimiter(firestore),
    authVerifier: new FirebaseAuthIdentityVerifier(runtimeConfig.security.requireAuth),
    appCheckVerifier: new FirebaseAppCheckVerifier(runtimeConfig.security.requireAppCheck),
    auditLogger: new ConsoleAuditLogger(),
    runtimeConfig,
  };
}
