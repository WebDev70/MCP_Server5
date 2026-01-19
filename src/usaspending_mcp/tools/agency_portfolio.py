import time
from typing import Any, Dict, List, Optional

from usaspending_mcp.award_types import SCOPE_ALL_AWARDS
from usaspending_mcp.response import fail, ok
from usaspending_mcp.tools.spending_rollups import SpendingRollupsTool
from usaspending_mcp.usaspending_client import APIError, USAspendingClient


class AgencyPortfolioTool:
    def __init__(self, client: USAspendingClient):
        self.client = client
        self.rollups = SpendingRollupsTool(client)

    def execute(
        self, 
        toptier_code: str,
        time_period: Optional[List[Dict[str, str]]] = None,
        views: Optional[List[str]] = None,
        scope_mode: str = SCOPE_ALL_AWARDS,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        
        request_id = request_id or f"req-{int(time.time())}"
        views = views or ["summary", "awards"]
        endpoints_used = []
        result_bundle = {}
        
        try:
            # 1. Agency Summary / Overview
            # Endpoint: /api/v2/agency/<toptier_code>/
            if "summary" in views:
                endpoint = f"agency/{toptier_code}/"
                try:
                    resp = self.client.request("GET", endpoint, request_id=request_id, tool_name="agency_portfolio")
                    result_bundle["summary"] = resp
                    endpoints_used.append(endpoint)
                except APIError as e:
                    # Some endpoints require FY param. 
                    # If 400 or 404, we might need to fallback or ignore.
                    result_bundle["summary_error"] = e.message

            # 2. Awards View (Top awards for this agency)
            # Use spending_rollups internally? No, user wants actual awards usually or rollup categories.
            # "awards" view usually implies "recent awards" or "breakdown".
            # Let's interpret "awards" as "Spending by Award Type" or "Top Awards". 
            # Given PRD says "summary + awards views", we'll provide top categories via rollups.
            
            if "awards" in views:
                # We'll fetch spending by Award Type (Category) for this agency
                # Filter by awarding_agency_id or toptier code
                # USASpending filters use "agencies": [{"type": "awarding", "tier": "toptier", "name": "Department of Defense"}]
                # But we have code. We might need to resolve code to name first if filter requires name?
                # Actually, API v2 filters often accept "agencies": [{"toptier_code": "097"}]?? No, usually strictly name or ID.
                # Wait, "agency" filter usually takes ID. 
                # Let's use `spending_rollups` with `awarding_agency` filter if possible.
                # Does `spending_rollups` support ID filter?
                # Our rollups tool uses `filters` dict passed directly. 
                # We need to construct the correct filter for Toptier Agency.
                
                # Filter schema: { "agencies": [ { "type": "awarding", "tier": "toptier", "toptier_code": "097" } ] }
                # Note: "toptier_code" key support depends on endpoint. 
                # award_search supports it. spending_by_category supports it.
                
                agency_filter = {
                    "agencies": [
                        {
                            "type": "awarding",
                            "tier": "toptier",
                            "toptier_code": toptier_code
                        }
                    ]
                }
                
                rollup_res = self.rollups.execute(
                    time_period=time_period,
                    filters=agency_filter,
                    group_by="recipient", # Top recipients for this agency
                    top_n=5,
                    scope_mode=scope_mode,
                    request_id=request_id
                )
                
                result_bundle["top_recipients"] = rollup_res.get("groups", [])
                endpoints_used.extend(rollup_res.get("meta", {}).get("endpoints_used", []))

            return ok(
                result_bundle,
                request_id=request_id,
                scope_mode=scope_mode,
                endpoints_used=endpoints_used
            )

        except APIError as e:
            return fail(e.error_type, e.message, request_id, endpoint=e.endpoint, status_code=e.status_code)
        except Exception as e:
            return fail("unknown", str(e), request_id)
