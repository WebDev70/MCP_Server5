from typing import Any, Dict, List, Optional, Tuple

TOOL_VERSION = "1.0"

TRIMMABLE_KEYS = ["results", "transactions", "subawards", "orders", "activity", "groups"]


def pick_fields(data, keys: list[str]):
    """Filter a dict (or list of dicts) to only the specified keys."""
    if isinstance(data, dict):
        return {k: v for k, v in data.items() if k in keys}
    if isinstance(data, list):
        return [pick_fields(item, keys) for item in data]
    return data

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
        "scope_mode": scope_mode,
    }

    if warnings:
        meta["warnings"] = warnings
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
    Trims payload to stay within size and item count limits.
    Checks all TRIMMABLE_KEYS (results, transactions, subawards, etc.).
    Returns (trimmed_data, truncation_meta)
    If no truncation occurred, truncation_meta is None.
    """
    import json

    truncated = False
    reason = []
    trimmed_keys: Dict[str, int] = {}

    if not isinstance(data, dict):
        return data, None

    # 1. Item count check on all trimmable keys
    for key in TRIMMABLE_KEYS:
        if key in data and isinstance(data[key], list):
            if len(data[key]) > max_items_per_list:
                data[key] = data[key][:max_items_per_list]
                truncated = True
                reason.append(f"{key}_limit_exceeded_capped_at_{max_items_per_list}")

    # 2. Byte size check — halve the largest trimmable list until we fit
    encoded = json.dumps(data, default=str)
    current_bytes = len(encoded.encode("utf-8"))

    if current_bytes > max_bytes:
        truncated = True
        reason.append("max_bytes_exceeded")

        while current_bytes > max_bytes:
            # Find the largest trimmable list
            largest_key = None
            largest_len = 1  # don't halve lists of length 1
            for key in TRIMMABLE_KEYS:
                if key in data and isinstance(data[key], list) and len(data[key]) > largest_len:
                    largest_key = key
                    largest_len = len(data[key])

            if largest_key is None:
                break  # nothing left to trim

            new_len = largest_len // 2
            data[largest_key] = data[largest_key][:new_len]

            encoded = json.dumps(data, default=str)
            current_bytes = len(encoded.encode("utf-8"))

    # Build per-key returned counts
    for key in TRIMMABLE_KEYS:
        if key in data and isinstance(data[key], list):
            trimmed_keys[key] = len(data[key])

    truncation_info = None
    if truncated:
        truncation_info = {
            "reason": ", ".join(reason),
            "max_bytes": max_bytes,
            "max_items_per_list": max_items_per_list,
            "returned_items": trimmed_keys or "N/A",
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
