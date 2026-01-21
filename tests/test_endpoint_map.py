import pytest

from usaspending_mcp.endpoint_map import ENDPOINT_MAP, get_cost_hint, get_endpoints_for_tool


@pytest.mark.unit
def test_all_tools_mapped():
    tools = [
        "bootstrap_catalog",
        "resolve_entities",
        "award_search",
        "award_explain",
        "spending_rollups",
        "recipient_profile",
        "agency_portfolio",
        "idv_vehicle_bundle",
        "answer_award_spending_question"
    ]
    for tool in tools:
        assert tool in ENDPOINT_MAP, f"Tool {tool} not found in ENDPOINT_MAP"

@pytest.mark.unit
def test_get_endpoints():
    endpoints = get_endpoints_for_tool("award_search")
    assert "/search/spending_by_award/" in endpoints
    assert "/search/spending_by_award_count/" in endpoints

@pytest.mark.unit
def test_get_cost_hint():
    assert get_cost_hint("award_explain") == 4
    assert get_cost_hint("bootstrap_catalog") == 1
    # Default
    assert get_cost_hint("unknown_tool") == 1
