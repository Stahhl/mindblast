# Terraform Infrastructure (Firebase + GCP)

This directory manages infrastructure for `Mindblast` hosting and expansion.

## Goals
- Provision Firebase/GCP control-plane resources with Terraform.
- Keep static content deploys on Firebase CLI / GitHub Actions.
- Support separate `staging` and `production` environments.

## Layout

```text
infra/terraform/
├── modules/
│   └── firebase_foundation/
└── envs/
    ├── staging/
    └── production/
```

## What Terraform Manages
- Required Google APIs for Firebase hosting + backend workflows.
- Firebase project enablement.
- Optional/default Firestore database resource (for feedback backend persistence).
- Firebase Hosting site.
- Optional CI service account + project IAM roles.

## What Terraform Does Not Manage
- Static asset uploads/deploys (`firebase deploy --only hosting`).
- Hosting preview channels for pull requests.

## Quick Start

1. Pick an environment:

```zsh
cd infra/terraform/envs/staging
```

2. Copy and edit variables:

```zsh
cp terraform.tfvars.example terraform.tfvars
```

Set `create_project = true` only when Terraform should create a new GCP project.
For existing projects, keep it `false` and set `project_id` to the existing project.

3. Optional remote state:
- Copy `backend.hcl.example` to `backend.hcl` and set bucket/prefix.
- If you do not want remote state yet, use `terraform init -backend=false`.

4. Initialize and plan:

```zsh
# With remote state:
terraform init -backend-config=backend.hcl

# Or local state only:
terraform init -backend=false

terraform plan
```

5. Apply:

```zsh
terraform apply
```

## Phase 6 Backend Infra Notes

The default module/env values now include APIs and IAM roles required for:
- Firebase Hosting deploys,
- Firebase Functions deploys,
- Firestore-backed feedback writes.

New default APIs:
- `cloudbilling.googleapis.com`
- `cloudbuild.googleapis.com`
- `cloudfunctions.googleapis.com`
- `eventarc.googleapis.com`
- `artifactregistry.googleapis.com`
- `run.googleapis.com`
- `firestore.googleapis.com`
- `identitytoolkit.googleapis.com` (Firebase Auth backend API)

New default CI service account roles:
- `roles/cloudfunctions.admin`
- `roles/datastore.indexAdmin`
- `roles/firebaserules.admin`
- `roles/iam.serviceAccountUser`

These are additive to the existing Hosting roles and are required before
GitHub Actions (or local CLI) can deploy `quizFeedbackApi`.

## Phase 7 Auth Infra Notes

Phase 7 authenticated feedback depends on:
- Firebase Auth enabled in each environment project.
- `identitytoolkit.googleapis.com` enabled (managed in default `required_services`).

Notes:
- Terraform can ensure API enablement, but OAuth provider settings (for example Google sign-in)
  are configured inside Firebase Auth and are not currently managed by this Terraform stack.

Important billing prerequisite:
- Firebase Functions v2 deployment requires projects on Blaze (pay-as-you-go).
- On Spark, enabling `cloudbuild.googleapis.com`, `artifactregistry.googleapis.com`,
  and `run.googleapis.com` fails and backend deploys are blocked.

After updating Terraform for staging/production, run:

```zsh
cd infra/terraform/envs/staging
terraform plan
terraform apply
```

## Phase 6.5 Access + IAM Toggles

Terraform now exposes environment-level toggles for feedback API access/iam:
- `manage_feedback_api_invoker_iam` (default `true` in envs)
- `feedback_api_allow_public_invoker` (default `false`)
- `feedback_api_additional_invoker_members` (default `[]`)
- `feedback_api_cloud_run_service_name` (default `quizfeedbackapi`)
- `feedback_api_region` (default `us-central1`)
- `manage_feedback_api_runtime_project_roles` (default `false`)
- `feedback_api_runtime_service_account_email` + `feedback_api_runtime_project_roles`

Common use:
- Keep staging closed: `feedback_api_allow_public_invoker = false`
- Temporarily open public invoker (if needed): set to `true`, `terraform apply`
- Re-close: set back to `false`, `terraform apply`

Current Phase 7 exception policy:
- staging may set `feedback_api_allow_public_invoker = true` temporarily to allow Hosting rewrite traffic.
- production must keep `feedback_api_allow_public_invoker = false` until Phase 7.5 edge hardening is complete.

Note:
- Terraform can only manage Cloud Run IAM after the feedback function has been deployed at least once (service exists).
- Firestore rules/indexes deploy requires a Firestore database in the project.
  Use `enable_firestore_database = true` to create/manage `(default)` via Terraform.
  If a database already exists, import it before enabling management.

## Import Notes
If an existing GCP project or Firebase Hosting site already exists, import resources before apply.

Examples:

```zsh
# Existing project (when create_project = false)
terraform import 'module.firebase_foundation.google_firebase_project.this' <project-id>

# Existing hosting site
terraform import 'module.firebase_foundation.google_firebase_hosting_site.default[0]' projects/<project-id>/sites/<site-id>

# Existing Firestore default database
terraform import 'module.firebase_foundation.google_firestore_database.default[0]' 'projects/<project-id>/databases/(default)'
```

## CI Authentication Recommendation
- Use GitHub OIDC Workload Identity Federation for deploy/auth.
- Avoid long-lived JSON service account keys.

## Helper Script: GitHub WIF + Secrets

Use `infra/scripts/setup_github_wif.sh` to:
- create/update workload identity pool + provider,
- grant `roles/iam.workloadIdentityUser` on the deploy service account,
- set GitHub repo secrets for a custom WIF-based deploy workflow.

Note: the current staging/production workflows use Firebase's official Hosting
action with:
- `FIREBASE_SERVICE_ACCOUNT_STAGING`
- `FIREBASE_SERVICE_ACCOUNT_PRODUCTION`

Legacy compatibility:
- The workflows also accept secrets with a trailing underscore
  (`..._STAGING_`, `..._PRODUCTION_`) from earlier script output.

Use `infra/scripts/set_firebase_service_account_secret.sh`
to generate a service-account JSON key and set the environment-specific GitHub secret.

Example (staging):

```zsh
infra/scripts/set_firebase_service_account_secret.sh \
  --environment staging
```

Example (production, standard project naming):

```zsh
infra/scripts/set_firebase_service_account_secret.sh \
  --environment production
```

Example (production, custom project id and optional additional legacy secret name):

```zsh
infra/scripts/set_firebase_service_account_secret.sh \
  --environment production \
  --project-id mindblast-prod \
  --also-set-secret FIREBASE_SERVICE_ACCOUNT_PRODUCTION_
```

Example (staging):

```zsh
infra/scripts/setup_github_wif.sh --project-id mindblast-staging
```

Example (production):

```zsh
infra/scripts/setup_github_wif.sh --project-id mindblast-prod
```

Optional override when auto-detect does not match:

```zsh
infra/scripts/setup_github_wif.sh \
  --project-id mindblast-staging \
  --service-account mindblast-staging-gha@mindblast-staging.iam.gserviceaccount.com \
  --repo owner/repo
```
