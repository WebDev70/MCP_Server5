from typing import List

ENDPOINT_MAP = {
    "bootstrap_catalog": {
        "endpoints": [
            "/references/toptier_agencies/",
            "/references/award_types/",
            "/references/filter_tree/psc/",
            "/references/filter_tree/naics/",
            "/references/cfda/totals/",
            "/references/submission_periods/",
        ],
        "methods": ["GET"],
        "cost_hint": 1,
    },
    "resolve_entities": {
        "endpoints": [
            "/autocomplete/recipient/",
            "/autocomplete/naics/",
            "/autocomplete/psc/",
            "/autocomplete/cfda/",
            "/autocomplete/location/",
        ],
        "methods": ["POST"],
        "cost_hint": 1,
    },
    "award_search": {
        "endpoints": [
            "/search/spending_by_award/",
            "/search/spending_by_award_count/",
        ],
        "methods": ["POST"],
        "cost_hint": 2,
    },
    "award_explain": {
        "endpoints": [
            "/awards/{award_id}/",
            "/transactions/",
            "/subawards/",
            "/awards/{award_id}/funding/",
            "/awards/{award_id}/funding_rollup/",
        ],
        "methods": ["GET", "POST"],
        "cost_hint": 4,
    },
    "spending_rollups": {
        "endpoints": [
            "/spending/",
            "/federal_obligations/",
            "/spending/agency/{toptier_code}/",
            "/spending/object_class/",
        ],
        "methods": ["POST", "GET"],
        "cost_hint": 1,
    },
    "recipient_profile": {
        "endpoints": [
            "/recipient/{recipient_id}/",
            "/recipient/{recipient_id}/children/",
            "/recipient/count/",
            "/recipient/state/",
        ],
        "methods": ["GET", "POST"],
        "cost_hint": 3,
    },
    "agency_portfolio": {
        "endpoints": [
            "/agency/{toptier_code}/",
            "/agency/{toptier_code}/awards/",
            "/agency/{toptier_code}/budgetary_resources/",
            "/agency/{toptier_code}/object_class/",
            "/agency/{toptier_code}/program_activity/",
            "/agency/{toptier_code}/federal_account/",
        ],
        "methods": ["GET"],
        "cost_hint": 3,
    },
    "idv_vehicle_bundle": {
        "endpoints": [
            "/idvs/awards/",
            "/idvs/activity/",
            "/idvs/funding/",
            "/idvs/funding_rollup/",
            "/idvs/amounts/{award_id}/",
        ],
        "methods": ["GET", "POST"],
        "cost_hint": 4,
    },
    "answer_award_spending_question": {
        "endpoints": [],  # Meta-tool, delegates to others
        "methods": [],
        "cost_hint": 5,  # High due to orchestration
    },
}


def get_endpoints_for_tool(tool_name: str) -> List[str]:
    """Return list of endpoints a tool may call."""
    return ENDPOINT_MAP.get(tool_name, {}).get("endpoints", [])


def get_cost_hint(tool_name: str) -> int:
    """Return estimated number of HTTP calls for a tool."""
    return ENDPOINT_MAP.get(tool_name, {}).get("cost_hint", 1)
