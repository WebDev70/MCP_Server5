import httpx
import pytest
import respx

from usaspending_mcp.award_types import SCOPE_CONTRACTS_ONLY
from usaspending_mcp.tools.spending_rollups import SpendingRollupsTool
from usaspending_mcp.usaspending_client import USAspendingClient


@pytest.fixture
def tool():
    client = USAspendingClient()
    return SpendingRollupsTool(client)

@respx.mock
def test_rollup_tier_a_success(tool):
    endpoint = f"{tool.client.base_url}/search/spending_by_category/awarding_agency/"
    
    respx.post(endpoint).mock(
        return_value=httpx.Response(200, json={
            "results": [{"name": "Department of Defense", "amount": 1000}],
            "page_metadata": {"total": 1}
        })
    )
    
    result = tool.execute(group_by="awarding_agency", top_n=5)
    
    assert result["tool_version"] == "1.0"
    assert result["meta"]["accuracy_tier"] == "A"
    assert len(result["groups"]) == 1
    assert result["groups"][0]["amount"] == 1000

@respx.mock
def test_rollup_tier_c_fallback(tool):
    category_endpoint = f"{tool.client.base_url}/search/spending_by_category/awarding_agency/"
    search_endpoint = f"{tool.client.base_url}/search/spending_by_award/"
    
    # 1. Tier A fails with 500
    respx.post(category_endpoint).mock(return_value=httpx.Response(500))
    
    # 2. Fallback Search succeeds
    mock_awards = [
        {"Awarding Agency": "Agency A", "Award Amount": 100},
        {"Awarding Agency": "Agency A", "Award Amount": 50},
        {"Awarding Agency": "Agency B", "Award Amount": 200},
    ]
    respx.post(search_endpoint).mock(
        return_value=httpx.Response(200, json={"results": mock_awards})
    )
    
    result = tool.execute(group_by="awarding_agency", top_n=5)
    
    assert result["meta"]["accuracy_tier"] == "C"
    assert "approximate_total" in result["meta"]["warnings"]
    assert len(result["groups"]) == 2
    
    # Check aggregation
    # Agency B: 200
    # Agency A: 150
    assert result["groups"][0]["name"] == "Agency B"
    assert result["groups"][0]["amount"] == 200
    assert result["groups"][1]["name"] == "Agency A"
    assert result["groups"][1]["amount"] == 150

@respx.mock
def test_rollup_top_n_cap(tool):
    endpoint = f"{tool.client.base_url}/search/spending_by_category/awarding_agency/"
    
    respx.post(endpoint).mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    
    tool.execute(top_n=100)
    
    # Verify request payload used limit=25 (default cap)
    import json
    payload = json.loads(respx.calls.last.request.content.decode())
    assert payload["limit"] == 25

@respx.mock
def test_rollup_scope_mode_filter(tool):
    endpoint = f"{tool.client.base_url}/search/spending_by_category/awarding_agency/"
    respx.post(endpoint).mock(return_value=httpx.Response(200, json={"results": []}))
    
    tool.execute(scope_mode=SCOPE_CONTRACTS_ONLY)
    
    import json
    payload = json.loads(respx.calls.last.request.content.decode())
    assert "award_type_codes" in payload["filters"]
