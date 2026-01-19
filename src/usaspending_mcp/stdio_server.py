from usaspending_mcp.server import mcp


def main():
    """
    Entrypoint for stdio transport.
    """
    print("Starting USAspending MCP Server (stdio)...")
    mcp.run()

if __name__ == "__main__":
    main()
