from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ..database import connect
from ..models import Device, EmployeeInfo, UnknownEmployee, anniversary, required


@dataclass(frozen=True)
class EmployeeDirectory:
    path: Path
    today: Callable[[], date] = date.today

    def get_employee_info(self, employee_id: str) -> EmployeeInfo:
        """Look up an employee's current role, completed years of service and assigned devices."""
        employee_id = required(employee_id, "employee_id")
        with connect(self.path) as db:
            row = db.execute(
                "SELECT role, hired FROM employee WHERE id = ?", (employee_id,)
            ).fetchone()
            if row is None:
                raise UnknownEmployee(f"Unknown employee: {employee_id}")
            devices = [
                Device(item, date.fromisoformat(issued) if issued else None)
                for item, issued in db.execute(
                    "SELECT item, issued FROM equipment_issue WHERE employee_id = ? AND assigned = 1 ORDER BY id",
                    (employee_id,),
                )
            ]
        role, hired_text = row
        hired = date.fromisoformat(hired_text)
        today = self.today()
        tenure = today.year - hired.year - (today < anniversary(hired, today.year))
        return EmployeeInfo(employee_id, role, hired, tenure, devices)

    def issue_dates(self, employee_id: str, item: str) -> list[date | None]:
        with connect(self.path) as db:
            return [
                date.fromisoformat(issued) if issued is not None else None
                for (issued,) in db.execute(
                    "SELECT issued FROM equipment_issue WHERE employee_id = ? AND item = ?",
                    (employee_id, item),
                )
            ]
