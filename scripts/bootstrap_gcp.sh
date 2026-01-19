#!/bin/bash
set -euo pipefail

# Configuration
PROJECT_ID=${PROJECT_ID}
REGION=${REGION:-"us-central1"}
SERVICE_NAME=${SERVICE_NAME:-"usaspending-mcp"}
AR_REPO=${AR_REPO:-"usaspending-mcp"}
RUNTIME_SA_NAME="${SERVICE_NAME}-runtime"
DEPLOYER_SA_NAME="${SERVICE_NAME}-deployer"

if [ -z "$PROJECT_ID" ]; then
    echo "Error: PROJECT_ID environment variable is required."
    echo "Usage: PROJECT_ID=... ./scripts/bootstrap_gcp.sh"
    exit 1
fi

echo "Bootstrapping GCP resources for project: $PROJECT_ID in $REGION"

# 1. Enable APIs
echo "Enabling APIs..."
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com \
    --project "$PROJECT_ID"

# 2. Create Artifact Registry Repo
echo "Checking Artifact Registry..."
if ! gcloud artifacts repositories describe "$AR_REPO" --location="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "Creating Artifact Registry repository: $AR_REPO..."
    gcloud artifacts repositories create "$AR_REPO" \
        --repository-format=docker \
        --location="$REGION" \
        --description="Docker repository for USAspending MCP" \
        --project="$PROJECT_ID"
else
    echo "Artifact Registry repository $AR_REPO already exists."
fi

# 3. Create Service Accounts

# A) Runtime SA
echo "Checking Runtime Service Account ($RUNTIME_SA_NAME)..."
RUNTIME_SA_EMAIL="${RUNTIME_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
if ! gcloud iam service-accounts describe "$RUNTIME_SA_EMAIL" --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "Creating Runtime SA..."
    gcloud iam service-accounts create "$RUNTIME_SA_NAME" \
        --display-name="Runtime SA for $SERVICE_NAME" \
        --project="$PROJECT_ID"
else
    echo "Runtime SA $RUNTIME_SA_EMAIL already exists."
fi

# B) Deployer SA
echo "Checking Deployer Service Account ($DEPLOYER_SA_NAME)..."
DEPLOYER_SA_EMAIL="${DEPLOYER_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
if ! gcloud iam service-accounts describe "$DEPLOYER_SA_EMAIL" --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "Creating Deployer SA..."
    gcloud iam service-accounts create "$DEPLOYER_SA_NAME" \
        --display-name="Cloud Build Deployer for $SERVICE_NAME" \
        --project="$PROJECT_ID"
else
    echo "Deployer SA $DEPLOYER_SA_EMAIL already exists."
fi

# 4. Grant Roles to Deployer SA
echo "Granting IAM roles to Deployer SA..."

# Allow Deployer to act as Runtime SA (needed to deploy Cloud Run with custom SA)
gcloud iam service-accounts add-iam-policy-binding "$RUNTIME_SA_EMAIL" \
    --member="serviceAccount:$DEPLOYER_SA_EMAIL" \
    --role="roles/iam.serviceAccountUser" \
    --project="$PROJECT_ID" >/dev/null

# Allow Deployer to push to Artifact Registry
gcloud artifacts repositories add-iam-policy-binding "$AR_REPO" \
    --location="$REGION" \
    --member="serviceAccount:$DEPLOYER_SA_EMAIL" \
    --role="roles/artifactregistry.writer" \
    --project="$PROJECT_ID" >/dev/null

# Allow Deployer to administer Cloud Run services (scoped to project for now, could be tighter)
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$DEPLOYER_SA_EMAIL" \
    --role="roles/run.admin" >/dev/null

echo "----------------------------------------------------------------"
echo "Setup complete!"
echo "Runtime SA:  $RUNTIME_SA_EMAIL"
echo "Deployer SA: $DEPLOYER_SA_EMAIL"
echo ""
echo "To grant a user permission to invoke the service (private by default):"
echo "  gcloud run services add-iam-policy-binding $SERVICE_NAME \"
    --region $REGION --project $PROJECT_ID \"
    --member='user:USER_EMAIL' \"
    --role='roles/run.invoker'"
echo "----------------------------------------------------------------"
