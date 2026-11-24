from mcp import ClientSession
from mcp.server.fastmcp import FastMCP


def test_sdk_and_project_packages_import():
    from equipment_mcp import agent, server

    assert agent.__package__ == "equipment_mcp.agent"
    assert server.__package__ == "equipment_mcp.server"
    assert callable(ClientSession)
    assert callable(FastMCP)
