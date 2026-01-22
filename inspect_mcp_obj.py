from usaspending_mcp.server import mcp
import inspect

print(f"FastMCP Object: {mcp}")
print(f"Has session_manager? {hasattr(mcp, 'session_manager')}")
if hasattr(mcp, 'session_manager'):
    print(f"Session Manager: {mcp.session_manager}")
    
# Check if we can find where the TaskGroup is initialized
print(f"Dir: {dir(mcp)}")
