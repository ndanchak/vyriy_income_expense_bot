"""
Shared handler logic used by all flows.

- Cancel handler (/скасувати)
- Photo router (OCR + classify: Monobank → income, other → expense)
- Callback router (dispatches by session state prefix)
- Text router (dispatches text input by session state)
- Finalize functions (write to DB + Sheets)
"""

import asyncio
import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Union

import asyncpg
from telegram import Update
from telegram.ext import ContextTypes

from config import (
    GOOGLE_VISION_API_KEY,
    ALLOWED_CHAT_IDS,
    PROPERTY_MAP,
    PAYMENT_TYPE_MAP,
    PLATFORM_MAP,
    SUP_DURATION_MAP,
    ACCOUNT_TYPE_MAP,
    EXPENSE_CATEGORY_MAP,
    EXPENSE_SUBCATEGORY_MAP,
    EXPENSE_PROPERTY_MAP,
    PAYMENT_METHOD_MAP,
    PAID_BY_MAP,
)
from utils.state import get_session, set_session, clear_session
from utils.formatters import format_cancel_message, format_negative_payment_summary
from utils.keyboards import expense_or_return_keyboard
from utils.parsers import (
    convert_date_for_sheets, get_month_label, detect_ocr_type,
    parse_receipt_ocr, parse_monobank_ocr,
)
from services.ocr import extract_text_from_image
from services.sheets import append_income_row, append_expense_row

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------

def is_authorized(update: Update) -> bool:
    """Check if the chat is in the allowed list.

    Returns True if ALLOWED_CHAT_IDS is empty (no restriction configured)
    or if the chat is explicitly allowed.
    """
    if not ALLOWED_CHAT_IDS:
        return True  # no restriction configured — allow all (dev mode)
    return update.effective_chat.id in ALLOWED_CHAT_IDS


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

async def check_duplicate_income(
    pool: asyncpg.Pool,
    tx_date: Union[datetime, "datetime.date"],
    amount: Decimal,
    guest_name: str,
) -> bool:
    """Check if an income transaction with same date, amount, and guest name exists.

    Returns True if a potential duplicate is found.
    """
    if not guest_name:
        return False  # can't check without guest name
    async with pool.acquire() as conn:
        exists = await conn.fetchval(
            """
            SELECT EXISTS(
                SELECT 1 FROM transactions
                WHERE type = 'income'
                  AND date = $1
                  AND amount = $2
                  AND counterparty = $3
            )
            """,
            tx_date, amount, guest_name,
        )
    return exists


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------

async def handle_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /скасувати command — clear session, return to idle."""
    if not is_authorized(update):
        logger.warning("Unauthorized cancel attempt from chat_id=%d", update.effective_chat.id)
        return
    pool: asyncpg.Pool = context.bot_data["db_pool"]
    chat_id = update.effective_chat.id
    await clear_session(pool, chat_id)
    await update.message.reply_text(format_cancel_message())


async def handle_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle cancel button press."""
    query = update.callback_query
    await query.answer()
    pool: asyncpg.Pool = context.bot_data["db_pool"]
    chat_id = update.effective_chat.id
    await clear_session(pool, chat_id)
    await query.edit_message_text(format_cancel_message())


# ---------------------------------------------------------------------------
# Photo router
# ---------------------------------------------------------------------------

