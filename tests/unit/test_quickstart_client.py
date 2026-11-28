import sys
from unittest.mock import AsyncMock, call

import pytest

from quickstart.client import (
    QuickstartCheckError,
    integer_content,
    main,
)


def test_integer_content_returns_none_when_the_tool_omits_it() -> None:
    assert integer_content(None) is None


def test_integer_content_keeps_integer_fields() -> None:
    assert integer_content({"result": 5}) == {"result": 5}


@pytest.mark.parametrize(
    ("content", "match"),
    [
        (["result"], "expected an object"),
        ({"result": True}, "not a string-to-int pair"),
        ({1: 5}, "not a string-to-int pair"),
    ],
)
def test_integer_content_rejects_unexpected_shapes(content: object, match: str) -> None:
    with pytest.raises(QuickstartCheckError, match=match):
        integer_content(content)


def test_main_rejects_a_different_add_result(monkeypatch: pytest.MonkeyPatch) -> None:
    run = AsyncMock(return_value=(["add"], False, {"result": 4}))
    monkeypatch.setattr(sys, "argv", ["quickstart.client"])
    monkeypatch.setattr("quickstart.client.run", run)

    with pytest.raises(QuickstartCheckError) as error:
        main()

    assert (run.await_args_list, str(error.value)) == (
        [call("http://127.0.0.1:8000/mcp")],
        "expected (['add'], False, {'result': 5}), got (['add'], False, {'result': 4})",
    )
