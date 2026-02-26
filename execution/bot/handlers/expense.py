"""
Expense flow handler — triggered by /expense command or receipt photo detection.

Three modes:
1. Interactive: Category → Amount → Description → Payment Method → Paid By → Receipt → Save
2. Fast entry:  /expense category;amount;description;paid_by → saves instantly
3. Receipt OCR: Photo auto-detected as receipt → pre-filled → Category → Amount → Description → Payment Method → Paid By → Receipt → Save
"""

import logging
from decimal import Decimal, InvalidOperation

import asyncpg
from telegram import Update
from telegram.ext import ContextTypes

from config import EXPENSE_CATEGORY_MAP, PAYMENT_METHOD_MAP, PAID_BY_MAP
from database.models import BotSession
from utils.state import get_session, set_session, update_context, clear_session
from utils.keyboards import (
    expense_category_keyboard,
    payment_method_keyboard,
    paid_by_keyboard,
    receipt_skip_keyboard,
    cancel_keyboard,
)
from utils.formatters import (
    format_ask_expense_category,
    format_ask_expense_amount,
    format_ask_expense_description,
    format_ask_expense_payment_method,
    format_ask_expense_paid_by,
    format_ask_expense_receipt,
    format_expense_confirmation,
    format_receipt_ocr_summary,
)
from handlers.common import finalize_expense, is_authorized

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Entry point: /expense command
# ---------------------------------------------------------------------------

