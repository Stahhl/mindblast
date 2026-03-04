import type { AuditLoggerPort } from "../../application/ports";

export class ConsoleAuditLogger implements AuditLoggerPort {
  reject(reason: string, context: Record<string, unknown> = {}): void {
    console.warn(
      JSON.stringify({
        event: "quiz_feedback_reject",
        reason,
        ...context,
      }),
    );
  }
}
