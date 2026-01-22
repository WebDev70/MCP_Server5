from usaspending_mcp.http_app import app
from starlette.routing import Mount, Route

print(" Inspecting Routes ".center(50, "="))

def print_routes(routes, prefix=""):
    for route in routes:
        if isinstance(route, Mount):
            print(f"Mount: {prefix}{route.path} -> {route.name}")
            # Recurse if possible, but Starlette Mounts hide the sub-app routes often
            # We can try to peek if it's a Starlette app
            if hasattr(route.app, "routes"):
                print_routes(route.app.routes, prefix=f"{prefix}{route.path}")
        elif isinstance(route, Route):
            methods = getattr(route, "methods", None)
            methods_str = ", ".join(methods) if methods else "ALL"
            print(f"Route: {prefix}{route.path} [{methods_str}]")
        else:
            print(f"Other: {prefix}{route.path} ({type(route).__name__})")

print_routes(app.routes)
print("=" * 50)
