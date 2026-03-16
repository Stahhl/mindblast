# Hosting Rollout Plan (Firebase-First)

## Naming
- Project name: `Mindblast`.
- User-facing app name: `Mindblast`.
- Backend generator service name: `quiz-forge`.

## Objective
Adopt a hosting platform that ships static web quickly now while minimizing migration risk for future backend APIs, dedicated mobile apps, data persistence, DNS management, and AI workloads.

## Recommendation
Use `Firebase` as the primary hosting platform, backed by `Google Cloud` services as the product expands.

Why this fits current and future needs:
- Static hosting is simple to ship now with Firebase Hosting.
- Mobile roadmap is strong with Firebase SDKs and FCM push support.
- Backend expansion path is clear: Auth, Firestore/Storage, Functions, Cloud Run.
- AI expansion path is available through Google Cloud and Vertex AI integrations.

## Scope For This Rollout
- In scope now: static hosting for Phase 2 frontend.
- In scope next: CI/CD, environments, DNS, and observability basics.
- Out of scope now: full backend API, account system, or mobile app implementation.

## Target Architecture
- `GitHub` remains source of truth, split across:
  - `mindblast` for frontend code, workflows, and infra
  - `mindblast-content` for generated quiz JSON artifacts
- `GitHub Actions` builds/deploys frontend to `Firebase Hosting`.
- `quizzes/` JSON remains statically served with cache-control rules.
- Terraform IaC scaffold lives in `infra/terraform/`.
- Two environments:
  - `staging`: preview and smoke checks.
  - `production`: public site.

## Rollout Phases

### Phase H1: Static Hosting Foundation
Deliverables:
- Create Firebase project for `mindblast`.
- Enable Firebase Hosting with two deploy targets: `staging` and `production`.
- Add `firebase.json` and `.firebaserc` in repo.
- Configure build output from `src/apps/frontend`.
- Ensure hosted site serves:
  - frontend app entrypoint
  - `quizzes/latest.json`
  - `quizzes/index/*.json`
  - quiz payload files referenced by index

Acceptance criteria:
- Production URL serves daily quizzes end-to-end from static files.
- Staging and production deploy independently.
- Frontend refresh loads latest daily quiz artifacts without manual app changes.

### Phase H1.5: CI/CD Hardening
Deliverables:
- Add GitHub Actions deploy workflows:
  - deploy on merge to `main` -> `staging`
  - promote/tag-based deploy -> `production`
- Current staging workflow: `.github/workflows/deploy-frontend-staging.yml`
- Current production workflow: `.github/workflows/deploy-frontend-production.yml`
- Add pre-deploy checks:
  - frontend build
  - quiz JSON contract validation
- Add rollback procedure doc.

Acceptance criteria:
- Any failed build/validation blocks deploy.
- One-command or one-workflow rollback to previous release.

Current staging workflow prerequisites:
- Repository secret `FIREBASE_SERVICE_ACCOUNT_STAGING`

Current production workflow prerequisites:
- Repository secret `FIREBASE_SERVICE_ACCOUNT_PRODUCTION`

### Phase H2: Backend-Ready Baseline (No Mandatory Cutover)
Deliverables:
- Define service boundaries for future API.
- Choose first backend runtime path (`Cloud Functions` for lightweight endpoints, `Cloud Run` for containerized services).
- Define auth model candidates (anonymous + optional registered users).
- Define persistence model for gameplay data.

Acceptance criteria:
- Backend design doc exists before implementation.
- No forced migration from static-only path unless decision gate is met.

### Phase H3: Mobile Readiness
Deliverables:
- Define shared API/content contract for web + mobile clients.
- Decide offline behavior and sync strategy.
- Define push notification strategy using FCM.

Acceptance criteria:
- Mobile team can start iOS/Android clients without redesigning core platform choices.

### Phase H4: AI Workload Readiness
Deliverables:
- Identify first AI-assisted feature candidates.
- Define data safety and cost guardrails.
- Decide runtime location for AI tasks (batch vs request-time).

Acceptance criteria:
- AI features can be piloted without replatforming hosting/auth/data foundations.

## DNS and Domain Strategy
- Keep registrar/domain ownership independent from hosting vendor.
- Use managed DNS with clear ownership and access controls.
- Start with subdomain for staging and apex or `www` for production.
- Keep TLS fully managed by platform defaults.

## Data and Security Guardrails
- Principle of least privilege for CI deploy credentials.
- Separate staging and production configs/secrets.
- Keep public quiz content in static hosting only.
- Do not expose future admin or write endpoints without auth + abuse controls.

## Cost Guardrails
- Start with free tiers where feasible.
- Add budget alerts before enabling paid backend features.
- Track per-environment usage separately.

## Decision Gates
Trigger backend API work when one or more conditions are true:
- Cross-device user state is required.
- Anti-cheat or hidden-answer flows are required.
- Write-heavy analytics is required.
- Personalization requires server-side logic.

## Initial Implementation Checklist
1. Create Firebase project and hosting targets.
2. Apply Terraform foundation in `infra/terraform/envs/staging`.
3. Apply Terraform foundation in `infra/terraform/envs/production`.
4. Add Firebase config files to repo.
5. Add staging deploy workflow.
6. Add production promotion workflow.
7. Validate static quiz discovery/files in deployed environment.
8. Document rollback and on-call basics.

## Risks and Mitigations
- Risk: Vendor lock-in concerns.
  - Mitigation: Keep contracts JSON-first and API boundaries explicit.
- Risk: Cost creep after backend/mobile features.
  - Mitigation: Budget alerts, staged rollouts, and usage dashboards.
- Risk: CI deployment complexity.
  - Mitigation: Keep workflow minimal and fail-closed on validation.

## Ownership
- Platform/hosting setup: project maintainers.
- Quiz content pipeline correctness: `quiz-forge` maintainers.
- Frontend deploy reliability: frontend maintainers.
