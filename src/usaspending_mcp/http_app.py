import os
import uvicorn
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from usaspending_mcp.server import mcp

# Initialize logger
logger = logging.getLogger("uvicorn.error")

# Initialize FastAPI with simple setup
app = FastAPI(title="USAspending MCP Server")

# Add Trusted Host Middleware - Allow all hosts for Cloud Run
# This must be added before other middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"],  # Allow all hosts (Cloud Run generates dynamic hostnames)
)

# Add CORS Middleware - Critical for browser-based clients like ChatGPT
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
    logger.info(f"Query Params: {request.query_params}")
    logger.info(f"Headers: {request.headers}")
    response = await call_next(request)
    return response

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "USAspending MCP Server",
        "endpoints": {
            "health": "/healthz",
            "mcp": "/mcp"
        }
    }

# Mount MCP Streamable HTTP app for HTTP transport
# This provides /mcp endpoint for ChatGPT and other MCP clients
# Streamable HTTP is the modern standard (SSE is deprecated)
mcp_app = mcp.streamable_http_app()
app.mount("/mcp", mcp_app)

def main():
    """
    Entrypoint for HTTP transport (Cloud Run compatible).
    """
    port = int(os.getenv("PORT", "8080"))
    log_level = os.getenv("LOG_LEVEL", "info")
    print(f"Starting server on port {port} with log level {log_level}...")
    # Using proxy_headers=True for Cloud Run/Load Balancer support
    uvicorn.run("usaspending_mcp.http_app:app", host="0.0.0.0", port=port, log_level=log_level, proxy_headers=True)

if __name__ == "__main__":
    main()
