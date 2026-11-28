import argparse

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Equipment quickstart", stateless_http=True)


@mcp.tool()
def add(a: int, b: int) -> int:
    """Return the sum of two integers."""
    return a + b


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the quickstart MCP server.")
    parser.add_argument(
        "--port", type=int, default=mcp.settings.port, help="HTTP listening port"
    )
    args = parser.parse_args()
    mcp.settings.port = args.port
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
