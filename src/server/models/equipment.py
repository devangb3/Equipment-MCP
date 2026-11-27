from datetime import date
from typing import Self

from sqlmodel import Field, Session, SQLModel, col, select

from .errors import UnknownEmployee, UnknownRole
from .helpers import anniversary


class Device(SQLModel, frozen=True):
    item: str
    issued: date | None


class EmployeeInfo(SQLModel, frozen=True):
    employee_id: str
    role: str
    hired: date
    tenure_years: int
    current_equipment: list[Device]


class Employee(SQLModel, table=True):
    id: str = Field(primary_key=True)
    role: str
    hired: date

    @classmethod
    def info(cls, session: Session, employee_id: str, today: date) -> EmployeeInfo:
        employee = session.get(cls, employee_id)
        if employee is None:
            raise UnknownEmployee(f"Unknown employee: {employee_id}")
        hired = employee.hired
        tenure = today.year - hired.year - (today < anniversary(hired, today.year))
        return EmployeeInfo(
            employee_id=employee.id,
            role=employee.role,
            hired=hired,
            tenure_years=tenure,
            current_equipment=EquipmentIssue.assigned_devices(session, employee_id),
        )


class EquipmentIssue(SQLModel, table=True):
    __tablename__ = "equipment_issue"

    id: int | None = Field(default=None, primary_key=True)
    employee_id: str = Field(foreign_key="employee.id")
    item: str
    issued: date | None
    assigned: bool

    @classmethod
    def assigned_devices(cls, session: Session, employee_id: str) -> list[Device]:
        query = (
            select(cls)
            .where(cls.employee_id == employee_id, col(cls.assigned).is_(True))
            .order_by(col(cls.id))
        )
        return [Device(item=row.item, issued=row.issued) for row in session.exec(query)]

    @classmethod
    def issue_dates(
        cls, session: Session, employee_id: str, item: str
    ) -> list[date | None]:
        query = select(col(cls.issued)).where(
            cls.employee_id == employee_id, cls.item == item
        )
        return list(session.exec(query))


class Policy(SQLModel, table=True):
    role: str = Field(primary_key=True)
    item: str = Field(primary_key=True)
    years: int

    @classmethod
    def for_role(cls, session: Session, role: str) -> list[Self]:
        query = (
            select(cls)
            .where(col(cls.role).collate("NOCASE") == role)
            .order_by(col(cls.item))
        )
        policies = list(session.exec(query))
        if not policies:
            raise UnknownRole(f"No equipment policy for role: {role}")
        return policies
