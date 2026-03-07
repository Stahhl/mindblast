# Phase 7.5 Specification: Feedback API Edge Hardening (`quiz_feedback_v2_hardening`)

## Naming
- Project name: `Mindblast`.
- User-facing app name: `Mindblast`.
- Backend generator service name: `quiz-forge`.

## Objective
Reduce abuse and billing risk for internet-exposed feedback writes by adding edge-layer protection before or alongside production `/api/**` exposure.

## Dependency
- Phase 7 (`docs/PHASE7.md`) auth + app-check write contract is implemented.
- Environment posture is documented in `docs/ENVIRONMENTS.md`.

## Why This Phase
Auth/App Check stop unauthorized writes, but they do not stop request volume from reaching backend compute.  
Rejected requests can still create billable usage on Blaze projects.

## Scope (Phase 7.5)
- Define and implement edge protection for feedback API traffic.
- Keep app-level controls from Phase 7:
  - Firebase Auth ID token verification
  - Firebase App Check verification
  - payload validation
  - backend rate limits
- Add edge-level abuse controls for `/api/**`:
  - request-rate throttling
  - bot/challenge policy
  - optional geo/IP posture rules
- Document emergency response steps that can be executed from phone only.
- Ensure exposure posture (public/private invoker) is explicitly documented per environment.

## Out of Scope
- Full user account/security redesign.
- New product features on top of feedback.
- Migrating away from Firebase Hosting/Functions in this phase.

## Target Security Model
Defense in depth, in this order:
1. Edge layer rejects obvious abusive traffic before backend compute.
2. Backend entrypoint enforces origin + auth + app-check.
3. Domain validation and write contract enforcement.
4. Rate limiting and feature-flag kill switches.

## Environment Policy
- `staging` and `production` are both internet-exposed and billable.
- No environment is treated as "safe to expose" without cost/security controls.
- If `feedback_api_allow_public_invoker = true`, this must be documented in:
  - `docs/ENVIRONMENTS.md`
  - rollout runbook
  - PR/incident notes
- Phase 7 exception:
  - staging may be public invoker temporarily.
  - production remains non-public until this phase is accepted.

## Rollout Plan
1. Select edge control implementation path (Cloudflare WAF/rate limit rules recommended with current DNS setup).
2. Define source-controlled config for what can be codified; script/manual runbook for what cannot.
3. Apply edge rules in staging and run abuse smoke checks.
4. Verify backend sees expected status profile (`401/403/429`) under normal and stress traffic.
5. Validate emergency kill-switch flow end-to-end.
6. Promote same policy to production.

## Abuse Smoke Checks (Minimum)
- Burst unauthenticated requests:
  - edge blocks/challenges significant portion before backend.
- Burst invalid app-check/auth requests:
  - backend returns expected reject codes for traffic that passes edge.
- Burst signed-in valid writes:
  - normal usage still works and rate limits enforce correctly.

## Acceptance Criteria
- Edge policy exists for feedback routes in staging and production.
- Production feedback route is not exposed without edge controls in place.
- On-call can execute a documented emergency containment sequence from phone.
- Runbook includes:
  - detection signals
  - threshold triggers
  - rollback/containment actions

## Rollback / Containment
In order of fastest containment:
1. Run GitHub workflow `Feedback Emergency Toggle` with `write_enabled=false` (confirmation: `SHORT_CIRCUIT`).
2. Disable `/api/**` Hosting rewrite for affected environment and deploy hosting.
3. Tighten/enable emergency edge block rules.
4. Revert invoker posture in Terraform if needed.

## Deliverables
- Updated environment posture docs.
- Updated rollout runbook with edge and emergency operations.
- Updated roadmap/checklists for production go-live gate.

Roadmap:
- `docs/roadmap/phase7_5_pr_plan.md`
