from dataclasses import dataclass
from pathlib import Path

from ..database import database_session
from ..models import Policy, required


@dataclass(frozen=True)
class RolePolicies:
    path: Path

    def list_policies(self, role: str) -> list[Policy]:
        """Return each policy row for a role."""
        role = required(role, "role")
        with database_session(self.path) as session:
            return Policy.for_role(session, role)

    def get_policy_limits(self, role: str) -> dict[str, int]:
        """Return each eligible item and its routine refresh interval in calendar years."""
        return {policy.item: policy.years for policy in self.list_policies(role)}
