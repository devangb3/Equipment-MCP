from dataclasses import dataclass
from pathlib import Path

from ..database import connect
from ..models import Policy, UnknownRole, required


@dataclass(frozen=True)
class RolePolicies:
    path: Path

    def list_policies(self, role: str) -> list[Policy]:
        """Return each policy row for a role."""
        role = required(role, "role")
        with connect(self.path) as db:
            policies = [
                Policy(stored_role, item, years)
                for stored_role, item, years in db.execute(
                    """SELECT role, item, years FROM policy
                       WHERE role = ? COLLATE NOCASE ORDER BY item""",
                    (role,),
                )
            ]
        if not policies:
            raise UnknownRole(f"No equipment policy for role: {role}")
        return policies

    def get_policy_limits(self, role: str) -> dict[str, int]:
        """Return each eligible item and its routine refresh interval in calendar years."""
        return {policy.item: policy.years for policy in self.list_policies(role)}
