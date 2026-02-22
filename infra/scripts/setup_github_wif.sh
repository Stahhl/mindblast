#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  setup_github_wif.sh --project-id <gcp-project-id> [options]

Required:
  --project-id <id>                 GCP/Firebase project ID.

Optional:
  --repo <owner/repo>               GitHub repo slug. Defaults to origin remote.
  --service-account <email>         Deployer service account email.
                                    Defaults to first account with display name:
                                    "GitHub Actions deployer for Mindblast".
  --pool-id <id>                    Workload identity pool ID. Default: github-actions
  --provider-id <id>                Workload identity provider ID. Default: github
  --wif-secret-name <name>          GitHub secret name for provider resource.
                                    Default: GCP_WIF_PROVIDER
  --sa-secret-name <name>           GitHub secret name for service account email.
                                    Default: GCP_DEPLOY_SERVICE_ACCOUNT
  --help                            Show this help.
EOF
}

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd" >&2
    exit 1
  fi
}

parse_github_repo_slug() {
  local remote_url="$1"

  if [[ "$remote_url" =~ ^git@github\.com:(.+)/(.+)\.git$ ]]; then
    echo "${BASH_REMATCH[1]}/${BASH_REMATCH[2]}"
    return 0
  fi

  if [[ "$remote_url" =~ ^git@github\.com:(.+)/(.+)$ ]]; then
    echo "${BASH_REMATCH[1]}/${BASH_REMATCH[2]}"
    return 0
  fi

  if [[ "$remote_url" =~ ^https://github\.com/(.+)/(.+)\.git$ ]]; then
    echo "${BASH_REMATCH[1]}/${BASH_REMATCH[2]}"
    return 0
  fi

  if [[ "$remote_url" =~ ^https://github\.com/(.+)/(.+)$ ]]; then
    echo "${BASH_REMATCH[1]}/${BASH_REMATCH[2]}"
    return 0
  fi

  if [[ "$remote_url" =~ ^ssh://git@github\.com/(.+)/(.+)\.git$ ]]; then
    echo "${BASH_REMATCH[1]}/${BASH_REMATCH[2]}"
    return 0
  fi

  if [[ "$remote_url" =~ ^ssh://git@github\.com/(.+)/(.+)$ ]]; then
    echo "${BASH_REMATCH[1]}/${BASH_REMATCH[2]}"
    return 0
  fi

  return 1
}

PROJECT_ID=""
REPO_SLUG=""
SERVICE_ACCOUNT_EMAIL=""
POOL_ID="github-actions"
PROVIDER_ID="github"
WIF_SECRET_NAME="GCP_WIF_PROVIDER"
SA_SECRET_NAME="GCP_DEPLOY_SERVICE_ACCOUNT"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-id)
      PROJECT_ID="${2:-}"
      shift 2
      ;;
    --repo)
      REPO_SLUG="${2:-}"
      shift 2
      ;;
    --service-account)
      SERVICE_ACCOUNT_EMAIL="${2:-}"
      shift 2
      ;;
    --pool-id)
      POOL_ID="${2:-}"
      shift 2
      ;;
    --provider-id)
      PROVIDER_ID="${2:-}"
      shift 2
      ;;
    --wif-secret-name)
      WIF_SECRET_NAME="${2:-}"
      shift 2
      ;;
    --sa-secret-name)
      SA_SECRET_NAME="${2:-}"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$PROJECT_ID" ]]; then
  echo "Missing required argument: --project-id" >&2
  usage
  exit 1
fi

require_cmd git
require_cmd gcloud
require_cmd gh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [[ -z "$REPO_SLUG" ]]; then
  REMOTE_URL="$(git -C "$REPO_ROOT" remote get-url origin)"
  if ! REPO_SLUG="$(parse_github_repo_slug "$REMOTE_URL")"; then
    echo "Could not parse GitHub repo slug from origin remote: $REMOTE_URL" >&2
    echo "Pass --repo <owner/repo> explicitly." >&2
    exit 1
  fi
fi

if [[ -z "$SERVICE_ACCOUNT_EMAIL" ]]; then
  SERVICE_ACCOUNT_EMAIL="$(
    gcloud iam service-accounts list \
      --project="$PROJECT_ID" \
      --filter='displayName="GitHub Actions deployer for Mindblast"' \
      --format='value(email)' \
      | head -n 1
  )"
fi

if [[ -z "$SERVICE_ACCOUNT_EMAIL" ]]; then
  echo "Could not find deploy service account in project $PROJECT_ID." >&2
  echo "Pass --service-account <email> explicitly." >&2
  exit 1
fi

PROJECT_NUMBER="$(
  gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)'
)"

if [[ -z "$PROJECT_NUMBER" ]]; then
  echo "Failed to resolve project number for $PROJECT_ID." >&2
  exit 1
fi

ATTRIBUTE_MAPPING="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner"
ATTRIBUTE_CONDITION="assertion.repository=='${REPO_SLUG}'"

echo "Project: $PROJECT_ID ($PROJECT_NUMBER)"
echo "Repository: $REPO_SLUG"
echo "Service account: $SERVICE_ACCOUNT_EMAIL"
echo "Pool/provider: $POOL_ID / $PROVIDER_ID"

if gcloud iam workload-identity-pools describe "$POOL_ID" \
  --project="$PROJECT_ID" \
  --location="global" >/dev/null 2>&1; then
  echo "Workload identity pool already exists: $POOL_ID"
else
  echo "Creating workload identity pool: $POOL_ID"
  gcloud iam workload-identity-pools create "$POOL_ID" \
    --project="$PROJECT_ID" \
    --location="global" \
    --display-name="GitHub Actions"
fi

if gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" \
  --project="$PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="$POOL_ID" >/dev/null 2>&1; then
  echo "Updating workload identity provider: $PROVIDER_ID"
  gcloud iam workload-identity-pools providers update-oidc "$PROVIDER_ID" \
    --project="$PROJECT_ID" \
    --location="global" \
    --workload-identity-pool="$POOL_ID" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="$ATTRIBUTE_MAPPING" \
    --attribute-condition="$ATTRIBUTE_CONDITION"
else
  echo "Creating workload identity provider: $PROVIDER_ID"
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
    --project="$PROJECT_ID" \
    --location="global" \
    --workload-identity-pool="$POOL_ID" \
    --display-name="GitHub OIDC" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="$ATTRIBUTE_MAPPING" \
    --attribute-condition="$ATTRIBUTE_CONDITION"
fi

PRINCIPAL_SET="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${REPO_SLUG}"

echo "Granting roles/iam.workloadIdentityUser on $SERVICE_ACCOUNT_EMAIL"
gcloud iam service-accounts add-iam-policy-binding "$SERVICE_ACCOUNT_EMAIL" \
  --project="$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="$PRINCIPAL_SET" >/dev/null

WIF_PROVIDER_RESOURCE="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/providers/${PROVIDER_ID}"

echo "Setting GitHub secret: $WIF_SECRET_NAME"
gh secret set "$WIF_SECRET_NAME" --repo "$REPO_SLUG" --body "$WIF_PROVIDER_RESOURCE"

echo "Setting GitHub secret: $SA_SECRET_NAME"
gh secret set "$SA_SECRET_NAME" --repo "$REPO_SLUG" --body "$SERVICE_ACCOUNT_EMAIL"

echo "Done."
echo "WIF provider: $WIF_PROVIDER_RESOURCE"
echo "Service account: $SERVICE_ACCOUNT_EMAIL"