async def handle_vitrata_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start expense entry flow.

    Supports fast entry: /expense category;amount;description;paid_by
    Example: /expense Laundry;850;Towel washing;Nestor
    """
    if not is_authorized(update):
        logger.warning("Unauthorized /expense from chat_id=%d", update.effective_chat.id)
        return
    pool: asyncpg.Pool = context.bot_data["db_pool"]
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Check for active session
    existing = await get_session(pool, chat_id)
    if existing:
        await update.message.reply_text(
            "⚠️ У вас вже є активна операція. Завершіть її або натисніть /cancel"
        )
        return

    # Check for fast entry: /expense category;amount;description;paid_by
    raw_text = update.message.text or ""
    parts = raw_text.split(maxsplit=1)
    if len(parts) > 1 and ";" in parts[1]:
        await _handle_fast_expense(update, context, parts[1])
        return

    # Interactive flow: initialize session
    await set_session(pool, chat_id, user_id, "expense:awaiting_category", {})

    await update.message.reply_text(
        format_ask_expense_category(),
        reply_markup=expense_category_keyboard(),
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------
# Fast expense entry
# ---------------------------------------------------------------------------

def _match_category(text: str) -> str | None:
    """Match user input to an expense category callback key.

    Case-insensitive partial match against EXPENSE_CATEGORY_MAP values.
    Returns callback key (e.g. 'exp_laundry') or None.
    """
    text_lower = text.lower().strip()
    for cb_key, label in EXPENSE_CATEGORY_MAP.items():
        if label.lower().startswith(text_lower) or text_lower == label.lower():
            return cb_key
    return None


def _match_paid_by(text: str) -> str:
    """Match user input to a paid_by callback key.

    Case-insensitive partial match against PAID_BY_MAP values.
    Returns callback key (e.g. 'paidby_nestor') or empty string.
    """
    text_lower = text.lower().strip()
    for cb_key, label in PAID_BY_MAP.items():
        if label.lower() == text_lower or label.lower().startswith(text_lower):
            return cb_key
    return ""


async def _handle_fast_expense(
    update: Update, context: ContextTypes.DEFAULT_TYPE, args_text: str
) -> None:
    """Parse and save expense from fast entry: category;amount;description;paid_by."""
    pool: asyncpg.Pool = context.bot_data["db_pool"]
    chat_id = update.effective_chat.id

    parts = [p.strip() for p in args_text.split(";")]

    # Must have at least category and amount
    if len(parts) < 2:
        categories = ", ".join(EXPENSE_CATEGORY_MAP.values())
        await update.message.reply_text(
            "⚠️ Невірний формат. Використовуйте:\n"
            "`/expense category;amount;description;paid by`\n\n"
            f"*Категорії:* {categories}",
            parse_mode="Markdown",
        )
        return

    # Parse category
    cat_key = _match_category(parts[0])
    if not cat_key:
        categories = "\n".join(f"• {v}" for v in EXPENSE_CATEGORY_MAP.values())
        await update.message.reply_text(
            f"⚠️ Невідома категорія: *{parts[0]}*\n\n"
            "Використовуйте:\n"
            "`/expense category;amount;description;paid by`\n\n"
            f"*Доступні категорії:*\n{categories}",
            parse_mode="Markdown",
        )
        return

    # Parse amount
    amount_str = parts[1].replace(" ", "").replace("\u00a0", "").replace(",", ".")
    try:
        amount = Decimal(amount_str)
        if amount <= 0:
            raise ValueError()
    except (InvalidOperation, ValueError):
        await update.message.reply_text(
            f"⚠️ Невірна сума: *{parts[1]}*\n"
            "Введіть число, наприклад: 850 або 1200,50",
            parse_mode="Markdown",
        )
        return

    # Parse description (optional third part)
    description = parts[2] if len(parts) > 2 else ""

    # Parse paid_by (optional fourth part)
    paid_by_key = ""
    if len(parts) > 3:
        paid_by_key = _match_paid_by(parts[3])

    # Build context with defaults
    ctx = {
        "category": cat_key,
        "amount": str(amount),
        "description": description,
        "payment_method": "",
        "paid_by": paid_by_key,
        "receipt_url": "",
    }

    # Save directly
    tx_id = await finalize_expense(pool, chat_id, ctx)
    if tx_id:
        confirmation = format_expense_confirmation(ctx)
        await update.message.reply_text(confirmation, parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Помилка збереження. Спробуйте ще раз.")


# ---------------------------------------------------------------------------
# Entry point: receipt photo detected by OCR classifier
# ---------------------------------------------------------------------------

async def handle_receipt_expense(
    update: Update, context: ContextTypes.DEFAULT_TYPE, parsed_receipt: dict
) -> None:
    """Start expense flow from a receipt photo auto-detected by OCR.

    Called by handle_photo_router() when detect_ocr_type() returns 'expense'.
    Pre-fills vendor, amount, and date from the receipt OCR, then asks for
    category selection to continue the normal expense flow.
    """
    pool: asyncpg.Pool = context.bot_data["db_pool"]
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Pre-fill context with receipt OCR data
    ctx = {
        "vendor": parsed_receipt.get("vendor", ""),
        "amount": str(parsed_receipt["amount"]) if parsed_receipt.get("amount") else "",
        "date": parsed_receipt.get("date", ""),
        "description": "",
        "receipt_url": "",
        "paid_by": "",
        "source": "receipt_ocr",
    }

    await set_session(pool, chat_id, user_id, "expense:awaiting_category", ctx)

    # Show receipt summary + category keyboard
    await update.message.reply_text(
        format_receipt_ocr_summary(parsed_receipt),
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
        if data not in EXPENSE_CATEGORY_MAP:
            await query.answer("Невідома категорія")
            return
        ctx["category"] = data
        # If amount is pre-filled (receipt OCR), skip to description
        if ctx.get("amount"):
            await update_context(pool, chat_id, "expense:awaiting_description", ctx)
            await query.edit_message_text(
                format_ask_expense_description(),
                parse_mode="Markdown",
            )
        else:
            await update_context(pool, chat_id, "expense:awaiting_amount", ctx)
            await query.edit_message_text(
                format_ask_expense_amount(),
                parse_mode="Markdown",
            )

    # --- Payment Method ---
    elif state == "expense:awaiting_payment_method":
        if data not in PAYMENT_METHOD_MAP:
            await query.answer("Невідомий спосіб оплати")
            return
        ctx["payment_method"] = data
        await update_context(pool, chat_id, "expense:awaiting_paid_by", ctx)
        await query.edit_message_text(
            format_ask_expense_paid_by(),
            reply_markup=paid_by_keyboard(),
            parse_mode="Markdown",
        )

    # --- Paid By ---
    elif state == "expense:awaiting_paid_by":
        if data not in PAID_BY_MAP:
            await query.answer("Невідомий платник")
            return
        ctx["paid_by"] = data
        await update_context(pool, chat_id, "expense:awaiting_receipt", ctx)
        await query.edit_message_text(
            format_ask_expense_receipt(),
            reply_markup=receipt_skip_keyboard(),
            parse_mode="Markdown",
        )

    # --- Receipt skip ---
    elif state == "expense:awaiting_receipt":
        if data == "receipt_skip":
            # Finalize
            tx_id = await finalize_expense(pool, chat_id, ctx)
            if tx_id:
                confirmation = format_expense_confirmation(ctx)
                await query.edit_message_text(confirmation, parse_mode="Markdown")
            else:
                await query.edit_message_text("❌ Помилка збереження. Спробуйте ще раз.")
            await clear_session(pool, chat_id)


# ---------------------------------------------------------------------------
# Text handler: amount, description, receipt URL
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
        await update_context(pool, chat_id, "expense:awaiting_description", ctx)
        await update.message.reply_text(
            format_ask_expense_description(),
            parse_mode="Markdown",
        )

    elif state == "expense:awaiting_description":
        ctx["description"] = text
        await update_context(pool, chat_id, "expense:awaiting_payment_method", ctx)
        await update.message.reply_text(
            format_ask_expense_payment_method(),
            reply_markup=payment_method_keyboard(),
            parse_mode="Markdown",
        )

    elif state == "expense:awaiting_receipt":
        # Accept a Drive link as the receipt URL
        if text.startswith("http"):
            ctx["receipt_url"] = text
            # Finalize
            tx_id = await finalize_expense(pool, chat_id, ctx)
            if tx_id:
                confirmation = format_expense_confirmation(ctx)
                await update.message.reply_text(
                    f"📎 Посилання збережено!\n\n{confirmation}",
                    parse_mode="Markdown",
                )
            else:
                await update.message.reply_text("❌ Помилка збереження. Спробуйте ще раз.")
            await clear_session(pool, chat_id)
        else:
            await update.message.reply_text(
                "⚠️ Надішліть посилання (починається з http) або натисніть Пропустити.",
                reply_markup=receipt_skip_keyboard(),
            )


# ---------------------------------------------------------------------------
# Receipt photo handler
# ---------------------------------------------------------------------------

async def handle_expense_receipt_photo(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle photo sent during receipt step — hint to upload to Drive manually."""
    pool: asyncpg.Pool = context.bot_data["db_pool"]
    chat_id = update.effective_chat.id

    session = await get_session(pool, chat_id)
    if not session or session.state != "expense:awaiting_receipt":
        return

    await update.message.reply_text(
        "⚠️ Пряме завантаження фото тимчасово недоступне.\n"
        "Завантажте чек на Google Drive та надішліть посилання, або натисніть Пропустити.",
        reply_markup=receipt_skip_keyboard(),
    )
