import argparse
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .database import initialize
from .services import EquipmentRequests


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the equipment MCP server over Streamable HTTP."
    )
    parser.add_argument("--database", type=Path, default=Path("equipment.sqlite3"))
    args = parser.parse_args()
    initialize(args.database)
    requests = EquipmentRequests(args.database)
    mcp = FastMCP("Equipment requests")
    mcp.tool()(requests.get_employee_info)
    mcp.tool()(requests.get_policy_limits)
    mcp.tool()(requests.check_request_eligibility)
    mcp.tool()(requests.flag_for_human_review)
    mcp.tool()(requests.submit_request)
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
