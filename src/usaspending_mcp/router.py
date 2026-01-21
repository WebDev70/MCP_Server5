import json
import os
import re
import time
from typing import Any, Dict, Optional

from usaspending_mcp.award_types import SCOPE_ASSISTANCE_ONLY, infer_scope_mode
from usaspending_mcp.cache import Cache
from usaspending_mcp.response import fail, trim_payload
from usaspending_mcp.tools.agency_portfolio import AgencyPortfolioTool
from usaspending_mcp.tools.award_explain import AwardExplainTool
from usaspending_mcp.tools.award_search import AwardSearchTool
from usaspending_mcp.tools.idv_vehicle_bundle import IDVVehicleBundleTool
from usaspending_mcp.tools.recipient_profile import RecipientProfileTool

# Tools imports (to be initialized by Router or Server)
from usaspending_mcp.tools.resolve_entities import ResolveEntitiesTool
from usaspending_mcp.tools.spending_rollups import SpendingRollupsTool
from usaspending_mcp.usaspending_client import USAspendingClient


class Router:
    def __init__(self, client: USAspendingClient, cache: Cache):
        self.client = client
        self.cache = cache
        self.rules = self._load_rules()
        
        # Tools initialized here for direct access
        self.tools = {
            "resolve_entities": ResolveEntitiesTool(client, cache),
            "award_search": AwardSearchTool(client),
            "award_explain": AwardExplainTool(client),
            "spending_rollups": SpendingRollupsTool(client),
            "recipient_profile": RecipientProfileTool(client, cache),
            "agency_portfolio": AgencyPortfolioTool(client),
            "idv_vehicle_bundle": IDVVehicleBundleTool(client)
        }

    def _load_rules(self) -> Dict[str, Any]:
        path = os.path.join(os.path.dirname(__file__), "router_rules.json")
        with open(path, "r") as f:
            return json.load(f)

    def _extract_signals(self, question: str) -> Dict[str, Any]:
        """
        Parses the question for routing signals.
        """
        q_lower = question.lower()
        
        # Determine scope mode using rules default if ambiguous? 
        # infer_scope_mode defaults to all_awards currently.
        # We can pass the rules default to it if we modify it, but let's stick to using the result.
        inferred_scope = infer_scope_mode(question)
        
        signals = {
            "scope_mode": inferred_scope,
            "award_id": None,
            "has_agency_hint": False,
            "has_recipient_hint": False,
            "intent_total_or_top_n": False,
            "intent_idv": False,
            "intent_list": False,
            "intent_explain": False,
            "intent_agency_portfolio": False,
            "intent_recipient_profile": False,
            "intent_resolve": False,
            "agency_type_hint": "awarding_agency", # Default
            "time_period": None, 
            "top_n": None,
            "entities": []
        }

        # Regex for Award IDs
        award_id_match = re.search(r"\b([A-Z0-9_-]{10,})\b", question)
        common_words = ["CONTRACT", "GRANT", "AWARD", "LOAN", "TOTAL", "SPENDING", "FISCAL", "YEAR"]
        if award_id_match:
            candidate = award_id_match.group(1)
            if candidate.upper() not in common_words and len(candidate) > 4 and any(c.isdigit() for c in candidate):
                signals["award_id"] = candidate

        # Intent detection
        if any(w in q_lower for w in ["total", "how much", "sum", "top ", "breakdown", "spend"]):
            signals["intent_total_or_top_n"] = True
            
        if any(w in q_lower for w in ["list", "show awards", "find awards", "search"]):
            signals["intent_list"] = True

        if any(w in q_lower for w in ["idv", "idiq", "bpa", "gwac", "vehicle", "task order"]):
            signals["intent_idv"] = True
            
        if any(w in q_lower for w in ["explain", "details", "transaction", "subaward", "history"]):
            signals["intent_explain"] = True

        if any(w in q_lower for w in ["resolve", "lookup", "find entity", "search for entity"]):
            signals["intent_resolve"] = True

        if any(w in q_lower for w in ["agency", "department", "bureau"]):
            signals["has_agency_hint"] = True
            
        if any(w in q_lower for w in ["recipient", "company", "vendor", "organization"]):
            signals["has_recipient_hint"] = True
            
        # Agency type inference (funding vs awarding)
        agency_keywords = self.rules.get("design_decisions", {}).get("agency_inference_keywords", {})
        for keyword, agency_type in agency_keywords.items():
            if keyword in q_lower:
                signals["agency_type_hint"] = agency_type
                break # First match wins? Or prioritize 'funded by'?
            
        if "profile" in q_lower and signals["has_recipient_hint"]:
            signals["intent_recipient_profile"] = True
            
        if "portfolio" in q_lower or ("overview" in q_lower and signals["has_agency_hint"]):
             signals["intent_agency_portfolio"] = True
             
        return signals

    def route_request(self, question: str, debug: bool = False, request_id: Optional[str] = None) -> Dict[str, Any]:
        request_id = request_id or f"req-{int(time.time())}"
        start_time = time.time()
        
        signals = self._extract_signals(question)
        scope_mode = signals["scope_mode"]
        
        # Check budgets
        budgets = self.rules["budgets"]
        
        # PLAN SELECTION
        selected_route = None
        
        # Resolve entities logic omitted for brevity (using stubs)
        resolved_entities = {}
        
        for route in self.rules["routes"]:
            preconditions = route.get("preconditions", [])
            deny_if = route.get("deny_if", [])
            
            # Check Deny
            if "scope_assistance_only" in deny_if and scope_mode == SCOPE_ASSISTANCE_ONLY:
                continue
                
            # Check Preconditions
            satisfied = True
            for p in preconditions:
                if p == "intent_total_or_top_n" and not signals["intent_total_or_top_n"]:
                    satisfied = False
                elif p == "intent_idv" and not signals["intent_idv"]:
                    satisfied = False
                elif p == "has_award_id" and not signals["award_id"]:
                    satisfied = False
                elif p == "intent_explain" and not signals["intent_explain"]:
                    satisfied = False
                elif p == "intent_recipient_profile" and not signals["intent_recipient_profile"]:
                    satisfied = False
                elif p == "intent_resolve" and not signals["intent_resolve"]:
                    satisfied = False
                elif p == "has_agency_id" and not resolved_entities.get("agency"):
                     satisfied = False
                elif p == "has_recipient" and not resolved_entities.get("recipient"):
                     satisfied = False
                elif p == "intent_agency_portfolio" and not signals["intent_agency_portfolio"]:
                     satisfied = False
            
            if satisfied:
                selected_route = route
                break
        
        if not selected_route:
            selected_route = [r for r in self.rules["routes"] if r["name"] == "award_search"][0]

        tool_name = selected_route["name"]
        
        # Budget Check
        estimated_cost = selected_route.get("cost_hint", 1)
        if estimated_cost > budgets["max_usaspending_requests"]:
             return fail(
                 "budget_exceeded", 
                 "Refinement required: Request is too broad or complex.", 
                 request_id,
                 meta_additions={"refinement_suggestion": "Please provide a specific Award ID or narrow your search."}
             )

        # EXECUTION
        result = {}
        
        try:
            if tool_name == "spending_rollups":
                # Default behavior: group by agency if unspecified
                group_by = signals["agency_type_hint"] # Use inferred agency type (awarding or funding)
                if "recipient" in question.lower():
                    group_by = "recipient"
                if "state" in question.lower():
                    group_by = "state"
                
                # Determine metric
                metric = self.rules.get("design_decisions", {}).get("default_metric", "obligations")
                metric_map = self.rules.get("design_decisions", {}).get("metric_by_award_type", {})
                
                # Simple logic: if assistance only and 'loan' is mentioned, use face_value?
                # Or map based on scope mode?
                # If scope_mode is assistance_only, we might default to obligations unless specifically loan?
                # If "loan" in question, use face_value_of_loan.
                if "loan" in question.lower():
                    metric = metric_map.get("loans", metric)
                elif "grant" in question.lower():
                    metric = metric_map.get("grants", metric)
                elif "contract" in question.lower():
                    metric = metric_map.get("contracts", metric)
                
                result = self.tools["spending_rollups"].execute(
                    scope_mode=scope_mode,
                    group_by=group_by,
                    top_n=self.rules["defaults"]["spending_rollups"]["top_n_default"],
                    metric=metric,
                    debug=debug,
                    request_id=request_id
                )
                
            elif tool_name == "idv_vehicle_bundle":
                result = self.tools["idv_vehicle_bundle"].execute(
                    idv_award_id=signals["award_id"],
                    scope_mode=scope_mode,
                    request_id=request_id
                )
                
            elif tool_name == "award_explain":
                result = self.tools["award_explain"].execute(
                    award_id=signals["award_id"],
                    scope_mode=scope_mode,
                    debug=debug,
                    request_id=request_id
                )

            elif tool_name == "award_search":
                filters = {"keywords": [question]} 
                result = self.tools["award_search"].execute(
                    filters=filters,
                    limit=self.rules["defaults"]["award_search"]["limit_default"],
                    scope_mode=scope_mode,
                    debug=debug,
                    request_id=request_id
                )
                
            elif tool_name == "resolve_entities":
                q_clean = question.replace("Resolve:", "").replace("resolve", "").strip()
                result = self.tools["resolve_entities"].execute(
                    q=q_clean,
                    types=["agency", "recipient", "psc", "naics", "assistance_listing"], 
                    request_id=request_id
                )
            
            elif tool_name == "recipient_profile":
                # Extracted recipient hint logic or simple text
                recipient_text = question # Simplified
                result = self.tools["recipient_profile"].execute(
                    recipient=recipient_text,
                    scope_mode=scope_mode,
                    request_id=request_id
                )

            elif tool_name == "agency_portfolio":
                # Needs resolution first usually, but for stub:
                # result = self.tools["agency_portfolio"].execute(...)
                pass

            
            # Add metadata
            meta = result.get("meta", {})
            meta["route_name"] = tool_name
            meta["budgets_used"] = {"wall_ms": (time.time() - start_time) * 1000}
            
            # Apply Output Policy (Summary First & Trimming)
            max_bytes = self.rules["budgets"]["max_response_bytes"]
            max_items = self.rules["budgets"]["max_items_per_list"]
            
            trimmed_result, truncation_info = trim_payload(result, max_bytes, max_items)
            if truncation_info:
                meta["truncated"] = True
                meta["truncation"] = truncation_info
            
            return {
                "tool_version": "1.0",
                "meta": meta,
                "plan": {
                    "scope_mode": scope_mode,
                    "actions": [tool_name]
                },
                "result": trimmed_result
            }

        except Exception as e:
            return fail("unknown", str(e), request_id)

    def execute(self, question: str, debug: bool = False, request_id: Optional[str] = None) -> Dict[str, Any]:
        return self.route_request(question, debug, request_id)
