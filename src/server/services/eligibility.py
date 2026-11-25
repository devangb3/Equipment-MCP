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
            return Eligibility(
                decision="human_review", reason=str(error), submitted=submitted
            )
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
        return Eligibility(
            decision="human_review",
            reason=f"No {item} policy for {role}",
            submitted=submitted,
        )
    if intent == "additional":
        return Eligibility(
            decision="human_review",
            reason=f"Additional {item} requested",
            submitted=submitted,
        )
    if intent == "unclear":
        return Eligibility(
            decision="human_review",
            reason="Request intent is unclear",
            submitted=submitted,
        )

    dates: list[date] = []
    for issued_on in issues:
        if issued_on is None:
            return Eligibility(
                decision="human_review",
                reason=f"Missing {item} issue date",
                submitted=submitted,
            )
        if not hired <= issued_on <= submitted:
            return Eligibility(
                decision="human_review",
                reason=f"Conflicting {item} issue date: {issued_on}",
                submitted=submitted,
            )
        dates.append(issued_on)
    if not dates:
        if intent == "broken":
            return Eligibility(
                decision="human_review",
                reason=f"No issue on file for reported broken {item}",
                submitted=submitted,
            )
        return Eligibility(
            decision="approve", reason=f"First {item} issue", submitted=submitted
        )
    latest = max(dates)
    eligible_on = anniversary(latest, latest.year + limits[item])
    if submitted >= eligible_on:
        return Eligibility(
            decision="approve",
            reason=f"{item.capitalize()} refresh interval met",
            submitted=submitted,
            next_eligible_date=eligible_on,
        )
    if intent == "broken":
        return Eligibility(
            decision="human_review",
            reason=f"Early replacement of broken {item}",
            submitted=submitted,
            next_eligible_date=eligible_on,
        )
    return Eligibility(
        decision="deny",
        reason=f"{item.capitalize()} refresh interval has not elapsed",
        submitted=submitted,
        next_eligible_date=eligible_on,
    )
