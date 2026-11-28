# Equipment agent evals

Each of the 25 [cases](cases.py) runs the full pipeline once. The agent investigates with MCP tools, writes its own draft, reflects, and returns a final answer. The judge grades that same trace, response, and database effects.

The LLM-as-Judge answers questions about response accuracy and grounding, plus the named yes/no questions in each case's `expected.rubric`. Each answer contains a `passed` boolean and a short `evidence` string. The grade records case-specific answers under `grade.verdict.case_rubric` using the same question IDs. A case passes when every rubric answer is yes and every deterministic check passes. Missing or unexpected rubric answers produce a grading error.

Run from the repository root with the agent’s Foundry settings in `.env`.

```sh
uv run --locked --env-file .env python -m evals.run run
```

The command writes a single timestamped JSONL file to `evals/results/`. Each line contains the capture and its `grade`. The command prints the pass count and exits with status 1 if any case fails. Use `--case ID` for a subset, `--judge-model DEPLOYMENT` to override the judge deployment, or `--output PATH` to write to a different new file. 

Use the [local results viewer](ui/README.md) to browse agent trajectories and grades together.

## CI

The [CI workflow](../.github/workflows/ci.yml) runs on every push and pull request. The **test** job installs Python 3.12 with `uv`, syncs locked dependencies, then runs `ruff check`, `ty check`, and `pytest`. The **container** job builds the project image and runs the same pytest suite inside Docker with `network_mode: none`,

Run the full graded suite locally with Foundry settings in `.env` (see above). To verify case fixtures and expected policy outcomes without credentials, run:

```sh
uv run --locked python -m evals.run validate
```
