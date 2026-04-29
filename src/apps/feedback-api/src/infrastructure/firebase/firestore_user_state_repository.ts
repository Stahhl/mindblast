import type { Firestore } from "firebase-admin/firestore";

import type { UserStateRepositoryPort } from "../../application/ports";
import type {
  UserFeedbackDraftRecord,
  UserFeedbackSubmissionState,
  UserQuizAnswerRecord,
} from "../../domain/user_state";
import type { FeedbackRecord } from "../../domain/feedback";

export class FirestoreUserStateRepository implements UserStateRepositoryPort {
  constructor(private readonly firestore: Firestore) {}

  async listQuizAnswers(input: { authUid: string; date: string }): Promise<UserQuizAnswerRecord[]> {
    const snapshot = await this.firestore
      .collection("user_quiz_state")
      .doc(input.authUid)
      .collection("dates")
      .doc(input.date)
      .collection("items")
      .get();

    return snapshot.docs.map((doc) => doc.data() as UserQuizAnswerRecord);
  }

  async upsertQuizAnswer(record: UserQuizAnswerRecord): Promise<void> {
    const docRef = this.firestore
      .collection("user_quiz_state")
      .doc(record.auth_uid)
      .collection("dates")
      .doc(record.date)
      .collection("items")
      .doc(record.question_id);

    await this.firestore.runTransaction(async (transaction) => {
      const existing = await transaction.get(docRef);
      const existingData = existing.exists ? (existing.data() as Partial<UserQuizAnswerRecord>) : {};
      transaction.set(
        docRef,
        {
          ...record,
          answered_at:
            typeof existingData.answered_at === "string" ? existingData.answered_at : record.answered_at,
        },
        { merge: false },
      );
    });
  }

  async listFeedbackDrafts(input: { authUid: string; questionIds: string[] }): Promise<UserFeedbackDraftRecord[]> {
    if (!input.questionIds.length) {
      return [];
    }

    const refs = input.questionIds.map((questionId) =>
      this.firestore
        .collection("user_feedback_drafts")
        .doc(input.authUid)
        .collection("questions")
        .doc(questionId),
    );
    const snapshots = await this.firestore.getAll(...refs);
    return snapshots
      .filter((snapshot) => snapshot.exists)
      .map((snapshot) => snapshot.data() as UserFeedbackDraftRecord);
  }

  async upsertFeedbackDraft(record: UserFeedbackDraftRecord): Promise<void> {
    await this.firestore
      .collection("user_feedback_drafts")
      .doc(record.auth_uid)
      .collection("questions")
      .doc(record.question_id)
      .set(record, { merge: false });
  }

  async listFeedbackSubmissions(input: { authUid: string; questionIds: string[] }): Promise<UserFeedbackSubmissionState[]> {
    if (!input.questionIds.length) {
      return [];
    }

    const chunks: string[][] = [];
    for (let index = 0; index < input.questionIds.length; index += 10) {
      chunks.push(input.questionIds.slice(index, index + 10));
    }

    const records: UserFeedbackSubmissionState[] = [];
    for (const chunk of chunks) {
      const snapshot = await this.firestore
        .collection("quiz_feedback")
        .where("auth_uid", "==", input.authUid)
        .where("question_id", "in", chunk)
        .get();

      snapshot.docs.forEach((doc) => {
        const record = doc.data() as FeedbackRecord;
        records.push({
          question_id: record.question_id,
          feedback_id: record.feedback_id,
          rating: record.rating,
          ...(record.comment ? { comment: record.comment } : {}),
          submitted_at: record.created_at,
          updated_at: record.updated_at,
        });
      });
    }

    const latestByQuestion = new Map<string, UserFeedbackSubmissionState>();
    records.forEach((record) => {
      const existing = latestByQuestion.get(record.question_id);
      if (!existing || record.updated_at > existing.updated_at) {
        latestByQuestion.set(record.question_id, record);
      }
    });
    return Array.from(latestByQuestion.values());
  }
}
