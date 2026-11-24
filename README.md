# Equipment-MCP

Internal IT equipment request handler. An MCP server exposes employee records, policy limits, eligibility, and human review. An agent uses those tools to investigate a natural-language request, draft a response, and reflect before the response is final.

## Local setup

With uv installed, run the same checks as CI from the repository root.

```sh
uv python install 3.12
uv sync --locked
uv run --locked pytest
```

The initial smoke test checks package discovery and SDK imports. GitHub Actions runs the suite on pushes and pull requests.

## Quickstart

To connect by URL, start the server with Streamable HTTP:

```sh
uv run --locked python -m server.quickstart
```

Connect your MCP client using **Streamable HTTP** and connect to `http://127.0.0.1:8000/mcp`. Use `--port` to choose a different port.

To verify both transports, run the checks below. Each starts its own server, lists the tools, calls `add(2, 3)`, and prints the result.


## Run the tests with Docker Compose

From the repository root, run the same Docker Compose command as CI. It builds the Python 3.12 image, runs pytest with container networking disabled, and removes the test container afterward.

```sh
docker compose run --build --rm test
```
