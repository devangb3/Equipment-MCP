# Equipment-MCP

Python scaffold for an internal IT equipment request handler. The planned MCP server exposes employee records, policy limits, eligibility checks, and human review. The agent will use those tools to investigate requests and reflect on its drafted responses.

## Local setup

With uv installed, run the same checks as CI from the repository root.

```sh
uv python install 3.12
uv sync --locked
uv run --locked pytest
```

The initial smoke test checks package discovery and SDK imports. GitHub Actions runs the suite on pushes and pull requests.

## Run the tests in Docker

From the repository root, build the Python 3.12 test image and run it with networking disabled. CI runs these same commands. The image includes the project and its test dependencies, so running it requires only Docker.

```sh
docker build --tag equipment-mcp-test .
docker run --rm --network none equipment-mcp-test
```
