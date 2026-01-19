import time
from typing import Any, Dict, List, Optional

from usaspending_mcp.award_types import FALLBACK_IDV_CODES, SCOPE_ASSISTANCE_ONLY
from usaspending_mcp.response import fail, ok, out_of_scope
from usaspending_mcp.usaspending_client import APIError, USAspendingClient


class IDVVehicleBundleTool:
    def __init__(self, client: USAspendingClient):
        self.client = client

    def _resolve_idv_id(self, idv_input: str, request_id: str) -> tuple[str, list[str]]:
        """
        Resolve an IDV identifier to its generated_unique_award_id.

        Args:
            idv_input: Either a PIID (e.g., "NNK14MA74C") or generated_unique_award_id
                       (e.g., "CONT_IDV_NNK14MA74C_8000")
            request_id: Request ID for API calls

        Returns:
            Tuple of (resolved_id, endpoints_used)
        """
        endpoints_used = []

        # If already in generated_unique_award_id format, use directly
        if idv_input.startswith("CONT_IDV_"):
            return idv_input, endpoints_used

        # Otherwise, search for the IDV by PIID/keyword
        endpoint = "search/spending_by_award/"
        payload = {
            "filters": {
                "keywords": [idv_input],
                "award_type_codes": FALLBACK_IDV_CODES
            },
            "limit": 1,
            "fields": ["Award ID", "generated_internal_id"]
        }

        resp = self.client.request("POST", endpoint, json_data=payload,
                                   request_id=request_id, tool_name="idv_vehicle_bundle")
        endpoints_used.append(endpoint)

        results = resp.get("results", [])
        if results:
            resolved_id = results[0].get("generated_internal_id")
            if resolved_id:
                return resolved_id, endpoints_used

        # Fallback: return original input and let the API handle any errors
        return idv_input, endpoints_used

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
            # 2. Resolve IDV ID (PIID -> generated_unique_award_id if needed)
            resolved_id, resolve_endpoints = self._resolve_idv_id(idv_award_id, request_id)
            endpoints_used.extend(resolve_endpoints)
            result_bundle["resolved_idv_id"] = resolved_id
            # 3. Task Orders (Awards under IDV)
            if "orders" in include:
                endpoint = "idvs/awards/"
                # POST /api/v2/idvs/awards/ requires:
                # - award_id: the generated_unique_award_id (e.g., "CONT_IDV_...")
                # - type: "child_awards" to return child awards (REQUIRED - without this, returns empty)
                payload = {
                    "award_id": resolved_id,
                    "type": "child_awards",  # Required to get child awards
                    "limit": 10,
                    "page": 1
                }

                resp = self.client.request("POST", endpoint, json_data=payload, request_id=request_id, tool_name="idv_vehicle_bundle")
                result_bundle["orders"] = resp.get("results", [])
                endpoints_used.append(endpoint)

            # 4. Activity (by year/month)
            if "activity" in include:
                endpoint = "idvs/activity/"
                payload = {"award_id": resolved_id}
                resp = self.client.request("POST", endpoint, json_data=payload, request_id=request_id, tool_name="idv_vehicle_bundle")
                result_bundle["activity"] = resp.get("results", [])
                endpoints_used.append(endpoint)

            # 5. Funding Rollup (by agency/account)
            if "funding_rollup" in include:
                endpoint = "idvs/funding_rollup/"
                payload = {"award_id": resolved_id}
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
