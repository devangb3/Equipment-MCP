import sqlite3
from pathlib import Path

import pytest

from server.database import connect, initialize


def test_failed_initial_creation_rolls_back_earlier_tables(tmp_path: Path) -> None:
    path = tmp_path / "equipment.db"
    with connect(path) as db:
        db.execute("CREATE TABLE policy (existing_column TEXT)")

    with pytest.raises(sqlite3.OperationalError, match="policy already exists"):
        initialize(path)

    with connect(path) as db:
        assert db.execute(
            "SELECT name FROM sqlite_schema WHERE type = 'table'"
        ).fetchall() == [("policy",)]
