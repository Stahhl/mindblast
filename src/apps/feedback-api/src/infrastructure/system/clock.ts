import type { ClockPort } from "../../application/ports";

export class SystemClock implements ClockPort {
  nowIsoUtc(): string {
    return new Date().toISOString();
  }

  todayUtc(): string {
    return this.nowIsoUtc().slice(0, 10);
  }
}
