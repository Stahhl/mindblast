# Phase 2 Specification: Frontend App (Static Client)

## Naming
- Project name: `Mindblast`.
- User-facing app name: `Mindblast`.
- Backend generator service name: `quiz-forge`.

## Objective
Ship the first playable `Mindblast` frontend that consumes generated quiz content directly from repository-hosted JSON files.

## Dependency
- Phase 2 assumes discovery artifacts from `docs/PHASE1_5.md` are implemented.

## Scope (Phase 2)
- Build a web frontend for daily quiz play.
- Use file-based discovery and quiz payloads only (no custom backend API).
- Support currently enabled quiz types:
  - `which_came_first`
  - `history_mcq_4`

## Out of Scope
- Accounts, auth, or user profiles.
- Server-side score tracking.
- Leaderboards, achievements, and streaks.
- Paid AI services.

## Data Access Contract
Frontend load order:
1. Fetch `quizzes/latest.json`.
2. Resolve target date:
   - default: `latest.date`
   - archive mode: user-selected `YYYY-MM-DD`
3. Fetch `quizzes/index/YYYY-MM-DD.json` for the resolved target date.
4. Fetch each quiz payload listed in `quiz_files`.

Required behavior:
- If any fetch fails, show a clear fallback UI with retry action.
- If one quiz type fails to load, show available types that did load.
- Frontend must accept quiz payload `metadata.version` values `1` and `2` during migration.

## Product Requirements
- Display one question card per quiz type for the selected date.
- Allow browsing previous quiz dates (archive mode) via date selection.
- Provide a quick "jump to latest" control (button and keyboard shortcut).
- Allow selecting one answer per quiz.
- Lock answer after selection for that quiz card.
- Show immediate correctness feedback.
- Show source attribution link(s) from quiz payload.
- Mobile and desktop responsive layouts.

## State and Persistence
- Keep answers in client state.
- Optional: persist answer state in `localStorage` per date (`YYYY-MM-DD` keying).

## Suggested Technical Approach
- Static frontend stack (example: React + Vite + TypeScript).
- Host as static site (GitHub Pages, Netlify, or Vercel static output).
- No server runtime required in Phase 2.
- Keep app files isolated under `src/apps/<app-name>/` to support multiple apps in this repo.

## Quality and Reliability
- Strict runtime validation of loaded JSON shape before rendering.
- Fail gracefully on malformed data with non-breaking UI.
- If selected archive date has no published index, show an explicit empty-state card with recovery actions.
- Keep bundle and runtime dependencies minimal.
- Prefer TypeScript source files (`.ts` / `.tsx`) for app code.

## Backend API Decision Gate (Post-Phase 2)
Introduce a backend API only if one or more become required:
- authenticated user state across devices,
- anti-cheat or hidden-answer flows,
- write-heavy analytics/events that should not run from client,
- dynamic personalization not representable by static files.

## Acceptance Criteria
- Deployed frontend can load and render daily quizzes using only discovery + quiz JSON files.
- User can complete all available quiz types for the day.
- Frontend works on current desktop and mobile browsers.
- No always-on backend service is required for normal play.
