from dataclasses import dataclass
from pathlib import Path

from ..database import database_session
from ..models import Receipt, required
from ..models.history import SubmittedRequest
from ..models.tool_inputs import EmployeeID, EquipmentItem, RequestIntent, RequestText
from .eligibility import EligibilityChecker


@dataclass(frozen=True)
class Submissions:
    path: Path
    checker: EligibilityChecker

    def submit_request(
        self,
        employee_id: EmployeeID,
        item: EquipmentItem,
        request: RequestText,
        intent: RequestIntent = "routine",
    ) -> Receipt:
        """Evaluate one item and persist the original request text with its policy outcome.

        Return a receipt with the submission ID and any review ID created for it.
        """
        employee_id = required(employee_id, "employee_id")
        item = required(item, "item").casefold()
        required(request, "request")
        outcome = self.checker.check_request_eligibility(employee_id, item, intent)
        with database_session(self.path, write=True) as session:
            return SubmittedRequest.record(
                session, employee_id, request, item, intent, outcome
            )
