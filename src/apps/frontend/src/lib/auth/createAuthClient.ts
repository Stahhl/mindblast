import type { FirebaseOptions } from "firebase/app";

import { FirebaseFeedbackAuthClient } from "./firebaseAuthClient";
import { NoopFeedbackAuthClient } from "./noopAuthClient";
import type { FeedbackAuthClient } from "./types";

let singletonAuthClient: FeedbackAuthClient | null = null;

function readFirebaseConfig(): FirebaseOptions | null {
  const apiKey = import.meta.env.VITE_FIREBASE_API_KEY;
  const authDomain = import.meta.env.VITE_FIREBASE_AUTH_DOMAIN;
  const projectId = import.meta.env.VITE_FIREBASE_PROJECT_ID;
  const appId = import.meta.env.VITE_FIREBASE_APP_ID;

  if (!apiKey || !authDomain || !projectId || !appId) {
    return null;
  }

  const config: FirebaseOptions = {
    apiKey,
    authDomain,
    projectId,
    appId,
  };

  const storageBucket = import.meta.env.VITE_FIREBASE_STORAGE_BUCKET;
  if (storageBucket) {
    config.storageBucket = storageBucket;
  }

  return config;
}

export function createFeedbackAuthClient(): FeedbackAuthClient {
  if (singletonAuthClient) {
    return singletonAuthClient;
  }

  const firebaseConfig = readFirebaseConfig();
  const appCheckSiteKey = import.meta.env.VITE_FIREBASE_APPCHECK_SITE_KEY;
  const appCheckDebugToken = import.meta.env.VITE_FIREBASE_APPCHECK_DEBUG_TOKEN;

  if (!firebaseConfig || !appCheckSiteKey) {
    singletonAuthClient = new NoopFeedbackAuthClient("firebase_auth_not_configured");
    return singletonAuthClient;
  }

  try {
    singletonAuthClient = new FirebaseFeedbackAuthClient({
      firebaseConfig,
      appCheckSiteKey,
      appCheckDebugToken,
    });
  } catch (error) {
    const reason = error instanceof Error ? error.message : "firebase_auth_init_failed";
    singletonAuthClient = new NoopFeedbackAuthClient(reason);
  }
  return singletonAuthClient;
}
