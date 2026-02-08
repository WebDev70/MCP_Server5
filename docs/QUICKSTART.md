# USAspending MCP Server - Quickstart Guide

Get the server running and tested in minutes.

## Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- Docker (for integration tests and containerization)
- Google Cloud SDK (for Cloud Run deployment)

## Setup

```bash
# Install dependencies
uv sync

# Create .env from example
cp .env.example .env
```

## Quick Start (Makefile)

The easiest way to run common tasks:

- **Linting:** `make lint`
- **Unit Tests:** `make unit`
- **Integration Tests:** `make integration` (Runs mock server + app + tests in Docker)
- **Run StdIO:** `make run-stdio` (For Claude Desktop / MCP Clients)
- **Run HTTP:** `make run-http` (For Cloud Run simulation)

---

## Local Development

### 1. StdIO Mode (Default for MCP)
```bash
PYTHONPATH=src uv run python -m usaspending_mcp.stdio_server
```

### 2. HTTP Mode (FastAPI)
```bash
PYTHONPATH=src uv run uvicorn usaspending_mcp.http_app:app --host 127.0.0.1 --port 8080
```
- Health: `curl http://localhost:8080/healthz`
- Ready: `curl http://localhost:8080/readyz`

### 3. Mock Server
If you want to run the mock USAspending API locally without Docker:
```bash
# Add current dir to python path
export PYTHONPATH=$PYTHONPATH:.
uv run python -m mock_usaspending.app
```
Mock server runs on port `8081`.

---

## Docker

```bash
# Build
make build

# Run
docker run -e PORT=8080 -p 8080:8080 usaspending-mcp
```

---

## GCP Deployment (Cloud Run)

### 1. Bootstrap Infrastructure (One-time)
```bash
PROJECT_ID=your-project-id ./scripts/bootstrap_gcp.sh
```

### 2. Deploy
```bash
PROJECT_ID=your-project-id ./scripts/deploy_cloud_run.sh
```

---

## Testing

The project uses `pytest` with markers:

```bash
# Run unit tests (logic only)
uv run pytest -m unit

# Run metrics tests (performance/cost validation)
uv run pytest -m metrics

# Run integration tests (real/mock network)
uv run pytest -m integration
```

---

## First MCP Tool Call (Example)

Test the orchestrator with a natural language question:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "answer_award_spending_question",
    "arguments": {
      "question": "Top 10 awards for DoD in FY2024"
    }
  }
}
```

## Next Steps

1. Read `docs/prd.md` for requirements and success metrics.
2. Follow `docs/PromptGuide.txt` for development history.
3. See `docs/runbook.md` for operational details.