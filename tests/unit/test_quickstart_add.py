import pytest

from quickstart.server import add


@pytest.mark.parametrize(("a", "b", "expected"), [(2, 3, 5), (0, 0, 0), (-5, 2, -3)])
def test_add(a: int, b: int, expected: int) -> None:
    result = add(a, b)

    assert result == expected
