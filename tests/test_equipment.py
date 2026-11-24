from datetime import date
from pathlib import Path

import pytest

from server.database import connect, initialize
from server.models import Device, EmployeeInfo, InvalidField, Policy, UnknownEmployee
from server.services import EquipmentRequests
from server.services.policies import RolePolicies


@pytest.fixture
def equipment(tmp_path: Path) -> EquipmentRequests:
    path = tmp_path / "equipment.db"
    initialize(path)
    return EquipmentRequests(path, lambda: date(2026, 5, 10))


def test_employee_info_only_includes_assigned_devices(equipment: EquipmentRequests):
    assert equipment.get_employee_info("M1") == EmployeeInfo(
        "M1", "Manager", date(2020, 1, 15), 6, [Device("laptop", date(2024, 5, 10))]
    )


def test_unknown_employee(equipment: EquipmentRequests):
    with pytest.raises(UnknownEmployee, match="X9"):
        equipment.get_employee_info("X9")


def test_blank_employee(equipment: EquipmentRequests):
    with pytest.raises(InvalidField, match="employee_id"):
        equipment.get_employee_info(" ")


def test_policy_rows_match_the_table(equipment: EquipmentRequests):
    assert RolePolicies(equipment.path).list_policies("Manager") == [
        Policy("Manager", "laptop", 2),
        Policy("Manager", "monitor", 3),
    ]


@pytest.mark.parametrize(("role", "years"), [("Manager", 2), ("Standard employee", 4)])
def test_policy_limits(equipment: EquipmentRequests, role: str, years: int):
    assert equipment.get_policy_limits(role) == {"laptop": years, "monitor": 3}


def test_missing_role(equipment: EquipmentRequests):
    from server.models import UnknownRole

    with pytest.raises(UnknownRole, match="Visitor"):
        equipment.get_policy_limits("Visitor")


@pytest.mark.parametrize(
    ("employee", "item", "day", "intent", "decision", "eligible_on"),
    [
        ("M1", "laptop", "2026-05-09", "routine", "deny", "2026-05-10"),
        ("M1", "laptop", "2026-05-10", "routine", "approve", "2026-05-10"),
        ("S1", "laptop", "2026-05-10", "routine", "deny", "2028-05-10"),
        ("M1", "laptop", "2026-05-09", "broken", "human_review", "2026-05-10"),
        ("M1", "laptop", "2026-05-10", "broken", "approve", "2026-05-10"),
        ("M1", "laptop", "2026-05-10", "additional", "human_review", None),
        ("M2", "laptop", "2026-05-10", "routine", "human_review", None),
        ("S1", "monitor", "2026-05-10", "routine", "approve", None),
        ("S1", "monitor", "2026-05-10", "broken", "human_review", None),
        ("X9", "monitor", "2026-05-10", "routine", "human_review", None),
        ("S2", "monitor", "2027-02-28", "routine", "approve", "2027-02-28"),
        ("S2", "tablet", "2027-02-28", "routine", "human_review", None),
        ("S2", "monitor", "2024-02-28", "routine", "human_review", None),
        ("S2", "monitor", "2027-02-28", "unclear", "human_review", None),
    ],
)
def test_eligibility(
    equipment: EquipmentRequests, employee, item, day, intent, decision, eligible_on
):
    result = EquipmentRequests(
        equipment.path, lambda: date.fromisoformat(day)
    ).check_request_eligibility(employee, item, intent)
    assert (result.decision, result.next_eligible_date) == (
        decision,
        date.fromisoformat(eligible_on) if eligible_on else None,
    )


@pytest.mark.parametrize("employee", ["M1", "X9"])
def test_review_survives_restart(equipment: EquipmentRequests, employee: str):
    request = "  Can I get a second monitor?  "
    reason = "Additional device requested"
    review = equipment.flag_for_human_review(employee, request, reason)
    initialize(equipment.path)
    with connect(equipment.path) as db:
        rows = db.execute(
            "SELECT id, employee_id, request, reason, submitted FROM human_review"
        ).fetchall()
    assert (review, rows) == ("R1", [(1, employee, request, reason, "2026-05-10")])


@pytest.mark.parametrize(
    ("employee", "request_text", "reason", "field"),
    [
        (" ", "Laptop please", "Missing date", "employee_id"),
        ("M1", " ", "Missing date", "request"),
        ("M1", "Laptop please", "", "reason"),
    ],
)
def test_invalid_review(
    equipment: EquipmentRequests, employee: str, request_text: str, reason: str, field: str
):
    with pytest.raises(InvalidField, match=field):
        equipment.flag_for_human_review(employee, request_text, reason)


@pytest.mark.parametrize(("day", "years"), [(date(2026, 1, 14), 5), (date(2026, 1, 15), 6)])
def test_tenure_counts_completed_years(equipment: EquipmentRequests, day: date, years: int):
    employees = EquipmentRequests(equipment.path, lambda: day)
    assert employees.get_employee_info("S1").tenure_years == years


def test_assigned_device_with_unknown_issue_date(equipment: EquipmentRequests):
    assert equipment.get_employee_info("M2").current_equipment == [Device("laptop", None)]
