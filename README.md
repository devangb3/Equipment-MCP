# Equipment-MCP

Internal IT equipment request handler. An MCP server exposes employee records, policy limits, eligibility, and human review. An agent uses those tools to investigate a natural-language request, draft a response, and reflect before the response is final.

## Local setup

With uv installed, run the same checks as CI from the repository root.

```sh
uv python install 3.12
uv sync --locked
uv run --locked ruff check
uv run --locked pytest
```

Ruff checks the code, then pytest runs the suite, including the smoke test for package discovery and SDK imports. GitHub Actions runs both on pushes and pull requests. The container job is the Docker Compose command below.

## Quickstart

To connect by URL, start the server with Streamable HTTP:

```sh
uv run --locked python -m quickstart.server --port 8163
```

Connect an MCP client using **Streamable HTTP** at `http://127.0.0.1:8163/mcp`.

The demo client lists the tools, calls `add(2, 3)`, and prints the result:

```sh
uv run --locked python -m quickstart.client --url http://127.0.0.1:8163/mcp
```


## Run the tests with Docker Compose

From the repository root, run the same Docker Compose command as CI. It builds the Python 3.12 image, runs pytest with container networking disabled, and removes the test container afterward.

```sh
docker compose run --build --rm test
```
