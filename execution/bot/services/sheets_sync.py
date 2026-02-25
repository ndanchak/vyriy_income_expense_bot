"""
Background retry job for failed Google Sheets writes.

Runs every hour via APScheduler. Queries all transactions with
sheets_synced=FALSE and attempts to write them to Sheets.
PostgreSQL is source of truth — Sheets write is best-effort.
"""

import asyncio
import json
import logging
from datetime import datetime

import asyncpg
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import (
    PROPERTY_MAP,
    PAYMENT_TYPE_MAP,
    PLATFORM_MAP,
    ACCOUNT_TYPE_MAP,
    EXPENSE_CATEGORY_MAP,
    EXPENSE_PROPERTY_MAP,
    PAYMENT_METHOD_MAP,
    PAID_BY_MAP,
)
from services.sheets import append_income_row, append_expense_row

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


SESSION_TIMEOUT_HOURS = 2


async def cleanup_stale_sessions(pool: asyncpg.Pool) -> None:
    """Delete bot sessions older than SESSION_TIMEOUT_HOURS.

    Prevents users from being permanently stuck if they abandon a flow.
    """
    async with pool.acquire() as conn:
        deleted = await conn.execute(
            "DELETE FROM bot_sessions WHERE updated_at < NOW() - make_interval(hours => $1)",
            SESSION_TIMEOUT_HOURS,
        )
    # asyncpg returns "DELETE N" string
    if deleted and deleted != "DELETE 0":
        logger.info("Cleaned up stale sessions: %s", deleted)


async def retry_failed_writes(pool: asyncpg.Pool) -> None:
    """Find all unsynced transactions and retry Sheets write."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM transactions WHERE sheets_synced = FALSE ORDER BY created_at"
        )

    if not rows:
        return

    logger.info("Retrying %d unsynced transactions", len(rows))

    for row in rows:
        tx_type = row["type"]
        success = False

        try:
            if tx_type == "income":
                data = _build_income_sheets_data(row)
                success = await asyncio.to_thread(append_income_row, data)
            elif tx_type == "expense":
                data = _build_expense_sheets_data(row)
                success = await asyncio.to_thread(append_expense_row, data)
        except Exception as e:
            logger.error("Retry failed for tx %s: %s", row["id"], e)

        if success:
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE transactions SET sheets_synced = TRUE WHERE id = $1",
                    row["id"],
                )
            logger.info("Synced transaction %s to Sheets", row["id"])


def _build_income_sheets_data(row) -> dict:
    """Build Sheets row data from a transactions DB row (income)."""
    from utils.parsers import convert_date_for_sheets, get_month_label

    date_str = row["date"].strftime("%d.%m.%Y") if row["date"] else ""
    return {
        "date": convert_date_for_sheets(date_str),
        "amount": float(row["amount"]) if row["amount"] else "",
        "property": PROPERTY_MAP.get(row["property_id"], row["property_id"] or ""),
        "platform": row["platform"] or "",
        "guest_name": row["counterparty"] or "",
        "checkin": row["checkin_date"].strftime("%d.%m.%Y") if row["checkin_date"] else "",
        "checkout": row["checkout_date"].strftime("%d.%m.%Y") if row["checkout_date"] else "",
        "payment_type": row["payment_type"] or "",
        "account_type": row["account_type"] or "",
        "notes": row["notes"] or "",
        "month": get_month_label(date_str),
    }


def _build_expense_sheets_data(row) -> dict:
    """Build Sheets row data from a transactions DB row (expense).

    New 10-column layout: Date | Category | Amount | Description |
    Payment Method | Paid By | Receipt Link | Vendor | Property | Notes
    """
    from utils.parsers import convert_date_for_sheets

    date_str = row["date"].strftime("%d.%m.%Y") if row["date"] else ""
    return {
        "date": convert_date_for_sheets(date_str),
        "category": row["category"] or "",
        "amount": float(row["amount"]) if row["amount"] else "",
        "description": row.get("description") or "",
        "payment_method": row["account_type"] or "",
        "paid_by": row.get("paid_by") or "",
        "receipt_url": row["receipt_url"] or "",
        "vendor": row["counterparty"] or "",
        "property": PROPERTY_MAP.get(row["property_id"], EXPENSE_PROPERTY_MAP.get(row["property_id"], row["property_id"] or "")),
        "notes": row["notes"] or "",
    }


def setup_sync_scheduler(pool: asyncpg.Pool) -> None:
    """Start APScheduler with hourly retry job and stale session cleanup."""
    global _scheduler
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        retry_failed_writes,
        "interval",
        hours=1,
        args=[pool],
        id="sheets_sync_retry",
        replace_existing=True,
    )
    _scheduler.add_job(
        cleanup_stale_sessions,
        "interval",
        hours=1,
        args=[pool],
        id="stale_session_cleanup",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Scheduler started (hourly Sheets sync + session cleanup)")
