from usaspending_mcp.response import REMEDIATION_HINTS, fail, ok, out_of_scope, trim_payload


def test_ok_response_structure():
    data = {"results": [1, 2, 3]}
    request_id = "req-123"
    
    resp = ok(
        data, 
        request_id=request_id, 
        endpoint_used="/test/endpoint",
        accuracy_tier="A"
    )
    
    assert resp["tool_version"] == "1.0"
    assert resp["results"] == [1, 2, 3]
    assert resp["meta"]["request_id"] == request_id
    assert resp["meta"]["endpoint_used"] == "/test/endpoint"
    assert resp["meta"]["accuracy_tier"] == "A"
    assert resp["meta"]["scope_mode"] == "all_awards"  # default

def test_fail_response_structure_manual_hint():
    request_id = "req-456"
    
    resp = fail(
        error_type="rate_limit",
        message="Too many requests",
        request_id=request_id,
        status_code=429,
        endpoint="/test/endpoint",
        remediation_hint="Manual backoff hint"
    )
    
    assert resp["tool_version"] == "1.0"
    assert resp["error"]["remediation_hint"] == "Manual backoff hint"

def test_fail_response_auto_hint_default():
    request_id = "req-456"
    
    resp = fail(
        error_type="rate_limit",
        message="Too many requests",
        request_id=request_id,
        status_code=429
    )
    
    # Should resolve to REMEDIATION_HINTS["rate_limit"]["default"]
    assert resp["error"]["remediation_hint"] == REMEDIATION_HINTS["rate_limit"]["default"]

def test_fail_response_auto_hint_key():
    request_id = "req-456"
    
    resp = fail(
        error_type="validation",
        message="Bad agency",
        request_id=request_id,
        hint_key="invalid_agency"
    )
    
    assert resp["error"]["remediation_hint"] == REMEDIATION_HINTS["validation"]["invalid_agency"]

def test_fail_response_unknown_type():
    request_id = "req-456"
    
    resp = fail(
        error_type="weird_error",
        message="Something happened",
        request_id=request_id
    )
    
    # Should be None if not found, or None. 
    # Logic: type_hints = {}.get("default") -> None.
    # So remediation_hint will be None if type unknown and no default/generic fallback used in helper.
    # My helper implementation:
    # type_hints = REMEDIATION_HINTS.get(error_type, {})
    # hint = type_hints.get(hint_key or "default", type_hints.get("default"))
    # If type_hints is empty, hint is None.
    
    assert resp["error"]["remediation_hint"] is None

def test_out_of_scope_helper():
    request_id = "req-789"
    resp = out_of_scope(
        request_id=request_id,
        scope_mode="assistance_only",
        feature_name="contracts_search"
    )
    
    assert resp["error"]["type"] == "validation"
    assert "not supported in scope_mode='assistance_only'" in resp["error"]["message"]
    # Should use the default scope hint from REMEDIATION_HINTS
    assert resp["error"]["remediation_hint"] == REMEDIATION_HINTS["validation"]["invalid_scope_mode"]

def test_trim_payload_items():
    # Test capping list items
    data = {"results": [i for i in range(100)]}
    trimmed, meta = trim_payload(data, max_items_per_list=50)
    
    assert len(trimmed["results"]) == 50
    assert meta is not None
    assert "results_limit_exceeded_capped_at_50" in meta["reason"]
    assert meta["max_items_per_list"] == 50
    assert meta["returned_items"] == 50

def test_trim_payload_bytes():
    # Test byte size trimming
    # Create a list of large strings
    # We want to exceed max_bytes (default 200k)
    # Let's use small max_bytes for test
    data = {"results": ["a" * 100 for _ in range(20)]}
    # Total ~2000 bytes
    
    trimmed, meta = trim_payload(data, max_bytes=1000)
    
    assert meta is not None
    assert "max_bytes_exceeded" in meta["reason"]
    assert len(trimmed["results"]) < 20
    # Should have cut in half at least once