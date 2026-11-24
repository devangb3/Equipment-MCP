from calendar import monthrange
from datetime import date

from .errors import InvalidField


def anniversary(start: date, year: int) -> date:
    return date(year, start.month, min(start.day, monthrange(year, start.month)[1]))


def required(value: str, field: str) -> str:
    if not value.strip():
        raise InvalidField(f"{field} is required")
    return value.strip()
