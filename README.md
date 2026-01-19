# USAspending MCP Server

A Model Context Protocol (MCP) server for USAspending.gov, enabling LLMs to answer federal award spending questions accurately.

## Setup

1.  Install `uv`:
    ```bash
    pip install uv
    ```

2.  Sync dependencies:
    ```bash
    uv sync
    ```

## Quick Start (Makefile)

- **Unit Tests:** `make unit`
- **Integration Tests:** `make integration` (requires Docker)
- **Lint:** `make lint`
- **Build:** `make build`
- **Run HTTP:** `make run-http`
- **Run StdIO:** `make run-stdio`

## Manual Running

### 1. Local Run (FastAPI/HTTP)
```bash
PYTHONPATH=src uv run uvicorn usaspending_mcp.http_app:app --host 0.0.0.0 --port 8080
```

### 2. Local StdIO (for Claude Desktop)
```bash
PYTHONPATH=src uv run python -m usaspending_mcp.stdio_server
```

### 3. Docker Run
```bash
docker build -t usaspending-mcp .
docker run -e PORT=8080 -p 8080:8080 usaspending-mcp
```
Test health: `curl http://localhost:8080/healthz`

### 3.a Docker Profiles                                                                    
docker compose --profile dev up -d--build                                                
  Or for both profiles: 
  docker compose --profile dev --profile test up -d --build 

## Cloud Run Deployment

### 0. Infrastructure Setup (One-time)
Bootstrap minimal GCP resources (APIs, Repo, Service Accounts) with least privileges:
```bash
PROJECT_ID=your-project REGION=us-central1 ./scripts/bootstrap_gcp.sh
```

### 1. Deploy Private
```bash
PROJECT_ID=your-project REGION=us-central1 ./scripts/deploy_cloud_run.sh
```

### 2. Grant Invoker Permissions
```bash
gcloud run services add-iam-policy-binding usaspending-mcp \
  --member="user:YOUR_EMAIL" \
  --role="roles/run.invoker" \
  --region us-central1 --project your-project
```

### 3. Call with Identity Token
```bash
SERVICE_URL=$(./scripts/get_service_url.sh)
TOKEN=$(gcloud auth print-identity-token)
curl -H "Authorization: Bearer $TOKEN" $SERVICE_URL/healthz
```

## CI/CD and Security

The `cloudbuild.yaml` supports optional security scanning. To enable:

```bash
gcloud builds submit --config cloudbuild.yaml --substitutions=_SECURITY_SCAN=true
```

Checks included:
- **pip-audit**: Scans dependencies for known vulnerabilities.
- **gitleaks**: Scans source for secrets.
- **trivy**: Scans the built container image for OS/package vulnerabilities.

## Testing

Run unit and integration tests:
```bash
uv run pytest -q
```

## Important Deployment Notes
- **Uvicorn Invariant:** `usaspending_mcp.http_app` exports the FastAPI `app` object.
- **Cloud Run CMD:** `uvicorn usaspending_mcp.http_app:app --host 0.0.0.0 --port ${PORT:-8080}`
- **Budgets:** The server enforces cost controls (max 5 requests per question).