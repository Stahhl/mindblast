import { createHash } from "node:crypto";

import type { IdGeneratorPort } from "../../application/ports";

export class Sha256IdGenerator implements IdGeneratorPort {
  buildFeedbackId(input: { clientId: string; questionId: string; feedbackDateUtc: string }): string {
    const raw = `${input.clientId}|${input.questionId}|${input.feedbackDateUtc}`;
    const digest = createHash("sha256").update(raw).digest("hex");
    return `fdbk_${digest.slice(0, 32)}`;
  }
}
