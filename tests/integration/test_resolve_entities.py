import httpx
import pytest
import respx

from usaspending_mcp.cache import Cache
from usaspending_mcp.tools.resolve_entities import ResolveEntitiesTool
from usaspending_mcp.usaspending_client import USAspendingClient


@pytest.fixture
def tool():
    client = USAspendingClient()
    cache = Cache()
    return ResolveEntitiesTool(client, cache)

@respx.mock
def test_resolve_entities_agency_local(tool):
    # Mock toptier agencies fetch
    agencies_url = f"{tool.client.base_url}/references/toptier_agencies/"
    mock_agencies = [
        {"agency_name": "Department of Defense", "toptier_code": "097", "abbreviation": "DOD"},
        {"agency_name": "Department of Education", "toptier_code": "018", "abbreviation": "ED"},
    ]
    respx.get(agencies_url).mock(return_value=httpx.Response(200, json={"results": mock_agencies}))
    
    # 1. Search for "Defense"
    result = tool.execute(q="Defense", types=["agency"])
    matches = result["matches"]["agency"]
    assert len(matches) == 1
    assert matches[0]["toptier_code"] == "097"

    # 2. Search for "ED" (abbreviation match)
    result = tool.execute(q="ED", types=["agency"])
    matches = result["matches"]["agency"]
    assert len(matches) >= 1
    assert matches[0]["abbreviation"] == "ED"

@respx.mock
def test_resolve_entities_recipient_remote(tool):
    # Mock recipient autocomplete
    url = f"{tool.client.base_url}/autocomplete/recipient/"
    mock_recipients = [{"recipient_name": "BOEING COMPANY", "uei": "12345"}]
    
    respx.post(url).mock(return_value=httpx.Response(200, json={"results": mock_recipients}))
    
    result = tool.execute(q="Boeing", types=["recipient"])
    
    assert len(result["matches"]["recipient"]) == 1
    assert result["matches"]["recipient"][0]["uei"] == "12345"

@respx.mock
def test_resolve_entities_mixed_and_cached(tool):
    # Mock both
    agencies_url = f"{tool.client.base_url}/references/toptier_agencies/"
    recipient_url = f"{tool.client.base_url}/autocomplete/recipient/"
    
    respx.get(agencies_url).mock(return_value=httpx.Response(200, json={"results": []}))
    respx.post(recipient_url).mock(return_value=httpx.Response(200, json={"results": []}))
    
    # Call 1
    tool.execute(q="Test", types=["agency", "recipient"])
    
    # Call 2 (should be cached)
    # Clear mocks to prove no requests made
    respx.get(agencies_url).side_effect = httpx.NetworkError("Should not be called")
    
    result = tool.execute(q="Test", types=["agency", "recipient"])
    assert result["meta"]["cache_hit"] is True

@respx.mock
def test_naics_autocomplete_endpoint(tool):
    url = f"{tool.client.base_url}/autocomplete/naics/"
    respx.post(url).mock(return_value=httpx.Response(200, json={"results": [{"code": "541511"}]}))
    
    result = tool.execute(q="software", types=["naics"])
    assert len(result["matches"]["naics"]) == 1
    assert result["matches"]["naics"][0]["code"] == "541511"
