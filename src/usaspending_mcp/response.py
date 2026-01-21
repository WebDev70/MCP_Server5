from typing import Any, Dict, List, Optional, Tuple

TOOL_VERSION = "1.0"

REMEDIATION_HINTS = {
    "validation": {
        "invalid_time_period": "Use format: {'start_date': 'YYYY-MM-DD', 'end_date': 'YYYY-MM-DD'} or {'fy': '2024'}",
        "invalid_agency": "Use toptier_code from bootstrap_catalog, e.g., '097' for DoD",
        "invalid_award_type": "Valid award types: 'A','B','C','D' (contracts), '02','03','04','05','06','07','08','09','10','11' (assistance)",
        "missing_required_filter": "At least one filter required: agency, recipient, time_period, or award_type",
        "invalid_scope_mode": "Valid scope_modes: 'all_awards', 'contracts_only', 'assistance_only'",
        "award_id_required": "award_explain requires an award_id. Use award_search first to find award IDs.",
        "idv_not_in_scope": "IDV tools not available for assistance_only scope. Use scope_mode='contracts_only' or 'all_awards'.",
        "default": "Check your input parameters."
    },
    "rate_limit": {
        "default": "USAspending API rate limited. Retry in 60 seconds or reduce query scope.",
    },
    "upstream": {
        "default": "USAspending API returned an error. Try again or simplify your query.",
        "timeout": "Request timed out. Try a narrower time_period or fewer filters.",
    },
    "network": {
        "default": "Network error connecting to USAspending. Check connectivity and retry.",
    },
    "unknown": {
        "default": "An unexpected error occurred. Please try again later."
    }
}

def _build_meta(
    request_id: str, 
    scope_mode: str = "all_awards", 
    endpoint_used: Optional[str] = None, 
    endpoints_used: Optional[List[str]] = None,
    time_period: Optional[Any] = None,
    warnings: Optional[List[str]] = None,
    accuracy_tier: Optional[str] = None,
    truncated: bool = False,
    truncation: Optional[Dict[str, Any]] = None,
    **kwargs
) -> Dict[str, Any]:
    meta = {
        "request_id": request_id,
        "scope_mode": scope_mode,
        "warnings": warnings or [],
    }
    
    if endpoint_used:
        meta["endpoint_used"] = endpoint_used
    if endpoints_used:
        meta["endpoints_used"] = endpoints_used
    if time_period:
        meta["time_period"] = time_period
    if accuracy_tier:
        meta["accuracy_tier"] = accuracy_tier
    if truncated:
        meta["truncated"] = truncated
    if truncation:
        meta["truncation"] = truncation
        
    meta.update(kwargs)
    return meta

def trim_payload(
    data: Any, 
    max_bytes: int = 200_000, 
    max_items_per_list: int = 200
) -> Tuple[Any, Optional[Dict[str, Any]]]:
    """
    Recursively trims payload to stay within size and item count limits.
    Returns (trimmed_data, truncation_meta)
    If no truncation occurred, truncation_meta is None.
    """
    import json
    
    truncated = False
    reason = []
    
    # 1. Simple item count check on top-level results list
    if isinstance(data, dict) and "results" in data and isinstance(data["results"], list):
        if len(data["results"]) > max_items_per_list:
            data["results"] = data["results"][:max_items_per_list]
            truncated = True
            reason.append(f"results_limit_exceeded_capped_at_{max_items_per_list}")

    # 2. Byte size check (rough estimation)
    # If we are over max_bytes, we aggressively trim the list further
    encoded = json.dumps(data, default=str)
    current_bytes = len(encoded.encode("utf-8"))
    
    if current_bytes > max_bytes:
        truncated = True
        reason.append("max_bytes_exceeded")
        
        # Strategy: if it's a list of results, cut it in half repeatedly until it fits
        # or until we reach a very small number
        if isinstance(data, dict) and "results" in data and isinstance(data["results"], list):
            results = data["results"]
            while current_bytes > max_bytes and len(results) > 1:
                # Reduce by half
                new_len = len(results) // 2
                results = results[:new_len]
                data["results"] = results
                
                encoded = json.dumps(data, default=str)
                current_bytes = len(encoded.encode("utf-8"))
    
    truncation_info = None
    if truncated:
        truncation_info = {
            "reason": ", ".join(reason),
            "max_bytes": max_bytes,
            "max_items_per_list": max_items_per_list,
            "returned_items": len(data.get("results", [])) if isinstance(data, dict) and "results" in data else "N/A"
        }
        
    return data, truncation_info

def ok(
    data: Dict[str, Any], 
    request_id: str, 
    scope_mode: str = "all_awards", 
    endpoint_used: Optional[str] = None,
    endpoints_used: Optional[List[str]] = None,
    time_period: Optional[Any] = None,
    warnings: Optional[List[str]] = None,
    accuracy_tier: Optional[str] = None,
    apply_trimming: bool = True,
    **meta_extras
) -> Dict[str, Any]:
    """
    Wraps successful tool response in the standard envelope.
    """
    truncation_meta = None
    if apply_trimming:
        data, truncation_meta = trim_payload(data)
        
    return {
        "tool_version": TOOL_VERSION,
        **data,  # Spread the data at the top level per FastMCP convention or just include it
        "meta": _build_meta(
            request_id=request_id,
            scope_mode=scope_mode,
            endpoint_used=endpoint_used,
            endpoints_used=endpoints_used,
            time_period=time_period,
            warnings=warnings,
            accuracy_tier=accuracy_tier,
            truncated=(truncation_meta is not None),
            truncation=truncation_meta,
            **meta_extras
        )
    }

def fail(
    error_type: str,
    message: str,
    request_id: str,
    scope_mode: str = "all_awards",
    remediation_hint: Optional[str] = None,
    hint_key: Optional[str] = None,
    status_code: Optional[int] = None,
    endpoint: Optional[str] = None,
    warnings: Optional[List[str]] = None,
    **meta_extras
) -> Dict[str, Any]:
    """
    Wraps failure response in the standard envelope.
    """
    # Resolve remediation hint from catalog if not explicitly provided
    if not remediation_hint:
        type_hints = REMEDIATION_HINTS.get(error_type, {})
        # Try specific key, fallback to default for type, fallback to generic message
        remediation_hint = type_hints.get(hint_key or "default", type_hints.get("default"))

    return {
        "tool_version": TOOL_VERSION,
        "error": {
            "type": error_type,
            "message": message,
            "status_code": status_code,
            "endpoint": endpoint,
            "remediation_hint": remediation_hint
        },
        "meta": _build_meta(
            request_id=request_id,
            scope_mode=scope_mode,
            endpoint_used=endpoint,
            warnings=warnings,
            **meta_extras
        )
    }

def out_of_scope(
    request_id: str,
    scope_mode: str,
    feature_name: str,
    remediation_hint: Optional[str] = None
) -> Dict[str, Any]:
    """
    Helper for returning out-of-scope errors.
    """
    msg = f"Feature '{feature_name}' is not supported in scope_mode='{scope_mode}'"
    hint = remediation_hint or REMEDIATION_HINTS["validation"]["invalid_scope_mode"]
    
    return fail(
        error_type="validation",
        message=msg,
        request_id=request_id,
        scope_mode=scope_mode,
        remediation_hint=hint
    )
