# Working on Equipment MCP

## Non-negotiables

- Policy lives in `docs/requirements.md`. Encode a rule only after that doc states the fields, the limit, the boundary example, and whether the outcome is approval, denial, or human review.
- Before adding a tool or a client, check the installed [MCP Python SDK](https://pypi.org/project/mcp/1.30.0/) (`mcp>=1,<2` in `pyproject.toml`; [v1 docs](https://py.sdk.modelcontextprotocol.io/v1/)) and the current official [Python quickstart](https://py.sdk.modelcontextprotocol.io/v1/#quick-example), and follow that API. 
- Keep test coverage high. Every tool's underlying function has unit tests for the success path and for edge cases, including unknown ids. Keep one assert per unit test. Make sure tests are high-fidelity. Unit Tests should follow Arrange-Act-Assert Pattern.
- Follow SOLID. Prefer small types and one reason to change per module. Add packages and files when that keeps a change local.
- Never commit, push, or open a pull request without explicit human approval. Leave `misc/` untracked.

## Code

- Python 3.12 only. Change dependencies in `pyproject.toml`, refresh `uv.lock`
- Use specific types, unions, and `TypeVar`. `typing.Any` is forbidden.
- Raise a specific exception for invalid input and missing records. Use `assert` only for internal invariants.
- Keep domain rules, MCP transport, and the agent loop in separate modules.

## Code Review Rules

Check pull request changes against all five SOLID principles. Report violations with a concrete effect on behavior, testability, or maintainability.

- **Single responsibility.** Keep eligibility and submission decisions separate from MCP request handling and database access.
- **Open/closed.** Flag changes that make adding an equipment policy or tool require edits across unrelated modules.
- **Liskov substitution.** Check that interchangeable implementations preserve the return values, error behavior, and side effects their callers rely on.
- **Interface segregation.** Flag interfaces that force callers or test doubles to depend on operations they never use.
- **Dependency inversion.** Flag direct dependencies on MCP or database implementations that prevent policy logic from being tested in isolation.

For each finding, point to the changed line, explain the impact, and suggest the smallest fix. Skip speculative abstractions.

## Checks

```sh
uv python install 3.12
uv sync --locked
uv run --locked ruff check
uv run --locked pytest
docker build --tag equipment-mcp-test .
docker run --rm --network none equipment-mcp-test
```
