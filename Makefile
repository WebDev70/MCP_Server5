.PHONY: all unit integration lint build run-http run-stdio clean

all: lint unit

unit:
	@echo "Running unit tests..."
	uv run pytest -q -m "not integration"

integration:
	@echo "Running integration tests..."
	docker compose --profile test up --build --exit-code-from tests

lint:
	@echo "Running lint and format check..."
	uv run ruff check .
	uv run ruff format --check .

lint-fix:
	@echo "Fixing lint errors..."
	uv run ruff check --fix .
	uv run ruff format .

build:
	@echo "Building Docker image..."
	docker build -t usaspending-mcp .

run-http:
	@echo "Starting HTTP server..."
	uv run uvicorn usaspending_mcp.http_app:app --host 0.0.0.0 --port 8080 --reload

run-stdio:
	@echo "Starting StdIO server..."
	uv run python -m usaspending_mcp.stdio_server

clean:
	@echo "Cleaning up..."
	rm -rf .venv/ __pycache__/ .pytest_cache/ .coverage coverage.xml dist/ build/
	docker compose --profile test down -v
