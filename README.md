# USAspending MCP Server

A Model Context Protocol (MCP) server that enables Large Language Models (LLMs) to query and analyze federal award spending data from USAspending.gov.

This server acts as a middleware, translating natural language questions into efficient API queries to retrieve data on contracts, grants, loans, and other financial assistance.

## Key Features

- **Model Context Protocol Support:** Compatible with any MCP-enabled client (e.g., Claude Desktop, Gemini).
- **Intelligent Routing:** Automatically selects the most efficient USAspending.gov API endpoints.
- **Entity Resolution:** Resolves natural language names for agencies and recipients to canonical IDs.
- **Smart Caching:** Multi-tier in-memory caching for performance and API rate-limit protection.
- **Comprehensive Coverage:** Supports the full "all-awards" scope (Contracts, IDVs, Grants, Loans, Direct Payments).

## Core Tools

- **`answer_award_spending_question`**: Orchestrator for natural language Q&A.
- **`spending_rollups`**: Aggregated spending totals and "Top N" breakdowns.
- **`award_search`**: Detailed search for individual awards with filtering.
- **`award_explain`**: Deep dive into a specific award, its transactions, and subawards.
- **`agency_portfolio`**: Overview of an agency's spending and top recipients.
- **`recipient_profile`**: Summary of a recipient's federal award history.
- **`idv_vehicle_bundle`**: Specialized tracking for Indefinite Delivery Vehicles (IDVs).
- **`resolve_entities`**: Map names to IDs for Agencies and Recipients.

## Setup

The project uses `uv` for Python package management.

1.  **Install `uv`**:
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

2.  **Sync Dependencies**:
    ```bash
    uv sync
    ```

3.  **Configure Environment**:
    ```bash
    cp .env.example .env
    ```

## Usage

### Local Development (stdio)
Recommended for use with Claude Desktop or other local MCP clients.
```bash
make run-stdio
```

### Local HTTP Server
Starts a FastAPI server with an MCP endpoint at `/mcp`.
```bash
make run-http
```

### Testing
- **Unit Tests**: `make unit`
- **Integration Tests**: `make integration` (requires Docker)
- **Linting**: `make lint`

## Deployment

The server is designed to run on **Google Cloud Run**.

1.  **Bootstrap Infrastructure**:
    ```bash
    ./scripts/bootstrap_gcp.sh
    ```
2.  **Deploy**:
    ```bash
    ./scripts/deploy_cloud_run.sh
    ```

For detailed deployment and operations guidance, see [docs/runbook.md](docs/runbook.md).

## Documentation

- **[docs/QUICKSTART.md](docs/QUICKSTART.md)**: 5-minute setup guide.
- **[docs/apis.md](docs/apis.md)**: API endpoint mapping and reference.
- **[docs/prd.md](docs/prd.md)**: Product Requirement Document.
- **[docs/runbook.md](docs/runbook.md)**: Operations and monitoring guide.
- **[GEMINI.md](GEMINI.md)**: Project overview and development conventions.
