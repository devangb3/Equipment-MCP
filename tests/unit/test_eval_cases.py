import pytest

from evals.cases import CASES, index_cases


def test_duplicate_case_ids_are_rejected() -> None:
    case = CASES[0]

    with pytest.raises(ValueError, match="Evaluation case IDs must be unique"):
        index_cases((case, case))
