from mcp import ClientSession
from mcp.server.fastmcp import FastMCP


def test_sdk_and_project_packages_import():
    from src import agent, server

    assert agent.__package__ == "src.agent"
    assert server.__package__ == "src.server"
    assert callable(ClientSession)
    assert callable(FastMCP)
