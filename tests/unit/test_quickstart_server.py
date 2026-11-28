import sys

import pytest

from quickstart.server import main, mcp


def test_main_listens_on_the_requested_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["quickstart.server", "--port", "8163"])
    calls: list[tuple[int, str]] = []

    def run(transport: str) -> None:
        calls.append((mcp.settings.port, transport))

    monkeypatch.setattr(mcp, "run", run)

    main()

    assert calls == [(8163, "streamable-http")]
