from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from ..models import (
    Eligibility,
    EmployeeInfo,
    Intent,
    UnknownEmployee,
    UnknownRole,
    anniversary,
    required,
)


@dataclass(frozen=True)
class EligibilityChecker:
    employee_info: Callable[[str], EmployeeInfo]
    policy_limits: Callable[[str], dict[str, int]]
    issue_dates: Callable[[str, str], list[date | None]]
    today: Callable[[], date] = date.today

    def check_request_eligibility(
        self, employee_id: str, item: str, intent: Intent = "routine"
    ) -> Eligibility:
        """Evaluate one item. Pass the request intent for exceptions. A review result needs flag_for_human_review."""
        item = required(item, "item").casefold()
        submitted = self.today()
        try:
            employee = self.employee_info(employee_id)
            limits = self.policy_limits(employee.role)
        except (UnknownEmployee, UnknownRole) as error:
            return Eligibility("human_review", str(error), submitted)
        return evaluate_request(
            employee.hired,
            employee.role,
            item,
            intent,
            submitted,
            limits,
            self.issue_dates(employee.employee_id, item),
        )


def evaluate_request(
    hired: date,
    role: str,
    item: str,
    intent: Intent,
    submitted: date,
    limits: dict[str, int],
    issues: list[date | None],
) -> Eligibility:
    if item not in limits:
        return Eligibility("human_review", f"No {item} policy for {role}", submitted)
    if intent == "additional":
        return Eligibility("human_review", f"Additional {item} requested", submitted)
    if intent == "unclear":
        return Eligibility("human_review", "Request intent is unclear", submitted)

    dates: list[date] = []
    for issued_on in issues:
        if issued_on is None:
            return Eligibility("human_review", f"Missing {item} issue date", submitted)
        if not hired <= issued_on <= submitted:
            return Eligibility(
                "human_review",
                f"Conflicting {item} issue date: {issued_on}",
                submitted,
            )
        dates.append(issued_on)
    if not dates:
        if intent == "broken":
            return Eligibility(
                "human_review",
                f"No issue on file for reported broken {item}",
                submitted,
            )
        return Eligibility("approve", f"First {item} issue", submitted)
    latest = max(dates)
    eligible_on = anniversary(latest, latest.year + limits[item])
    if submitted >= eligible_on:
        return Eligibility(
            "approve",
            f"{item.capitalize()} refresh interval met",
            submitted,
            eligible_on,
        )
    if intent == "broken":
        return Eligibility(
            "human_review",
            f"Early replacement of broken {item}",
            submitted,
            eligible_on,
        )
    return Eligibility(
        "deny",
        f"{item.capitalize()} refresh interval has not elapsed",
        submitted,
        eligible_on,
    )
