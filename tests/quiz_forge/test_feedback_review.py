from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pytest

from feedback_review.aggregation import aggregate_feedback_submissions
from feedback_review.cli import main as weekly_feedback_review_main
from feedback_review.firestore_reader import FirestoreFeedbackReader, parse_feedback_submission
from feedback_review.quiz_context import load_quiz_card_context
from feedback_review.rendering import build_weekly_report_payload, render_weekly_report_markdown
from feedback_review.sanitize import sanitize_comment_text
from feedback_review.summarization import summarize_weekly_feedback
from feedback_review.types import FeedbackSubmission
from feedback_review.window import build_previous_completed_days_window


def _write_quiz_payload(content_root: Path, quiz_file: str) -> None:
    payload_path = content_root / quiz_file
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    payload_path.write_text(
        """
{
  "date": "2026-03-10",
  "type": "history_mcq_4",
  "question": "Who did the thing?",
  "questions": [
    {
      "id": "question-1",
      "human_id": "Q77",
      "prompt": "Who did the thing?",
      "answer_fact_ids": ["a1", "a2", "a3", "a4"]
    }
  ],
  "choices": [
    {"id": "A", "label": "Ada"},
    {"id": "B", "label": "Grace"},
    {"id": "C", "label": "Linus"},
    {"id": "D", "label": "Margaret"}
  ],
  "generation": {
    "edition": 2
  },
  "answer_facts": [
    {"id": "a1", "label": "Ada"},
    {"id": "a2", "label": "Grace"},
    {"id": "a3", "label": "Linus"},
    {"id": "a4", "label": "Margaret"}
  ]
}
        """.strip()
        + "\n",
        encoding="utf-8",
    )


def test_build_previous_completed_days_window_uses_prior_seven_days() -> None:
    window = build_previous_completed_days_window(dt.date(2026, 3, 16))
    assert window.start_date == dt.date(2026, 3, 9)
    assert window.end_date == dt.date(2026, 3, 15)


def test_sanitize_comment_text_redacts_common_sensitive_patterns() -> None:
    comment = "Email me at person@example.com or visit https://example.com case 123456789."
    assert sanitize_comment_text(comment) == "Email me at [redacted-email] or visit [redacted-url] case [redacted-number]."


def test_load_quiz_card_context_reads_prompt_and_choices(tmp_path: Path) -> None:
    _write_quiz_payload(tmp_path, "quizzes/test-quiz.json")
    context = load_quiz_card_context(
        content_repo_root=tmp_path,
        quiz_file="quizzes/test-quiz.json",
        question_id="question-1",
        question_human_id="Q77",
    )
    assert context.question_prompt == "Who did the thing?"
    assert context.choice_labels == ("Ada", "Grace", "Linus", "Margaret")
    assert context.edition == 2
    assert context.issue_tags == ()


def test_aggregate_feedback_submissions_builds_sorted_question_summaries(tmp_path: Path) -> None:
    _write_quiz_payload(tmp_path, "quizzes/q1.json")
    _write_quiz_payload(tmp_path, "quizzes/q2.json")

    submissions = [
        FeedbackSubmission(
            feedback_id="f1",
            quiz_file="quizzes/q1.json",
            date="2026-03-10",
            quiz_type="history_mcq_4",
            edition=2,
            question_id="question-1",
            question_human_id="Q77",
            rating=2,
            comment="Bad distractor. contact me test@example.com",
            feedback_date_utc="2026-03-11",
            created_at="2026-03-11T08:00:00Z",
            updated_at="2026-03-11T08:00:00Z",
        ),
        FeedbackSubmission(
            feedback_id="f2",
            quiz_file="quizzes/q1.json",
            date="2026-03-10",
            quiz_type="history_mcq_4",
            edition=2,
            question_id="question-1",
            question_human_id="Q77",
            rating=3,
            comment="Too easy",
            feedback_date_utc="2026-03-12",
            created_at="2026-03-12T08:00:00Z",
            updated_at="2026-03-12T08:00:00Z",
        ),
        FeedbackSubmission(
            feedback_id="f3",
            quiz_file="quizzes/q2.json",
            date="2026-03-10",
            quiz_type="history_mcq_4",
            edition=2,
            question_id="question-1",
            question_human_id="Q77",
            rating=5,
            comment="Great question",
            feedback_date_utc="2026-03-12",
            created_at="2026-03-12T09:00:00Z",
            updated_at="2026-03-12T09:00:00Z",
        ),
    ]

    aggregate = aggregate_feedback_submissions(
        submissions=submissions,
        content_repo_root=tmp_path.as_posix(),
        window=build_previous_completed_days_window(dt.date(2026, 3, 16)),
    )

    assert aggregate.total_submissions == 3
    assert aggregate.commented_submissions == 3
    assert aggregate.ratings_histogram == {1: 0, 2: 1, 3: 1, 4: 0, 5: 1}
    assert len(aggregate.question_summaries) == 2
    assert aggregate.question_summaries[0].quiz_file == "quizzes/q1.json"
    assert aggregate.question_summaries[0].average_rating == 2.5
    assert aggregate.question_summaries[0].sanitized_excerpts == (
        "Bad distractor. contact me [redacted-email]",
        "Too easy",
    )
    assert aggregate.issue_counts == {}


