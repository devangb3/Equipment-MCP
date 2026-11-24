from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Device:
    item: str
    issued: date | None

@dataclass(frozen=True)
class Policy:
    role: str
    item: str
    years: int


@dataclass(frozen=True)
class EmployeeInfo:
    employee_id: str
    role: str
    hired: date
    tenure_years: int
    current_equipment: list[Device]