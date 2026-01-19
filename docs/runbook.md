# Operations Runbook

## Service Overview

- **Service:** USAspending MCP Server
- **Transport:** HTTP (Cloud Run) or stdio (local)
- **Dependencies:** USAspending.gov API v2 (external)
- **State:** Stateless (in-memory cache only)

## Health Checks

```bash
# Liveness (is the process running?)
curl $SERVICE_URL/healthz
# Expected: {"status": "ok"}

# Readiness (is it ready to serve traffic?)
curl $SERVICE_URL/readyz
# Expected: {"ready": "true"}
# If {"ready": "false"}, startup is still in progress
```

## Common Issues

### High 400 Error Rate

**Symptoms:**
- `error.type: "validation"` responses increasing
- Users reporting "invalid filter" errors

**Diagnosis:**
```bash
# Check recent logs for 400s
gcloud logging read "resource.type=cloud_run_revision AND jsonPayload.status_code=400" --limit=50

# Check if award_type codes have changed
curl https://api.usaspending.gov/api/v2/references/award_types/ | jq .
```

**Resolution:**
1. Check if USAspending updated their award type codes
2. Force refresh the bootstrap_catalog cache:
   ```json
   {"name": "bootstrap_catalog", "arguments": {"force_refresh": true}}
   ```
3. If codes changed, update fallback values in `award_types.py`

---

### High 429 Rate (Rate Limited)

**Symptoms:**
- `error.type: "rate_limit"` responses
- Increased latency due to retries

**Diagnosis:**
```bash
# Check 429 rate in logs
gcloud logging read "jsonPayload.status_code=429" --limit=50
```

**Resolution:**
1. Check if traffic spike caused the issue
2. Increase `USASPENDING_BACKOFF_BASE_S` to be more conservative
3. Consider adding request queuing or reducing `max_usaspending_requests` budget
4. Check USAspending status page for any announced rate limit changes

---

### Slow Responses (P95 > 15s)

**Symptoms:**
- Users reporting timeouts
- Cloud Run scaling up aggressively

**Diagnosis:**
```bash
# Check latency distribution
gcloud logging read "jsonPayload.latency_ms>5000" --limit=50

# Check cache hit rate
gcloud logging read "jsonPayload.cache_hit=false" --limit=100 | wc -l
```

**Resolution:**
1. **Low cache hit rate:**
   - Check if cache TTLs are appropriate
   - Verify bootstrap_catalog is being called at startup
2. **Rollups falling back to search:**
   - Check if rollup endpoints are returning errors
   - Look for `accuracy_tier: "C"` in responses (indicates fallback)
3. **USAspending API slow:**
   - Check https://api.usaspending.gov status
   - Consider increasing timeout or reducing scope of queries

---

### Circuit Breaker Open

**Symptoms:**
- Immediate failures without hitting USAspending
- `error.type: "upstream"` with message about circuit breaker

**Diagnosis:**
```bash
# Check for repeated upstream failures
gcloud logging read "jsonPayload.error_type=upstream" --limit=50
```

**Resolution:**
1. Check USAspending API status
2. Wait for recovery_timeout (default 60s) to allow half-open state
3. If USAspending is down, consider returning cached stale data with warning

---

### Memory Issues (OOM)

**Symptoms:**
- Container restarts
- Cloud Run reporting memory limit exceeded

**Diagnosis:**
```bash
# Check memory usage
gcloud run services describe $SERVICE_NAME --format="value(status.conditions)"
```

**Resolution:**
1. Check if `MAX_RESPONSE_BYTES` limit is being enforced
2. Look for queries returning extremely large result sets
3. Increase memory limit or reduce `MAX_ITEMS_PER_LIST`

---

## Routine Maintenance

### Refresh Reference Cache

Run weekly or after USAspending announces data updates:

```bash
# Call bootstrap_catalog with force_refresh
curl -X POST $SERVICE_URL/mcp \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"bootstrap_catalog","arguments":{"force_refresh":true}}}'
```

### Check Data Freshness

```bash
# Call data_freshness tool
curl -X POST $SERVICE_URL/mcp \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"data_freshness","arguments":{"check_type":"submission_periods"}}}'
```

### View Logs

```bash
# Recent errors
gcloud logging read "resource.type=cloud_run_revision AND severity>=ERROR" --limit=50

# Specific request
gcloud logging read "jsonPayload.request_id=YOUR_REQUEST_ID"

# Tool usage
gcloud logging read "jsonPayload.tool_name=spending_rollups" --limit=100
```

### Metrics to Monitor

| Metric | Warning | Critical |
|--------|---------|----------|
| Error rate (non-4xx) | > 1% | > 5% |
| P95 latency | > 10s | > 15s |
| 429 rate | > 5% | > 15% |
| Cache hit rate | < 50% | < 25% |
| Avg outbound calls/question | > 3 | > 5 |

---

## Deployment

### Deploy New Version

```bash
PROJECT_ID=your-project REGION=us-central1 SERVICE_NAME=usaspending-mcp \
  ./scripts/deploy_cloud_run.sh
```

### Rollback

```bash
# List revisions
gcloud run revisions list --service $SERVICE_NAME

# Route traffic to previous revision
gcloud run services update-traffic $SERVICE_NAME \
  --to-revisions=PREVIOUS_REVISION=100
```

### Verify Deployment

```bash
./scripts/smoke_test_cloud_run.sh
```

---

## Contacts

- **USAspending API Issues:** https://github.com/fedspendingtransparency/usaspending-api/issues
- **USAspending Status:** Check their GitHub or API status page
- **MCP Protocol Issues:** https://github.com/anthropics/claude-code/issues
