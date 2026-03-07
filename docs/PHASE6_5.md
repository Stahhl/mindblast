# Phase 6.5 Specification: Terraform Access/IAM Parameterization

## Goal

Make staging/production feedback API access controls reproducible from source control, without ad-hoc `gcloud` IAM edits.

## Motivation

Phase 6 introduced backend deploy/runtime operations that required manual invoker/IAM commands during debugging.
For an internet-facing and billable environment, we need deterministic, reviewable toggles in Terraform.

## Scope

1. Add Terraform variables to manage feedback API Cloud Run invoker policy:
   - `manage_feedback_api_invoker_iam`
   - `feedback_api_allow_public_invoker`
   - `feedback_api_additional_invoker_members`
   - `feedback_api_cloud_run_service_name`
   - `feedback_api_region`
2. Add Terraform variables/resources for runtime service-account project roles:
   - `manage_feedback_api_runtime_project_roles`
   - `feedback_api_runtime_service_account_email`
   - `feedback_api_runtime_project_roles`
3. Keep environment defaults conservative:
   - no public invoker by default.
4. Update infra docs and examples for toggling these values safely.

## Out of Scope

- Full Terraform ownership of function deployment artifacts.
- Runtime service account redesign/least-privilege migration.
- WIF migration for GitHub deploy auth.

## Acceptance Criteria

- `terraform apply` can toggle public invoker access without manual `gcloud` IAM commands.
- Runtime project roles for the configured function service account can be added/removed through Terraform variables.
- Staging and production have the same toggle model in source-controlled env configs.

## Operator Examples

Keep staging closed (default):

```hcl
# infra/terraform/envs/staging/terraform.tfvars
manage_feedback_api_invoker_iam = true
feedback_api_allow_public_invoker = false
```

Temporarily allow public invoker:

```hcl
# infra/terraform/envs/staging/terraform.tfvars
manage_feedback_api_invoker_iam = true
feedback_api_allow_public_invoker = true
```

Apply:

```zsh
cd infra/terraform/envs/staging
terraform plan
terraform apply
```
