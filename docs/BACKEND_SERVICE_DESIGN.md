# Backend Service Design: Portable Interfaces First

## Naming
- Project name: `Mindblast`.
- User-facing app name: `Mindblast`.
- Backend generator service name: `quiz-forge`.

## Purpose
Define how backend services should be built so product logic is portable and testable, while cloud vendors (Firebase/GCP today) remain replaceable infrastructure adapters.

This doc applies to all backend APIs introduced after static-only phases (for example, Phase 6 feedback APIs).

## Design Goals
- Keep domain and application logic independent from Firebase SDKs.
- Make backend behavior deterministic and easy to unit test.
- Minimize migration cost to non-Firebase runtimes/stores.
- Keep initial implementation small and pragmatic.
- Enforce explicit contracts for auth/abuse controls and persistence.

## Non-Goals
- Full microservice platform design.
- Premature abstraction for features that do not exist yet.
- Supporting every cloud provider equally on day one.

## Core Principle
`Business logic must depend only on interfaces (ports), never on vendor SDKs.`

Vendor code must live in infrastructure adapters and be wired at startup.

## Architecture Model

Use a layered architecture:

1. `Domain`
- Business entities, value objects, invariants.
- No I/O, no SDK imports, no framework types.

2. `Application`
- Use cases and orchestration.
- Depends on domain + abstract ports.
- Contains request-level behavior (validation decisions, upsert semantics, abuse decisions).

3. `Infrastructure`
- Vendor adapters implementing ports.
- HTTP transport, Firebase Admin SDK, App Check verification, Firestore persistence, logging sinks.

4. `Composition Root`
- Wires concrete adapters to use cases (per runtime environment).
- Only place where vendor dependencies are selected.

## Required Ports (Interfaces)

The following ports should be used for write APIs like feedback:

- `FeedbackRepository`
  - `upsert(record, key): UpsertResult`
  - `findByKey(key): FeedbackRecord | null`
- `RateLimiter`
  - `checkAndConsume(scopeKey, policy): RateLimitDecision`
- `ClientIdentityProvider`
  - `getOrCreateClientId(request): ClientIdResult`
- `RequestAttestationVerifier`
  - `verify(request): AttestationDecision` (App Check / equivalent)
- `Clock`
  - `nowUtc(): Instant`
  - `todayUtc(): Date`
- `IdGenerator`
  - deterministic key/hash generation
- `ConfigProvider`
  - typed access to runtime config and limits
- `AuditLogger`
  - structured event logs with reason codes

## Firebase Adapter Mapping

Concrete Firebase implementations should be adapters behind those ports:

- `FirestoreFeedbackRepository` -> `FeedbackRepository`
- `FirestoreRateLimiter` (or Redis/Memory variant) -> `RateLimiter`
- `FirebaseAppCheckVerifier` -> `RequestAttestationVerifier`
- `CookieClientIdentityProvider` -> `ClientIdentityProvider`
- `CloudLoggingAuditLogger` -> `AuditLogger`

The application use case must not import from:
- `firebase-admin/*`
- `firebase-functions/*`
- Cloud provider request/response types

## API Transport Rule
- HTTP handlers are thin translators only:
  - parse request
  - call use case
  - map result to HTTP response
- They must not contain business branching (except transport-level errors).

## Data Contract Rule
- API request/response schemas are versioned and documented in phase specs.
- Internal storage representation may evolve, but use case input/output contracts must remain stable.
- Use explicit DTO mapping between API schema and domain/application models.

## Vendor Lock-in Guardrails

1. No raw Firestore document shapes outside adapters.
2. No Firebase-specific IDs as business keys.
3. Use deterministic app-owned IDs for idempotency/upserts.
4. Keep rate-limiting policies vendor-neutral (policy in app layer, enforcement in adapter).
5. Keep attestation/auth decisions expressed as domain/application enums, not SDK booleans.
6. Maintain adapter conformance tests so alternate adapters can be added safely.

## Project Structure (Recommended)

For backend APIs, prefer a structure like:

```text
backend/
  src/
    domain/
      feedback/
        entities.ts
        value_objects.ts
        rules.ts
    application/
      feedback/
        submit_feedback_use_case.ts
        ports.ts
        dto.ts
    infrastructure/
      firebase/
        firestore_feedback_repository.ts
        firestore_rate_limiter.ts
        app_check_verifier.ts
      web/
        http_handler.ts
        cookie_identity_provider.ts
      observability/
        audit_logger.ts
    composition/
      firebase_runtime.ts
  tests/
    unit/
      application/
    contract/
      adapters/
```

If introducing a new top-level `backend/` directory is deferred, keep equivalent layering inside the selected runtime folder.

## Testing Strategy

1. Unit tests (application layer)
- No network, no SDKs, no emulator required.
- Mock ports only.
- Validate business invariants and edge cases.

2. Adapter contract tests
- Each adapter must satisfy port behavior contract.
- Include deterministic failure-mode tests (timeouts, quota errors, stale writes).

3. Transport tests
- Request parsing, status codes, error mapping.

4. Minimal integration tests
- Optional emulator-backed tests for staging confidence.

## Configuration Strategy
- All limits and feature flags are typed config, not hardcoded literals.
- Example keys:
  - `feedback.rate_limit.client_hourly`
  - `feedback.rate_limit.client_daily`
  - `feedback.rate_limit.ip_hourly`
  - `feedback.rate_limit.global_hourly`
  - `feedback.comments_enabled`
  - `feedback.write_enabled`

## Observability and Operations
- Structured logs with stable reason codes:
  - `invalid_payload`
  - `rate_limited`
  - `attestation_failed`
  - `storage_error`
- Emit counters for accepts/rejects by reason.
- Keep emergency feature flags to disable writes/comments without redeploy.

## Migration Playbook (Firebase -> Alternative)

When moving from Firebase to another provider:

1. Implement new adapters for existing ports.
2. Run adapter contract tests against new adapters.
3. Switch composition root by environment flag.
4. Run dual-write (optional) for confidence.
5. Cut read/write over after consistency checks.

No application/domain code should need changes for provider migration.

## Delivery Rules for New Backend Features

For every new backend feature:

1. Write/update phase spec and API contract first.
2. Define ports in application layer before adapter code.
3. Implement use case with in-memory test doubles.
4. Implement Firebase adapters.
5. Add adapter contract tests.
6. Add runtime wiring in composition root.
7. Add rollout and kill-switch runbook notes.

## Initial Application to Phase 6

Phase 6 feedback implementation should follow this architecture:
- Feedback endpoint use case depends on ports only.
- Firebase-specific logic is confined to adapters.
- Rate limiting, identity, and attestation are all pluggable via interfaces.
- API behavior remains unchanged if backend provider changes.
