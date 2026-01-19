import os
import uvicorn
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from usaspending_mcp.server import mcp

# Initialize logger
logger = logging.getLogger("uvicorn.error")

# Initialize FastAPI with simple setup
app = FastAPI(title="USAspending MCP Server")

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

# Mount MCP SSE app for HTTP transport
# This provides /mcp/sse and /mcp/messages endpoints
mcp_app = mcp.sse_app()
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
