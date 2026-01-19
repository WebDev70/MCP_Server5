import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from usaspending_mcp.server import mcp

# Readiness flag
is_ready = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    global is_ready
    # Startup logic
    print("USAspending MCP Server warming up...")
    # Optional: Pre-fetch catalog here if desired
    is_ready = True
    yield
    # Shutdown logic
    print("Shutting down...")

app = FastAPI(title="USAspending MCP Server", lifespan=lifespan)

# Add CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.get("/readyz")
async def readyz():
    if is_ready:
        return {"ready": "true"}
    return {"ready": "false"}, 503

# Mount MCP SSE app for HTTP transport
# sse_app() provides /sse and /messages endpoints
mcp_app = mcp.sse_app()
app.mount("/mcp", mcp_app)

def main():
    """
    Entrypoint for HTTP transport (Cloud Run compatible).
    """
    port = int(os.getenv("PORT", "8080"))
    log_level = os.getenv("LOG_LEVEL", "info")
    print(f"Starting server on port {port} with log level {log_level}...")
    uvicorn.run("usaspending_mcp.http_app:app", host="0.0.0.0", port=port, log_level=log_level)

if __name__ == "__main__":
    main()