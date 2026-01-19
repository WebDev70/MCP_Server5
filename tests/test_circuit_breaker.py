import pytest
import time
import httpx
from unittest.mock import MagicMock
from usaspending_mcp.usaspending_client import CircuitBreaker, CircuitOpenError

def test_circuit_breaker_opens_after_threshold():
    # Threshold 3
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
    
    func = MagicMock(side_effect=httpx.NetworkError("API Down"))
    
    # 1st failure
    with pytest.raises(httpx.NetworkError):
        cb.call(func)
    assert cb.state == "CLOSED"
    
    # 2nd failure
    with pytest.raises(httpx.NetworkError):
        cb.call(func)
    assert cb.state == "CLOSED"
    
    # 3rd failure triggers OPEN
    with pytest.raises(httpx.NetworkError):
        cb.call(func)
    assert cb.state == "OPEN"
    
    # Subsequent call fails fast without calling func
    with pytest.raises(CircuitOpenError):
        cb.call(func)
    assert func.call_count == 3

def test_circuit_breaker_recovery_timeout():
    # Short timeout for testing
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1)
    
    func = MagicMock(side_effect=httpx.NetworkError("API Down"))
    
    # Open the circuit
    with pytest.raises(httpx.NetworkError):
        cb.call(func)
    assert cb.state == "OPEN"
    
    # Wait for recovery timeout
    time.sleep(1.1)
    
    # Next call should move to HALF_OPEN
    func.side_effect = None
    func.return_value = "Success"
    
    result = cb.call(func)
    assert result == "Success"
    assert cb.state == "HALF_OPEN" or cb.state == "CLOSED"

def test_half_open_to_closed_on_success():
    # Requires 2 successes to close
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0, half_open_requests=2)
    
    # 1. Open it
    with pytest.raises(httpx.NetworkError):
        cb.call(MagicMock(side_effect=httpx.NetworkError("Fail")))
    assert cb.state == "OPEN"
    
    # 2. Move to HALF_OPEN (timeout 0 means immediate)
    func = MagicMock(return_value="OK")
    cb.call(func)
    assert cb.state == "HALF_OPEN"
    assert cb.half_open_success_count == 1
    
    # 3. Second success closes it
    cb.call(func)
    assert cb.state == "CLOSED"
    assert cb.failure_count == 0

def test_half_open_to_open_on_failure():
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0, half_open_requests=2)
    
    # Open
    with pytest.raises(httpx.NetworkError):
        cb.call(MagicMock(side_effect=httpx.NetworkError("Fail")))
    
    # Half-Open first success
    cb.call(MagicMock(return_value="OK"))
    assert cb.state == "HALF_OPEN"
    
    # Half-Open failure resets to OPEN
    with pytest.raises(httpx.NetworkError):
        cb.call(MagicMock(side_effect=httpx.NetworkError("Fail Again")))
    assert cb.state == "OPEN"