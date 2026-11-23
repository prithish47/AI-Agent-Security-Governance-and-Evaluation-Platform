# =============================================================================
# Alembic Environment Configuration
# =============================================================================
# This file tells Alembic how to connect to the database and which models
# to use for auto-generating migrations.
#
# KEY CONCEPTS:
# - target_metadata: Points to our SQLAlchemy Base.metadata so Alembic
#   can compare the current database state with our model definitions
# - run_migrations_online: Uses our async engine for database operations
# =============================================================================

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import our application's database configuration
from app.core.config import settings
from app.core.database import Base

# Import all models so they're registered with Base.metadata
# This import is crucial — without it, Alembic won't see any tables
from app.persistence import models  # noqa: F401

# Alembic Config object — provides access to alembic.ini values
config = context.config

# Override the sqlalchemy.url from alembic.ini with our application config
# This ensures we always use the same database URL as the application
config.set_main_option("sqlalchemy.url", settings.database_url)

# Set up Python logging from the alembic.ini [loggers] section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# This is what Alembic compares against the database to detect changes
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    
    This generates SQL scripts without connecting to the database.
    Useful for reviewing migrations before applying them.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    """Execute migrations using the provided connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    """
    Run migrations using an async engine.
    
    We need this because our application uses asyncpg (async PostgreSQL driver).
    Alembic doesn't natively support async, so we bridge it here.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode — connected to the database.
    
    This is the normal path: connect to the database, compare current
    state with model definitions, and apply any pending migrations.
    """
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
