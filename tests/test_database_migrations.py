from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

APP_TABLES = {
    "documents",
    "chunks",
    "answer_runs",
    "eval_cases",
    "eval_runs",
    "replay_experiments",
}


def build_alembic_config(database_url: str) -> Config:
    repo_root = Path(__file__).resolve().parents[1]
    config = Config(str(repo_root / "alembic.ini"))
    config.set_main_option("script_location", str(repo_root / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_alembic_upgrade_head_creates_current_schema(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'upgrade.db'}"
    config = build_alembic_config(database_url)

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    document_columns = {column["name"] for column in inspector.get_columns("documents")}
    chunk_columns = {column["name"] for column in inspector.get_columns("chunks")}
    answer_run_columns = {column["name"] for column in inspector.get_columns("answer_runs")}
    engine.dispose()

    assert APP_TABLES.issubset(table_names)
    assert "alembic_version" in table_names
    assert {"source_path", "checksum", "status"}.issubset(document_columns)
    assert {"embedding", "title_path", "sequence"}.issubset(chunk_columns)
    assert {"failure_stage", "prompt_version", "generator_model"}.issubset(answer_run_columns)


def test_alembic_downgrade_base_removes_application_tables(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'downgrade.db'}"
    config = build_alembic_config(database_url)

    command.upgrade(config, "head")
    command.downgrade(config, "base")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    engine.dispose()

    assert APP_TABLES.isdisjoint(table_names)


def test_alembic_check_reports_no_pending_schema_drift(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'drift-check.db'}"
    config = build_alembic_config(database_url)

    command.upgrade(config, "head")
    command.check(config)


def test_alembic_respects_database_url_from_settings_when_ini_uses_default(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    database_url = f"sqlite:///{tmp_path / 'settings-override.db'}"
    config = Config(str(repo_root / "alembic.ini"))
    config.set_main_option("script_location", str(repo_root / "migrations"))

    monkeypatch.setenv("DATABASE_URL", database_url)

    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        command.upgrade(config, "head")
    finally:
        get_settings.cache_clear()

    engine = create_engine(database_url)
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    engine.dispose()

    assert APP_TABLES.issubset(table_names)
