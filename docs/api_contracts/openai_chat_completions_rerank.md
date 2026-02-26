# OpenAI Chat Completions Contract (`quiz-forge`)

## Scope
- Provider: `openai`
- API: `chat.completions`
- Task: `history_mcq_4` distractor rerank
- Snapshot file: `/Users/stahl/dev/mindblast/docs/api_contracts/openai_chat_completions_rerank.snapshot.json`
- Last reviewed: `2026-02-26`

## Canonical Sources
- [OpenAI Chat Completions API Reference](https://platform.openai.com/docs/api-reference/chat/create-chat-completion)
- [Chat temperature parameter reference](https://platform.openai.com/docs/api-reference/chat/create#chat-createtemperature)
- [Reasoning models guide](https://platform.openai.com/docs/guides/reasoning)

## Request Rules

### GPT-5 family (`model` starts with `gpt-5`)
- Required:
  - `model`
  - `messages`
  - `response_format: {"type":"json_object"}`
  - `max_completion_tokens`
  - `reasoning_effort: "minimal"`
- Forbidden:
  - `max_tokens`
  - `temperature`

### Non-GPT-5 family
- Required:
  - `model`
  - `messages`
  - `response_format: {"type":"json_object"}`
  - `max_tokens`
  - `temperature: 0`
- Forbidden:
  - `max_completion_tokens`
  - `reasoning_effort`

## Response Parsing Rules
- Preferred ranked ID key: `ranked_distractor_ids`
- Accepted fallback keys:
  - `selected_distractor_ids`
  - `selected`
  - `distractors`
  - `ranked_ids`
- If no accepted list key is present, provider returns an empty list and downstream validation must fallback deterministically.

## Operational Note
- If provider behavior changes, update both:
  - `/Users/stahl/dev/mindblast/scripts/quiz_forge/ai/providers/openai_contract.py`
  - `/Users/stahl/dev/mindblast/docs/api_contracts/openai_chat_completions_rerank.snapshot.json`
- CI contract tests in `/Users/stahl/dev/mindblast/tests/quiz_forge/` are expected to fail until both are aligned.
