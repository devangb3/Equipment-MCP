import sys
from unittest.mock import AsyncMock, call

import pytest
from mcp.types import CallToolResult, TextContent

from quickstart.employee_client import EmployeeLookupError, employee_record, main


def test_main_defaults_to_m1_on_the_equipment_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = AsyncMock(return_value={})
    monkeypatch.setattr(sys, "argv", ["quickstart.employee_client"])
    monkeypatch.setattr("quickstart.employee_client.run", run)

    main()

    assert run.await_args_list == [call("http://127.0.0.1:43817/mcp", "M1")]


def test_main_passes_the_requested_employee(monkeypatch: pytest.MonkeyPatch) -> None:
    run = AsyncMock(return_value={})
    monkeypatch.setattr(
        sys, "argv", ["quickstart.employee_client", "--employee-id", "S1"]
    )
    monkeypatch.setattr("quickstart.employee_client.run", run)

    main()

    assert run.await_args_list == [call("http://127.0.0.1:43817/mcp", "S1")]


def test_employee_record_returns_structured_content() -> None:
    result = CallToolResult(
        content=[], structuredContent={"employee_id": "M1"}, isError=False
    )

    record = employee_record("M1", result)

    assert record == {"employee_id": "M1"}


def test_employee_record_raises_with_the_server_error() -> None:
    result = CallToolResult(
        content=[TextContent(type="text", text="Unknown employee: X9")], isError=True
    )

    with pytest.raises(EmployeeLookupError, match="Unknown employee: X9"):
        employee_record("X9", result)


def test_employee_record_raises_when_content_is_missing() -> None:
    result = CallToolResult(content=[], structuredContent=None, isError=False)

    with pytest.raises(EmployeeLookupError, match="'M1'"):
        employee_record("M1", result)
