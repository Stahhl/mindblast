import { getApp, getApps, initializeApp, type FirebaseOptions } from "firebase/app";
import type { AppCheck } from "firebase/app-check";
import { ReCaptchaV3Provider, getToken, initializeAppCheck } from "firebase/app-check";
import {
  GoogleAuthProvider,
  getAuth,
  onAuthStateChanged,
  signInWithPopup,
  signOut as firebaseSignOut,
} from "firebase/auth";

import type { FeedbackAuthClient, FeedbackAuthSnapshot } from "./types";

export interface FirebaseFeedbackAuthClientOptions {
  firebaseConfig: FirebaseOptions;
  appCheckSiteKey: string;
  appCheckDebugToken?: string;
}

export class FirebaseFeedbackAuthClient implements FeedbackAuthClient {
  private readonly listeners = new Set<(snapshot: FeedbackAuthSnapshot) => void>();
  private snapshot: FeedbackAuthSnapshot = { status: "loading" };
  private readonly auth;
  private readonly googleProvider;
  private readonly appCheck: AppCheck;

  constructor(options: FirebaseFeedbackAuthClientOptions) {
    const app = getApps().length ? getApp() : initializeApp(options.firebaseConfig);
    this.auth = getAuth(app);
    this.googleProvider = new GoogleAuthProvider();

    if (options.appCheckDebugToken && options.appCheckDebugToken.trim()) {
      (
        globalThis as {
          FIREBASE_APPCHECK_DEBUG_TOKEN?: string | boolean;
        }
      ).FIREBASE_APPCHECK_DEBUG_TOKEN = options.appCheckDebugToken.trim();
    }

    this.appCheck = initializeAppCheck(app, {
      provider: new ReCaptchaV3Provider(options.appCheckSiteKey),
      isTokenAutoRefreshEnabled: true,
    });

    onAuthStateChanged(
      this.auth,
      (user) => {
        if (!user) {
          this.publish({
            status: "signed_out",
          });
          return;
        }
        this.publish({
          status: "authenticated",
          email: user.email || undefined,
          providerId: user.providerData[0]?.providerId || "unknown",
        });
      },
      (error) => {
        this.publish({
          status: "unavailable",
          reason: error instanceof Error ? error.message : "auth_state_error",
        });
      },
    );
  }

  getSnapshot(): FeedbackAuthSnapshot {
    return this.snapshot;
  }

  subscribe(listener: (snapshot: FeedbackAuthSnapshot) => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  async signInWithGoogle(): Promise<void> {
    await signInWithPopup(this.auth, this.googleProvider);
  }

  async signOut(): Promise<void> {
    await firebaseSignOut(this.auth);
  }

  async getFeedbackRequestHeaders(): Promise<Record<string, string>> {
    const user = this.auth.currentUser;
    if (!user) {
      throw new Error("sign_in_required");
    }

    const idToken = await user.getIdToken();
    if (!idToken.trim()) {
      throw new Error("missing_id_token");
    }

    const appCheckToken = await getToken(this.appCheck, false);
    if (!appCheckToken.token || !appCheckToken.token.trim()) {
      throw new Error("missing_app_check_token");
    }

    return {
      "X-Firebase-ID-Token": idToken,
      "X-Firebase-AppCheck": appCheckToken.token,
    };
  }

  private publish(snapshot: FeedbackAuthSnapshot): void {
    this.snapshot = snapshot;
    for (const listener of this.listeners) {
      listener(snapshot);
    }
  }
}
