from dataclasses import dataclass
from pathlib import Path

from ..database import database_session
from ..models import Intent, Receipt, required
from ..models.history import SubmittedRequest
from .eligibility import EligibilityChecker


@dataclass(frozen=True)
class Submissions:
    path: Path
    checker: EligibilityChecker

    def submit_request(
        self, employee_id: str, item: str, request: str, intent: Intent = "routine"
    ) -> Receipt:
        """Submit one equipment request. Saves the outcome and opens any required review case."""
        employee_id = required(employee_id, "employee_id")
        item = required(item, "item").casefold()
        required(request, "request")
        outcome = self.checker.check_request_eligibility(employee_id, item, intent)
        with database_session(self.path, write=True) as session:
            return SubmittedRequest.record(
                session, employee_id, request, item, intent, outcome
            )
