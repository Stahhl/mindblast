export type FeedbackAuthStatus = "loading" | "authenticated" | "signed_out" | "unavailable";

export interface FeedbackAuthSnapshot {
  status: FeedbackAuthStatus;
  email?: string;
  providerId?: string;
  reason?: string;
}

export interface FeedbackAuthClient {
  getSnapshot(): FeedbackAuthSnapshot;
  subscribe(listener: (snapshot: FeedbackAuthSnapshot) => void): () => void;
  signInWithGoogle(): Promise<void>;
  signOut(): Promise<void>;
  getFeedbackRequestHeaders(): Promise<Record<string, string>>;
}
