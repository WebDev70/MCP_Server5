import json
import os
import subprocess
import sys

import pytest


@pytest.mark.integration
def test_mcp_stdio_lifecycle():
    # Path to the module
    cmd = [sys.executable, "-m", "usaspending_mcp.stdio_server"]
    
    # Environment with mock URL if needed, but we won't mock HTTP here easily without complex setup.
    # We will just test 'tools/list' which doesn't hit network if just listing.
    env = os.environ.copy()
    # Add src to PYTHONPATH to ensure module is found
    # This is redundant if installed in editable mode, but safe.
    env["PYTHONPATH"] = os.path.abspath("src") + os.pathsep + env.get("PYTHONPATH", "")
    
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
        bufsize=0 # Unbuffered
    )
    
    try:
        # 1. Initialize
        init_req = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": 1,
            "params": {
                "protocolVersion": "2024-11-05", # Use a recent version or generic string
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"}
            }
        }
        
        # Write input
        proc.stdin.write(json.dumps(init_req) + "\n")
        proc.stdin.flush()
        
        # Read response
        # Read line by line. FastMCP should output one JSON line per message.
        response_line = proc.stdout.readline()
        
        if not response_line:
            # Debug failure
            stderr_output = proc.stderr.read()
            raise AssertionError(f"No response from stdio server. Stderr: {stderr_output}")
            
        resp = json.loads(response_line)
        assert resp["id"] == 1
        assert "result" in resp
        assert "serverInfo" in resp["result"]
        
        # 2. Initialized notification
        notif = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        proc.stdin.write(json.dumps(notif) + "\n")
        proc.stdin.flush()
        
        # 3. List Tools
        list_req = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 2
        }
        proc.stdin.write(json.dumps(list_req) + "\n")
        proc.stdin.flush()
        
        response_line = proc.stdout.readline()
        assert response_line
        resp = json.loads(response_line)
        
        assert resp["id"] == 2
        tools = [t["name"] for t in resp["result"]["tools"]]
        assert "award_search" in tools
        assert "answer_award_spending_question" in tools
        
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
