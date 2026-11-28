import asyncio
import sys

import pytest

from quickstart.employee_client import EmployeeLookupError, main, run


def test_employee_client_returns_the_m1_record(equipment_url: str) -> None:
    record = asyncio.run(run(equipment_url, "M1"))

    assert {
        key: record[key] for key in ("employee_id", "role", "current_equipment")
    } == {
        "employee_id": "M1",
        "role": "Manager",
        "current_equipment": [{"item": "laptop", "issued": "2024-05-10"}],
    }


def test_employee_client_cli_prints_the_lookup(
    equipment_url: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        sys, "argv", ["quickstart.employee_client", "--url", equipment_url]
    )

    main()

    assert (
        capsys.readouterr()
        .out.splitlines()[-1]
        .startswith("get_employee_info('M1'): {'employee_id': 'M1', 'role': 'Manager'")
    )


def test_employee_client_lists_get_employee_info(
    equipment_url: str, capsys: pytest.CaptureFixture[str]
) -> None:
    asyncio.run(run(equipment_url, "M1"))

    assert "'get_employee_info'" in capsys.readouterr().out.splitlines()[0]


def test_employee_client_rejects_an_unknown_employee(equipment_url: str) -> None:
    lookup = run(equipment_url, "X9")

    with pytest.raises(EmployeeLookupError, match="X9"):
        asyncio.run(lookup)
