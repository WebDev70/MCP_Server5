import json
import logging
import io
import pytest
from usaspending_mcp.logging_config import StructuredFormatter, log_context, setup_logging

def test_structured_formatter_output():
    formatter = StructuredFormatter()
    log_record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test message",
        args=(),
        exc_info=None
    )
    # Manually attach attributes
    log_record.request_id = "req-123"
    log_record.tool_name = "test_tool"
    
    formatted = formatter.format(log_record)
    data = json.loads(formatted)
    
    assert data["level"] == "INFO"
    assert data["message"] == "Test message"
    assert data["request_id"] == "req-123"
    assert data["tool_name"] == "test_tool"
    assert "timestamp" in data

def test_log_context_propagation():
    formatter = StructuredFormatter()
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(formatter)
    
    logger = logging.getLogger("test_context")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    request_id = "req-456"
    tool_name = "tool-abc"
    
    with log_context(request_id=request_id, tool_name=tool_name):
        logger.info("Inside context")
        
    formatted = stream.getvalue().strip()
    data = json.loads(formatted)
    
    assert data["request_id"] == request_id
    assert data["tool_name"] == tool_name
    assert data["message"] == "Inside context"

def test_log_extra_attributes():
    formatter = StructuredFormatter()
    log_record = logging.LogRecord(
        name="test_logger",
        level=logging.ERROR,
        pathname="test.py",
        lineno=20,
        msg="API Error",
        args=(),
        exc_info=None
    )
    log_record.status_code = 500
    log_record.endpoint = "/api/v2/test"
    log_record.latency_ms = 150.5
    
    formatted = formatter.format(log_record)
    data = json.loads(formatted)
    
    assert data["status_code"] == 500
    assert data["endpoint"] == "/api/v2/test"
    assert data["latency_ms"] == 150.5
