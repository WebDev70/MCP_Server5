import httpx
import pytest
import respx

from usaspending_mcp.tools.agency_portfolio import AgencyPortfolioTool
from usaspending_mcp.usaspending_client import USAspendingClient


@pytest.fixture
def tool():
    client = USAspendingClient()
    return AgencyPortfolioTool(client)

@respx.mock
def test_agency_portfolio_success(tool):
    toptier_code = "097"
    
    # Mock Summary
    summary_url = f"{tool.client.base_url}/agency/{toptier_code}/"
    respx.get(summary_url).mock(
        return_value=httpx.Response(200, json={"name": "Department of Defense", "mission": "Protect"})
    )
    
    # Mock Rollups (Top Recipients)
    rollup_url = f"{tool.client.base_url}/search/spending_by_category/recipient/"
    respx.post(rollup_url).mock(
        return_value=httpx.Response(200, json={
            "results": [{"name": "Boeing", "amount": 1000}],
            "page_metadata": {"total": 1}
        })
    )
    
    result = tool.execute(toptier_code, views=["summary", "awards"])
    
    assert result["tool_version"] == "1.0"
    assert result["summary"]["name"] == "Department of Defense"
    assert len(result["top_recipients"]) == 1
    assert result["top_recipients"][0]["name"] == "Boeing"

@respx.mock
def test_agency_portfolio_summary_fail(tool):
    toptier_code = "999"
    
    # 404
    summary_url = f"{tool.client.base_url}/agency/{toptier_code}/"
    respx.get(summary_url).mock(return_value=httpx.Response(404))
    
    result = tool.execute(toptier_code, views=["summary"])
    
    # Should contain error message but not fail entire tool execution usually?
    # Code implementation catches APIError and returns result_bundle with "summary_error" key
    assert "summary" not in result
    assert "summary_error" in result
