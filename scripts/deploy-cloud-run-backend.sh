#!/usr/bin/env bash
# Deploy the NaturalCAD control-plane API to Cloud Run from apps/backend-api.
#
# Usage:
#   GCP_PROJECT_ID=your-project \
#   CLOUD_RUN_REGION=us-west1 \
#   CLOUD_RUN_ENV_FILE=apps/backend-api/cloudrun.env.yaml \
#   ./scripts/deploy-cloud-run-backend.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT/apps/backend-api"

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID to the Google Cloud project id}"

CLOUD_RUN_SERVICE="${CLOUD_RUN_SERVICE:-naturalcad-api}"
CLOUD_RUN_REGION="${CLOUD_RUN_REGION:-us-west1}"
CLOUD_RUN_ENV_FILE="${CLOUD_RUN_ENV_FILE:-}"

if ! command -v gcloud >/dev/null 2>&1; then
  echo "gcloud CLI is required. Install and authenticate with: gcloud auth login" >&2
  exit 1
fi

ENV_ARGS=()
if [[ -n "$CLOUD_RUN_ENV_FILE" ]]; then
  if [[ ! -f "$CLOUD_RUN_ENV_FILE" ]]; then
    echo "CLOUD_RUN_ENV_FILE does not exist: $CLOUD_RUN_ENV_FILE" >&2
    exit 1
  fi
  ENV_ARGS+=(--env-vars-file "$CLOUD_RUN_ENV_FILE")
fi

gcloud config set project "$GCP_PROJECT_ID" >/dev/null
gcloud services enable run.googleapis.com cloudbuild.googleapis.com --quiet

gcloud run deploy "$CLOUD_RUN_SERVICE" \
  --source "$BACKEND_DIR" \
  --region "$CLOUD_RUN_REGION" \
  --allow-unauthenticated \
  --port 8080 \
  --memory 512Mi \
  --cpu 1 \
  --timeout 300 \
  --no-cpu-throttling \
  --min-instances 1 \
  --max-instances 10 \
  "${ENV_ARGS[@]}" \
  --quiet

echo
echo "Cloud Run backend deployed:"
gcloud run services describe "$CLOUD_RUN_SERVICE" \
  --region "$CLOUD_RUN_REGION" \
  --format='value(status.url)'
