#!/bin/bash
set -e

PROJECT_ID=${PROJECT_ID}
REGION=${REGION:-"us-central1"}
SERVICE_NAME=${SERVICE_NAME:-"usaspending-mcp"}

if [ -z "$PROJECT_ID" ]; then
    echo "Error: PROJECT_ID environment variable is required."
    exit 1
fi

gcloud run services describe "$SERVICE_NAME" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --format "value(status.url)"

