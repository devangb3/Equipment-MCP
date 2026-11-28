import sys
from pathlib import Path

import pytest
from mcp.server.fastmcp import FastMCP

from server.__main__ import create_server, main
from server.models import Device
from server.services import EquipmentRequests


def test_cli_initializes_the_database_and_starts_http(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "equipment.sqlite3"
    launches: list[tuple[Path, int, str, list[Device]]] = []

    def build(requests: EquipmentRequests, port: int) -> FastMCP:
        server = create_server(requests, port)

        def launch(*, transport: str) -> None:
            employee = requests.get_employee_info("M2")
            launches.append(
                (
                    requests.path,
                    server.settings.port,
                    transport,
                    employee.current_equipment,
                )
            )

        monkeypatch.setattr(server, "run", launch)
        return server

    monkeypatch.setattr(
        sys, "argv", ["server", "--database", str(database), "--port", "43999"]
    )
    monkeypatch.setattr("server.__main__.create_server", build)

    main()

    assert launches == [
        (database, 43999, "streamable-http", [Device(item="laptop", issued=None)])
    ]