async def handle_photo_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route incoming photos: OCR → classify → income or expense flow.

    1. If session state is expense:awaiting_receipt → hint to upload to Drive
    2. If any other active session exists → error message
    3. Download photo + OCR
    4. Classify: Monobank → income, anything else → expense
    """
    if not is_authorized(update):
        logger.warning("Unauthorized photo from chat_id=%d", update.effective_chat.id)
        return
    pool: asyncpg.Pool = context.bot_data["db_pool"]
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    session = await get_session(pool, chat_id)

    # If we're in expense receipt step, show the Drive upload hint
    if session and session.state == "expense:awaiting_receipt":
        from handlers.expense import handle_expense_receipt_photo
        await handle_expense_receipt_photo(update, context)
        return

    # If any other session is active, warn the user
    if session:
        await update.message.reply_text(
            "⚠️ У вас вже є активна операція. Завершіть її або натисніть /cancel"
        )
        return

    # Download photo (highest resolution)
    photo = update.message.photo[-1]
    file = await photo.get_file()
    image_bytes = await file.download_as_bytearray()

    # Run OCR
    ocr_text = await extract_text_from_image(bytes(image_bytes), GOOGLE_VISION_API_KEY)

    if not ocr_text:
        await update.message.reply_text(
            "⚠️ Не вдалося розпізнати текст на зображенні. "
            "Спробуйте ще раз або введіть дані вручну."
        )
        return

    logger.info("OCR completed: %d characters extracted", len(ocr_text))
    logger.debug("OCR raw text:\n%s", ocr_text)

    # Classify: Monobank payment or expense receipt
    ocr_type = detect_ocr_type(ocr_text)
    logger.info("OCR type detected: %s", ocr_type)

    if ocr_type == "monobank":
        # Parse Monobank OCR to check if amount is negative (outgoing payment)
        parsed = parse_monobank_ocr(ocr_text)
        amount = parsed.get("amount")

        if amount is not None and amount < 0:
            # Negative amount → could be expense OR return to guest.
            # Ask the user to disambiguate.
            logger.info("Negative Monobank payment detected (%s), showing disambiguation", amount)
            session_ctx = {
                "ocr_sender": parsed["sender_name"],
                "ocr_amount": str(parsed["amount"]),
                "ocr_date": parsed["date"],
                "ocr_purpose": parsed["purpose"],
                "ocr_text": ocr_text,
                "source": "ocr",
            }
            await set_session(pool, chat_id, user_id, "disambig:awaiting_type", session_ctx)
            await update.message.reply_text(
                format_negative_payment_summary(parsed),
                reply_markup=expense_or_return_keyboard(),
                parse_mode="Markdown",
            )
        else:
            # Positive or zero amount → income flow
            from handlers.income import handle_photo_with_ocr
            await handle_photo_with_ocr(update, context, ocr_text)
    else:
        # Default: treat as expense receipt
        parsed = parse_receipt_ocr(ocr_text)
        from handlers.expense import handle_receipt_expense
        await handle_receipt_expense(update, context, parsed)


# ---------------------------------------------------------------------------
# Callback router
# ---------------------------------------------------------------------------

async def handle_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route callback queries by session state prefix.

    Reads bot_sessions to determine which flow the user is in,
    then delegates to the appropriate handler.
    """
    if not is_authorized(update):
        logger.warning("Unauthorized callback from chat_id=%d", update.effective_chat.id)
        await update.callback_query.answer()
        return
    query = update.callback_query
    data = query.data

    # Handle cancel from any state
    if data == "cancel":
        await handle_cancel_callback(update, context)
        return

    pool: asyncpg.Pool = context.bot_data["db_pool"]
    chat_id = update.effective_chat.id

    session = await get_session(pool, chat_id)
    if not session:
        await query.answer("Немає активної сесії. Надішліть скріншот або введіть команду.")
        return

    # NOTE: No per-user session lock — any authorized team member in the
    # group chat can continue another member's session (e.g. Ihor sends
    # screenshot, Ira finishes entering data).  Authorization at the
    # chat level (is_authorized) is the security boundary.

    state = session.state or ""

    # Guard: if already finalizing, ignore duplicate clicks
    if state.endswith(":finalizing"):
        await query.answer("⏳ Зберігаємо…")
        return

    if state.startswith("disambig:"):
        await handle_disambig_callback(update, context, session)
    elif state.startswith("income:") or state.startswith("income_manual:"):
        from handlers.income import handle_income_callback
        await handle_income_callback(update, context, session)
    elif state.startswith("expense:"):
        from handlers.expense import handle_expense_callback
        await handle_expense_callback(update, context, session)
    else:
        await query.answer("Невідомий стан. Спробуйте ще раз.")


# ---------------------------------------------------------------------------
# Disambiguation: negative payment → expense or return
# ---------------------------------------------------------------------------

async def handle_disambig_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session
) -> None:
    """Handle the expense-vs-return disambiguation choice.

    When a Monobank screenshot has a negative amount, the user taps:
    - 'flow_expense' → start expense flow (amount becomes positive, pre-filled)
    - 'flow_return' → start income flow (keeps negative amount = return)
    """
    query = update.callback_query
    await query.answer()

    pool: asyncpg.Pool = context.bot_data["db_pool"]
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    ctx = dict(session.context)
    data = query.data

    if data == "flow_expense":
        # --- Branch into expense flow ---
        # Convert negative amount to positive for expense tracking
        amount_raw = ctx.get("ocr_amount", "0")
        try:
            amount_abs = abs(Decimal(amount_raw.replace(" ", "").replace(",", ".").replace("−", "-")))
        except Exception:
            amount_abs = Decimal("0")

        expense_ctx = {
            "amount": str(amount_abs),
            "date": ctx.get("ocr_date", ""),
            "vendor": ctx.get("ocr_sender", ""),       # recipient → vendor
            "description": ctx.get("ocr_purpose", ""),  # purpose → description
            "receipt_url": "",
            "paid_by": "",
            "payment_method": "method_vyriy_transfer",   # bank screenshot → VyriY bank transfer
            "source": "bank_ocr",
        }

        await set_session(pool, chat_id, user_id, "expense:awaiting_category", expense_ctx)

        from utils.formatters import format_ask_expense_category
        from utils.keyboards import expense_category_keyboard
        await query.edit_message_text(
            format_ask_expense_category(),
            reply_markup=expense_category_keyboard(),
            parse_mode="Markdown",
        )

    elif data == "flow_return":
        # --- Branch into income flow (return to guest) ---
        # Keep the original OCR text so the income handler can re-parse as usual
        ocr_text = ctx.get("ocr_text", "")
        await clear_session(pool, chat_id)

        from handlers.income import handle_photo_with_ocr
        await handle_photo_with_ocr(update, context, ocr_text, from_disambiguation=True)


