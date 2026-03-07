# Phase 7.5 PR Plan: Feedback API Edge Hardening

## Objective
Deliver edge-level abuse and cost controls for feedback API traffic before production exposure decisions.

## Dependency
- Phase 7 auth/app-check contract is implemented (`docs/PHASE7.md`).
- Environment posture is defined (`docs/ENVIRONMENTS.md`).

## PR1: Policy Definition and Source Control Baseline

Scope:
- [ ] Define approved invoker postures per environment.
- [ ] Define required edge controls for production exposure.
- [ ] Update runbook and environment docs with explicit risk statements.

Exit criteria:
- Exposure rules and hardening gate are documented and reviewable.

## PR2: Staging Edge Controls

Scope:
- [ ] Apply edge rate-limit/challenge rules for staging `/api/**`.
- [ ] Verify normal signed-in feedback flow still works.
- [ ] Verify abusive burst traffic is reduced before backend.

Exit criteria:
- Staging demonstrates effective edge filtering with no product regression.

## PR3: Production Readiness Gate

Scope:
- [ ] Mirror edge policy to production.
- [ ] Validate emergency containment sequence.
- [ ] Record telemetry checks and operational thresholds.

Exit criteria:
- Production exposure decision is backed by edge controls and tested incident handling.

## Definition of Done

- [ ] Edge controls exist for staging and production feedback API routes.
- [ ] Production route enablement requires edge controls to be active.
- [ ] Runbook includes phone-only containment steps.
