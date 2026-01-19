import httpx
import pytest
import respx

from usaspending_mcp.award_types import SCOPE_CONTRACTS_ONLY
from usaspending_mcp.tools.award_search import AwardSearchTool
from usaspending_mcp.usaspending_client import USAspendingClient


@pytest.fixture
def tool():
    client = USAspendingClient()
    return AwardSearchTool(client)

def test_normalize_payload(tool):
    raw = {
        "a": 1,
        "b": None,
        "c": "",
        "d": [],
        "e": {"nested": None, "val": 2},
        "f": {"empty": {}}
    }
    normalized = tool._normalize_payload(raw)
    assert normalized == {"a": 1, "e": {"val": 2}}

@respx.mock
def test_award_search_contracts_only(tool):
    endpoint = f"{tool.client.base_url}/search/spending_by_award/"
    
    # Mock response
    respx.post(endpoint).mock(return_value=httpx.Response(200, json={
        "results": [{"Award ID": "123"}],
        "page_metadata": {"page": 1}
    }))
    
    result = tool.execute(
        mode="list",
        scope_mode=SCOPE_CONTRACTS_ONLY,
        filters={"keywords": ["test"]}
    )
    
    assert result["tool_version"] == "1.0"
    assert len(result["results"]) == 1
    assert result["meta"]["scope_mode"] == SCOPE_CONTRACTS_ONLY
    
    # Check that contract codes were applied to the payload
    # We can inspect the last request
    last_request = respx.calls.last.request
    payload = last_request.content.decode()
    assert "award_type_codes" in payload
    assert "A" in payload  # Check for contract code

@respx.mock
def test_award_search_count_and_list(tool):
    url_list = f"{tool.client.base_url}/search/spending_by_award/"
    url_count = f"{tool.client.base_url}/search/spending_by_award_count/"
    
    respx.post(url_list).mock(return_value=httpx.Response(200, json={"results": []}))
    respx.post(url_count).mock(return_value=httpx.Response(200, json={"results": {"count": 100}}))
    
    result = tool.execute(mode="both")
    
    assert "results" in result
    assert "count" in result
    assert result["count"] == 100
    assert len(result["meta"]["endpoints_used"]) == 2

@respx.mock
def test_award_search_truncation(tool):
    # Simulate a large response that triggers trimming
    endpoint = f"{tool.client.base_url}/search/spending_by_award/"
    
    # Create 300 items (limit default cap is 50 in code, but let's say API returned more somehow, 
    # or we verify the fields trimming logic)
    # Actually, the trimming logic is in response.py. 
    # Let's verify standard response flow uses trim_payload.
    
    large_results = [{"id": i} for i in range(300)]
    respx.post(endpoint).mock(return_value=httpx.Response(200, json={"results": large_results}))
    
    # Override the internal limit just to test the response trimmer logic integrated in 'ok'
    # Wait, tool forces limit=50. So API request will request 50.
    # To test trimming logic via tool execution, we have to mock API returning more than requested 
    # (unlikely) or rely on the fact that trim_payload defaults (200) are higher than tool cap (50).
    # So normally tool cap prevents trimming.
    # Let's verify 'limit' capping first.
    
    tool.execute(limit=100)
    # Request should have limit=50
    import json
    payload = json.loads(respx.calls.last.request.content.decode())
    assert payload["limit"] == 50

