"""
State machine helpers for bot_sessions table.

Replaces Make.com's implicit state (scenario execution position) with
explicit PostgreSQL state that survives restarts and handles concurrent users.
"""

import json
import logging
from typing import Optional

import asyncpg

from database.models import BotSession

logger = logging.getLogger(__name__)


async def get_session(pool: asyncpg.Pool, chat_id: int) -> Optional[BotSession]:
    """Fetch the current bot session for a chat, or None if idle."""
    async with pool.acquire() as conn:
        record = await conn.fetchrow(
            "SELECT chat_id, user_id, state, context, updated_at "
            "FROM bot_sessions WHERE chat_id = $1",
            chat_id,
        )
    if record is None:
        return None
    return BotSession.from_record(record)


async def set_session(
    pool: asyncpg.Pool,
    chat_id: int,
    user_id: int,
    state: str,
    context: dict,
) -> None:
    """Create or replace the session for a chat (UPSERT)."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO bot_sessions (chat_id, user_id, state, context, updated_at)
            VALUES ($1, $2, $3, $4::jsonb, NOW())
            ON CONFLICT (chat_id) DO UPDATE
            SET user_id = $2, state = $3, context = $4::jsonb, updated_at = NOW()
            """,
            chat_id,
            user_id,
            state,
            json.dumps(context, ensure_ascii=False),
        )
    logger.debug("Session set: chat_id=%d state=%s", chat_id, state)


async def update_state(pool: asyncpg.Pool, chat_id: int, state: str) -> None:
    """Update only the state field (context unchanged)."""
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE bot_sessions SET state = $1, updated_at = NOW() WHERE chat_id = $2",
            state,
            chat_id,
        )
    logger.debug("State updated: chat_id=%d → %s", chat_id, state)


async def update_context(pool: asyncpg.Pool, chat_id: int, state: str, context: dict) -> None:
    """Update both state and context."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE bot_sessions
            SET state = $1, context = $2::jsonb, updated_at = NOW()
            WHERE chat_id = $3
            """,
            state,
            json.dumps(context, ensure_ascii=False),
            chat_id,
        )
    logger.debug("Context updated: chat_id=%d state=%s", chat_id, state)


async def clear_session(pool: asyncpg.Pool, chat_id: int) -> None:
    """Delete session — return to idle."""
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM bot_sessions WHERE chat_id = $1", chat_id)
    logger.debug("Session cleared: chat_id=%d", chat_id)