# ---------------------------------------------------------------------------
# Text router
# ---------------------------------------------------------------------------

async def handle_text_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route text messages by session state.

    Text input is used for: amounts, guest names, dates, vendor names, notes.
    """
    if not is_authorized(update):
        return  # silently ignore text from unauthorized chats
    pool: asyncpg.Pool = context.bot_data["db_pool"]
    chat_id = update.effective_chat.id

    session = await get_session(pool, chat_id)
    if not session:
        return  # No active session, ignore text

    # NOTE: Any authorized team member can continue the session
    # (same rationale as callback router — shared team workflow).

    state = session.state or ""

    if state.startswith("income:"):
        from handlers.income import handle_income_text
        await handle_income_text(update, context, session)
    elif state.startswith("income_manual:"):
        from handlers.income_manual import handle_manual_income_text
        await handle_manual_income_text(update, context, session)
    elif state.startswith("expense:"):
        from handlers.expense import handle_expense_text
        await handle_expense_text(update, context, session)


# ---------------------------------------------------------------------------
# Finalize: write to DB + Sheets
# ---------------------------------------------------------------------------

async def finalize_income(pool: asyncpg.Pool, chat_id: int, ctx: dict) -> str:
    """Write income transaction to PostgreSQL and Google Sheets.

    Returns transaction ID on success, empty string on DB failure.
    """
    # Resolve display labels from callback data
    # Support multi-select properties (list) and legacy single property (string)
    properties = ctx.get("properties", [])
    if not properties:
        single = ctx.get("property", "")
        properties = [single] if single and single != "prop_skip" else []
    property_labels = [PROPERTY_MAP.get(p, p) for p in properties if p]
    property_label = " + ".join(property_labels) if property_labels else ""
    is_sup = properties == ["prop_sup"]

    pay_cb = ctx.get("payment_type", "")
    payment_label = "Сапи" if is_sup else PAYMENT_TYPE_MAP.get(pay_cb, "")

    plat_cb = ctx.get("platform", "")
    platform_label = PLATFORM_MAP.get(plat_cb, "")

    acc_cb = ctx.get("account_type", "")
    account_label = ACCOUNT_TYPE_MAP.get(acc_cb, "")

    dur_cb = ctx.get("sup_duration", "")
    duration_label = SUP_DURATION_MAP.get(dur_cb, "")

    # Build notes
    if is_sup and duration_label:
        notes = f"Тривалість: {duration_label}"
    else:
        notes = ctx.get("ocr_purpose") or ctx.get("notes", "")

    # Parse amount
    amount_raw = ctx.get("amount") or ctx.get("ocr_amount")
    try:
        amount = Decimal(str(amount_raw).replace(" ", "").replace(",", "."))
    except Exception:
        amount = Decimal("0")

    # Parse date
    date_str = ctx.get("date") or ctx.get("ocr_date", "")
    try:
        tx_date = datetime.strptime(date_str.replace("/", "."), "%d.%m.%Y").date()
    except ValueError:
        tx_date = datetime.now().date()

    # Parse checkin/checkout
    checkin = ctx.get("checkin")
    checkout = ctx.get("checkout")
    checkin_date = None
    checkout_date = None
    if checkin:
        try:
            checkin_date = datetime.strptime(checkin.replace("/", "."), "%d.%m.%Y").date()
        except ValueError:
            pass
    if checkout:
        try:
            checkout_date = datetime.strptime(checkout.replace("/", "."), "%d.%m.%Y").date()
        except ValueError:
            pass

    source = ctx.get("source", "manual")
    guest_name = ctx.get("guest_name") or ctx.get("ocr_sender", "")

    # --- PostgreSQL INSERT ---
    try:
        async with pool.acquire() as conn:
            tx_id = await conn.fetchval(
                """
                INSERT INTO transactions
                    (type, date, amount, property_id, platform, counterparty,
                     payment_type, account_type, checkin_date, checkout_date,
                     sup_duration, notes, source, sheets_synced)
                VALUES
                    ('income', $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, FALSE)
                RETURNING id
                """,
                tx_date,
                amount,
                ",".join(properties) if properties else None,
                platform_label or None,
                guest_name or None,
                payment_label or None,
                account_label or None,
                checkin_date,
                checkout_date,
                duration_label or None,
                notes or None,
                source,
            )
        logger.info("Income transaction saved: %s", tx_id)
    except Exception as e:
        logger.error("Failed to save income to DB: %s", e)
        return ""

    # --- Google Sheets write ---
    sheets_data = {
        "date": convert_date_for_sheets(date_str) if date_str else datetime.now().strftime("%Y-%m-%d") + " 0:00:00",
        "amount": float(amount),
        "property": property_label,
        "platform": platform_label,
        "guest_name": guest_name,
        "checkin": checkin or "",
        "checkout": checkout or "",
        "payment_type": payment_label,
        "account_type": account_label,
        "notes": notes,
        "month": get_month_label(date_str) if date_str else "",
    }

    try:
        synced = await asyncio.to_thread(append_income_row, sheets_data)
        if synced:
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE transactions SET sheets_synced = TRUE WHERE id = $1", tx_id
                )
    except Exception as e:
        logger.error("Sheets write failed (will retry): %s", e)

    # Store resolved labels back in context for confirmation message
    ctx["property_label"] = property_label
    ctx["payment_type_label"] = payment_label
    ctx["platform_label"] = platform_label
    ctx["account_type_label"] = account_label
    ctx["duration_label"] = duration_label
    ctx["month"] = get_month_label(date_str) if date_str else ""

    return str(tx_id)


async def finalize_expense(pool: asyncpg.Pool, chat_id: int, ctx: dict) -> str:
    """Write expense transaction to PostgreSQL and Google Sheets.

    Returns transaction ID on success, empty string on DB failure.
    """
    cat_cb = ctx.get("category", "")
    category_label = EXPENSE_CATEGORY_MAP.get(cat_cb, cat_cb)

    # Resolve subcategory label (empty string for categories without subcategories)
    sub_cb = ctx.get("subcategory", "")
    subcategory_label = ""
    if sub_cb and cat_cb in EXPENSE_SUBCATEGORY_MAP:
        subcategory_label = EXPENSE_SUBCATEGORY_MAP[cat_cb].get(sub_cb, sub_cb)

    method_cb = ctx.get("payment_method", "")
    method_label = PAYMENT_METHOD_MAP.get(method_cb, method_cb)

    paidby_cb = ctx.get("paid_by", "")
    paidby_label = PAID_BY_MAP.get(paidby_cb, paidby_cb)

    amount_raw = ctx.get("amount", "0")
    try:
        amount = Decimal(str(amount_raw).replace(" ", "").replace(",", "."))
    except Exception:
        amount = Decimal("0")

    description = ctx.get("description", "")
    vendor = ctx.get("vendor", "")         # from receipt OCR, empty otherwise
    notes = ctx.get("notes", "")           # not asked interactively anymore
    receipt_url = ctx.get("receipt_url", "")
    tx_date = datetime.now().date()

    # Property is not asked in new flow; keep for receipt OCR backward compat
    prop_cb = ctx.get("property", "")
    property_label = EXPENSE_PROPERTY_MAP.get(prop_cb, PROPERTY_MAP.get(prop_cb, ""))

    # --- PostgreSQL INSERT ---
    try:
        async with pool.acquire() as conn:
            tx_id = await conn.fetchval(
                """
                INSERT INTO transactions
                    (type, date, amount, property_id, counterparty, account_type,
                     category, description, paid_by, notes, receipt_url, source, sheets_synced)
                VALUES
                    ('expense', $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 'manual', FALSE)
                RETURNING id
                """,
                tx_date,
                amount,
                prop_cb if prop_cb not in ("prop_skip", "") else None,
                vendor or None,
                method_label or None,
                category_label or None,
                description or None,
                paidby_label or None,
                notes or None,
                receipt_url or None,
            )
        logger.info("Expense transaction saved: %s", tx_id)
    except Exception as e:
        logger.error("Failed to save expense to DB: %s", e)
        return ""

    # --- Google Sheets write ---
    sheets_data = {
        "date": tx_date.strftime("%Y-%m-%d") + " 0:00:00",
        "category": category_label,
        "amount": float(amount),
        "description": description,
        "payment_method": method_label,
        "paid_by": paidby_label,
        "receipt_url": receipt_url,
        "vendor": vendor,
        "property": property_label,
        "notes": notes,
        "subcategory": subcategory_label,   # blank for non-subcategory categories
    }

    try:
        synced = await asyncio.to_thread(append_expense_row, sheets_data)
        if synced:
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE transactions SET sheets_synced = TRUE WHERE id = $1", tx_id
                )
    except Exception as e:
        logger.error("Sheets write failed (will retry): %s", e)

    return str(tx_id)
