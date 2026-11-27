# Equipment-MCP

Internal IT equipment request handler. An MCP server exposes employee records, policy limits, eligibility, and human review. An agent uses those tools to investigate a natural-language request, draft a response, and reflect before the response is final.

## Local setup

With uv installed, run the same checks as CI from the repository root.

```sh
uv python install 3.12
uv sync --locked
uv run --locked ruff check
uv run --locked ty check
uv run --locked pytest
```

Ruff lints the code, ty checks Python types, and pytest runs the suite, including the smoke test for package discovery and SDK imports. GitHub Actions runs all three on pushes and pull requests. The container job is the Docker Compose command below.

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

## Equipment MCP server

Start the server from the repository root.

```sh
uv run --locked python -m server --database equipment.sqlite3
```

With the server running, configure your MCP client to use Streamable HTTP at `http://127.0.0.1:43817/mcp`. To select another port, pass `--port` when starting the server.

The first start initializes SQLite file with four fictional employees and the role limits in [the requirements](docs/requirements.md). Subsequent runs reuse it.

| Tool | Example arguments | Result |
| --- | --- | --- |
| `get_employee_info` | `{"employee_id":"M1"}` | Role, hire date, completed years of service and current equipment |
| `get_policy_limits` | `{"role":"Manager"}` | Refresh intervals in calendar years for each covered item |
| `check_request_eligibility` | `{"employee_id":"M2","item":"laptop"}` | Decision and reason using today's date. Optional `intent` accepts `routine` (default), `additional`, `broken` or `unclear`. |
| `flag_for_human_review` | `{"employee_id":"M2","request":"Please refresh my laptop.","reason":"Missing laptop issue date"}` | Saves the case and returns its review ID, such as `R1` |
| `submit_request` | `{"employee_id":"M2","item":"laptop","request":"Please refresh my laptop."}` | Saves the submission and returns its request ID, policy result and any review ID. Accepts the same optional intent as the eligibility check. |

`submit_request` is used once per submission. Its review ID identifies the case it already opened. `check_request_eligibility` is used for previews and `flag_for_human_review` for a direct referral.

A human operator can record a decision for a pending review using its returned ID. For example, if the case is R1:

```sh
uv run --locked python -m server.resolve_review --database equipment.sqlite3 R1 approve --reviewer "Taylor" --rationale "Verified the original issue date."
```


## Run the ReAct agent MCP CLient

Start the equipment MCP server as shown above. Copy `.env.example` to `.env` and set
`FOUNDRY_BASE_URL`, `FOUNDRY_MODEL` (deployment name), and `FOUNDRY_API_KEY`.

In a second terminal, supply the employee ID and the request in their own words.

```sh
uv run --locked --env-file .env python -m agent S1 "I need my first monitor."
```

Each turn prints the model's brief action purpose under `Thought`, the MCP call under
`Action`, and the server result under `Observation`. The model receives that result
before selecting its next action. The same model then checks its draft against
the verified eligibility decision and any review receipt. If the draft needs work,
the model gives specific feedback, rewrites it, and checks the revision. Each pass
sees the original request, earlier drafts, and feedback. Refinement runs without tools.
After three unsuccessful rewrites the agent returns the verified decision. Approvals and denials report
eligibility. An escalation opens a case and returns its ID.

To see the approval, denial, and escalation traces without credentials, run the
integration scenarios. They use scripted model responses, a running MCP server,
and a fresh SQLite database per request. The denial and escalation cases also
exercise correction of a draft that promises shipment.

```sh
uv run --locked pytest -q -s tests/integration/test_agent.py
```

## Agent evaluation

The [equipment evaluation suite](evals/README.md) runs the ReAct and Self-Refine loops against isolated employee histories.
Run the eval suite using:
```sh
mkdir -p evals/results
uv run --locked --env-file .env python -m evals.run run > evals/results/runs.jsonl
uv run --locked --env-file .env python -m evals.judge evals/results/runs.jsonl > evals/results/run-grades.jsonl
```
