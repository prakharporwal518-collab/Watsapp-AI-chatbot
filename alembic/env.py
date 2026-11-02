"""Alembic environment (async). Usage:  alembic upgrade head"""

import asyncio

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.config import get_settings
from app.db import models  # noqa: F401  (registers models on Base.metadata)
from app.db.base import Base, EncryptedText

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata


def render_item(type_, obj, autogen_context):
    # Encrypted columns are plain TEXT in the database.
    if type_ == "type" and isinstance(obj, EncryptedText):
        return "sa.Text()"
    return False


def _configure(connection=None, url=None):
    context.configure(
        connection=connection,
        url=url,
        target_metadata=target_metadata,
        render_item=render_item,
        render_as_batch=True,  # SQLite-friendly ALTERs
        compare_type=True,
        literal_binds=connection is None,
    )


def run_migrations_offline() -> None:
    _configure(url=config.get_main_option("sqlalchemy.url"))
    with context.begin_transaction():
        context.run_migrations()


def _run_sync(connection) -> None:
    _configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = async_engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.",
                                      poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(_run_sync)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
