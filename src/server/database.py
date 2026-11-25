"""SQLite connections and transactional initialization."""

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

from sqlalchemy import URL, Engine
from sqlalchemy.pool import NullPool
from sqlmodel import Session, create_engine


@lru_cache(maxsize=16)
def _engine(path: Path) -> Engine:
    return create_engine(URL.create("sqlite", database=str(path)), poolclass=NullPool)


@contextmanager
def database_session(path: Path, *, write: bool = False) -> Iterator[Session]:
    with (
        Session(_engine(path.resolve()), expire_on_commit=False) as session,
        session.begin(),
    ):
        connection = session.connection()
        connection.exec_driver_sql("PRAGMA foreign_keys = ON")
        connection.exec_driver_sql("BEGIN IMMEDIATE" if write else "BEGIN")
        yield session


@contextmanager
def connect(path: Path) -> Iterator[sqlite3.Connection]:
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("PRAGMA foreign_keys = ON")
        yield db


def initialize(path: Path) -> None:
    """Create and seed the database once, including across concurrent starts."""
    with connect(path) as db:
        # Explicit transaction control keeps executescript from committing between files.
        db.autocommit = True
        db.execute("BEGIN IMMEDIATE")
        version = db.execute("PRAGMA user_version").fetchone()[0]
        scripts = files("server").joinpath("sql")
        if version == 0:
            for name in ("001_initial.sql", "seed_demo.sql"):
                db.executescript(scripts.joinpath(name).read_text(encoding="utf-8"))
            version = 1
        if version == 1:
            db.executescript(
                scripts.joinpath("002_request_history.sql").read_text(encoding="utf-8")
            )
            db.execute("PRAGMA user_version = 2")
        elif version != 2:
            raise sqlite3.NotSupportedError(
                f"Unsupported equipment schema version: {version}"
            )
        db.execute("COMMIT")
