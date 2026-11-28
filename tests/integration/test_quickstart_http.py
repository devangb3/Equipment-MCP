import asyncio
import sys

import pytest

from quickstart.client import main


def test_quickstart_cli_connects_and_adds_two_and_three(
    free_tcp_port: int,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    url = f"http://127.0.0.1:{free_tcp_port}/mcp"
    monkeypatch.setattr(sys, "argv", ["quickstart.client", "--url", url])

    async def check_server() -> None:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "quickstart.server",
            "--port",
            str(free_tcp_port),
        )
        try:
            async with asyncio.timeout(15):
                while process.returncode is None:
                    try:
                        _, writer = await asyncio.open_connection(
                            "127.0.0.1", free_tcp_port
                        )
                    except ConnectionRefusedError:
                        await asyncio.sleep(0.05)
                        continue
                    writer.close()
                    await writer.wait_closed()
                    break
                else:
                    pytest.fail(
                        f"HTTP server exited during startup with code {process.returncode}"
                    )

                await asyncio.to_thread(main)
        finally:
            if process.returncode is None:
                process.terminate()
                await process.wait()

    asyncio.run(check_server())

    assert capsys.readouterr().out == (
        "Connected to Equipment quickstart. Registered tools: ['add']. "
        "add(2, 3): {'result': 5}\n"
    )
