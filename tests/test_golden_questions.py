import pytest
from unittest.mock import MagicMock
from usaspending_mcp.router import Router
from usaspending_mcp.tools.answer_award_spending_question import AnswerAwardSpendingQuestionTool
from usaspending_mcp.award_types import (
    SCOPE_ALL_AWARDS,
    SCOPE_CONTRACTS_ONLY,
    SCOPE_GRANTS_ONLY,
    SCOPE_IDVS_ONLY,
    SCOPE_LOANS_ONLY,
    SCOPE_DIRECT_PAYMENTS_ONLY,
)

@pytest.fixture
def orchestrator():
    client = MagicMock()
    cache = MagicMock()
    router = Router(client, cache)

    # Mock all internal tools to avoid network
    for name in router.tools:
        router.tools[name] = MagicMock()
        # Default return
        router.tools[name].execute.return_value = {
            "tool_version": "1.0",
            "meta": {"endpoint_used": "/mocked"},
            "result": {}
        }

    return AnswerAwardSpendingQuestionTool(router)

def test_golden_1_top_contracts_dod(orchestrator):
    q = "Top 10 contract awards for DoD in FY2024"
    resp = orchestrator.execute(q)

    assert resp["tool_version"] == "1.0"
    assert resp["plan"]["scope_mode"] == SCOPE_CONTRACTS_ONLY
    # Should use spending_rollups (cheapest for Top N) OR award_search (list)
    # Router logic: "Top ..." -> intent_total_or_top_n -> spending_rollups
    assert resp["meta"]["route_name"] == "spending_rollups"

def test_golden_2_idv_task_orders(orchestrator):
    q = "Task orders under IDV N0001921C0001"
    resp = orchestrator.execute(q)

    assert resp["meta"]["route_name"] == "idv_vehicle_bundle"
    # "Task orders" -> IDV_KEYWORDS -> idvs_only
    assert resp["plan"]["scope_mode"] == SCOPE_IDVS_ONLY

def test_golden_3_dhs_grants_obligations(orchestrator):
    q = "How much did DHS obligate on grants last quarter?"
    resp = orchestrator.execute(q)

    assert resp["plan"]["scope_mode"] == SCOPE_GRANTS_ONLY
    assert resp["meta"]["route_name"] == "spending_rollups"

def test_golden_4_top_recipients_nih_grants(orchestrator):
    q = "Top recipients for NIH grants in 2023"
    resp = orchestrator.execute(q)

    assert resp["plan"]["scope_mode"] == SCOPE_GRANTS_ONLY
    assert resp["meta"]["route_name"] == "spending_rollups"

def test_golden_5_loans_by_agency(orchestrator):
    q = "Total loans by agency for FY2022"
    resp = orchestrator.execute(q)

    assert resp["plan"]["scope_mode"] == SCOPE_LOANS_ONLY
    assert resp["meta"]["route_name"] == "spending_rollups"

def test_golden_6_direct_payments_by_state(orchestrator):
    q = "Total direct payments by state for last year"
    resp = orchestrator.execute(q)

    assert resp["plan"]["scope_mode"] == SCOPE_DIRECT_PAYMENTS_ONLY
    assert resp["meta"]["route_name"] == "spending_rollups"

def test_golden_7_all_awards_agency_total(orchestrator):
    q = "All awards total for NASA in FY2024"
    resp = orchestrator.execute(q)

    assert resp["plan"]["scope_mode"] == SCOPE_ALL_AWARDS
    assert resp["meta"]["route_name"] == "spending_rollups"

def test_golden_8_resolve_entities(orchestrator):
    q = "Resolve: 'CACI', 'cloud PSC', and 'Assistance Listing 20.205'"

    # Configure mock return for resolve_entities tool
    # Access the router from the tool wrapper
    router = orchestrator.router
    router.tools["resolve_entities"].execute.return_value = {
        "tool_version": "1.0",
        "matches": {
            "recipient": [{"recipient_name": "CACI INC"}],
            "psc": [{"code": "D302", "description": "IT and Telecom - Systems Development"}],
            "assistance_listing": [{"code": "20.205", "title": "Highway Planning and Construction"}]
        },
        "meta": {
            "request_id": "req-mock",
            "endpoint_used": "/mocked"
        }
    }

    resp = orchestrator.execute(q)

    # Assert Routing
    assert resp["meta"]["route_name"] == "resolve_entities"
    router.tools["resolve_entities"].execute.assert_called_once()

    # Assert Result content (propagated from mock)
    # Note: result is in resp["result"] or top level depending on response logic.
    # In router.py, `result` key in envelope contains the tool output.
    # But `ResolveEntitiesTool` returns `matches` directly in `ok()` data.
    # Router wraps it: `return { ..., "result": trimmed_result }`

    matches = resp["result"]["matches"]

    # Recipient match
    assert any("CACI" in m["recipient_name"] for m in matches["recipient"])

    # PSC match
    assert len(matches["psc"]) >= 1

    # Assistance Listing match
    assert matches["assistance_listing"][0]["code"] == "20.205"

    # Meta presence
    assert resp["tool_version"] == "1.0"
    assert "request_id" in resp["meta"]
    assert "endpoints_used" in resp["meta"] or "endpoint_used" in resp["meta"]
