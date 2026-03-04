# Phase 7 Specification: Authenticated Feedback API

## Goal

Add authentication and request attestation so feedback writes can be safely exposed on public routes without unacceptable abuse/cost risk.

## Motivation

As of 2026-03-04:
- Staging backend is technically functional but internet-exposed traffic can incur costs.
- To reduce risk, staging public access was intentionally locked down:
  - direct function/service URLs return `403`,
  - staging Hosting no longer rewrites `/api/**` to the backend.
- Next step is to re-open API access only behind authentication and stronger request controls.

## Proposed Scope (Initial)

1. Require authenticated identity for `POST /api/quiz-feedback`.
2. Enforce App Check for web clients in both staging and production.
3. Keep strict origin allowlist and existing rate limits as defense-in-depth.
4. Re-enable staging `/api/**` Hosting rewrite only after auth flow is validated.

## Non-Goals

- No full user profile system.
- No social login UX optimization in this phase.
- No analytics redesign.

## Acceptance Criteria (Draft)

- Unauthenticated requests cannot write feedback.
- Authenticated requests from approved web clients can create/update feedback.
- Staging can safely re-enable public `/api/**` routing with bounded abuse risk.
