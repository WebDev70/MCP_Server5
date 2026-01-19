# GEMINI.md

## Project Overview

This project is a Python-based **MCP (Model Context Protocol) Server** that acts as a middleware between a large language model (like Gemini) and the official **USAspending.gov API v2**. Its primary purpose is to enable the AI to reliably and efficiently answer complex questions about U.S. federal government award spending, including contracts, grants, loans, and other financial assistance.

The server is designed to be robust and efficient, implementing features like:
- **Smart Query Routing:** A router/planner component that selects the most efficient USAspending endpoint (e.g., preferring pre-calculated rollups over large data queries).
- **Entity Resolution:** Converts natural language queries for agencies, recipients, etc., into canonical IDs for the API.
- **Caching:** In-memory caching for reference data and common queries to improve performance and reduce API load.
- **Scope Management:** Supports different award scopes (`all_awards`, `contracts_only`, `assistance_only`).
- **Observability:** Provides detailed debugging information and structured logging.

The architecture is built to run locally on macOS and be deployed to **Google Cloud Run** as a containerized, stateless service.

## Building and Running

The project uses `uv` for Python package management.

### Local Development (stdio transport)

This mode is for running the server as a local process that communicates over standard input/output.

1.  **Install dependencies:**
    ```bash
    uv sync
    ```

2.  **Run unit tests:**
    ```bash
    uv run pytest -q -m "not integration"
    ```

3.  **Start the MCP server:**
    ```bash
    uv run python -m usaspending_mcp.stdio_server
    ```

### Local Development (HTTP transport)

This mode runs the server with a FastAPI web interface.

1.  **Install dependencies:**
    ```bash
    uv sync
    ```

2.  **Start the HTTP server:**
    ```bash
    uv run uvicorn usaspending_mcp.http_app:app --host 127.0.0.1 --port 8080
    ```

3.  **Test health endpoints:**
    ```bash
    curl http://localhost:8080/healthz
    ```

### Docker

The project includes a `Dockerfile` for containerization.

1.  **Build the Docker image:**
    ```bash
    docker build -t usaspending-mcp .
    ```

2.  **Run the container:**
    ```bash
    docker run -e PORT=8080 -p 8080:8080 usaspending-mcp
    ```

## Development Conventions

- **Dependency Management:** All Python dependencies are managed in `pyproject.toml` and installed using `uv`.
- **Testing:** The project uses `pytest`. Unit tests are separated from integration tests. A mock USAspending API is available for deterministic integration testing via `docker-compose`.
- **Configuration:** Environment variables are used for configuration (e.g., API URLs, timeouts, log levels). A `.env.example` file is provided as a template.
- **Code Structure:** The main application logic is located in the `src/usaspending_mcp/` directory, with a clear separation of concerns (server, client, tools, router).
- **Deployment:** The target deployment environment is Google Cloud Run, with scripts provided for deployment and smoke testing.
- **Error Handling:** The server is designed to handle API errors gracefully, with structured error responses, retries with backoff for rate limits, and clear logging.
