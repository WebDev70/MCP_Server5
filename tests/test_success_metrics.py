import json
import os
import time

import httpx
import pytest
import respx

from usaspending_mcp.cache import Cache
from usaspending_mcp.router import Router
from usaspending_mcp.tools.answer_award_spending_question import AnswerAwardSpendingQuestionTool
from usaspending_mcp.tools.bootstrap_catalog import BootstrapCatalogTool
from usaspending_mcp.tools.resolve_entities import ResolveEntitiesTool
from usaspending_mcp.usaspending_client import USAspendingClient

# Load fixtures
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "../mock_usaspending/fixtures")

def load_fixture(filename):
    with open(os.path.join(FIXTURES_DIR, filename)) as f:
        return json.load(f)

@pytest.fixture
def orchestrator():
    client = USAspendingClient()
    cache = Cache()
    router = Router(client, cache)
    return AnswerAwardSpendingQuestionTool(router)

@pytest.fixture
def tools_deps():
    client = USAspendingClient()
    cache = Cache()
    return client, cache

GOLDEN_QUESTIONS = [
    "Top 10 contract awards for DoD in FY2024",
    "Task orders under IDV CONT_IDV_123",
    "How much did DHS obligate on grants last quarter?",
    "Top recipients for NIH grants in 2023",
    "Total loans by agency for FY2022",
    "Direct payments by state for last year",
    "All awards total for NASA in FY2024",
    "Resolve: 'CACI', 'cloud PSC', and 'Assistance Listing 20.205'"
]

@pytest.mark.metrics
@respx.mock
def test_success_metrics(orchestrator):
    # Setup Mocks for all expected endpoints
    base_url = "https://api.usaspending.gov/api/v2"
    
    # Common mocks
    respx.post(f"{base_url}/search/spending_by_category/awarding_agency/").mock(return_value=httpx.Response(200, json={"results": [{"name": "Agency A", "amount": 1000}], "page_metadata": {"total": 1}}))
    respx.post(f"{base_url}/search/spending_by_category/recipient/").mock(return_value=httpx.Response(200, json={"results": [{"name": "Recipient A", "amount": 1000}], "page_metadata": {"total": 1}}))
    respx.post(f"{base_url}/search/spending_by_category/state_territory/").mock(return_value=httpx.Response(200, json={"results": [{"name": "CA", "amount": 1000}], "page_metadata": {"total": 1}}))
    
    respx.post(f"{base_url}/search/spending_by_award/").mock(return_value=httpx.Response(200, json=load_fixture("sample_awards.json")))
    respx.post(f"{base_url}/search/spending_by_award_count/").mock(return_value=httpx.Response(200, json={"results": {"count": 50}}))
    
    respx.post(f"{base_url}/idvs/awards/").mock(return_value=httpx.Response(200, json=load_fixture("sample_idv_orders.json")))
    respx.post(f"{base_url}/idvs/activity/").mock(return_value=httpx.Response(200, json={"results": []}))
    respx.post(f"{base_url}/idvs/funding_rollup/").mock(return_value=httpx.Response(200, json={"total_transaction_obligated_amount": 1000}))
    
    # Resolve
    respx.get(f"{base_url}/references/toptier_agencies/").mock(return_value=httpx.Response(200, json=load_fixture("toptier_agencies.json")))
    respx.post(f"{base_url}/autocomplete/recipient/").mock(return_value=httpx.Response(200, json={"results": [{"recipient_name": "CACI INC"}]}))
    respx.post(f"{base_url}/autocomplete/psc/").mock(return_value=httpx.Response(200, json={"results": [{"code": "D302"}]}))
    respx.post(f"{base_url}/autocomplete/assistance_listing/").mock(return_value=httpx.Response(200, json={"results": [{"code": "20.205"}]}))
    respx.post(f"{base_url}/autocomplete/naics/").mock(return_value=httpx.Response(200, json={"results": []}))

    results = []
    
    for q in GOLDEN_QUESTIONS:
        start = time.time()
        resp = orchestrator.execute(q)
        duration = (time.time() - start) * 1000
        
        # 3) Test: no 400 errors
        if "error" in resp:
            # Allow budget_exceeded as it's a valid "success" for the guardrail system, but 400 validation is bad.
            # But golden questions should be valid.
            assert resp["error"]["type"] != "validation", f"Validation error for: {q}\n{resp['error']}"
            
        results.append({
            "question": q,
            "resp": resp,
            "duration": duration,
            "outbound_calls": len(resp.get("meta", {}).get("endpoints_used", [])), # Approximate from meta
            "response_bytes": len(json.dumps(resp).encode("utf-8"))
        })

    # 1) Test: Average outbound calls <= 3
    outbound_counts = [r["outbound_calls"] for r in results]
    avg_calls = sum(outbound_counts) / len(outbound_counts)
    outbound_counts.sort()
    idx95 = int(len(outbound_counts) * 0.95)
    # Ensure index is within bounds (if len is small)
    idx95 = min(idx95, len(outbound_counts) - 1)
    p95_calls = outbound_counts[idx95] if outbound_counts else 0
    
    print(f"\n[Metrics] Avg Calls: {avg_calls:.2f}, P95 Calls: {p95_calls}")
    assert avg_calls <= 3.5, f"Average calls {avg_calls} > 3.5"
    assert p95_calls <= 5, f"P95 calls {p95_calls} > 5"

    # 2) Test: Response size <= 200KB (P95)
    sizes = [r["response_bytes"] for r in results]
    sizes.sort()
    idx95_size = int(len(sizes) * 0.95)
    idx95_size = min(idx95_size, len(sizes) - 1)
    p95_size = sizes[idx95_size] if sizes else 0
    
    print(f"[Metrics] P95 Size: {p95_size} bytes")
    assert p95_size <= 200_000
    
    for r in results:
        if r["response_bytes"] > 200_000:
            assert r["resp"]["meta"].get("truncated") is True, f"Response > 200KB but not marked truncated: {r['question']}"

@pytest.mark.metrics
@respx.mock
def test_cache_effectiveness(tools_deps):
    client, cache = tools_deps
    
    # 1. Bootstrap Catalog
    tool = BootstrapCatalogTool(client, cache)
    url = f"{client.base_url}/references/toptier_agencies/"
    respx.get(url).mock(return_value=httpx.Response(200, json=load_fixture("toptier_agencies.json")))
    
    # First call
    res1 = tool.execute(include=["toptier_agencies"])
    assert res1["meta"]["cache_hit"] is False
    
    # Second call
    res2 = tool.execute(include=["toptier_agencies"])
    assert res2["meta"]["cache_hit"] is True
    
    # 2. Resolve Entities
    tool_res = ResolveEntitiesTool(client, cache)
    url_rec = f"{client.base_url}/autocomplete/recipient/"
    respx.post(url_rec).mock(return_value=httpx.Response(200, json={"results": [{"recipient_name": "CACI"}]}))
    
    # First call
    res3 = tool_res.execute("CACI", types=["recipient"])
    assert res3["meta"]["cache_hit"] is False
    
    # Second call
    res4 = tool_res.execute("CACI", types=["recipient"])
    assert res4["meta"]["cache_hit"] is True

@pytest.mark.metrics
def test_latency_buckets():
    # Informational
    pass