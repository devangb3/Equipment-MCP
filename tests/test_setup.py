from mcp import ClientSession
from mcp.server.fastmcp import FastMCP


def test_sdk_and_project_packages_import():
    import agent
    import server

    assert (agent.__package__, server.__package__, callable(ClientSession), callable(FastMCP)) == (
        "agent", "server", True, True
    )
