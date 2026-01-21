import logging
import os

import uvicorn
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Route

from usaspending_mcp.server import mcp

# Initialize logger
logger = logging.getLogger("uvicorn.error")

async def healthz(request):
    return JSONResponse({"status": "ok"})

async def root(request):
    return JSONResponse({
        "status": "online",
        "service": "USAspending MCP Server",
        "mcp_endpoint": "/mcp",
        "protocol": "MCP Streamable HTTP (POST /mcp for requests)",
        "endpoints": {
            "health": "/healthz",
            "mcp": "/mcp"
        }
    })

# Get the base Starlette app from FastMCP
# We do this to ensure the Lifecycle logic (TaskGroups) runs as the main app
app = mcp.streamable_http_app()

# Add our custom routes
# Note: FastMCP app is a Starlette app, so we can access .routes
app.routes.append(Route("/healthz", healthz))
app.routes.append(Route("/", root))

# Add Middleware
# Note: Starlette middleware is usually added at construction, but we can wrap the app
# or insert into the middleware stack if we are careful.
# However, FastMCP might already have middleware.
# The safest way to add middleware to an existing Starlette app is to wrap it,
# BUT wrapping it might hide the lifespan.
# LUCKILY, uvicorn handles the lifespan of the wrapped app if we use Middleware properly.

# Let's inspect if we can add middleware to the app instance directly.
# Starlette apps allow app.add_middleware()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"],
)

def main():
    """
    Entrypoint for HTTP transport (Cloud Run compatible).
    """
    port = int(os.getenv("PORT", "8080"))
    log_level = os.getenv("LOG_LEVEL", "info")
    print(f"Starting server on port {port} with log level {log_level}...")
    # Using proxy_headers=True for Cloud Run/Load Balancer support
    uvicorn.run(app, host="0.0.0.0", port=port, log_level=log_level, proxy_headers=True)

if __name__ == "__main__":
    main()
