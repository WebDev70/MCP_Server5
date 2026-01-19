from usaspending_mcp.server import mcp


def test_server_init():
    assert mcp is not None
    assert mcp.name == "USAspending MCP"
