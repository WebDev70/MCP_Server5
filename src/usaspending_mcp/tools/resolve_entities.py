import time
from typing import Any, Dict, List, Optional

from usaspending_mcp.cache import Cache
from usaspending_mcp.response import fail, ok, pick_fields
from usaspending_mcp.usaspending_client import APIError, USAspendingClient

CACHE_TTL = 3600  # 1 hour
DEFAULT_TYPES = ["agency", "recipient"]
AGENCY_OUTPUT_FIELDS = ["agency_name", "toptier_code", "abbreviation"]

class ResolveEntitiesTool:
    def __init__(self, client: USAspendingClient, cache: Cache):
        self.client = client
        self.cache = cache

    def execute(
        self, 
        q: str, 
        types: Optional[List[str]] = None, 
        limit: int = 5,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        request_id = request_id or f"req-{int(time.time())}"
        types = types or DEFAULT_TYPES
        
        # Check cache
        cache_key = {
            "tool": "resolve_entities",
            "q": q.lower(),
            "types": sorted(types),
            "limit": limit
        }
        cached_data, hit = self.cache.get(cache_key)
        if hit:
            return ok(
                cached_data, 
                request_id=request_id,
                endpoints_used=["(cached)"],
                cache_hit=True
            )

        matches = {k: [] for k in types}
        endpoints_used = []
        notes = []

        try:
            # 1. Agencies (Local Search from Toptier List)
            if "agency" in types:
                # We need the full agency list. We could use BootstrapCatalogTool logic here,
                # but for simplicity we'll fetch/cache the list directly or assume it's pre-loaded.
                # In a real app, we might share the catalog instance. Here we'll just fetch it if needed.
                # Ideally, we should use a shared catalog service, but we'll fetch it here and rely on client cache or short TTL.
                
                # Check if we have agencies in cache under the catalog key to avoid re-fetching
                catalog_data, catalog_hit = self.cache.get("bootstrap_catalog_v1")
                agencies = []
                
                if catalog_hit and "toptier_agencies" in catalog_data:
                    agencies = catalog_data["toptier_agencies"]
                else:
                    # Fetch fresh if missing
                    endpoint = "references/toptier_agencies/"
                    resp = self.client.request("GET", endpoint, request_id=request_id, tool_name="resolve_entities")
                    agencies = resp.get("results", [])
                    endpoints_used.append(endpoint)
                
                # Simple containment search
                q_lower = q.lower()
                agency_matches = []
                for agency in agencies:
                    name = agency.get("agency_name", "") or agency.get("toptier_code", "")
                    abbrev = agency.get("abbreviation", "")
                    
                    if q_lower in name.lower() or (abbrev and q_lower == abbrev.lower()):
                        agency_matches.append(agency)
                
                # Sort by simple relevance (exact match first, then starts with)
                agency_matches.sort(key=lambda x: (
                    x.get("abbreviation", "").lower() != q_lower, # Abbrev match first
                    not x.get("agency_name", "").lower().startswith(q_lower), # Starts with second
                    x.get("agency_name") # Alphabetical
                ))
                
                matches["agency"] = pick_fields(agency_matches[:limit], AGENCY_OUTPUT_FIELDS)

            # 2. Recipients (Autocomplete API)
            if "recipient" in types:
                endpoint = "autocomplete/recipient/"
                payload = {"search_text": q, "limit": limit}
                resp = self.client.request("POST", endpoint, json_data=payload, request_id=request_id, tool_name="resolve_entities")
                matches["recipient"] = resp.get("results", [])
                endpoints_used.append(endpoint)

            # 3. NAICS (Autocomplete API - assumed available based on standard USASpending structure)
            if "naics" in types:
                # Try glossaries or filter tree if autocomplete isn't direct. 
                # Checking API docs, /api/v2/references/filter_tree/naics/ exists, 
                # but autocomplete might be separate. We'll try a common pattern or skip if unsure.
                # Given PRD says "POST /autocomplete/naics/ (if available)", let's assume it is or use filter tree search logic.
                # For safety in v1, let's omit if not standard. 
                # Actually, standard usage often implies `api/v2/autocomplete/funding_agency` etc. 
                # Let's try `api/v2/autocomplete/naics` if it exists, otherwise note it.
                # We'll stick to PRD request: "POST /autocomplete/naics/"
                try:
                    endpoint = "autocomplete/naics/" 
                    payload = {"search_text": q, "limit": limit}
                    # This might 404 if not real. Wrapping in try/except for this specific block if we aren't sure.
                    # However, usually we want to fail or just log. We'll attempt it.
                    resp = self.client.request("POST", endpoint, json_data=payload, request_id=request_id, tool_name="resolve_entities")
                    matches["naics"] = resp.get("results", [])
                    endpoints_used.append(endpoint)
                except APIError as e:
                    if e.status_code == 404:
                         notes.append("NAICS autocomplete endpoint not found.")
                    else:
                        raise e

            # 4. PSC (Autocomplete API)
            if "psc" in types:
                try:
                    endpoint = "autocomplete/psc/"
                    payload = {"search_text": q, "limit": limit}
                    resp = self.client.request("POST", endpoint, json_data=payload, request_id=request_id, tool_name="resolve_entities")
                    matches["psc"] = resp.get("results", [])
                    endpoints_used.append(endpoint)
                except APIError as e:
                    if e.status_code == 404:
                         notes.append("PSC autocomplete endpoint not found.")
                    else:
                        raise e

            # 5. Assistance Listing (CFDA)
            if "assistance_listing" in types:
                # often under /api/v2/autocomplete/assistance_listing/ or similar
                try:
                    endpoint = "autocomplete/assistance_listing/"
                    payload = {"search_text": q, "limit": limit}
                    resp = self.client.request("POST", endpoint, json_data=payload, request_id=request_id, tool_name="resolve_entities")
                    matches["assistance_listing"] = resp.get("results", [])
                    endpoints_used.append(endpoint)
                except APIError:
                     notes.append("Assistance Listing autocomplete endpoint failed or not found.")


            result_data = {"matches": matches, "notes": notes}
            
            # Cache result
            self.cache.set(cache_key, result_data, ttl_seconds=CACHE_TTL)

            return ok(
                result_data,
                request_id=request_id,
                endpoints_used=endpoints_used,
                cache_hit=False
            )

        except APIError as e:
            return fail(e.error_type, e.message, request_id, endpoint=e.endpoint, status_code=e.status_code)
        except Exception as e:
            return fail("unknown", str(e), request_id)
