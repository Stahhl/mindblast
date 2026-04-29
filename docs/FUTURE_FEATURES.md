# Future Features Backlog

## Goal
Track potential future quiz formats and product features after Phase 1.

## Naming
- Project name: `Mindblast`.
- User-facing app name: `Mindblast`.
- Backend generator service name: `quiz-forge`.

## Quiz Modes

### Implemented in Phase 1
- `which_came_first`: two events, choose the earlier one.
- `history_mcq_4`: four options, choose the event that matches a target year.

### Additional Quiz Formats
- Geography quiz:
  - selected next category for Phase 9: capital-to-country factoid MCQ (`geography_factoid_mcq_4`)
  - later candidates: country-to-capital, flag, and timezone prompts
- Science myth-or-fact: classify a statement and show explanation.
- News context quiz: current event with background question.
- Timeline ordering: place 3 to 5 events in chronological order.
- Quote guess: identify who said a quote.
- Code trivia: programming concept/debugging question.
- Language mini quiz: synonym, translation, etymology, or usage.
- Image-based quiz: identify person/place/object from an image.
- Prediction question: pick an outcome that resolves in the future.

## Product Features
- AI-assisted distractor ranking for MCQ quality (Phase 3 candidate).
- Phase 3 budget defaults target low-risk experimentation:
  - `AI_MAX_DAILY_USD=1.00`
  - `AI_MAX_MONTHLY_USD=5.00`
- Optional synthetic distractors for experiments only after explicit provenance/labeling contract is implemented.
- Ratings on each generated question.
- Improvement loop using ratings to tune generation quality.
- Signed-in cross-device quiz progress and feedback draft persistence (Phase 10).
- Category expansion beyond history.
- Music quiz mode (blocked until rights-cleared catalog and platform-compliant playback model are documented in `docs/CONTENT_COMPLIANCE_POLICY.md`).
- Difficulty levels.
- Leaderboards.
- Achievements.
- Streaks.
- Sharing and social challenge links.

## Suggested Evolution Order
1. Keep Phase 1 stable (`which_came_first` + `history_mcq_4`, one question per type/day).
2. Add Phase 1.5 discovery artifacts (`quizzes/latest.json` + daily index files).
3. Ship Phase 2 static frontend app using discovery artifacts.
4. Add Phase 3 AI-assisted distractor reranking with strict budget/fallback controls.
5. Add ratings and lightweight analytics.
6. Add the first non-history category via Phase 9 geography factoids.
7. Broaden categories and difficulty controls beyond the initial geography rollout.
8. Add leaderboard/achievement/streak systems.
