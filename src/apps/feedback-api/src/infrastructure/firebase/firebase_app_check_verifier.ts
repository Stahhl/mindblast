import { getAppCheck } from "firebase-admin/app-check";

import type { RequestAttestationDecision, RequestAttestationVerifierPort } from "../../application/ports";

export class FirebaseAppCheckVerifier implements RequestAttestationVerifierPort {
  constructor(private readonly required: boolean) {}

  async verifyToken(token: string | undefined): Promise<RequestAttestationDecision> {
    if (!this.required) {
      return { ok: true };
    }

    if (!token || !token.trim()) {
      return { ok: false, reason: "missing_app_check_token" };
    }

    try {
      await getAppCheck().verifyToken(token.trim());
      return { ok: true };
    } catch {
      return { ok: false, reason: "invalid_app_check_token" };
    }
  }
}
