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
- Geography quiz: country/capital/flag/timezone prompts.
- Science myth-or-fact: classify a statement and show explanation.
- News context quiz: current event with background question.
- Timeline ordering: place 3 to 5 events in chronological order.
- Quote guess: identify who said a quote.
- Code trivia: programming concept/debugging question.
- Language mini quiz: synonym, translation, etymology, or usage.
- Image-based quiz: identify person/place/object from an image.
- Prediction question: pick an outcome that resolves in the future.

## Product Features
- Ratings on each generated question.
- Improvement loop using ratings to tune generation quality.
- Category expansion beyond history.
- Difficulty levels.
- Leaderboards.
- Achievements.
- Streaks.
- Sharing and social challenge links.

## Suggested Evolution Order
1. Keep Phase 1 stable (`which_came_first` + `history_mcq_4`, one question per type/day).
2. Add Phase 1.5 discovery artifacts (`quizzes/latest.json` + daily index files).
3. Ship Phase 2 static frontend app using discovery artifacts.
4. Add ratings and lightweight analytics.
5. Add categories and difficulty controls.
6. Add leaderboard/achievement/streak systems.
