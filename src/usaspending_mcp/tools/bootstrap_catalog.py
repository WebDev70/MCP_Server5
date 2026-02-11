import time
from typing import Any, Dict, List, Optional

from usaspending_mcp.cache import Cache
from usaspending_mcp.response import fail, ok, pick_fields
from usaspending_mcp.usaspending_client import APIError, USAspendingClient

# Defaults
DEFAULT_INCLUDES = ["toptier_agencies", "award_types"]
CATALOG_CACHE_KEY = "bootstrap_catalog_v1"
CATALOG_TTL_SECONDS = 86400  # 24 hours
AGENCY_OUTPUT_FIELDS = ["agency_name", "toptier_code", "abbreviation"]

class BootstrapCatalogTool:
    def __init__(self, client: USAspendingClient, cache: Cache):
        self.client = client
        self.cache = cache

    def execute(
        self, 
        include: Optional[List[str]] = None, 
        force_refresh: bool = False,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        include = include or DEFAULT_INCLUDES
        request_id = request_id or f"req-{int(time.time())}"
        
        # Check cache unless forced
        if not force_refresh:
            cached_data, hit = self.cache.get(CATALOG_CACHE_KEY)
            if hit:
                # Filter cached catalog to requested keys, slim for output
                filtered_catalog = {k: v for k, v in cached_data.items() if k in include}
                if "toptier_agencies" in filtered_catalog:
                    filtered_catalog["toptier_agencies"] = pick_fields(
                        filtered_catalog["toptier_agencies"], AGENCY_OUTPUT_FIELDS
                    )
                return ok(
                    {"catalog": filtered_catalog},
                    request_id=request_id,
                    endpoints_used=["(cached)"],
                    cache_hit=True
                )

        catalog = {}
        endpoints_used = []
        
        try:
            # 1. Toptier Agencies
            if "toptier_agencies" in include:
                endpoint = "references/toptier_agencies/"
                resp = self.client.request("GET", endpoint, request_id=request_id, tool_name="bootstrap_catalog")
                catalog["toptier_agencies"] = resp.get("results", [])
                endpoints_used.append(endpoint)
            
            # 2. Award Types
            if "award_types" in include or "filter" in include:
                endpoint = "references/award_types/"
                resp = self.client.request("GET", endpoint, request_id=request_id, tool_name="bootstrap_catalog")
                # Response is a dict of groups (contracts, grants, loans, etc.)
                catalog["award_types"] = resp
                endpoints_used.append(endpoint)

            # 3. Submission Periods
            if "submission_periods" in include:
                 endpoint = "references/submission_periods/"
                 resp = self.client.request("GET", endpoint, request_id=request_id, tool_name="bootstrap_catalog")
                 catalog["submission_periods"] = resp.get("available_periods", [])
                 endpoints_used.append(endpoint)

            # Store full catalog in cache (resolve_entities needs full agency objects)
            self.cache.set(CATALOG_CACHE_KEY, catalog, ttl_seconds=CATALOG_TTL_SECONDS)

            # Slim output for LLM
            output = dict(catalog)
            if "toptier_agencies" in output:
                output["toptier_agencies"] = pick_fields(
                    output["toptier_agencies"], AGENCY_OUTPUT_FIELDS
                )

            return ok(
                {"catalog": output},
                request_id=request_id,
                endpoints_used=endpoints_used,
                cache_hit=False
            )

        except APIError as e:
            return fail(
                error_type=e.error_type,
                message=e.message,
                request_id=request_id,
                status_code=e.status_code,
                endpoint=e.endpoint,
                remediation_hint=e.to_dict()["error"]["remediation_hint"]
            )
        except Exception as e:
            return fail(
                error_type="unknown",
                message=str(e),
                request_id=request_id
            )

# Standalone function for use with FastMCP registry if needed, 
# but we typically register instances or functions that use a shared client/cache.
# For now, we'll keep the logic in the class and instantiate it in server.py
