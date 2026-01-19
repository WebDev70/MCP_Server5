import httpx
import pytest
import respx

from usaspending_mcp.award_types import SCOPE_ASSISTANCE_ONLY
from usaspending_mcp.tools.idv_vehicle_bundle import IDVVehicleBundleTool
from usaspending_mcp.usaspending_client import USAspendingClient


@pytest.fixture
def tool():
    client = USAspendingClient()
    return IDVVehicleBundleTool(client)

@respx.mock
def test_idv_bundle_success(tool):
    idv_id = "CONT_IDV_123"
    
    # Mock Orders
    url_orders = f"{tool.client.base_url}/idvs/awards/"
    respx.post(url_orders).mock(
        return_value=httpx.Response(200, json={"results": [{"id": 1}]})
    )
    
    # Mock Funding
    url_funding = f"{tool.client.base_url}/idvs/funding_rollup/"
    respx.post(url_funding).mock(
        return_value=httpx.Response(200, json={"total_transaction_obligated_amount": 5000})
    )
    
    result = tool.execute(idv_id, include=["orders", "funding_rollup"])
    
    assert result["tool_version"] == "1.0"
    assert len(result["orders"]) == 1
    assert result["funding_rollup"]["total_transaction_obligated_amount"] == 5000
    assert len(result["meta"]["endpoints_used"]) == 2

@respx.mock
def test_idv_scope_rejection(tool):
    result = tool.execute("CONT_IDV_123", scope_mode=SCOPE_ASSISTANCE_ONLY)
    
    assert "error" in result
    assert result["error"]["type"] == "validation"
    assert "contracts_only" in result["error"]["remediation_hint"]
