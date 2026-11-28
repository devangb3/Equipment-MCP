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

Ruff lints the code, ty checks Python types, and pytest runs the unit and integration tests, including real MCP client/server connections. GitHub Actions runs all three on pushes and pull requests. The container job is the Docker Compose command below.

Check test coverage:

```sh
uv run --locked pytest --cov=agent --cov=server --cov=quickstart --cov=evals --cov-report=term-missing
```

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

## OpenRouter and provider failover

The agent defaults to Foundry. To use OpenRouter directly, set `MODEL_PROVIDER=openrouter`,
`OPENROUTER_API_KEY`, and `OPENROUTER_MODEL` in `.env`. Choose a model that supports
function tools. No Foundry credentials are needed in this mode.

To keep Foundry primary and enable OpenRouter as a fallback:

```dotenv
MODEL_PROVIDER=foundry
MODEL_FALLBACK_PROVIDER=openrouter
OPENROUTER_API_KEY=your-key
OPENROUTER_MODEL=vendor/tool-capable-model
```

Keep the existing Foundry settings as well. Setting the fallback is an explicit opt-in
to send employee requests, public conversation messages, and tool observations to
OpenRouter and its selected model provider. Merely adding an API key does not enable it.
Provider-private reasoning and message IDs are removed from OpenRouter history;
tool call IDs and completed tool results are preserved. Both providers use `store=false`;
that flag is not a guarantee of third-party retention policy. Check your organization's
provider/data rules before enabling external routing.

The integration uses OpenRouter's [Responses API](https://openrouter.ai/docs/api/api-reference/responses/create-a-response)
with bearer authentication. It switches on connection/transport errors, HTTP 408/429,
and HTTP 5xx, then stays with OpenRouter for the rest of that agent request, including
reflection. Each turn makes at most one attempt per provider with a 120-second HTTP
operation timeout. There is no retry loop, workflow restart, or automatic MCP tool retry.
A saved human-review receipt remains part of the history. HTTP 4xx other than 408/429,
invalid configuration, invalid/incomplete model output, and cancellation do not trigger
failover. The agent stops on fallback failure. A warning reports the provider switch
without logging credentials or conversation content.

Evaluation CLIs (`evals.run` and `evals.judge`) continue to use Foundry independently;
the new routing settings apply to `python -m agent`.

## Agent evaluation

The [equipment evaluation suite](evals/README.md) runs the ReAct and Self-Refine loops against isolated employee histories.

```sh
uv run --locked --env-file .env python -m evals.run run
```

The command captures and grades each case and saves one JSONL file in `evals/results/`. Open it in the [local results viewer](evals/ui/README.md).
