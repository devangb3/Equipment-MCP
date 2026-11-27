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
    parser.add_argument("--port", type=int, default=43817)
    args = parser.parse_args()
    initialize(args.database)
    requests = EquipmentRequests(args.database)
    mcp = FastMCP("Equipment requests", port=args.port, stateless_http=True)
    mcp.tool(
        title="Look up employee equipment",
        description=(
            "Look up an employee by ID to see their current role, hire date, "
            "completed years of service, and assigned devices. Each device includes "
            "its issue date when known. An unknown ID returns an error."
        ),
    )(requests.get_employee_info)
    mcp.tool(
        title="Look up equipment policy by role",
        description=(
            "Use the employee's current role to look up covered items and their routine refresh intervals in calendar years."
            "For an individual employee's eligibility on a specific item, use check_request_eligibility."
        ),
    )(requests.get_policy_limits)
    mcp.tool(
        title="Preview equipment eligibility",
        description=(
            "Preview today's policy decision for one employee and item. Set intent "
            "from the employee's request, choosing routine, additional, broken, or "
            "unclear. This read-only check returns approve, deny, or human_review "
            "with the reason and, when available, the next eligible date."
        ),
    )(requests.check_request_eligibility)
    mcp.tool(
        title="Open a human review case",
        description=(
            "Use for a direct referral when a person needs to review a request. "
            "Supply the employee ID, the employee's original wording, and the "
            "specific reason for review. Each call creates a case and returns its "
            "review ID, even for an unknown employee. If submit_request already "
            "returned a review ID, use that existing case."
        ),
    )(requests.flag_for_human_review)
    mcp.tool(
        title="Submit an equipment request",
        description=(
            "Call once to file a request for one item. Supply the employee ID, item, "
            "original request text, and intent. The default intent is routine. Each "
            "call saves a new submission and returns its ID and policy decision. If "
            "review is required, the receipt also includes the ID of the case opened "
            "by this call."
        ),
    )(requests.submit_request)
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
