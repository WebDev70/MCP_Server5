from unittest.mock import MagicMock

import pytest

from usaspending_mcp.award_types import SCOPE_ALL_AWARDS, SCOPE_GRANTS_ONLY
from usaspending_mcp.router import THIN_FIELDS, Router


@pytest.fixture
def router():
    client = MagicMock()
    cache = MagicMock()
    r = Router(client, cache)

    # Mock tools — return shape matching ok() output (tool_version + meta + data keys)
    for name in r.tools:
        r.tools[name] = MagicMock()
        r.tools[name].execute.return_value = {"tool_version": "1.0", "meta": {}}

    return r

def test_router_golden_question_1_totals(router):
    # "Top 10 awards for DoD" -> Spending Rollups
    q = "Top 10 awards for DoD in FY2024"
    resp = router.route_request(q)

    assert resp["meta"]["route_name"] == "spending_rollups"
    assert resp["plan"]["scope_mode"] == SCOPE_ALL_AWARDS
    router.tools["spending_rollups"].execute.assert_called_once()

def test_router_golden_question_idv(router):
    # "Task orders under IDV ..." -> IDV Bundle
    q = "Task orders under IDV CONT_IDV_123"
    resp = router.route_request(q)

    assert resp["meta"]["route_name"] == "idv_vehicle_bundle"
    router.tools["idv_vehicle_bundle"].execute.assert_called_once()

def test_router_explain_award(router):
    # "Explain award ..." -> Award Explain
    q = "Explain award CONT_AWD_123"
    resp = router.route_request(q)

    assert resp["meta"]["route_name"] == "award_explain"
    router.tools["award_explain"].execute.assert_called_once()

def test_router_assistance_only_denies_idv(router):
    q = "Show me grants for vehicle 123"
    resp = router.route_request(q)

    assert resp["plan"]["scope_mode"] == SCOPE_GRANTS_ONLY
    assert resp["meta"]["route_name"] != "idv_vehicle_bundle"
    assert resp["meta"]["route_name"] == "award_search"

def test_router_budgets_check(router):
    router.rules["budgets"]["max_usaspending_requests"] = 0

    q = "Top spending"
    resp = router.route_request(q)

    assert "error" in resp or "budget_exceeded" in str(resp)

def test_router_summary_first_trimming(router):
    """Flat envelope: results should be at top level, not nested under 'result'."""
    router.tools["award_search"].execute.return_value = {
        "tool_version": "1.0",
        "meta": {},
        "results": [{"id": i} for i in range(500)]
    }

    q = "List awards"
    resp = router.route_request(q)

    assert resp["meta"]["route_name"] == "award_search"
    assert resp["meta"]["truncated"] is True
    # Flat envelope — results at top level
    assert "result" not in resp
    assert len(resp["results"]) == 200

def test_router_flat_envelope_no_double_wrap(router):
    """Ensure tool_version and meta appear only once (no nesting under 'result')."""
    router.tools["spending_rollups"].execute.return_value = {
        "tool_version": "1.0",
        "meta": {"endpoint_used": "/api/v2/spending"},
        "groups": [{"agency": "DoD", "amount": 100}],
    }

    resp = router.route_request("Top spending by agency")

    # Single tool_version at top level
    assert resp["tool_version"] == "1.0"
    # Data at top level, not under 'result'
    assert "result" not in resp
    assert resp["groups"] == [{"agency": "DoD", "amount": 100}]
    # Meta merged
    assert resp["meta"]["route_name"] == "spending_rollups"
    assert resp["meta"]["endpoint_used"] == "/api/v2/spending"

def test_router_award_search_passes_thin_fields(router):
    """Router should pass THIN_FIELDS (no Description) to award_search."""
    q = "List awards for NASA"
    router.route_request(q)

    router.tools["award_search"].execute.assert_called_once()
    call_kwargs = router.tools["award_search"].execute.call_args
    assert call_kwargs.kwargs.get("fields") == THIN_FIELDS
    assert "Description" not in call_kwargs.kwargs["fields"]
