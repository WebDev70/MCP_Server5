import asyncio
import uvicorn
from multiprocessing import Process
import time
import httpx
from usaspending_mcp.http_app import app

def run_server():
    uvicorn.run(app, port=8081)

async def test_endpoint(path):
    async with httpx.AsyncClient() as client:
        print(f"Testing {path}...")
        try:
            response = await client.get(f"http://localhost:8081{path}", timeout=2)
            print(f"Status: {response.status_code}")
            print(f"Headers: {response.headers}")
            print(f"Content start: {response.text[:100]}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    p = Process(target=run_server)
    p.start()
    time.sleep(2) # Wait for startup
    
    try:
        asyncio.run(test_endpoint("/mcp"))
        asyncio.run(test_endpoint("/sse"))
        asyncio.run(test_endpoint("/healthz"))
    finally:
        p.terminate()
