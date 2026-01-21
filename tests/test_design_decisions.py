from unittest.mock import MagicMock

import pytest

from usaspending_mcp.award_types import normalize_award_category
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

def test_normalize_award_category():
    assert normalize_award_category("A") == "contract"
    assert normalize_award_category("IDV_A") == "idv"
    assert normalize_award_category("04") == "grant"
    assert normalize_award_category("07") == "loan"
    assert normalize_award_category("06") == "direct_payment"
    assert normalize_award_category("unknown") == "other_assistance"

def test_agency_inference_funding(router):
    q = "How much was funded by DoD?"
    # "funded by" -> funding_agency
    signals = router._extract_signals(q)
    assert signals["agency_type_hint"] == "funding_agency"

def test_agency_inference_awarding_default(router):
    q = "DoD contracts"
    # Default is awarding_agency
    signals = router._extract_signals(q)
    assert signals["agency_type_hint"] == "awarding_agency"

def test_metric_inference_loans(router):
    q = "Total loans by agency"
    # Router should pick loan metric logic
    # We verify that execute call receives the correct metric
    router.route_request(q)
    
    # Check spending_rollups call args
    call_args = router.tools["spending_rollups"].execute.call_args
    assert call_args
    kwargs = call_args[1]
    assert kwargs["metric"] == "face_value_of_loan"

def test_metric_inference_default(router):
    q = "Total contracts by agency"
    router.route_request(q)
    
    call_args = router.tools["spending_rollups"].execute.call_args
    kwargs = call_args[1]
    assert kwargs["metric"] == "obligations"
