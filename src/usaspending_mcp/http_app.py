import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Mount

from usaspending_mcp.server import mcp

# Initialize logger
logger = logging.getLogger("uvicorn.error")

# -----------------------------------------------------------------------------
# LIFECYCLE MANAGEMENT
# -----------------------------------------------------------------------------
# This is the critical fix. We manually extract the lifespan context from the 
# FastMCP Starlette app and ensure it runs when FastAPI starts.
# This initializes the 'TaskGroup' that caused the 500 crashes.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Get the underlying Starlette app from FastMCP
    mcp_starlette_app = mcp.streamable_http_app()
    
    # Trigger its startup logic
    async with mcp_starlette_app.router.lifespan_context(mcp_starlette_app):
        logger.info("FastMCP Internal Server Started")
        yield
        logger.info("FastMCP Internal Server Stopped")

# -----------------------------------------------------------------------------
# MAIN APP SETUP
# -----------------------------------------------------------------------------
app = FastAPI(
    title="USAspending MCP Server", 
    lifespan=lifespan
)

# Middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"], # Fixes 421 errors
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_request_info(request: Request, call_next):
    logger.info(f"Incoming Request: {request.method} {request.url}")
    response = await call_next(request)
    return response

# -----------------------------------------------------------------------------
# ROUTES
# -----------------------------------------------------------------------------

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "USAspending MCP Server",
        "instructions": "Connect Claude Desktop to the URL below.",
        "mcp_endpoint": "/mcp", 
        "note": "FastMCP uses a single endpoint '/mcp' for both SSE (GET) and Messages (POST)."
    }

# Mount the MCP app
# We mount it at root "/" so that "/mcp" is accessible directly.
# Using 'app.mount' with the lifespan wrapper above ensures safety.
mcp_app = mcp.streamable_http_app()
app.mount("/", mcp_app)

def main():
    port = int(os.getenv("PORT", "8080"))
    log_level = os.getenv("LOG_LEVEL", "info")
    print(f"Starting server on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level=log_level, proxy_headers=True)

if __name__ == "__main__":
    main()
