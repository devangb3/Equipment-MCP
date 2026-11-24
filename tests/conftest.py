import socket

import pytest


@pytest.fixture
def free_tcp_port() -> int:
    """Return an ephemeral localhost port that is free at fixture setup."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    assert isinstance(port, int)
    return port