class _FakeDocument:
    def __init__(self, doc_id: str, payload: dict[str, object]) -> None:
        self.id = doc_id
        self._payload = payload

    def to_dict(self) -> dict[str, object]:
        return dict(self._payload)


class _FakeQuery:
    def __init__(self, documents: list[_FakeDocument]) -> None:
        self.documents = documents
        self.filters: list[object] = []

    def where(self, *, filter: object) -> "_FakeQuery":
        self.filters.append(filter)
        return self

    def stream(self) -> list[_FakeDocument]:
        return self.documents


class _FakeClient:
    def __init__(self, query: _FakeQuery) -> None:
        self.query = query
        self.collection_name: str | None = None

    def collection(self, name: str) -> _FakeQuery:
        self.collection_name = name
        return self.query


def test_parse_feedback_submission_requires_expected_fields() -> None:
    submission = parse_feedback_submission(
        "doc-1",
        {
            "quiz_file": "quizzes/example.json",
            "date": "2026-03-10",
            "quiz_type": "history_mcq_4",
            "edition": 1,
            "question_id": "question-1",
            "question_human_id": "Q1",
            "rating": 4,
            "feedback_date_utc": "2026-03-12",
            "created_at": "2026-03-12T10:00:00Z",
            "updated_at": "2026-03-12T10:00:00Z",
            "comment": "Nice",
        },
    )
    assert submission.feedback_id == "doc-1"
    assert submission.comment == "Nice"


def test_firestore_feedback_reader_uses_window_dates() -> None:
    fake_query = _FakeQuery(
        [
            _FakeDocument(
                "doc-1",
                {
                    "feedback_id": "fdbk_1",
                    "quiz_file": "quizzes/example.json",
                    "date": "2026-03-10",
                    "quiz_type": "history_mcq_4",
                    "edition": 1,
                    "question_id": "question-1",
                    "question_human_id": "Q1",
                    "rating": 4,
                    "feedback_date_utc": "2026-03-12",
                    "created_at": "2026-03-12T10:00:00Z",
                    "updated_at": "2026-03-12T10:00:00Z",
                },
            )
        ]
    )
    client = _FakeClient(fake_query)

    class _FakeFieldFilter:
        def __init__(self, field_path: str, op_string: str, value: str) -> None:
            self.field_path = field_path
            self.op_string = op_string
            self.value = value

    reader = FirestoreFeedbackReader(client=client, field_filter_factory=_FakeFieldFilter)
    submissions = reader.list_feedback_for_window(build_previous_completed_days_window(dt.date(2026, 3, 16)))

    assert client.collection_name == "quiz_feedback"
    assert len(fake_query.filters) == 2
    assert fake_query.filters[0].field_path == "feedback_date_utc"
    assert fake_query.filters[0].op_string == ">="
    assert fake_query.filters[0].value == "2026-03-09"
    assert fake_query.filters[1].op_string == "<="
    assert fake_query.filters[1].value == "2026-03-15"
    assert submissions[0].feedback_id == "fdbk_1"


