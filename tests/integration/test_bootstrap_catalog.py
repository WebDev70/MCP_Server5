import httpx
import pytest
import respx

from usaspending_mcp.cache import Cache
from usaspending_mcp.tools.bootstrap_catalog import BootstrapCatalogTool
from usaspending_mcp.usaspending_client import USAspendingClient


@pytest.fixture
def tool():
    client = USAspendingClient()
    cache = Cache()
    return BootstrapCatalogTool(client, cache)

@respx.mock
def test_bootstrap_catalog_fresh(tool):
    # Mock endpoints
    agencies_url = f"{tool.client.base_url}/references/toptier_agencies/"
    types_url = f"{tool.client.base_url}/references/award_types/"

    respx.get(agencies_url).mock(return_value=httpx.Response(200, json={"results": [{"agency_name": "DoD", "toptier_code": "097", "abbreviation": "DOD", "agency_id": 1}]}))
    # award_types endpoint returns a dict of groups, not {"results": [...]}
    respx.get(types_url).mock(return_value=httpx.Response(200, json={"contracts": [{"code": "A"}]}))

    result = tool.execute(include=["toptier_agencies", "award_types"])

    assert result["tool_version"] == "1.0"
    assert "toptier_agencies" in result["catalog"]
    # Output is slimmed to allowlisted fields only
    assert result["catalog"]["toptier_agencies"][0]["agency_name"] == "DoD"
    assert result["catalog"]["toptier_agencies"][0]["toptier_code"] == "097"
    assert "agency_id" not in result["catalog"]["toptier_agencies"][0]
    assert result["meta"]["cache_hit"] is False

@respx.mock
def test_bootstrap_catalog_cached(tool):
    # 1. First call to populate cache
    agencies_url = f"{tool.client.base_url}/references/toptier_agencies/"
    respx.get(agencies_url).mock(return_value=httpx.Response(200, json={"results": [{"agency_name": "DoD", "toptier_code": "097", "abbreviation": "DOD", "agency_id": 1}]}))

    tool.execute(include=["toptier_agencies"])

    # 2. Second call should hit cache (no new network requests)
    # Clear mocks to ensure no network calls happen
    # (respx would raise error if unmocked call made)

    result = tool.execute(include=["toptier_agencies"])

    # Output is slimmed; agency_id is filtered out
    assert result["catalog"]["toptier_agencies"][0]["agency_name"] == "DoD"
    assert "agency_id" not in result["catalog"]["toptier_agencies"][0]
    assert result["meta"]["cache_hit"] is True

@respx.mock
def test_bootstrap_catalog_force_refresh(tool):
    agencies_url = f"{tool.client.base_url}/references/toptier_agencies/"
    route = respx.get(agencies_url).mock(return_value=httpx.Response(200, json={"results": []}))
    
    # Call 1
    tool.execute(include=["toptier_agencies"])
    # Call 2 with force_refresh
    tool.execute(include=["toptier_agencies"], force_refresh=True)
    
    assert route.call_count == 2
