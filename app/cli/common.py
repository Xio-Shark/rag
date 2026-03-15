from __future__ import annotations

from contextlib import contextmanager

from app.db.session import get_session_factory, init_database


@contextmanager
def managed_session():
    init_database()
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
