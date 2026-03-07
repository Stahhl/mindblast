# Environments

## Purpose

Define the canonical environment posture for `Mindblast` so both humans and agents treat staging and production with the correct risk model.

This is the source of truth for:
- environment names and project IDs
- internet exposure expectations
- billing/cost posture
- deploy targets and guardrails

## Canonical Environments (As of 2026-03-07)

| Environment | Firebase Project | Hosting Target | Primary Domain | Internet-Exposed | Billable |
| --- | --- | --- | --- | --- | --- |
| staging | `mindblast-staging` | `staging` | `staging.mindblast.app` | Yes | Yes (Blaze) |
| production | `mindblast-prod` | `production` | `mindblast.app` | Yes | Yes (Blaze) |

## Current Feedback API Exposure Posture (Phase 7 Exception)

| Environment | `feedback_api_allow_public_invoker` | Status | Notes |
| --- | --- | --- | --- |
| staging | `true` | Temporary exception | Allowed during Phase 7 validation because Hosting rewrite traffic to Cloud Run is unauthenticated at invoker layer. |
| production | `false` | Required baseline | Must remain non-public until Phase 7.5 edge hardening is implemented and accepted. |

## Non-Negotiable Posture

1. `staging` is not a safe sandbox by default.
2. `staging` is publicly reachable on the internet.
3. `staging` spend is tied to real billing and can incur charges.
4. Any security/cost control required for production should be treated as required for staging unless explicitly waived in writing.
5. Current written waiver: temporary staging public invoker for Phase 7 only; production remains gated by Phase 7.5.

## Deployment Mapping

- Project mapping is defined in `.firebaserc`.
- Frontend deploy workflows:
  - `.github/workflows/deploy-frontend-staging.yml`
  - `.github/workflows/deploy-frontend-production.yml`
- Feedback API deploy workflows:
  - `.github/workflows/deploy-feedback-api-staging.yml`
  - `.github/workflows/deploy-feedback-api-production.yml`

## API Exposure and IAM Baseline

- Current desired baseline:
  - direct backend URL access should remain non-public
  - API access should require app-level auth checks (Firebase Auth + App Check + validation + rate limits)
- Terraform control surface:
  - `infra/terraform/README.md`
  - `feedback_api_allow_public_invoker` controls public `run.invoker`

Note:
- Allowing public invoker can be necessary for some Hosting rewrite patterns.
- Public invoker does not bypass app-level auth checks, but rejected traffic can still create billable load.

## Cost and Abuse Guardrails

Minimum guardrails for both environments:
1. Budget alerts enabled at project level.
2. App-level reject paths enabled (`401`/`403`/`429`).
3. Rate limits enabled and monitored.
4. Emergency kill-switch documented and tested.
5. No long-lived secrets committed to git.

## Change Management Rules

When changing environment exposure, IAM, or routing:
1. Update this file in the same PR.
2. Update relevant phase/runbook docs in the same PR.
3. Record whether the change increases internet exposure or spend risk.
4. Include rollback steps before merge.

## Related Docs

- `docs/HOSTING_ROLLOUT.md`
- `docs/PHASE6_5.md`
- `docs/PHASE7.md`
- `docs/PHASE7_5.md`
- `docs/roadmap/phase7_rollout_runbook.md`
