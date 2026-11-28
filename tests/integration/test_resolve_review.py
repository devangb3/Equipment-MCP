import sys
from datetime import date
from pathlib import Path

import pytest

from server.database import connect, initialize
from server.resolve_review import main
from server.services import EquipmentRequests


def test_cli_records_an_operator_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "equipment.sqlite3"
    initialize(path)
    review = EquipmentRequests(path, lambda: date(2026, 5, 10)).flag_for_human_review(
        "X9", "Need a laptop", "Unknown employee"
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "resolve_review",
            "--database",
            str(path),
            review,
            "approve",
            "--reviewer",
            "Taylor",
            "--rationale",
            "Verified the roster.",
        ],
    )

    main()
    with connect(path) as db:
        status = db.execute("SELECT status FROM request_history").fetchone()[0]

    assert (capsys.readouterr().out, status) == (f"{review}: approve\n", "approve")


def test_cli_reports_an_unknown_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "equipment.sqlite3"
    initialize(path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "resolve_review",
            "--database",
            str(path),
            "R9",
            "deny",
            "--reviewer",
            "Taylor",
            "--rationale",
            "No such case.",
        ],
    )

    try:
        main()
        outcome = None
    except SystemExit as error:
        outcome = (error.code, capsys.readouterr().err)

    assert outcome == (1, "Unknown review: R9\n")
