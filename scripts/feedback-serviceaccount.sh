#!/usr/bin/env bash

PROJECT_ID="mindblast-prod"
SERVICE_ACCOUNT_ID="prod-feedback-report-reader"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_ID}@${PROJECT_ID}.iam.gserviceaccount.com"
KEY_FILE="$(mktemp -t feedback-report-prod-XXXXXX.json)"

gcloud iam service-accounts create "${SERVICE_ACCOUNT_ID}" \
  --project "${PROJECT_ID}" \
  --display-name "Mindblast feedback report reader"

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member "serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role "roles/datastore.viewer"

gcloud iam service-accounts keys create "${KEY_FILE}" \
  --iam-account "${SERVICE_ACCOUNT_EMAIL}" \
  --project "${PROJECT_ID}"

gh secret set FEEDBACK_REPORT_FIREBASE_SERVICE_ACCOUNT_PRODUCTION \
  --repo Stahhl/mindblast < "${KEY_FILE}"

rm -f "${KEY_FILE}"
