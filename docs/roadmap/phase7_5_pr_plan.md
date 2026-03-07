# Phase 7.5 PR Plan: Feedback API Edge Hardening

## Objective
Deliver edge-level abuse and cost controls for feedback API traffic before production exposure decisions.

## Dependency
- Phase 7 auth/app-check contract is implemented (`docs/PHASE7.md`).
- Environment posture is defined (`docs/ENVIRONMENTS.md`).

## PR1: Policy Definition and Source Control Baseline

Scope:
- [x] Define approved invoker postures per environment.
- [x] Define required edge controls for production exposure.
- [x] Update runbook and environment docs with explicit risk statements.

Exit criteria:
- Exposure rules and hardening gate are documented and reviewable.

## PR2: Staging Edge Controls

Scope:
- [x] Apply edge rate-limit/challenge rules for staging `/api/**`.
- [x] Verify normal signed-in feedback flow still works.
- [x] Verify abusive burst traffic is reduced before backend.

Validation snapshot (2026-03-07):
- External burst to `staging.mindblast.app/api/quiz-feedback` returned `401` for first 5 requests, then `429` from Cloudflare edge.

Exit criteria:
- Staging demonstrates effective edge filtering with no product regression.

## PR3: Production Readiness Gate

Scope:
- [x] Mirror edge policy to production.
- [x] Validate emergency containment sequence.
- [x] Record telemetry checks and operational thresholds.

Validation snapshot (2026-03-07):
- External burst to `mindblast.app/api/quiz-feedback` returned `429` from Cloudflare edge, confirming policy applies to production host.
- Staging containment drill via CLI:
  - set `FEEDBACK_WRITE_ENABLED=false` -> `POST /api/quiz-feedback` returned `503 writes_disabled`
  - set `FEEDBACK_WRITE_ENABLED=true` -> unauthenticated `POST /api/quiz-feedback` returned `401 unauthenticated` (normal auth gate restored)
- Telemetry thresholds and Discord-first alerting procedure documented in runbook.

Exit criteria:
- Production exposure decision is backed by edge controls and tested incident handling.

## Definition of Done

- [x] Edge controls exist for staging and production feedback API routes.
- [ ] Production route enablement requires edge controls to be active.
- [x] Runbook includes phone-only containment steps.
