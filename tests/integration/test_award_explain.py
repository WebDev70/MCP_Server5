import httpx
import pytest
import respx

from usaspending_mcp.award_types import SCOPE_ASSISTANCE_ONLY, SCOPE_CONTRACTS_ONLY
from usaspending_mcp.tools.award_explain import AwardExplainTool
from usaspending_mcp.usaspending_client import USAspendingClient


@pytest.fixture
def tool():
    client = USAspendingClient()
    return AwardExplainTool(client)

@respx.mock
def test_award_explain_success(tool):
    award_id = "CONT_AWD_123"
    
    # Mock Summary
    respx.get(f"{tool.client.base_url}/awards/{award_id}/").mock(
        return_value=httpx.Response(200, json={"id": 123, "type": "A", "category": "contract"})
    )
    
    # Mock Transactions
    respx.post(f"{tool.client.base_url}/transactions/").mock(
        return_value=httpx.Response(200, json={
            "results": [{"action_date": "2023-01-01"}],
            "page_metadata": {"total": 5}
        })
    )
    
    result = tool.execute(award_id, include=["summary", "transactions"])
    
    assert result["tool_version"] == "1.0"
    assert result["summary"]["type"] == "A"
    assert len(result["transactions"]) == 1
    assert result["transactions_total"] == 5
    assert len(result["meta"]["endpoints_used"]) == 2

@respx.mock
def test_award_explain_scope_validation_fail(tool):
    award_id = "GRANT_AWD_999"
    
    # Summary returns a Grant type (02)
    respx.get(f"{tool.client.base_url}/awards/{award_id}/").mock(
        return_value=httpx.Response(200, json={"id": 999, "type": "02", "category": "grant"})
    )
    
    # Try to access as Contracts Only
    result = tool.execute(award_id, scope_mode=SCOPE_CONTRACTS_ONLY)
    
    assert "error" in result
    assert result["error"]["type"] == "validation"
    assert "not supported" in result["error"]["message"]

@respx.mock
def test_award_explain_scope_validation_pass(tool):
    award_id = "GRANT_AWD_999"
    
    # Summary returns a Grant type (02)
    respx.get(f"{tool.client.base_url}/awards/{award_id}/").mock(
        return_value=httpx.Response(200, json={"id": 999, "type": "02", "category": "grant"})
    )
    
    # Try to access as Assistance Only, explicitly only asking for summary to avoid unmocked tx call
    result = tool.execute(award_id, include=["summary"], scope_mode=SCOPE_ASSISTANCE_ONLY)
    
    assert "summary" in result
    assert result["summary"]["type"] == "02"

@respx.mock
def test_award_explain_subawards_limit(tool):
    award_id = "CONT_AWD_ABC"
    
    respx.get(f"{tool.client.base_url}/awards/{award_id}/").mock(
        return_value=httpx.Response(200, json={"type": "A"})
    )
    
    # Return 100 subawards
    subawards = [{"id": i} for i in range(100)]
    respx.post(f"{tool.client.base_url}/subawards/").mock(
        return_value=httpx.Response(200, json={"results": subawards})
    )
    
    # Request limit 10
    result = tool.execute(award_id, include=["subawards"], subawards_limit=10)
    
    assert len(result["subawards"]) == 10