def test_rendering_includes_ai_unavailable_fallback(tmp_path: Path) -> None:
    _write_quiz_payload(tmp_path, "quizzes/q1.json")
    aggregate = aggregate_feedback_submissions(
        submissions=[
            FeedbackSubmission(
                feedback_id="f1",
                quiz_file="quizzes/q1.json",
                date="2026-03-10",
                quiz_type="history_mcq_4",
                edition=2,
                question_id="question-1",
                question_human_id="Q77",
                rating=2,
                comment="Could be clearer",
                feedback_date_utc="2026-03-12",
                created_at="2026-03-12T08:00:00Z",
                updated_at="2026-03-12T08:00:00Z",
            )
        ],
        content_repo_root=tmp_path.as_posix(),
        window=build_previous_completed_days_window(dt.date(2026, 3, 16)),
    )

    markdown = render_weekly_report_markdown(
        aggregate=aggregate,
        generated_at="2026-03-16T07:00:00Z",
        llm_summary=None,
        ai_unavailable_reason="ai_disabled",
    )
    payload = build_weekly_report_payload(
        aggregate=aggregate,
        generated_at="2026-03-16T07:00:00Z",
        llm_summary=None,
        ai_unavailable_reason="ai_disabled",
    )

    assert "AI summary unavailable: `ai_disabled`" in markdown
    assert payload["aggregates"]["total_submissions"] == 1
    assert payload["questions"][0]["question_human_id"] == "Q77"
    assert payload["aggregates"]["issue_counts"] == {}
    assert payload["questions"][0]["issue_tags"] == []
    assert payload["ai_unavailable_reason"] == "ai_disabled"


class _FakeSummaryOrchestrator:
    def __init__(self, response: dict[str, object] | None, reason: str | None = None) -> None:
        self._response = response
        self._reason = reason
        self.last_kwargs: dict[str, object] | None = None

    def is_enabled(self) -> bool:
        return True

    def run_json_task(self, **_: object) -> tuple[dict[str, object] | None, str | None]:
        self.last_kwargs = dict(_)
        return self._response, self._reason


def test_summarize_weekly_feedback_validates_payload(tmp_path: Path) -> None:
    _write_quiz_payload(tmp_path, "quizzes/q1.json")
    aggregate = aggregate_feedback_submissions(
        submissions=[
            FeedbackSubmission(
                feedback_id="f1",
                quiz_file="quizzes/q1.json",
                date="2026-03-10",
                quiz_type="history_mcq_4",
                edition=2,
                question_id="question-1",
                question_human_id="Q77",
                rating=1,
                comment="Too vague",
                feedback_date_utc="2026-03-12",
                created_at="2026-03-12T08:00:00Z",
                updated_at="2026-03-12T08:00:00Z",
            )
        ],
        content_repo_root=tmp_path.as_posix(),
        window=build_previous_completed_days_window(dt.date(2026, 3, 16)),
    )

    orchestrator = _FakeSummaryOrchestrator(
        {
            "executive_summary": "Feedback is sparse but one question should be reviewed.",
            "themes": ["Question clarity needs work."],
            "positive_signals": ["Users are leaving actionable comments."],
            "questions_to_review": [{"question_human_id": "Q77", "reason": "Low rating this week."}],
            "action_items": [{"title": "Review Q77", "detail": "Tighten the prompt wording.", "priority": "high"}],
        }
    )
    summary, reason = summarize_weekly_feedback(
        aggregate=aggregate,
        ai_orchestrator=orchestrator,
    )

    assert reason is None
    assert summary is not None
    assert summary["questions_to_review"][0]["question_human_id"] == "Q77"
    assert orchestrator.last_kwargs is not None
    response_schema = orchestrator.last_kwargs.get("response_schema")
    assert isinstance(response_schema, dict)
    assert response_schema.get("name") == "weekly_feedback_review"
    assert response_schema.get("strict") is True


def test_summarize_weekly_feedback_falls_back_on_invalid_payload(tmp_path: Path) -> None:
    _write_quiz_payload(tmp_path, "quizzes/q1.json")
    aggregate = aggregate_feedback_submissions(
        submissions=[
            FeedbackSubmission(
                feedback_id="f1",
                quiz_file="quizzes/q1.json",
                date="2026-03-10",
                quiz_type="history_mcq_4",
                edition=2,
                question_id="question-1",
                question_human_id="Q77",
                rating=4,
                comment="Good",
                feedback_date_utc="2026-03-12",
                created_at="2026-03-12T08:00:00Z",
                updated_at="2026-03-12T08:00:00Z",
            )
        ],
        content_repo_root=tmp_path.as_posix(),
        window=build_previous_completed_days_window(dt.date(2026, 3, 16)),
    )

    summary, reason = summarize_weekly_feedback(
        aggregate=aggregate,
        ai_orchestrator=_FakeSummaryOrchestrator(
            {
                "executive_summary": "",
                "themes": [],
                "positive_signals": [],
                "questions_to_review": [],
                "action_items": [],
            }
        ),
    )

    assert summary is None
    assert reason is not None
    assert reason.startswith("summary_payload_invalid:")


