"""Compose the tool implementations for a SQLite-backed server."""

from collections.abc import Callable
from datetime import date
from pathlib import Path

from .eligibility import EligibilityChecker
from .employees import EmployeeDirectory
from .policies import RolePolicies
from .reviews import ReviewQueue
from .submissions import Submissions


class EquipmentRequests:
    def __init__(self, path: Path, today: Callable[[], date] = date.today) -> None:
        self.path = path
        employees = EmployeeDirectory(path, today)
        policies = RolePolicies(path)
        eligibility = EligibilityChecker(
            employees.get_employee_info,
            policies.get_policy_limits,
            employees.issue_dates,
            today,
        )
        self.get_employee_info = employees.get_employee_info
        self.get_policy_limits = policies.get_policy_limits
        self.check_request_eligibility = eligibility.check_request_eligibility
        self.submit_request = Submissions(path, eligibility).submit_request
        self.flag_for_human_review = ReviewQueue(path, today).flag_for_human_review
