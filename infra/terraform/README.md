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
- Required Google APIs for Firebase hosting workflows.
- Firebase project enablement.
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

## Import Notes
If an existing GCP project or Firebase Hosting site already exists, import resources before apply.

Examples:

```zsh
# Existing project (when create_project = false)
terraform import 'module.firebase_foundation.google_firebase_project.this' <project-id>

# Existing hosting site
terraform import 'module.firebase_foundation.google_firebase_hosting_site.default[0]' projects/<project-id>/sites/<site-id>
```

## CI Authentication Recommendation
- Use GitHub OIDC Workload Identity Federation for deploy/auth.
- Avoid long-lived JSON service account keys.

## Helper Script: GitHub WIF + Secrets

Use `/Users/stahl/dev/mindblast/infra/scripts/setup_github_wif.sh` to:
- create/update workload identity pool + provider,
- grant `roles/iam.workloadIdentityUser` on the deploy service account,
- set GitHub repo secrets for a custom WIF-based deploy workflow.

Note: the current staging workflow uses Firebase's official Hosting action with
`FIREBASE_SERVICE_ACCOUNT_STAGING` instead of WIF.

Use `/Users/stahl/dev/mindblast/infra/scripts/set_firebase_service_account_secret.sh`
to generate a service-account JSON key and set the environment-specific GitHub secret.

Example (staging):

```zsh
/Users/stahl/dev/mindblast/infra/scripts/set_firebase_service_account_secret.sh \
  --environment staging
```

Example (production, standard project naming):

```zsh
/Users/stahl/dev/mindblast/infra/scripts/set_firebase_service_account_secret.sh \
  --environment production
```

Example (production, custom project id and additional legacy secret name):

```zsh
/Users/stahl/dev/mindblast/infra/scripts/set_firebase_service_account_secret.sh \
  --environment production \
  --project-id mindblast-prod \
  --also-set-secret FIREBASE_SERVICE_ACCOUNT
```

Example (staging):

```zsh
/Users/stahl/dev/mindblast/infra/scripts/setup_github_wif.sh --project-id mindblast-staging
```

Example (production):

```zsh
/Users/stahl/dev/mindblast/infra/scripts/setup_github_wif.sh --project-id mindblast-prod
```

Optional override when auto-detect does not match:

```zsh
/Users/stahl/dev/mindblast/infra/scripts/setup_github_wif.sh \
  --project-id mindblast-staging \
  --service-account mindblast-staging-gha@mindblast-staging.iam.gserviceaccount.com \
  --repo owner/repo
```
