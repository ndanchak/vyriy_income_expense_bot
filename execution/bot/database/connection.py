"""
Async PostgreSQL connection pool using asyncpg.

Usage:
    pool = await init_pool(DATABASE_URL)
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT 1")
    await close_pool()
"""

from pathlib import Path

import asyncpg
import logging

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def init_pool(dsn: str, min_size: int = 2, max_size: int = 10) -> asyncpg.Pool:
    """Create and return the global asyncpg connection pool."""
    global _pool
    _pool = await asyncpg.create_pool(dsn, min_size=min_size, max_size=max_size)
    logger.info("Database pool initialized (min=%d, max=%d)", min_size, max_size)
    return _pool


def get_pool() -> asyncpg.Pool:
    """Return the initialized pool. Raises if init_pool() hasn't been called."""
    if _pool is None:
        raise RuntimeError("Database pool not initialized — call init_pool() first")
    return _pool


async def close_pool() -> None:
    """Gracefully close the connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Database pool closed")


async def run_migration(pool: asyncpg.Pool, migration_path: str) -> None:
    """Execute SQL migration files incrementally.

    Runs 001_initial.sql if tables don't exist,
    then 002_expense_refactor.sql if description column is missing, etc.
    """
    async with pool.acquire() as conn:
        # --- 001: Initial schema ---
        exists = await conn.fetchval(
            "SELECT EXISTS(SELECT FROM information_schema.tables WHERE table_name = 'transactions')"
        )
        if not exists:
            with open(migration_path, "r") as f:
                sql = f.read()
            await conn.execute(sql)
            logger.info("Migration applied: %s", migration_path)
        else:
            logger.info("Tables already exist, skipping 001_initial")

        # --- 002: Expense refactor (description + paid_by columns) ---
        has_description = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'transactions' AND column_name = 'description')"
        )
        if not has_description:
            migration_002 = Path(migration_path).parent / "002_expense_refactor.sql"
            if migration_002.exists():
                with open(migration_002, "r") as f:
                    sql = f.read()
                await conn.execute(sql)
                logger.info("Migration applied: %s", migration_002)
            else:
                logger.warning("Migration file not found: %s", migration_002)
