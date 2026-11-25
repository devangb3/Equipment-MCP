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
    ("employee", "status", "review"),
    [
        ("M1", "approve", None),
        ("S1", "deny", None),
        ("X9", "pending_review", "R1"),
    ],
)
def test_submission_history(
    service: EquipmentRequests, employee: str, status: str, review: str | None
):
    receipt = service.submit_request(employee, "Laptop", "  Refresh my laptop.  ")
    with connect(service.path) as db:
        row = db.execute("""SELECT request_id, employee_id, request, item, intent, submitted,
            status, review_id, policy_reason FROM request_history""").fetchone()
    assert row == (
        receipt.request_id,
        employee,
        "  Refresh my laptop.  ",
        "laptop",
        "routine",
        "2026-05-10",
        status,
        review,
        receipt.eligibility.reason,
    )


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
        resolve_review(service.path, "R9223372036854775808", "deny", "Taylor", "Checked roster")
