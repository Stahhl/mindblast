import { createHash } from "node:crypto";

import type { IdGeneratorPort } from "../../application/ports";

export class Sha256IdGenerator implements IdGeneratorPort {
  buildFeedbackId(input: { authUid: string; questionId: string; feedbackDateUtc: string }): string {
    const raw = `${input.authUid}|${input.questionId}|${input.feedbackDateUtc}`;
    const digest = createHash("sha256").update(raw).digest("hex");
    return `fdbk_${digest.slice(0, 32)}`;
  }
}
