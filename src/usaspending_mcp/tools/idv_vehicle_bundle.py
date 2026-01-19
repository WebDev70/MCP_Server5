import time
from typing import Any, Dict, List, Optional

from usaspending_mcp.award_types import SCOPE_ASSISTANCE_ONLY
from usaspending_mcp.response import fail, ok, out_of_scope
from usaspending_mcp.usaspending_client import APIError, USAspendingClient


class IDVVehicleBundleTool:
    def __init__(self, client: USAspendingClient):
        self.client = client

    def execute(
        self, 
        idv_award_id: str,
        include: Optional[List[str]] = None,
        time_period: Optional[List[Dict[str, str]]] = None,
        scope_mode: str = "all_awards",
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        
        request_id = request_id or f"req-{int(time.time())}"
        include = include or ["orders", "funding_rollup"]
        endpoints_used = []
        result_bundle = {}

        # 1. Scope Validation
        # IDVs are purely contracts.
        if scope_mode == SCOPE_ASSISTANCE_ONLY:
             return out_of_scope(
                 request_id=request_id,
                 scope_mode=scope_mode,
                 feature_name="IDV/Contract Vehicles",
                 remediation_hint="IDVs are strictly contracts. Switch to 'all_awards' or 'contracts_only'."
             )

        try:
            # 2. Task Orders (Awards under IDV)
            if "orders" in include:
                endpoint = "idvs/awards/"
                # Filters needed? Or payload?
                # Docs say payload requires "award_id" (which is the PIID/IDV ID).
                # Actually, check endpoint usage: POST /api/v2/idvs/awards/
                # Payload: { "award_id": ... }
                payload = {"award_id": idv_award_id}
                
                # Note: This endpoint lists awards related to the IDV.
                # It supports pagination, sort, order.
                # We'll default to limit 10 for bundle.
                payload["limit"] = 10
                payload["page"] = 1
                
                resp = self.client.request("POST", endpoint, json_data=payload, request_id=request_id, tool_name="idv_vehicle_bundle")
                result_bundle["orders"] = resp.get("results", [])
                endpoints_used.append(endpoint)
            
            # 3. Activity (by year/month)
            if "activity" in include:
                endpoint = "idvs/activity/"
                payload = {"award_id": idv_award_id}
                resp = self.client.request("POST", endpoint, json_data=payload, request_id=request_id, tool_name="idv_vehicle_bundle")
                result_bundle["activity"] = resp.get("results", [])
                endpoints_used.append(endpoint)

            # 4. Funding Rollup (by agency/account)
            if "funding_rollup" in include:
                endpoint = "idvs/funding_rollup/"
                payload = {"award_id": idv_award_id}
                resp = self.client.request("POST", endpoint, json_data=payload, request_id=request_id, tool_name="idv_vehicle_bundle")
                # Structure: { "total_transaction_obligated_amount": ..., "awarding_agency_count": ..., ... }
                result_bundle["funding_rollup"] = resp
                endpoints_used.append(endpoint)

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
