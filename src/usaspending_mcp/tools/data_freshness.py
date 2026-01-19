import time
from typing import Dict, Any, Optional
from datetime import datetime, date
from usaspending_mcp.usaspending_client import USAspendingClient, APIError
from usaspending_mcp.response import ok, fail

class DataFreshnessTool:
    def __init__(self, client: USAspendingClient):
        self.client = client

    def _parse_date(self, date_str: str) -> date | None:
        """Parse date string in various formats (ISO 8601, YYYY-MM-DD, MM/DD/YYYY)."""
        if not date_str:
            return None
        # Try ISO 8601 with time component (e.g., 2024-01-18T00:00:00Z)
        for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%m/%d/%Y"):
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        return None

    def execute(
        self, 
        check_type: str = "submission_periods", 
        agency_code: Optional[str] = None, 
        debug: bool = False,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        
        request_id = request_id or f"req-{int(time.time())}"
        endpoints_used = []
        freshness_data = {}
        
        try:
            # 1. Submission Periods (System-wide freshness)
            if check_type in ("submission_periods", "all"):
                endpoint = "references/submission_periods/"
                resp = self.client.request("GET", endpoint, request_id=request_id, tool_name="data_freshness")
                endpoints_used.append(endpoint)
                
                # Find latest closed period
                periods = resp.get("available_periods", [])
                
                # Filter for quarterly periods as requested
                quarterly_periods = [p for p in periods if p.get("is_quarter") is True]
                
                if quarterly_periods:
                    # Sort by year desc, quarter desc
                    quarterly_periods.sort(key=lambda x: (x.get("submission_fiscal_year", 0), x.get("submission_fiscal_quarter", 0)), reverse=True)
                    latest = quarterly_periods[0]
                    
                    freshness_data["latest_period"] = {
                        "fy": latest.get("submission_fiscal_year"),
                        "quarter": latest.get("submission_fiscal_quarter"),
                        "submission_due": latest.get("submission_due_date"),
                        "period_start": latest.get("period_start_date"),
                        "period_end": latest.get("period_end_date")
                    }
                    
                    # Calculate days since end
                    end_date_str = latest.get("period_end_date")
                    if end_date_str:
                        end_date = self._parse_date(end_date_str)
                        if end_date:
                            days_since = (date.today() - end_date).days
                            freshness_data["days_since_period_close"] = days_since

            # 2. Last Updated (DB freshness)
            if check_type in ("last_updated", "all"):
                endpoint = "awards/last_updated/"
                try:
                    resp = self.client.request("GET", endpoint, request_id=request_id, tool_name="data_freshness")
                    endpoints_used.append(endpoint)
                    
                    last_update = resp.get("last_updated")
                    freshness_data["data_as_of"] = last_update
                    
                    if last_update:
                        update_date = self._parse_date(last_update)
                        if update_date:
                            freshness_data["days_since_update"] = (date.today() - update_date).days
                            
                except APIError as e:
                    if e.status_code != 404: # Maybe not available
                        raise e

            # 3. Agency Reporting (Specific agency)
            if check_type == "agency_reporting":
                if not agency_code:
                    return fail("validation", "agency_code required for agency_reporting check", request_id)
                    
                endpoint = f"reporting/agencies/{agency_code}/overview/"
                resp = self.client.request("GET", endpoint, request_id=request_id, tool_name="data_freshness")
                endpoints_used.append(endpoint)
                
                freshness_data["agency_status"] = {
                    "fiscal_year": resp.get("fiscal_year"),
                    "toptier_code": resp.get("toptier_code"),
                    "latest_upload_date": resp.get("latest_upload_date"), # if available
                    # Actually overview returns list of years? No, usually specific FY via params. 
                    # If param missing, defaults to current?
                    # The response schema usually includes reporting stats.
                    # We'll just dump interesting fields.
                    "total_dollars_obligated": resp.get("total_dollars_obligated"),
                    "current_total_budget_authority_amount": resp.get("current_total_budget_authority_amount"),
                    # Check for missing submission?
                }

            return ok(
                {"freshness": freshness_data},
                request_id=request_id,
                endpoints_used=endpoints_used
            )

        except APIError as e:
            return fail(e.error_type, e.message, request_id, endpoint=e.endpoint, status_code=e.status_code)
        except Exception as e:
            return fail("unknown", str(e), request_id)
