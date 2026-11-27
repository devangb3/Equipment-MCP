import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def equipment_url(tmp_path: Path, free_tcp_port: int) -> Iterator[str]:
    database = tmp_path / "equipment.sqlite3"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "server",
            "--database",
            str(database),
            "--port",
            str(free_tcp_port),
        ]
    )
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if process.poll() is not None:
                pytest.fail(f"Equipment server exited with code {process.returncode}")
            try:
                with socket.create_connection(
                    ("127.0.0.1", free_tcp_port), timeout=0.5
                ):
                    break
            except ConnectionRefusedError:
                time.sleep(0.05)
        else:
            pytest.fail("Equipment server did not start within 15 seconds")
        yield f"http://127.0.0.1:{free_tcp_port}/mcp"
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
