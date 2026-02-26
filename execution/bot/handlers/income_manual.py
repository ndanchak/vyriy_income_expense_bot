"""
Manual income entry flow — triggered by /дохід command.

User enters amount and guest name via text, then follows the same
Property → Payment/Duration → Platform → Dates flow as OCR.
Account Type step removed — always defaults to "Account" for non-SUP.
"""

import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

import asyncpg
from telegram import Update
from telegram.ext import ContextTypes

from database.models import BotSession
from utils.state import get_session, set_session, update_context, clear_session
from utils.parsers import parse_dates_input
from utils.keyboards import property_keyboard, cancel_keyboard, duplicate_confirm_keyboard
from utils.formatters import (
    format_manual_income_start,
    format_ask_guest_name,
    format_ask_property,
    format_income_confirmation,
    format_duplicate_warning,
)
from handlers.common import finalize_income, check_duplicate_income, is_authorized

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Entry point: /дохід command
# ---------------------------------------------------------------------------

async def handle_dohid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start manual income entry flow."""
    if not is_authorized(update):
        logger.warning("Unauthorized /income from chat_id=%d", update.effective_chat.id)
        return
    pool: asyncpg.Pool = context.bot_data["db_pool"]
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Check for active session
    existing = await get_session(pool, chat_id)
    if existing:
        await update.message.reply_text(
            "⚠️ У вас вже є активна операція. Завершіть її або натисніть /скасувати"
        )
        return

    # Initialize session
    session_ctx = {
        "source": "manual",
        "date": datetime.now().strftime("%d.%m.%Y"),
    }
    await set_session(pool, chat_id, user_id, "income_manual:awaiting_amount", session_ctx)

    await update.message.reply_text(
        format_manual_income_start(),
        reply_markup=cancel_keyboard(),
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------
# Text handler: amount, guest name, dates
# ---------------------------------------------------------------------------

async def handle_manual_income_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: BotSession,
) -> None:
    """Handle text input during manual income flow."""
    pool: asyncpg.Pool = context.bot_data["db_pool"]
    chat_id = update.effective_chat.id
    state = session.state
    text = update.message.text.strip()
    ctx = dict(session.context)

    if state == "income_manual:awaiting_amount":
        # Parse amount
        cleaned = text.replace(" ", "").replace("\u00a0", "").replace(",", ".").replace("−", "-")
        try:
            amount = Decimal(cleaned)
            if amount == 0:
                raise ValueError("Amount cannot be zero")
        except (InvalidOperation, ValueError):
            await update.message.reply_text(
                "⚠️ Невірний формат суми. Введіть число, наприклад: 2400, 1 500,50 або -2400 (повернення)"
            )
            return

        ctx["amount"] = str(amount)
        ctx["ocr_amount"] = str(amount)  # for compatibility with finalize
        await update_context(pool, chat_id, "income_manual:awaiting_guest_name", ctx)
        await update.message.reply_text(
            format_ask_guest_name(),
            reply_markup=cancel_keyboard(),
            parse_mode="Markdown",
        )

    elif state == "income_manual:awaiting_guest_name":
        ctx["guest_name"] = text
        ctx["ocr_sender"] = text  # for compatibility with finalize
        await update_context(pool, chat_id, "income_manual:awaiting_property", ctx)
        await update.message.reply_text(
            format_ask_property(),
            reply_markup=property_keyboard(),
            parse_mode="Markdown",
        )

    elif state == "income_manual:awaiting_dates":
        # Parse dates (same as OCR flow)
        checkin, checkout = parse_dates_input(text)
        ctx["checkin"] = checkin
        ctx["checkout"] = checkout

        # Duplicate check before finalizing
        amount_raw = ctx.get("amount") or ctx.get("ocr_amount")
        try:
            amount = Decimal(
                str(amount_raw).replace(" ", "").replace(",", ".").replace("\u2212", "-")
            )
        except Exception:
            amount = Decimal("0")

        date_str = ctx.get("date") or ctx.get("ocr_date", "")
        try:
            tx_date = datetime.strptime(date_str.replace("/", "."), "%d.%m.%Y").date()
        except ValueError:
            tx_date = datetime.now().date()

        guest_name = ctx.get("guest_name") or ctx.get("ocr_sender", "")

        is_dup = await check_duplicate_income(pool, tx_date, amount, guest_name)
        if is_dup:
            await update_context(pool, chat_id, "income_manual:awaiting_dup_confirm", ctx)
            await update.message.reply_text(
                format_duplicate_warning(ctx),
                reply_markup=duplicate_confirm_keyboard(),
                parse_mode="Markdown",
            )
            return

        # Finalize
        tx_id = await finalize_income(pool, chat_id, ctx)

        if tx_id:
            confirmation = format_income_confirmation(ctx)
            await update.message.reply_text(confirmation, parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Помилка збереження. Спробуйте ще раз.")

        await clear_session(pool, chat_id)
