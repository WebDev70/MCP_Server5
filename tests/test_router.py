from unittest.mock import MagicMock

import pytest

from usaspending_mcp.award_types import SCOPE_ALL_AWARDS, SCOPE_GRANTS_ONLY
from usaspending_mcp.router import Router


@pytest.fixture
def router():
    client = MagicMock()
    cache = MagicMock()
    r = Router(client, cache)
    
    # Mock tools
    for name in r.tools:
        r.tools[name] = MagicMock()
        r.tools[name].execute.return_value = {"meta": {}, "result": {}}
        
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
    # "Grants under IDV ..." -> Should fallback or deny IDV route
    # IDV intent is present, but scope is assistance_only.
    # Rules say deny_if scope_assistance_only.
    # Should fall through to award_search or similar.
    q = "Show me grants for vehicle 123" # 'vehicle' triggers IDV intent but not contract scope
    resp = router.route_request(q)
    
    # scope should be grants_only due to "grants"
    assert resp["plan"]["scope_mode"] == SCOPE_GRANTS_ONLY
    # Should NOT be idv_vehicle_bundle
    assert resp["meta"]["route_name"] != "idv_vehicle_bundle"
    # Likely award_search (default)
    assert resp["meta"]["route_name"] == "award_search"

def test_router_budgets_check(router):
    # Simulate high cost budget exhaustion (artificially)
    # We can patch the cost_hint in the rules for a specific test
    router.rules["budgets"]["max_usaspending_requests"] = 0
    
    q = "Top spending"
    resp = router.route_request(q)
    
    assert "error" in resp or "budget_exceeded" in str(resp)

def test_router_summary_first_trimming(router):
    # Verify trim_payload is called (mocking the return value of tool to be huge)
    router.tools["award_search"].execute.return_value = {
        "meta": {},
        "results": [{"id": i} for i in range(500)] # > 200 default limit
    }
    
    q = "List awards"
    resp = router.route_request(q)
    
    assert resp["meta"]["route_name"] == "award_search"
    assert resp["meta"]["truncated"] is True
    # Should be capped at 200
    assert len(resp["result"]["results"]) == 200
