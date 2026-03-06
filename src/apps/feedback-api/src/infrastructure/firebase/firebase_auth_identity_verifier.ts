import { getAuth } from "firebase-admin/auth";

import type { AuthIdentityDecision, AuthIdentityVerifierPort } from "../../application/ports";

export class FirebaseAuthIdentityVerifier implements AuthIdentityVerifierPort {
  constructor(private readonly required: boolean) {}

  async verifyIdToken(token: string | undefined): Promise<AuthIdentityDecision> {
    if (!this.required) {
      return {
        ok: true,
        identity: {
          uid: "dev-local",
          providerId: "local-debug",
        },
      };
    }

    if (!token || !token.trim()) {
      return { ok: false, reason: "missing_id_token" };
    }

    try {
      const decoded = await getAuth().verifyIdToken(token.trim());
      const providerId = decoded.firebase?.sign_in_provider || "unknown";
      return {
        ok: true,
        identity: {
          uid: decoded.uid,
          providerId,
        },
      };
    } catch {
      return { ok: false, reason: "invalid_id_token" };
    }
  }
}
