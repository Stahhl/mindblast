#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  set_firebase_service_account_secret.sh --environment <env> [options]

Required:
  --environment <env>              Environment name (e.g. staging, prod, production).

Optional:
  --project-id <id>                Full GCP project ID override.
  --project-prefix <prefix>        Prefix used to derive project ID. Default: mindblast
  --repo <owner/repo>              GitHub repository slug. Defaults to origin remote.
  --service-account <email>        Service account email override.
  --secret-prefix <prefix>         Secret prefix. Default: FIREBASE_SERVICE_ACCOUNT
  --also-set-secret <name>         Also write the same JSON to an additional secret name.
  --help                           Show this help.

Defaults:
  project_id: "<project-prefix>-<environment>"
  (special case: environment=production -> suffix "prod")
  secret: "<secret-prefix>_<ENV_UPPER>"
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

ENVIRONMENT=""
PROJECT_ID=""
PROJECT_PREFIX="mindblast"
REPO_SLUG=""
SERVICE_ACCOUNT_EMAIL=""
SECRET_PREFIX="FIREBASE_SERVICE_ACCOUNT"
ALSO_SET_SECRET=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --environment)
      ENVIRONMENT="${2:-}"
      shift 2
      ;;
    --project-id)
      PROJECT_ID="${2:-}"
      shift 2
      ;;
    --project-prefix)
      PROJECT_PREFIX="${2:-}"
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
    --secret-prefix)
      SECRET_PREFIX="${2:-}"
      shift 2
      ;;
    --also-set-secret)
      ALSO_SET_SECRET="${2:-}"
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

if [[ -z "$ENVIRONMENT" ]]; then
  echo "Missing required argument: --environment" >&2
  usage
  exit 1
fi

require_cmd git
require_cmd gcloud
require_cmd gh

lower_env="$(printf '%s' "$ENVIRONMENT" | tr '[:upper:]' '[:lower:]')"
project_env_suffix="$lower_env"
if [[ "$lower_env" == "production" ]]; then
  project_env_suffix="prod"
fi

if [[ -z "$PROJECT_ID" ]]; then
  PROJECT_ID="${PROJECT_PREFIX}-${project_env_suffix}"
fi

upper_env="$(printf '%s' "$lower_env" | tr '[:lower:]' '[:upper:]' | tr -c 'A-Z0-9' '_')"
while [[ "$upper_env" == _* ]]; do
  upper_env="${upper_env#_}"
done
while [[ "$upper_env" == *_ ]]; do
  upper_env="${upper_env%_}"
done
SECRET_NAME="${SECRET_PREFIX}_${upper_env}"

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

umask 077
KEY_FILE="$(mktemp -t "${PROJECT_ID}-${lower_env}-sa-key-XXXXXX.json")"
cleanup() {
  rm -f "$KEY_FILE"
}
trap cleanup EXIT

echo "Creating service account key for: $SERVICE_ACCOUNT_EMAIL"
gcloud iam service-accounts keys create "$KEY_FILE" \
  --iam-account "$SERVICE_ACCOUNT_EMAIL" \
  --project "$PROJECT_ID" >/dev/null

echo "Setting GitHub secret: $SECRET_NAME (repo: $REPO_SLUG)"
gh secret set "$SECRET_NAME" --repo "$REPO_SLUG" < "$KEY_FILE"

if [[ -n "$ALSO_SET_SECRET" ]]; then
  echo "Setting additional GitHub secret: $ALSO_SET_SECRET (repo: $REPO_SLUG)"
  gh secret set "$ALSO_SET_SECRET" --repo "$REPO_SLUG" < "$KEY_FILE"
fi

echo "Done."
echo "Project: $PROJECT_ID"
echo "Service account: $SERVICE_ACCOUNT_EMAIL"
echo "Secret name: $SECRET_NAME"
if [[ -n "$ALSO_SET_SECRET" ]]; then
  echo "Additional secret: $ALSO_SET_SECRET"
fi
