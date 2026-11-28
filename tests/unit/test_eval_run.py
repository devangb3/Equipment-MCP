import asyncio
import errno
import os
import sys
from pathlib import Path

import pytest

from evals.cases import CASES, CASES_BY_ID
from evals.run import main, prepare, validate


def test_validate_rejects_a_fixture_that_cannot_produce_the_reference(
    tmp_path: Path,
) -> None:
    case = CASES_BY_ID["ledger-a"]
    forged = case.model_copy(
        update={
            "expected": case.expected.model_copy(
                update={"reason": "Not the policy reason"}
            )
        }
    )
    services = prepare(forged, tmp_path / "equipment.sqlite3")

    with pytest.raises(ValueError, match="ledger-a: fixture cannot produce"):
        validate(forged, services)


def test_validate_command_accepts_every_fixture(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["evals.run", "validate"])

    asyncio.run(main())

    assert capsys.readouterr().out.splitlines() == [
        f"{case.id}: validated" for case in CASES
    ]


@pytest.mark.parametrize(
    ("arguments", "diagnostic"),
    [
        pytest.param(
            ["capture", "--judge-model", "grader"],
            "--output and --judge-model require run mode.",
            id="judge-option-in-capture-mode",
        ),
        pytest.param(
            ["validate", "--case", "missing"],
            "Unknown cases: ['missing']",
            id="unknown-case",
        ),
    ],
)
def test_command_rejects_invalid_arguments(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    arguments: list[str],
    diagnostic: str,
) -> None:
    monkeypatch.setattr(sys, "argv", ["evals.run", *arguments])

    with pytest.raises(SystemExit) as error:
        asyncio.run(main())

    output = capsys.readouterr()
    assert (error.value.code, output.out, output.err.splitlines()[-1:]) == (
        2,
        "",
        [f"evals.run: error: {diagnostic}"],
    )


def test_capture_command_reports_missing_foundry_settings(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["evals.run", "capture"])
    monkeypatch.delenv("FOUNDRY_BASE_URL", raising=False)
    monkeypatch.delenv("FOUNDRY_MODEL", raising=False)
    monkeypatch.delenv("FOUNDRY_API_KEY", raising=False)

    with pytest.raises(SystemExit) as error:
        asyncio.run(main())

    output = capsys.readouterr()
    assert (error.value.code, output.out, output.err.splitlines()[-1:]) == (
        2,
        "",
        ["evals.run: error: Set FOUNDRY_BASE_URL in .env using .env.example."],
    )


def test_run_command_refuses_to_overwrite_existing_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "results.jsonl"
    previous_results = '{"id": "previous-run"}\n'
    output.write_text(previous_results, encoding="utf-8")
    monkeypatch.setenv("FOUNDRY_BASE_URL", "https://foundry.example")
    monkeypatch.setenv("FOUNDRY_MODEL", "agent")
    monkeypatch.setenv("FOUNDRY_API_KEY", "test-key")
    monkeypatch.delenv("FOUNDRY_PROMPT_CACHE_KEY", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        ["evals.run", "run", "--case", "ledger-a", "--output", str(output)],
    )

    with pytest.raises(SystemExit) as error:
        asyncio.run(main())

    captured = capsys.readouterr()
    exists = FileExistsError(errno.EEXIST, os.strerror(errno.EEXIST), str(output))
    assert (
        error.value.code,
        captured.out,
        captured.err,
        output.read_text(encoding="utf-8"),
    ) == (2, "", f"{exists}\n", previous_results)
