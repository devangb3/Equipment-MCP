from dataclasses import dataclass
from pathlib import Path

from ..database import database_session
from ..models import Policy, required
from ..models.tool_inputs import EmployeeRole


@dataclass(frozen=True)
class RolePolicies:
    path: Path

    def list_policies(self, role: str) -> list[Policy]:
        """Return each policy row for a role."""
        role = required(role, "role")
        with database_session(self.path) as session:
            return Policy.for_role(session, role)

    def get_policy_limits(self, role: EmployeeRole) -> dict[str, int]:
        """Map each covered item to its refresh interval in years.

        Role lookup is case-insensitive and raises UnknownRole for an unlisted role.
        """
        return {policy.item: policy.years for policy in self.list_policies(role)}
