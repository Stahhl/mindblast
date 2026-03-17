"""Read-only Firestore feedback access for weekly review jobs."""

from __future__ import annotations

from typing import Any

from .types import FeedbackSubmission, WeeklyWindow


def _required_string(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _required_int(payload: dict[str, Any], field: str) -> int:
    value = payload.get(field)
    if not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return value


def parse_feedback_submission(doc_id: str, payload: dict[str, Any]) -> FeedbackSubmission:
    return FeedbackSubmission(
        feedback_id=_required_string(payload, "feedback_id") if isinstance(payload.get("feedback_id"), str) else doc_id,
        quiz_file=_required_string(payload, "quiz_file"),
        date=_required_string(payload, "date"),
        quiz_type=_required_string(payload, "quiz_type"),
        edition=_required_int(payload, "edition"),
        question_id=_required_string(payload, "question_id"),
        question_human_id=_required_string(payload, "question_human_id"),
        rating=_required_int(payload, "rating"),
        feedback_date_utc=_required_string(payload, "feedback_date_utc"),
        created_at=_required_string(payload, "created_at"),
        updated_at=_required_string(payload, "updated_at"),
        comment=payload.get("comment").strip() if isinstance(payload.get("comment"), str) and payload.get("comment").strip() else None,
    )


class FirestoreFeedbackReader:
    def __init__(
        self,
        *,
        client: Any | None = None,
        field_filter_factory: Any | None = None,
        project_id: str | None = None,
        credentials_path: str | None = None,
        collection_name: str = "quiz_feedback",
    ) -> None:
        self._client = client
        self._field_filter_factory = field_filter_factory
        self._project_id = project_id
        self._credentials_path = credentials_path
        self._collection_name = collection_name

    def _build_client(self) -> Any:
        if self._client is not None:
            return self._client

        try:
            from google.cloud import firestore  # type: ignore[import-not-found]
            from google.cloud.firestore_v1.base_query import FieldFilter  # noqa: F401  # type: ignore[import-not-found]
            from google.oauth2 import service_account  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - exercised after dependency is added
            raise RuntimeError("google-cloud-firestore dependencies are required for Firestore feedback reads.") from exc

        credentials = None
        if self._credentials_path:
            credentials = service_account.Credentials.from_service_account_file(self._credentials_path)
        self._client = firestore.Client(project=self._project_id, credentials=credentials)
        return self._client

    def list_feedback_for_window(self, window: WeeklyWindow) -> list[FeedbackSubmission]:
        client = self._build_client()
        field_filter = self._field_filter_factory
        if field_filter is None:
            try:
                from google.cloud.firestore_v1.base_query import FieldFilter as field_filter  # type: ignore[import-not-found]
            except ImportError as exc:  # pragma: no cover - exercised after dependency is added
                raise RuntimeError("google-cloud-firestore dependencies are required for Firestore feedback reads.") from exc

        query = (
            client.collection(self._collection_name)
            .where(filter=field_filter("feedback_date_utc", ">=", window.start_date_iso))
            .where(filter=field_filter("feedback_date_utc", "<=", window.end_date_iso))
        )
        submissions: list[FeedbackSubmission] = []
        for document in query.stream():
            payload = document.to_dict()
            if not isinstance(payload, dict):
                raise ValueError(f"Feedback document {document.id} payload must be an object.")
            submissions.append(parse_feedback_submission(document.id, payload))
        submissions.sort(key=lambda item: (item.feedback_date_utc, item.updated_at, item.feedback_id))
        return submissions
