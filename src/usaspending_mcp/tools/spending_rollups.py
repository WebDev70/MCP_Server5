import time
from typing import Any, Dict, List, Optional

from usaspending_mcp.award_types import SCOPE_ALL_AWARDS, get_award_type_codes
from usaspending_mcp.response import fail, ok
from usaspending_mcp.usaspending_client import APIError, USAspendingClient


class SpendingRollupsTool:
    def __init__(self, client: USAspendingClient):
        self.client = client

    def _get_mapping_for_group_by(self, group_by: str) -> str:
        # Maps user-friendly group_by to API values
        mapping = {
            "agency": "awarding_agency",
            "awarding_agency": "awarding_agency",
            "funding_agency": "funding_agency",
            "recipient": "recipient",
            "recipient_duns": "recipient_duns",
            "state": "state",
            "country": "country",
            "psc": "psc",
            "naics": "naics",
            "assistance_listing": "cfda"
        }
        return mapping.get(group_by, group_by)

    def execute(
        self, 
        time_period: Optional[List[Dict[str, str]]] = None, 
        filters: Optional[Dict[str, Any]] = None, 
        group_by: str = "awarding_agency", 
        top_n: int = 10, 
        metric: str = "obligations",  # obligations (usually)
        scope_mode: str = SCOPE_ALL_AWARDS,
        award_type_groups: Optional[List[str]] = None,
        debug: bool = False,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        
        request_id = request_id or f"req-{int(time.time())}"
        filters = filters or {}
        
        # Enforce cap
        if not debug and top_n > 25:
            top_n = 25
            
        # Apply award types
        explicit_codes = filters.get("award_type_codes")
        if not explicit_codes:
            inferred_codes = get_award_type_codes(scope_mode)
            if inferred_codes:
                filters["award_type_codes"] = inferred_codes

        if time_period:
            filters["time_period"] = time_period

        # Clean filters (simple recursive clean)
        # We can reuse the normalizer from award_search if we refactor, but for now duplicate simple one
        def normalize(d):
            if isinstance(d, dict):
                return {k: normalize(v) for k, v in d.items() if v not in (None, "", [], {}) and normalize(v) not in (None, "", [], {})}
            if isinstance(d, list):
                return [normalize(x) for x in d if x not in (None, "", [], {})]
            return d
        
        filters = normalize(filters)
        
        api_group = self._get_mapping_for_group_by(group_by)
        endpoints_used = []

        # Attempt Tier A: True Rollup
        # Endpoint: /api/v2/search/spending_by_category/
        # This is the standard rollup endpoint for advanced filters
        
        # Mapping group_by to category
        category_mapping = {
            "awarding_agency": "awarding_agency",
            "funding_agency": "funding_agency",
            "recipient": "recipient",
            "cfda": "cfda",
            "psc": "psc",
            "naics": "naics",
            "state": "state_territory",
            "country": "country"
        }
        
        category = category_mapping.get(api_group)
        
        if category:
            try:
                endpoint = f"search/spending_by_category/{category}/"
                payload = {
                    "filters": filters,
                    "limit": top_n,
                    "page": 1
                }
                
                resp = self.client.request("POST", endpoint, json_data=payload, request_id=request_id, tool_name="spending_rollups")
                endpoints_used.append(endpoint)
                
                return ok(
                    {
                        "groups": resp.get("results", []),
                        "total_groups": resp.get("page_metadata", {}).get("total", 0)
                    },
                    request_id=request_id,
                    scope_mode=scope_mode,
                    endpoints_used=endpoints_used,
                    accuracy_tier="A"
                )
            except APIError:
                # Fallback to Tier C if standard rollup fails
                pass
        
        # Fallback Tier C: Award Search Sampling
        # This is expensive and approximate.
        try:
            endpoint = "search/spending_by_award/"
            # Limit to 100 to approximate top N
            payload = {
                "filters": filters,
                "fields": ["Award Amount", api_group], # Need to check if api_group is a valid field name. 
                # This is risky. If group_by is not a field, this fails. 
                # Common fields: Recipient Name, Awarding Agency, etc.
                "limit": 100, 
                "sort": "Award Amount",
                "order": "desc"
            }
            # Mapping group to field name for fallback
            field_map = {
                "awarding_agency": "Awarding Agency",
                "funding_agency": "Funding Agency",
                "recipient": "Recipient Name",
                "state": "Place of Performance State Code" # Simplified
            }
            field_name = field_map.get(api_group)
            
            if not field_name:
                return fail(
                    "validation", 
                    f"Cannot fallback for group_by='{group_by}': No field mapping available.", 
                    request_id=request_id
                )
                
            payload["fields"] = ["Award Amount", field_name]
            
            resp = self.client.request("POST", endpoint, json_data=payload, request_id=request_id, tool_name="spending_rollups_fallback")
            endpoints_used.append(endpoint)
            
            results = resp.get("results", [])
            
            # Simple aggregation in memory
            groups = {}
            for r in results:
                key = r.get(field_name, "Unknown")
                amt = r.get("Award Amount", 0) or 0
                groups[key] = groups.get(key, 0) + amt
                
            # Sort and take top N
            sorted_groups = sorted(groups.items(), key=lambda x: x[1], reverse=True)[:top_n]
            formatted_groups = [{"name": k, "amount": v} for k, v in sorted_groups]
            
            return ok(
                {
                    "groups": formatted_groups,
                    "note": "Approximated from top 100 awards."
                },
                request_id=request_id,
                scope_mode=scope_mode,
                endpoints_used=endpoints_used,
                accuracy_tier="C",
                warnings=["approximate_total", "fallback_used"]
            )
            
        except Exception as e:
            return fail("unknown", f"Rollup failed: {str(e)}", request_id)