def test_weekly_feedback_cli_writes_markdown_and_json_reports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    content_root = tmp_path / "mindblast-content"
    _write_quiz_payload(content_root, "quizzes/q1.json")
    fixture_path = tmp_path / "feedback.json"
    fixture_path.write_text(
        json.dumps(
            [
                {
                    "feedback_id": "f1",
                    "quiz_file": "quizzes/q1.json",
                    "date": "2026-03-10",
                    "quiz_type": "history_mcq_4",
                    "edition": 2,
                    "question_id": "question-1",
                    "question_human_id": "Q77",
                    "rating": 3,
                    "comment": "Interesting but a bit easy.",
                    "feedback_date_utc": "2026-03-12",
                    "created_at": "2026-03-12T08:00:00Z",
                    "updated_at": "2026-03-12T08:00:00Z",
                }
            ],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate_weekly_feedback_report.py",
            "--content-repo-root",
            content_root.as_posix(),
            "--feedback-json",
            fixture_path.as_posix(),
            "--run-date",
            "2026-03-16",
            "--disable-ai",
        ],
    )

    assert weekly_feedback_review_main() == 0

    markdown_path = content_root / "reports" / "feedback" / "weekly" / "2026" / "2026-W11.md"
    json_path = content_root / "reports" / "feedback" / "weekly" / "2026" / "2026-W11.json"
    assert markdown_path.exists()
    assert json_path.exists()
    assert "Weekly Feedback Review" in markdown_path.read_text(encoding="utf-8")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["window"] == {"start_date": "2026-03-09", "end_date": "2026-03-15"}


def test_feedback_report_payload_includes_deterministic_issue_tags(tmp_path: Path) -> None:
    content_root = tmp_path / "mindblast-content"
    payload_path = content_root / "quizzes" / "q48.json"
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    payload_path.write_text(
        json.dumps(
            {
                "date": "2026-03-11",
                "type": "history_mcq_4",
                "question": "Which event happened in 2010?",
                "questions": [
                    {
                        "id": "question-1",
                        "human_id": "Q48",
                        "prompt": "Which event happened in 2010?",
                        "answer_fact_ids": ["a1", "a2", "a3", "a4"],
                        "correct_answer_fact_id": "a2",
                        "selection_rules": {"target_year": 2010},
                    }
                ],
                "choices": [
                    {"id": "A", "label": "Event in 1928.", "answer_fact_id": "a1"},
                    {"id": "B", "label": "Economist is sworn in during the 2010 earthquake ceremony.", "answer_fact_id": "a2"},
                    {"id": "C", "label": "Event in 1990.", "answer_fact_id": "a3"},
                    {"id": "D", "label": "Event in 1985.", "answer_fact_id": "a4"},
                ],
                "correct_choice_id": "B",
                "generation": {"edition": 1},
                "answer_facts": [
                    {"id": "a1", "label": "Event in 1928."},
                    {"id": "a2", "label": "Economist is sworn in during the 2010 earthquake ceremony."},
                    {"id": "a3", "label": "Event in 1990."},
                    {"id": "a4", "label": "Event in 1985."},
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    aggregate = aggregate_feedback_submissions(
        submissions=[
            FeedbackSubmission(
                feedback_id="f1",
                quiz_file="quizzes/q48.json",
                date="2026-03-11",
                quiz_type="history_mcq_4",
                edition=1,
                question_id="question-1",
                question_human_id="Q48",
                rating=1,
                comment="Too easy",
                feedback_date_utc="2026-03-12",
                created_at="2026-03-12T08:00:00Z",
                updated_at="2026-03-12T08:00:00Z",
            )
        ],
        content_repo_root=content_root.as_posix(),
        window=build_previous_completed_days_window(dt.date(2026, 3, 16)),
    )

    payload = build_weekly_report_payload(
        aggregate=aggregate,
        generated_at="2026-03-16T07:00:00Z",
        llm_summary=None,
        ai_unavailable_reason="ai_disabled",
    )

    assert payload["aggregates"]["issue_counts"] == {"prompt_leak_year": 1}
    assert payload["questions"][0]["issue_tags"] == ["prompt_leak_year"]
