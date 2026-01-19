import httpx
import pytest
import respx

from usaspending_mcp.cache import Cache
from usaspending_mcp.tools.recipient_profile import RecipientProfileTool
from usaspending_mcp.usaspending_client import USAspendingClient


@pytest.fixture
def tool():
    client = USAspendingClient()
    cache = Cache()
    return RecipientProfileTool(client, cache)

@respx.mock
def test_recipient_profile_success(tool):
    # 1. Mock Resolve
    resolve_url = f"{tool.client.base_url}/autocomplete/recipient/"
    mock_recipient = {"recipient_name": "BOEING", "recipient_hash": "hash-123", "uei": "UEI123"}
    respx.post(resolve_url).mock(return_value=httpx.Response(200, json={"results": [mock_recipient]}))
    
    # 2. Mock Rollups (Category Search)
    rollup_url = f"{tool.client.base_url}/search/spending_by_category/awarding_agency/"
    respx.post(rollup_url).mock(
        return_value=httpx.Response(200, json={
            "results": [{"name": "Department of Defense", "amount": 5000}],
            "page_metadata": {"total": 1}
        })
    )
    
    result = tool.execute("Boeing", include=["profile", "rollups"])
    
    assert result["tool_version"] == "1.0"
    assert result["recipient_info"]["recipient_hash"] == "hash-123"
    assert len(result["spending_by_agency"]) == 1
    assert result["spending_by_agency"][0]["amount"] == 5000

@respx.mock
def test_recipient_profile_not_found(tool):
    resolve_url = f"{tool.client.base_url}/autocomplete/recipient/"
    respx.post(resolve_url).mock(return_value=httpx.Response(200, json={"results": []}))
    
    result = tool.execute("Ghost Company")
    
    assert "error" in result
    assert result["error"]["type"] == "validation"
    assert "not found" in result["error"]["message"]
