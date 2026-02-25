"""Constants for quiz-forge generation."""

import uuid

API_URL_TEMPLATE = "https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/events/{month}/{day}"
QUIZ_TYPE_WHICH_CAME_FIRST = "which_came_first"
QUIZ_TYPE_HISTORY_MCQ_4 = "history_mcq_4"
SUPPORTED_QUIZ_TYPES = (QUIZ_TYPE_WHICH_CAME_FIRST, QUIZ_TYPE_HISTORY_MCQ_4)
DEFAULT_QUIZ_TYPES = ",".join(SUPPORTED_QUIZ_TYPES)
QUIZ_FILENAME_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "mindblast.quiz-forge.daily.v1")
QUIZ_QUESTION_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "mindblast.quiz-forge.question.v1")
ANSWER_FACT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "mindblast.quiz-forge.answer-fact.v1")
QUIZ_SCHEMA_VERSION = 2
NORMALIZED_MODEL_VERSION = "question_answer_facts_v1"
WHICH_CAME_FIRST_QUESTION = "Which event happened earlier?"
