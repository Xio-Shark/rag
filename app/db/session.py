from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.db.types import get_embedding_storage_backend


@dataclass(frozen=True)
class DatabaseCompatibilityStatus:
    database_backend: str
    embedding_storage: str


def _create_engine() -> Engine:
    settings = get_settings()
    connect_args = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    return create_engine(settings.database_url, future=True, connect_args=connect_args)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return _create_engine()


@lru_cache(maxsize=1)
def get_session_factory():
    return sessionmaker(
        bind=get_engine(), autoflush=False, autocommit=False, expire_on_commit=False
    )


def get_database_compatibility_status(engine: Engine | None = None) -> DatabaseCompatibilityStatus:
    active_engine = engine or get_engine()
    database_backend = active_engine.dialect.name
    return DatabaseCompatibilityStatus(
        database_backend=database_backend,
        embedding_storage=get_embedding_storage_backend(database_backend),
    )


def get_db_session() -> Session:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def init_database() -> None:
    engine = get_engine()
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    # 兼容现有本地开发与测试启动链路；正式 schema 演进以 Alembic 迁移为准。
    Base.metadata.create_all(bind=engine)


def ping_database() -> bool:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
