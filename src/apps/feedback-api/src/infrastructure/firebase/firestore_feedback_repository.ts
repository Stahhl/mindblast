import type { Firestore } from "firebase-admin/firestore";

import type { FeedbackRepositoryPort } from "../../application/ports";
import type { FeedbackRecord, SubmitFeedbackMode } from "../../domain/feedback";

export class FirestoreFeedbackRepository implements FeedbackRepositoryPort {
  constructor(
    private readonly firestore: Firestore,
    private readonly collectionName: string = "quiz_feedback",
  ) {}

  async upsertById(feedbackId: string, record: FeedbackRecord): Promise<{ mode: SubmitFeedbackMode }> {
    const docRef = this.firestore.collection(this.collectionName).doc(feedbackId);

    let mode: SubmitFeedbackMode = "created";
    await this.firestore.runTransaction(async (transaction) => {
      const existing = await transaction.get(docRef);
      if (!existing.exists) {
        transaction.set(docRef, record, { merge: false });
        mode = "created";
        return;
      }

      const existingData = existing.data() as Partial<FeedbackRecord>;
      transaction.set(
        docRef,
        {
          ...record,
          created_at:
            typeof existingData.created_at === "string" ? existingData.created_at : record.created_at,
        },
        { merge: false },
      );
      mode = "updated";
    });

    return { mode };
  }
}
