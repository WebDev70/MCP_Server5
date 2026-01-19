import os
import time
import uuid
import json
import logging
import httpx
from typing import Optional, Dict, Any, Union, Callable
from usaspending_mcp.logging_config import get_logger, log_context
from tenacity import (
    Retrying,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

logger = get_logger("usaspending_client")

class APIError(Exception):
    def __init__(
        self, 
        error_type: str, 
        message: str, 
        status_code: Optional[int] = None, 
        endpoint: Optional[str] = None, 
        method: Optional[str] = None, 
        response_snippet: Optional[str] = None
    ):
        self.error_type = error_type
        self.message = message
        self.status_code = status_code
        self.endpoint = endpoint
        self.method = method
        self.response_snippet = response_snippet
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": {
                "type": self.error_type,
                "message": self.message,
                "status_code": self.status_code,
                "endpoint": self.endpoint,
                "method": self.method,
                "remediation_hint": self._get_remediation_hint()
            }
        }

    def _get_remediation_hint(self) -> Optional[str]:
        if self.error_type == "rate_limit":
            return "Wait a few seconds before retrying."
        if self.error_type == "validation":
            return "Check filters and parameters for correctness."
        return None

class CircuitOpenError(Exception):
    """Raised when the circuit breaker is open."""
    pass

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60, half_open_requests: int = 2):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_requests_limit = half_open_requests
        
        self.state = "CLOSED"
        self.failure_count = 0
        self.last_failure_time = None
        self.half_open_success_count = 0
        self.half_open_request_count = 0

    def _should_try_reset(self) -> bool:
        if self.last_failure_time is None:
            return True
        return (time.time() - self.last_failure_time) >= self.recovery_timeout

    def _on_success(self):
        if self.state == "HALF_OPEN":
            self.half_open_success_count += 1
            if self.half_open_success_count >= self.half_open_requests_limit:
                logger.info("CircuitBreaker HALF_OPEN -> CLOSED (Recovery Success)")
                self.state = "CLOSED"
                self.failure_count = 0
                self.half_open_success_count = 0
                self.half_open_request_count = 0
        elif self.state == "CLOSED":
            self.failure_count = 0

    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == "CLOSED":
            if self.failure_count >= self.failure_threshold:
                logger.warning(f"CircuitBreaker CLOSED -> OPEN (Threshold {self.failure_threshold} reached)")
                self.state = "OPEN"
        elif self.state == "HALF_OPEN":
            logger.warning("CircuitBreaker HALF_OPEN -> OPEN (Probe Failed)")
            self.state = "OPEN"
            self.half_open_success_count = 0
            self.half_open_request_count = 0

    def call(self, func: Callable, *args, **kwargs):
        if self.state == "OPEN":
            if self._should_try_reset():
                logger.info("CircuitBreaker OPEN -> HALF_OPEN (Attempting Recovery)")
                self.state = "HALF_OPEN"
                self.half_open_request_count = 0
                self.half_open_success_count = 0
            else:
                raise CircuitOpenError("Circuit breaker is open - failing fast")

        if self.state == "HALF_OPEN":
            if self.half_open_request_count >= self.half_open_requests_limit:
                 raise CircuitOpenError("Circuit breaker is half-open - probe limit reached")
            self.half_open_request_count += 1

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except (httpx.NetworkError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
            # We only count network/upstream errors as breaker failures
            should_count_failure = True
            if isinstance(e, httpx.HTTPStatusError) and e.response.status_code < 500 and e.response.status_code != 429:
                should_count_failure = False
            
            if should_count_failure:
                self._on_failure()
            raise

class USAspendingClient:
    def __init__(self):
        self.base_url = os.getenv("USASPENDING_BASE_URL", "https://api.usaspending.gov/api/v2").rstrip("/")
        self.timeout = float(os.getenv("USASPENDING_TIMEOUT_S", "60.0"))
        self.max_retries = int(os.getenv("USASPENDING_MAX_RETRIES", "3"))
        self.backoff_base = float(os.getenv("USASPENDING_BACKOFF_BASE_S", "0.5"))
        
        self.client = httpx.Client(timeout=self.timeout)
        
        # Initialize Breaker with defaults or from config file if available
        rules_path = os.path.join(os.path.dirname(__file__), "router_rules.json")
        cb_config = {"failure_threshold": 5, "recovery_timeout_seconds": 60, "half_open_requests": 2}
        if os.path.exists(rules_path):
            try:
                with open(rules_path, "r") as f:
                    rules = json.load(f)
                    cb_config.update(rules.get("circuit_breaker", {}))
            except Exception:
                pass
        
        self.breaker = CircuitBreaker(
            failure_threshold=cb_config["failure_threshold"],
            recovery_timeout=cb_config["recovery_timeout_seconds"],
            half_open_requests=cb_config["half_open_requests"]
        )

    def request(
        self, 
        method: str, 
        endpoint: str, 
        request_id: Optional[str] = None,
        tool_name: str = "unknown",
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None
    ) -> Union[Dict, Any]:
        
        request_id = request_id or str(uuid.uuid4())
        
        try:
            return self.breaker.call(
                self._do_request,
                method=method,
                endpoint=endpoint,
                request_id=request_id,
                tool_name=tool_name,
                params=params,
                json_data=json_data
            )
        except CircuitOpenError as e:
            logger.error(
                f"Circuit breaker open for {endpoint}",
                extra={
                    "endpoint": endpoint,
                    "error_type": "circuit_open",
                    "circuit_state": "OPEN"
                }
            )
            raise APIError(
                error_type="upstream",
                message=str(e),
                endpoint=endpoint,
                method=method
            ) from e

    def _do_request(
        self,
        method: str,
        endpoint: str,
        request_id: str,
        tool_name: str,
        params: Optional[Dict],
        json_data: Optional[Dict]
    ) -> Dict:
        endpoint_clean = f"/{endpoint.lstrip('/')}"
        url = f"{self.base_url}{endpoint_clean}"
        start_time = time.perf_counter()
        
        retryer = Retrying(
            stop=stop_after_attempt(self.max_retries + 1),
            wait=wait_exponential(multiplier=self.backoff_base, min=self.backoff_base, max=10),
            retry=retry_if_exception_type((httpx.NetworkError, httpx.TimeoutException, httpx.HTTPStatusError)),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True
        )

        response = None
        
        try:
            for attempt in retryer:
                with attempt:
                    try:
                        response = self.client.request(
                            method=method,
                            url=url,
                            params=params,
                            json=json_data
                        )
                        response.raise_for_status()
                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 429 or e.response.status_code >= 500:
                            raise e
                        else:
                            raise e
                            
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            latency_ms = (time.perf_counter() - start_time) * 1000
            error_type = "unknown"
            
            if status_code == 429:
                error_type = "rate_limit"
            elif 400 <= status_code < 500:
                error_type = "validation"
            elif status_code >= 500:
                error_type = "upstream"
            
            logger.error(
                f"USAspending API error: {status_code}",
                extra={
                    "endpoint": endpoint_clean,
                    "method": method,
                    "status_code": status_code,
                    "latency_ms": latency_ms,
                    "error_type": error_type
                }
            )
            
            raise APIError(
                error_type=error_type,
                message=str(e),
                status_code=status_code,
                endpoint=endpoint_clean,
                method=method,
                response_snippet=e.response.text[:200]
            ) from e
            
        except (httpx.NetworkError, httpx.TimeoutException) as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"Network error connecting to {endpoint_clean}",
                extra={
                    "endpoint": endpoint_clean,
                    "method": method,
                    "latency_ms": latency_ms,
                    "error_type": "network"
                }
            )
            raise APIError(
                error_type="network",
                message=f"Network error: {str(e)}",
                endpoint=endpoint_clean,
                method=method
            ) from e
            
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"Unexpected error: {str(e)}",
                extra={
                    "endpoint": endpoint_clean,
                    "method": method,
                    "latency_ms": latency_ms,
                    "error_type": "unknown"
                }
            )
            raise APIError(
                error_type="unknown",
                message=f"Unexpected error: {str(e)}",
                endpoint=endpoint_clean,
                method=method
            ) from e

        # Success path
        status_code = response.status_code
        latency_ms = (time.perf_counter() - start_time) * 1000
        
        logger.info(
            f"USAspending API success: {endpoint_clean}",
            extra={
                "endpoint": endpoint_clean,
                "method": method,
                "status_code": status_code,
                "latency_ms": latency_ms,
                "cache_hit": False
            }
        )
        
        return response.json()