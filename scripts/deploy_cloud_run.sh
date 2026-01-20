#!/bin/bash
set -e

# Default values
PROJECT_ID=${PROJECT_ID}
REGION=${REGION:-"us-central1"}
SERVICE_NAME=${SERVICE_NAME:-"usaspending-mcp"}

if [ -z "$PROJECT_ID" ]; then
    echo "Error: PROJECT_ID environment variable is required."
    exit 1
fi

echo "Deploying $SERVICE_NAME to Cloud Run in $REGION (Project: $PROJECT_ID)..."

gcloud run deploy "$SERVICE_NAME" \
  --image "$IMAGE" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --port 8080 \
  --allow-unauthenticated \
  --set-env-vars DEFAULT_SCOPE_MODE=all_awards \
  --set-env-vars USASPENDING_BASE_URL=https://api.usaspending.gov/api/v2 \
  --set-env-vars USASPENDING_TIMEOUT_S=30 \
  --set-env-vars USASPENDING_MAX_RETRIES=3 \
  --set-env-vars USASPENDING_BACKOFF_BASE_S=0.5 \
  --set-env-vars LOG_LEVEL=INFO \
  --set-env-vars FASTMCP_STATELESS_HTTP=true

echo "Deployment complete."

