from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ..database import database_session
from ..models import EmployeeInfo, required
from ..models.equipment import Employee, EquipmentIssue


@dataclass(frozen=True)
class EmployeeDirectory:
    path: Path
    today: Callable[[], date] = date.today

    def get_employee_info(self, employee_id: str) -> EmployeeInfo:
        """Look up an employee's current role, completed years of service and assigned devices."""
        employee_id = required(employee_id, "employee_id")
        with database_session(self.path) as session:
            return Employee.info(session, employee_id, self.today())

    def issue_dates(self, employee_id: str, item: str) -> list[date | None]:
        with database_session(self.path) as session:
            return EquipmentIssue.issue_dates(session, employee_id, item)
