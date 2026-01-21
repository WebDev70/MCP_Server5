import os
import uvicorn
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from usaspending_mcp.server import mcp

# Initialize logger
logger = logging.getLogger("uvicorn.error")

# Initialize FastAPI with simple setup
app = FastAPI(title="USAspending MCP Server", redirect_slashes=False)

# Add HTTPS Redirect - Critical for Cloud Run to prevent mixed content/insecure calls
# Note: In Cloud Run, the termination is at the GFE, but this helps consistent routing
# Only enable in production if needed, but for now let's use TrustedHost
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"],
)

# Add CORS Middleware
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

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.get("/mcp")
async def mcp_root_redirect():
    # If someone hits /mcp, they probably want the SSE endpoint info
    return {
        "message": "MCP Server is running",
        "sse_endpoint": "/mcp/sse",
        "messages_endpoint": "/mcp/messages"
    }

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "USAspending MCP Server",
        "mcp_connection_info": {
            "sse_url": "/mcp/sse",
            "messages_url": "/mcp/messages"
        },
        "endpoints": {
            "health": "/healthz",
            "mcp_base": "/mcp"
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
