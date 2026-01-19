# Base image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set working directory
WORKDIR /app

# Copy all source files needed for installation
COPY pyproject.toml .
COPY README.md .
COPY src/ src/

# Install dependencies
# Using system python environment in container for simplicity with cloud run
RUN uv pip install --system -e .

# Create a non-root user (optional but good practice)
# RUN useradd -m appuser && chown -R appuser /app
# USER appuser

# Expose port
EXPOSE ${PORT}

# Command to run the application
CMD ["sh", "-c", "uvicorn usaspending_mcp.http_app:app --host 0.0.0.0 --port ${PORT:-8080}"]
