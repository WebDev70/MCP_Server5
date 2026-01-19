#!/bin/bash
set -e

SERVICE_URL=${SERVICE_URL}

if [ -z "$SERVICE_URL" ]; then
    echo "Error: SERVICE_URL environment variable is required."
    echo "Usage: SERVICE_URL=https://... ./scripts/smoke_test_cloud_run.sh"
    exit 1
fi

echo "Getting identity token..."
TOKEN=$(gcloud auth print-identity-token)

echo "Checking Health ($SERVICE_URL/healthz)..."
curl -fsS -H "Authorization: Bearer $TOKEN" "$SERVICE_URL/healthz"
echo -e "\nOK"

echo "Checking Readiness ($SERVICE_URL/readyz)..."
curl -fsS -H "Authorization: Bearer $TOKEN" "$SERVICE_URL/readyz"
echo -e "\nOK"

echo "Invoking 'bootstrap_catalog' via MCP JSON-RPC..."

# Payload for tools/call
# We use a static sessionId for the smoke test
SESSION_ID="smoke-test-$(date +%s)"
PAYLOAD='{
  "jsonrpc": "2.0", 
  "id": 1, 
  "method": "tools/call", 
  "params": {
    "name": "bootstrap_catalog", 
    "arguments": {
      "include": ["toptier_agencies"],
      "force_refresh": false
    }
  }
}'

# We attempt to hit the /messages endpoint which is standard for MCP HTTP transport.
# We mount at /mcp, so path is /mcp/messages.
ENDPOINT="$SERVICE_URL/mcp/messages?sessionId=$SESSION_ID"

echo "POST $ENDPOINT"

# Capture HTTP code and response
# We rely on curl -f to fail on >400, but we want to inspect output on error manually if needed.
# However, user requested "Fail fast on any non-200".

curl -fsS \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -X POST \
  -d "$PAYLOAD" \
  "$ENDPOINT"

echo -e "\nSmoke test complete."
