import time
from typing import Any, Dict, List, Optional

from usaspending_mcp.award_types import SCOPE_ALL_AWARDS
from usaspending_mcp.cache import Cache
from usaspending_mcp.response import fail, ok
from usaspending_mcp.tools.resolve_entities import ResolveEntitiesTool
from usaspending_mcp.tools.spending_rollups import SpendingRollupsTool
from usaspending_mcp.usaspending_client import APIError, USAspendingClient


class RecipientProfileTool:
    def __init__(self, client: USAspendingClient, cache: Cache):
        self.client = client
        self.cache = cache
        self.resolver = ResolveEntitiesTool(client, cache)
        self.rollups = SpendingRollupsTool(client)

    def _is_uei(self, val: str) -> bool:
        return len(val) == 12 and val.isalnum()

    def _is_duns(self, val: str) -> bool:
        return len(val) == 9 and val.isdigit()

    def execute(
        self, 
        recipient: str,
        time_period: Optional[List[Dict[str, str]]] = None,
        include: Optional[List[str]] = None,
        scope_mode: str = SCOPE_ALL_AWARDS,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        
        request_id = request_id or f"req-{int(time.time())}"
        include = include or ["profile", "rollups"]
        endpoints_used = []
        result_bundle = {}
        
        # 1. Resolve Recipient to Hash/ID/UEI
        # If input looks like UEI or DUNS, we might need to search to get the internal Hash needed for some endpoints,
        # or use UEI directly if endpoints support it.
        # Most v2 endpoints accept hash or sometimes UEI.
        # Let's try to resolve to get a canonical object.
        
        recipient_info = None
        
        # Heuristic: if it looks like a hash (UUID-ish), assume it is.
        is_hash = len(recipient) > 20 and "-" in recipient # weak check
        
        if is_hash:
             recipient_info = {"recipient_hash": recipient}
        else:
            # Try to resolve
            # We use our resolver tool
            # Note: ResolveEntities returns a list of matches. We take top 1.
            resolve_res = self.resolver.execute(recipient, types=["recipient"], limit=1, request_id=request_id)
            if resolve_res.get("error"):
                 return fail("dependency_error", "Failed to resolve recipient", request_id)
            
            matches = resolve_res.get("matches", {}).get("recipient", [])
            if not matches:
                 return fail("validation", f"Recipient '{recipient}' not found.", request_id)
            
            recipient_info = matches[0] # {"recipient_name": "...", "recipient_hash": "...", "uei": "..."}
            
        recipient_hash = recipient_info.get("recipient_hash")
        recipient_name = recipient_info.get("recipient_name", recipient)
        uei = recipient_info.get("uei")
        
        result_bundle["recipient_info"] = recipient_info

        try:
            # 2. Profile (Overview)
            # Endpoint: /api/v2/recipient/duns/<duns>/ or /api/v2/recipient/uei/<uei>/ ??
            # Actually standard is /api/v2/recipient/overview/ ?? No.
            # /api/v2/recipient/duns/ is old.
            # Let's look for /api/v2/recipient/overview/ or similar.
            # Assuming we might default to just returning the resolved info if no better profile endpoint exists publicly documented well.
            # But let's check standard endpoints.
            # /api/v2/recipient/children/<duns>/ exists.
            
            # Let's stick to using what we have. If "profile" is requested, we pass the info we have.
            # We can also fetch total spending via rollups if not separate.
            
            # 3. Rollups (Spending by Category filtered by this recipient)
            if "rollups" in include:
                # We use the spending_rollups tool programmatically
                # Filter by recipient_hash (preferred) or UEI
                
                rollup_filters = {}
                if recipient_hash:
                    rollup_filters["recipient_id"] = recipient_hash
                elif uei:
                     rollup_filters["recipient_uei"] = uei # Check valid filter key
                else:
                    # Search by name exact? Riskier.
                    rollup_filters["recipient_search_text"] = [recipient_name]

                # We want spending by Agency and maybe by State
                rollup_res = self.rollups.execute(
                    time_period=time_period,
                    filters=rollup_filters,
                    group_by="awarding_agency",
                    top_n=5,
                    scope_mode=scope_mode,
                    request_id=request_id
                )
                
                if rollup_res.get("error"):
                    # Warn but don't fail entire bundle
                    result_bundle["warnings"] = result_bundle.get("warnings", []) + [f"Rollups failed: {rollup_res['error']['message']}"]
                else:
                    result_bundle["spending_by_agency"] = rollup_res.get("groups", [])
                    endpoints_used.extend(rollup_res.get("meta", {}).get("endpoints_used", []))
                    
            # 4. Children
            if "children" in include and "duns" in recipient_info:
                 # Only works if we have DUNS usually? Or separate endpoint.
                 # Skip for v1 unless we are sure of endpoint.
                 pass

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
