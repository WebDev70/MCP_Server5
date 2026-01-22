from usaspending_mcp.http_app import app
import inspect

print(f"App Type: {type(app)}")
print(f"Routes: {app.routes}")

for r in app.routes:
    print(f"Path: {r.path}, Name: {r.name}, Methods: {getattr(r, 'methods', 'ALL')}")
    if hasattr(r, 'endpoint'):
        print(f"  Endpoint: {r.endpoint}")
