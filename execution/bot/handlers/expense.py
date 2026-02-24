"""
Expense flow handler — triggered by /витрата command.

Category → Property → Amount → Vendor → Payment Method → Receipt → Notes → Save.
"""

import asyncio
import logging
from decimal import Decimal, InvalidOperation

import asyncpg
from telegram import Update
from telegram.ext import ContextTypes

from database.models import BotSession
from utils.state import get_session, set_session, update_context, clear_session
from utils.keyboards import (
    expense_category_keyboard,
    expense_property_keyboard,
    payment_method_keyboard,
    receipt_skip_keyboard,
    notes_skip_keyboard,
    cancel_keyboard,
)
from utils.formatters import (
    format_ask_expense_category,
    format_ask_expense_property,
    format_ask_expense_amount,
    format_ask_expense_vendor,
    format_ask_expense_payment_method,
    format_ask_expense_receipt,
    format_ask_expense_notes,
    format_expense_confirmation,
    format_receipt_uploaded,
)
from handlers.common import finalize_expense

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Entry point: /витрата command
# ---------------------------------------------------------------------------

async def handle_vitrata_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start expense entry flow."""
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
    await set_session(pool, chat_id, user_id, "expense:awaiting_category", {})

    await update.message.reply_text(
        format_ask_expense_category(),
        reply_markup=expense_category_keyboard(),
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------
# Callback handler: expense state machine
# ---------------------------------------------------------------------------

async def handle_expense_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: BotSession,
) -> None:
    """Handle callback_query presses during expense flow."""
    query = update.callback_query
    await query.answer()

    pool: asyncpg.Pool = context.bot_data["db_pool"]
    chat_id = update.effective_chat.id
    state = session.state
    data = query.data
    ctx = dict(session.context)

    # --- Category ---
    if state == "expense:awaiting_category":
        ctx["category"] = data
        await update_context(pool, chat_id, "expense:awaiting_property", ctx)
        await query.edit_message_text(
            format_ask_expense_property(),
            reply_markup=expense_property_keyboard(),
            parse_mode="Markdown",
        )

    # --- Property ---
    elif state == "expense:awaiting_property":
        ctx["property"] = data
        await update_context(pool, chat_id, "expense:awaiting_amount", ctx)
        await query.edit_message_text(
            format_ask_expense_amount(),
            parse_mode="Markdown",
        )

    # --- Payment Method ---
    elif state == "expense:awaiting_payment_method":
        ctx["payment_method"] = data
        await update_context(pool, chat_id, "expense:awaiting_receipt", ctx)
        await query.edit_message_text(
            format_ask_expense_receipt(),
            reply_markup=receipt_skip_keyboard(),
            parse_mode="Markdown",
        )

    # --- Receipt skip ---
    elif state == "expense:awaiting_receipt":
        if data == "receipt_skip":
            await update_context(pool, chat_id, "expense:awaiting_notes", ctx)
            await query.edit_message_text(
                format_ask_expense_notes(),
                reply_markup=notes_skip_keyboard(),
                parse_mode="Markdown",
            )

    # --- Notes skip ---
    elif state == "expense:awaiting_notes":
        if data == "notes_skip":
            # Finalize
            tx_id = await finalize_expense(pool, chat_id, ctx)
            if tx_id:
                confirmation = format_expense_confirmation(ctx)
                await query.edit_message_text(confirmation, parse_mode="Markdown")
            else:
                await query.edit_message_text("❌ Помилка збереження. Спробуйте ще раз.")
            await clear_session(pool, chat_id)


# ---------------------------------------------------------------------------
# Text handler: amount, vendor, notes
# ---------------------------------------------------------------------------

async def handle_expense_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: BotSession,
) -> None:
    """Handle text input during expense flow."""
    pool: asyncpg.Pool = context.bot_data["db_pool"]
    chat_id = update.effective_chat.id
    state = session.state
    text = update.message.text.strip()
    ctx = dict(session.context)

    if state == "expense:awaiting_amount":
        # Parse amount
        cleaned = text.replace(" ", "").replace("\u00a0", "").replace(",", ".")
        try:
            amount = Decimal(cleaned)
            if amount <= 0:
                raise ValueError("Amount must be positive")
        except (InvalidOperation, ValueError):
            await update.message.reply_text(
                "⚠️ Невірний формат суми. Введіть число, наприклад: 850 або 1 200,50"
            )
            return

        ctx["amount"] = str(amount)
        await update_context(pool, chat_id, "expense:awaiting_vendor", ctx)
        await update.message.reply_text(
            format_ask_expense_vendor(),
            reply_markup=notes_skip_keyboard(),  # reuse skip button
            parse_mode="Markdown",
        )

    elif state == "expense:awaiting_vendor":
        ctx["vendor"] = text
        await update_context(pool, chat_id, "expense:awaiting_payment_method", ctx)
        await update.message.reply_text(
            format_ask_expense_payment_method(),
            reply_markup=payment_method_keyboard(),
            parse_mode="Markdown",
        )

    elif state == "expense:awaiting_notes":
        ctx["notes"] = text
        # Finalize
        tx_id = await finalize_expense(pool, chat_id, ctx)
        if tx_id:
            confirmation = format_expense_confirmation(ctx)
            await update.message.reply_text(confirmation, parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Помилка збереження. Спробуйте ще раз.")
        await clear_session(pool, chat_id)


# ---------------------------------------------------------------------------
# Receipt photo handler
# ---------------------------------------------------------------------------

async def handle_expense_receipt_photo(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle receipt photo upload during expense flow.

    Downloads the photo, uploads to Google Drive, stores the link.
    """
    pool: asyncpg.Pool = context.bot_data["db_pool"]
    chat_id = update.effective_chat.id

    session = await get_session(pool, chat_id)
    if not session or session.state != "expense:awaiting_receipt":
        return

    ctx = dict(session.context)

    # Download photo
    photo = update.message.photo[-1]  # highest resolution
    file = await photo.get_file()
    image_bytes = await file.download_as_bytearray()

    # Upload to Google Drive
    from services.drive import upload_receipt

    await update.message.reply_text("⏳ Завантажую чек...")

    receipt_url = await asyncio.to_thread(upload_receipt, bytes(image_bytes))

    if receipt_url:
        ctx["receipt_url"] = receipt_url
        await update_context(pool, chat_id, "expense:awaiting_notes", ctx)
        await update.message.reply_text(
            f"{format_receipt_uploaded()}\n\n{format_ask_expense_notes()}",
            reply_markup=notes_skip_keyboard(),
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            "⚠️ Не вдалося завантажити чек. Спробуйте ще раз або натисніть Пропустити.",
            reply_markup=receipt_skip_keyboard(),
        )
