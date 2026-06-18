"""Engine + session factory. SQLite in WAL mode for concurrent read (Node, later)."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _record) -> None:  # type: ignore[no-untyped-def]
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


@lru_cache
def get_engine(path: str | None = None) -> Engine:
    db_path = path or get_settings().sqlite_path
    if db_path != ":memory:":
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    url = "sqlite:///:memory:" if db_path == ":memory:" else f"sqlite:///{db_path}"
    return create_engine(url, future=True)


def get_sessionmaker(path: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(path), expire_on_commit=False, future=True)


@contextmanager
def session_scope(path: str | None = None) -> Iterator[Session]:
    sess = get_sessionmaker(path)()
    try:
        yield sess
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        sess.close()
