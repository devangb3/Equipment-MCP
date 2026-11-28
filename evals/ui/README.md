# Eval results viewer

Start the viewer from the repository root.

```sh
uv run --locked python -m evals.ui
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). Use `--port` to choose a different port.

Select a run from `evals/results/`, then select a case to see its request, final response, grade, and agent trace together. Search by case ID or request text, filter graded cases by result, or open the raw JSONL. Use **Refresh files** after generating results.

The viewer runs locally and reads existing files. It requires no Foundry credentials or frontend build.
