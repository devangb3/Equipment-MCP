# Equipment agent evals

Each of the 25 [cases](cases.py) runs the full pipeline once. The agent investigates with MCP tools, writes its own draft, reflects, and returns a final answer. The judge grades that same trace, response, and database effects.

The LLM-as-Judge answers questions about response accuracy, grounding, and reflection, plus the named yes/no questions in each case's `expected.rubric`. Each answer contains a `passed` boolean and a short `evidence` string. The grade records case-specific answers under `verdict.case_rubric` using the same question IDs. A run passes when every rubric answer is yes and every deterministic check passes. Missing or unexpected rubric answers produce a grading error.

Run from the repository root with the agent’s Foundry settings in `.env`.

```sh
mkdir -p evals/results
uv run --locked --env-file .env python -m evals.run run > evals/results/runs.jsonl
uv run --locked --env-file .env python -m evals.judge evals/results/runs.jsonl > evals/results/run-grades.jsonl
```

Report the end-to-end score as passing pipeline cases out of 25. Use `--case ID` for a subset, `--model DEPLOYMENT` on the judge to choose its model, or `python -m evals.run validate` to check the labels offline. Git ignores `evals/results/`.
