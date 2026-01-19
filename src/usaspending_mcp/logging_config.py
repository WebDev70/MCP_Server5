import json
import logging
import uuid
from datetime import datetime, UTC
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Optional, Dict, Any

# Context variables for request tracking
_request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_tool_name_var: ContextVar[Optional[str]] = ContextVar("tool_name", default=None)

class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Get context values
        request_id = _request_id_var.get() or getattr(record, "request_id", None)
        tool_name = _tool_name_var.get() or getattr(record, "tool_name", None)

        log_entry = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "message": record.getMessage(),
            "request_id": request_id,
            "tool_name": tool_name,
            "endpoint": getattr(record, "endpoint", None),
            "method": getattr(record, "method", None),
            "status_code": getattr(record, "status_code", None),
            "latency_ms": getattr(record, "latency_ms", None),
            "cache_hit": getattr(record, "cache_hit", None),
            "error_type": getattr(record, "error_type", None),
            "circuit_state": getattr(record, "circuit_state", None),
        }
        
        # Remove None values for cleaner output
        log_entry = {k: v for k, v in log_entry.items() if v is not None}
        return json.dumps(log_entry)

def setup_logging(level: str = "INFO"):
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter())
    root_logger.addHandler(handler)

@contextmanager
def log_context(request_id: str, tool_name: Optional[str] = None):
    """Attach context to all log messages within scope."""
    tokens = [
        _request_id_var.set(request_id),
        _tool_name_var.set(tool_name)
    ]
    try:
        yield
    finally:
        _request_id_var.reset(tokens[0])
        _tool_name_var.reset(tokens[1])

def get_logger(name: str):
    return logging.getLogger(name)
