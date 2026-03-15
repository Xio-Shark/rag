from __future__ import annotations

from configparser import ConfigParser
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

import app.db.models  # noqa: F401
from app.core.config import get_settings
from app.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_default_configured_url() -> str:
    if not config.config_file_name:
        return ""

    parser = ConfigParser()
    parser.read(config.config_file_name, encoding="utf-8")
    if parser.has_option(config.config_ini_section, "sqlalchemy.url"):
        return parser.get(config.config_ini_section, "sqlalchemy.url")
    return ""


def get_database_url() -> str:
    settings_url = get_settings().database_url
    configured_url = config.get_main_option("sqlalchemy.url")
    default_configured_url = get_default_configured_url()
    if configured_url and configured_url != default_configured_url:
        return configured_url
    return settings_url or configured_url


def run_migrations_offline() -> None:
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = get_database_url()

    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
