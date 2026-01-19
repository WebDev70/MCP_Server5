import time
from typing import Any, Dict, List, Optional

from usaspending_mcp.award_types import (
    FALLBACK_CONTRACT_CODES,
    FALLBACK_IDV_CODES,
    SCOPE_ALL_AWARDS,
    SCOPE_ASSISTANCE_ONLY,
    SCOPE_CONTRACTS_ONLY,
)
from usaspending_mcp.response import fail, ok, out_of_scope
from usaspending_mcp.usaspending_client import APIError, USAspendingClient


class AwardExplainTool:
    def __init__(self, client: USAspendingClient):
        self.client = client

    def _validate_scope(self, award_summary: Dict[str, Any], scope_mode: str) -> bool:
        """
        Validates if the award type fits the requested scope_mode.
        """
        if scope_mode == SCOPE_ALL_AWARDS:
            return True
            
        award_type = award_summary.get("type")
        if not award_type:
            # If type is missing, we can't strict validate, so permissive or strict?
            # Safe to assume permissive for now or reject. Let's be permissive but warn?
            # Actually, standard behavior is strict. If no type, it's weird.
            return True 
            
        is_contract = (award_type in FALLBACK_CONTRACT_CODES) or (award_type in FALLBACK_IDV_CODES) or (award_type.startswith("IDV"))
        
        # Assistance includes grants, loans, etc.
        # Check if NOT contract
        is_assistance = not is_contract
        
        if scope_mode == SCOPE_CONTRACTS_ONLY:
            return is_contract
        if scope_mode == SCOPE_ASSISTANCE_ONLY:
            return is_assistance
            
        return True

    def execute(
        self, 
        award_id: str,
        include: Optional[List[str]] = None, 
        transactions_limit: int = 25,
        subawards_limit: int = 25,
        scope_mode: str = SCOPE_ALL_AWARDS,
        debug: bool = False,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        
        request_id = request_id or f"req-{int(time.time())}"
        include = include or ["summary", "transactions"]
        endpoints_used = []
        result_bundle = {}
        
        try:
            # 1. Fetch Summary (Always needed for validation)
            endpoint_summary = f"awards/{award_id}/"
            resp_summary = self.client.request("GET", endpoint_summary, request_id=request_id, tool_name="award_explain")
            endpoints_used.append(endpoint_summary)
            
            # Unpack validation
            # Note: /api/v2/awards/{id}/ returns keys like "id", "type", "category", etc.
            # We assume standard response shape.
            
            if not self._validate_scope(resp_summary, scope_mode):
                return out_of_scope(
                    request_id=request_id,
                    scope_mode=scope_mode,
                    feature_name=f"Award {award_id} (type={resp_summary.get('type')})",
                    remediation_hint="This award does not match the requested scope mode."
                )
                
            if "summary" in include:
                result_bundle["summary"] = resp_summary
                
            # 2. Transactions
            if "transactions" in include:
                endpoint_tx = "transactions/"
                payload_tx = {
                    "award_id": award_id,
                    "limit": transactions_limit,
                    "page": 1,
                    "sort": "action_date",
                    "order": "desc"
                }
                resp_tx = self.client.request("POST", endpoint_tx, json_data=payload_tx, request_id=request_id, tool_name="award_explain")
                endpoints_used.append(endpoint_tx)
                
                tx_results = resp_tx.get("results", [])
                result_bundle["transactions"] = tx_results[:transactions_limit]
                
                # Copy total metadata if available
                # Often in page_metadata
                page_meta = resp_tx.get("page_metadata", {})
                if "total" in page_meta:
                     result_bundle["transactions_total"] = page_meta["total"]

            # 3. Subawards
            if "subawards" in include:
                endpoint_sub = "subawards/"
                payload_sub = {
                    "award_id": award_id,
                    "limit": subawards_limit,
                    "page": 1,
                    "order": "desc", 
                    "sort": "subaward_amount"
                }
                resp_sub = self.client.request("POST", endpoint_sub, json_data=payload_sub, request_id=request_id, tool_name="award_explain")
                endpoints_used.append(endpoint_sub)
                
                sub_results = resp_sub.get("results", [])
                result_bundle["subawards"] = sub_results[:subawards_limit]
                
                page_meta = resp_sub.get("page_metadata", {})
                if "total" in page_meta:
                     result_bundle["subawards_total"] = page_meta["total"]

            return ok(
                result_bundle,
                request_id=request_id,
                scope_mode=scope_mode,
                endpoints_used=endpoints_used,
                # Note: Cache logic is usually handled by the caller or specialized cache decorator if we wanted strictly scoped caching.
                # Here we just execute.
            )

        except APIError as e:
            return fail(e.error_type, e.message, request_id, endpoint=e.endpoint, status_code=e.status_code)
        except Exception as e:
            return fail("unknown", str(e), request_id)
