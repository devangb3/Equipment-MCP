from datetime import date
from importlib.resources import files
from pathlib import Path

import pytest

from server.database import connect, initialize
from server.models import InvalidField, ReviewAlreadyResolved, UnknownReview
from server.services import EquipmentRequests
from server.services.reviews import resolve_review


@pytest.fixture
def service(tmp_path: Path) -> EquipmentRequests:
    path = tmp_path / "history.db"
    initialize(path)
    return EquipmentRequests(path, lambda: date(2026, 5, 10))


@pytest.mark.parametrize(
    ("employee", "status", "review", "reason", "eligible_on"),
    [
        ("M1", "approve", None, "Laptop refresh interval met", "2026-05-10"),
        ("S1", "deny", None, "Laptop refresh interval has not elapsed", "2028-05-10"),
        ("X9", "pending_review", "R1", "Unknown employee: X9", None),
    ],
)
def test_submission_history(
    service: EquipmentRequests,
    employee: str,
    status: str,
    review: str | None,
    reason: str,
    eligible_on: str | None,
) -> None:
    request = "  Refresh my laptop.  "

    receipt = service.submit_request(employee, "Laptop", request)

    with connect(service.path) as db:
        rows = db.execute("""SELECT request_id, employee_id, request, item, intent, submitted,
            status, review_id, policy_reason, next_eligible_date FROM request_history""").fetchall()
    assert rows == [
        (
            receipt.request_id,
            employee,
            request,
            "laptop",
            "routine",
            "2026-05-10",
            status,
            review,
            reason,
            eligible_on,
        )
    ]


def test_blank_submission(service: EquipmentRequests):
    with pytest.raises(InvalidField, match="request"):
        service.submit_request("M1", "monitor", " ")


@pytest.mark.parametrize("decision", ["approve", "deny"])
def test_review_resolution_survives_retry_and_restart(
    service: EquipmentRequests, decision: str
):
    receipt = service.submit_request("X9", "laptop", "Please replace it")
    resolve_review(service.path, "R1", decision, "Taylor", "Checked records")
    initialize(service.path)
    resolve_review(service.path, "R1", decision, "Taylor", "Checked records")
    with connect(service.path) as db:
        rows = db.execute("""SELECT request_id, policy_outcome, review_id, human_decision,
            status, reviewer, rationale, decided_at IS NOT NULL FROM request_history""").fetchall()
    assert rows == [
        (
            receipt.request_id,
            "human_review",
            receipt.review_id,
            decision,
            decision,
            "Taylor",
            "Checked records",
            1,
        )
    ]


def test_conflicting_decision(service: EquipmentRequests):
    review = service.flag_for_human_review("X9", "Need laptop", "Unknown employee")
    resolve_review(service.path, review, "deny", "Taylor", "Checked records")
    with pytest.raises(ReviewAlreadyResolved):
        resolve_review(service.path, review, "approve", "Taylor", "Changed decision")


def test_automatic_approval_has_no_review(service: EquipmentRequests):
    service.submit_request("M1", "monitor", "First monitor")
    with pytest.raises(UnknownReview):
        resolve_review(service.path, "R1", "approve", "Taylor", "Confirmed")


def test_existing_review_migration(tmp_path: Path):
    path = tmp_path / "v1.db"
    with connect(path) as db:
        db.executescript(files("server").joinpath("sql/001_initial.sql").read_text())
        db.execute("PRAGMA user_version = 1")
        db.execute(
            "INSERT INTO human_review VALUES (42, 'X9', 'My request', 'Unknown ID', '2025-02-20')"
        )
    initialize(path)
    resolve_review(path, "R42", "deny", "Taylor", "Checked roster")
    with connect(path) as db:
        row = db.execute("""SELECT review_id, employee_id, request, policy_reason, item, intent,
            submitted, status FROM request_history""").fetchone()
    assert row == (
        "R42",
        "X9",
        "My request",
        "Unknown ID",
        None,
        None,
        "2025-02-20",
        "deny",
    )


def test_unknown_review_outside_sqlite_integer_range(service: EquipmentRequests):
    with pytest.raises(UnknownReview):
        resolve_review(
            service.path, "R9223372036854775808", "deny", "Taylor", "Checked roster"
        )


@pytest.mark.parametrize(
    ("review_id", "decision", "reviewer", "rationale", "match"),
    [
        ("R0", "approve", "Taylor", "Checked roster", "review ID"),
        ("R1", "hold", "Taylor", "Checked roster", "approve or deny"),
        ("R1", "approve", " ", "Checked roster", "reviewer"),
        ("R1", "deny", "Taylor", " ", "rationale"),
    ],
)
def test_resolve_review_rejects_invalid_fields(
    service: EquipmentRequests,
    review_id: str,
    decision: str,
    reviewer: str,
    rationale: str,
    match: str,
) -> None:
    with pytest.raises(InvalidField, match=match):
        resolve_review(service.path, review_id, decision, reviewer, rationale)
