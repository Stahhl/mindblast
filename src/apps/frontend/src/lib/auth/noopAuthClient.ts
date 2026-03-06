import type { FeedbackAuthClient, FeedbackAuthSnapshot } from "./types";

export class NoopFeedbackAuthClient implements FeedbackAuthClient {
  private readonly snapshot: FeedbackAuthSnapshot;

  constructor(reason: string) {
    this.snapshot = {
      status: "unavailable",
      reason,
    };
  }

  getSnapshot(): FeedbackAuthSnapshot {
    return this.snapshot;
  }

  subscribe(_listener: (snapshot: FeedbackAuthSnapshot) => void): () => void {
    return () => {};
  }

  async signInWithGoogle(): Promise<void> {
    throw new Error(this.snapshot.reason || "auth_unavailable");
  }

  async signOut(): Promise<void> {
    return Promise.resolve();
  }

  async getFeedbackRequestHeaders(): Promise<Record<string, string>> {
    throw new Error(this.snapshot.reason || "auth_unavailable");
  }
}
