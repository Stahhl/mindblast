import { createHash } from "node:crypto";

import type { Firestore } from "firebase-admin/firestore";

import type { RateLimitCheck, RateLimitDecision, RateLimiterPort } from "../../application/ports";

function buildDocumentId(check: RateLimitCheck, windowStartSec: number): string {
  const raw = `${check.key}|${check.windowSeconds}|${windowStartSec}`;
  const digest = createHash("sha256").update(raw).digest("hex");
  return `rl_${digest.slice(0, 40)}`;
}

export class FirestoreRateLimiter implements RateLimiterPort {
  constructor(
    private readonly firestore: Firestore,
    private readonly collectionName: string = "quiz_feedback_rate_limits",
  ) {}

  async checkAndConsume(checks: RateLimitCheck[]): Promise<RateLimitDecision> {
    if (!checks.length) {
      return { allowed: true };
    }

    const nowSec = Math.floor(Date.now() / 1000);

    return this.firestore.runTransaction(async (transaction) => {
      const slots = checks.map((check) => {
        const windowStartSec = Math.floor(nowSec / check.windowSeconds) * check.windowSeconds;
        const docId = buildDocumentId(check, windowStartSec);
        const docRef = this.firestore.collection(this.collectionName).doc(docId);
        return {
          check,
          windowStartSec,
          docRef,
        };
      });

      const snapshots = await Promise.all(slots.map((slot) => transaction.get(slot.docRef)));

      for (let idx = 0; idx < slots.length; idx += 1) {
        const slot = slots[idx];
        const snapshot = snapshots[idx];
        const count = Number(snapshot.get("count") || 0);
        if (count >= slot.check.limit) {
          const elapsedInWindow = nowSec - slot.windowStartSec;
          const retryAfterSeconds = Math.max(1, slot.check.windowSeconds - elapsedInWindow);
          return {
            allowed: false,
            reason: slot.check.label,
            retryAfterSeconds,
          };
        }
      }

      for (let idx = 0; idx < slots.length; idx += 1) {
        const slot = slots[idx];
        const snapshot = snapshots[idx];
        const count = Number(snapshot.get("count") || 0);
        const nowIso = new Date(nowSec * 1000).toISOString();
        const expiresAtIso = new Date((slot.windowStartSec + slot.check.windowSeconds * 2) * 1000).toISOString();
        transaction.set(
          slot.docRef,
          {
            key: slot.check.key,
            label: slot.check.label,
            window_start_sec: slot.windowStartSec,
            window_seconds: slot.check.windowSeconds,
            count: count + 1,
            updated_at: nowIso,
            expires_at: expiresAtIso,
          },
          { merge: false },
        );
      }

      return { allowed: true };
    });
  }
}
