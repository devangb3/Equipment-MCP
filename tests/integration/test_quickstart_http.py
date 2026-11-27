import asyncio
import sys

import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


def test_streamable_http_registers_and_runs_add(free_tcp_port: int) -> None:
    async def check_server() -> None:
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "quickstart.server",
            "--port", str(free_tcp_port),
        )
        try:
            async with asyncio.timeout(15):
                while process.returncode is None:
                    try:
                        _, writer = await asyncio.open_connection("127.0.0.1", free_tcp_port)
                    except ConnectionRefusedError:
                        await asyncio.sleep(0.05)
                        continue
                    writer.close()
                    await writer.wait_closed()
                    break
                else:
                    pytest.fail(f"HTTP server exited during startup with code {process.returncode}")

                url = f"http://127.0.0.1:{free_tcp_port}/mcp"
                async with (
                    streamable_http_client(url) as (reader, writer_stream, _),
                    ClientSession(reader, writer_stream) as session,
                ):
                    info = await session.initialize()
                    names = [tool.name for tool in (await session.list_tools()).tools]
                    result = await session.call_tool("add", {"a": 2, "b": 3})
                    print(
                        f"Connected to {info.serverInfo.name}. "
                        f"Registered tools: {names}. add(2, 3): {result.structuredContent}"
                    )
                    assert (names, result.isError, result.structuredContent) == (
                        ["add"],
                        False,
                        {"result": 5},
                    )
        finally:
            if process.returncode is None:
                process.terminate()
                await process.wait()

    asyncio.run(check_server())
