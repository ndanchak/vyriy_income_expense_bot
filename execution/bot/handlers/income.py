"""
Income OCR flow handler.

Ports the entire Make.com blueprint (31 modules) into a Python state machine.
Photo → OCR → Parse → Property → Payment/Duration → Platform → Dates → Save.

Account Type step removed — always defaults to "Account" for non-SUP income.
"""

import logging
from datetime import datetime
from decimal import Decimal

import asyncpg
from telegram import Update
from telegram.ext import ContextTypes

from config import (
    PROPERTY_MAP,
    PAYMENT_TYPE_MAP,
    PLATFORM_MAP,
    SUP_DURATION_MAP,
)
from database.models import BotSession
from utils.state import set_session, update_context, clear_session
from utils.parsers import parse_monobank_ocr, parse_dates_input
from utils.keyboards import (
    property_keyboard,
    property_toggle_keyboard,
    sup_duration_keyboard,
    payment_type_keyboard,
    platform_keyboard,
    dates_skip_keyboard,
    duplicate_confirm_keyboard,
)
from utils.formatters import (
    format_ocr_summary,
    format_income_confirmation,
    format_ask_payment_type,
    format_ask_platform,
    format_ask_dates,
    format_ask_sup_duration,
    format_ask_property,
    format_duplicate_warning,
)
from handlers.common import finalize_income, check_duplicate_income

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Entry point: OCR text already extracted by photo router
# ---------------------------------------------------------------------------

async def handle_photo_with_ocr(
    update: Update, context: ContextTypes.DEFAULT_TYPE, ocr_text: str,
    from_disambiguation: bool = False,
) -> None:
    """Handle Monobank screenshot — parse OCR text and start income flow.

    Called by handle_photo_router() in common.py after download + OCR + classification.
    Also called from disambiguation callback when user chooses "Повернення гостю".
    Session existence is already checked by the router.

    Equivalent to Make.com modules 6b-7: parse → show summary → ask property.
    """
    pool: asyncpg.Pool = context.bot_data["db_pool"]
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Parse Monobank OCR text
    parsed = parse_monobank_ocr(ocr_text)
    logger.info(
        "Parsed Monobank OCR: amount=%s, date=%s, has_sender=%s, has_purpose=%s",
        parsed["amount"], parsed["date"],
        bool(parsed["sender_name"]), bool(parsed["purpose"]),
    )
    logger.debug("Parsed Monobank OCR full: %s", parsed)

    # Save session
    session_ctx = {
        "ocr_sender": parsed["sender_name"],
        "ocr_amount": str(parsed["amount"]) if parsed["amount"] else "",
        "ocr_date": parsed["date"],
        "ocr_purpose": parsed["purpose"],
        "source": "ocr",
    }
    await set_session(pool, chat_id, user_id, "income:awaiting_property", session_ctx)

    # Send summary + property keyboard (Make.com module 7)
    # When called from disambiguation callback, edit the existing message
    if from_disambiguation and update.callback_query:
        await update.callback_query.edit_message_text(
            format_ocr_summary(parsed),
            reply_markup=property_keyboard(show_save_minimal=True),
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            format_ocr_summary(parsed),
            reply_markup=property_keyboard(show_save_minimal=True),
            parse_mode="Markdown",
        )


# ---------------------------------------------------------------------------
# Callback handler: state machine for income flow
# ---------------------------------------------------------------------------

async def handle_income_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: BotSession,
) -> None:
    """Handle callback_query presses during income flow.

    Replaces Make.com modules 8-29: the chain of Wait→Answer→Route→Ask→Wait.
    """
    query = update.callback_query
    await query.answer()

    pool: asyncpg.Pool = context.bot_data["db_pool"]
    chat_id = update.effective_chat.id
    state = session.state
    data = query.data
    ctx = dict(session.context)

    # --- Property selection (multi-select toggle) ---
    if state in ("income:awaiting_property", "income_manual:awaiting_property"):
        selected = ctx.get("properties", [])

        if data == "save_minimal":
            # Quick-save: keep any toggled properties, skip all other steps
            ctx["properties"] = selected
            ctx["payment_type"] = ""
            ctx["platform"] = ""
            ctx["account_type"] = "acc_account"  # default to Account
            ctx["dates_skipped"] = True
            prefix = state.split(":")[0]
            await update_context(pool, chat_id, f"{prefix}:finalizing", ctx)
            await _pre_finalize(pool, chat_id, ctx, query, prefix)
            return

        if data == "prop_confirm":
            # User confirmed selection → proceed to next step
            if "prop_sup" in selected:
                # SUP branch: ask duration (Make.com module 11)
                next_state = state.replace("awaiting_property", "awaiting_sup_duration")
                await update_context(pool, chat_id, next_state, ctx)
                await query.edit_message_text(
                    format_ask_sup_duration(),
                    reply_markup=sup_duration_keyboard(),
                    parse_mode="Markdown",
                )
            else:
                # Normal property: ask payment type
                next_state = state.replace("awaiting_property", "awaiting_payment_type")
                await update_context(pool, chat_id, next_state, ctx)
                await query.edit_message_text(
                    format_ask_payment_type(),
                    reply_markup=payment_type_keyboard(),
                    parse_mode="Markdown",
                )

        elif data == "prop_skip":
            # Skip: go to payment type with empty properties
            ctx["properties"] = []
            next_state = state.replace("awaiting_property", "awaiting_payment_type")
            await update_context(pool, chat_id, next_state, ctx)
            await query.edit_message_text(
                format_ask_payment_type(),
                reply_markup=payment_type_keyboard(),
                parse_mode="Markdown",
            )

        elif data == "prop_sup":
            # SUP is exclusive — clear all others, set only SUP
            selected = ["prop_sup"]
            ctx["properties"] = selected
            await update_context(pool, chat_id, state, ctx)
            await query.edit_message_text(
                format_ask_property(),
                reply_markup=property_toggle_keyboard(selected),
                parse_mode="Markdown",
            )

        elif data.startswith("prop_") and data in PROPERTY_MAP:
            # Toggle property in/out of selected list
            if data in selected:
                selected.remove(data)
            else:
                # If SUP was selected, clear it when adding a normal property
                if "prop_sup" in selected:
                    selected.remove("prop_sup")
                selected.append(data)
            ctx["properties"] = selected
            await update_context(pool, chat_id, state, ctx)
            await query.edit_message_text(
                format_ask_property(),
                reply_markup=property_toggle_keyboard(selected),
                parse_mode="Markdown",
            )

    # --- SUP Duration ---
    elif state in ("income:awaiting_sup_duration", "income_manual:awaiting_sup_duration"):
        if data not in SUP_DURATION_MAP and data != "dur_skip":
            await query.answer("Невідома тривалість")
            return
        ctx["sup_duration"] = data
        ctx["payment_type"] = "Сапи"  # auto-set (Make.com module 30 logic)
        ctx["account_type"] = "acc_nestor"  # SUP always uses Nestor Account

        # Auto-detect cash for SUP (Make.com module 28)
        purpose = ctx.get("ocr_purpose", "")
        if "готівка" in purpose.lower():
            ctx["account_type"] = "acc_cash"

        # SUP: skip platform and dates — go directly to finalize
        ctx["platform"] = ""
        ctx["dates_skipped"] = True
        prefix = state.split(":")[0]
        await update_context(pool, chat_id, f"{prefix}:finalizing", ctx)
        await _pre_finalize(pool, chat_id, ctx, query, prefix)

    # --- Payment Type ---
    elif state in ("income:awaiting_payment_type", "income_manual:awaiting_payment_type"):
        if data not in PAYMENT_TYPE_MAP and data != "pay_skip":
            await query.answer("Невідомий тип платежу")
            return
        ctx["payment_type"] = data
        prefix = state.split(":")[0]
        next_state = f"{prefix}:awaiting_platform"
        await update_context(pool, chat_id, next_state, ctx)
        await query.edit_message_text(
            format_ask_platform(),
            reply_markup=platform_keyboard(),
            parse_mode="Markdown",
        )

    # --- Platform ---
    elif state in ("income:awaiting_platform", "income_manual:awaiting_platform"):
        if data not in PLATFORM_MAP and data != "plat_skip":
            await query.answer("Невідома платформа")
            return
        ctx["platform"] = data

        # Account type: always default to "Account" for non-SUP
        # SUP already has account_type set from duration step
        is_sup = "prop_sup" in ctx.get("properties", [])
        prefix = state.split(":")[0]

        if not is_sup:
            ctx["account_type"] = "acc_account"  # always default to Account

        next_state = f"{prefix}:awaiting_dates"
        await update_context(pool, chat_id, next_state, ctx)
        await query.edit_message_text(
            format_ask_dates(),
            reply_markup=dates_skip_keyboard(),
            parse_mode="Markdown",
        )

    # --- Dates skip ---
    elif state in ("income:awaiting_dates", "income_manual:awaiting_dates"):
        if data == "dates_skip":
            ctx["dates_skipped"] = True
            prefix = state.split(":")[0]
            await update_context(pool, chat_id, f"{prefix}:finalizing", ctx)
            await _pre_finalize(pool, chat_id, ctx, query, prefix)

    # --- Duplicate confirmation ---
    elif state in ("income:awaiting_dup_confirm", "income_manual:awaiting_dup_confirm"):
        if data == "dup_confirm":
            prefix = state.split(":")[0]
            await update_context(pool, chat_id, f"{prefix}:finalizing", ctx)
            await _finalize_and_confirm(pool, chat_id, ctx, query)


# ---------------------------------------------------------------------------
# Pre-finalize: duplicate check before saving
# ---------------------------------------------------------------------------

async def _pre_finalize(pool, chat_id, ctx, query, prefix) -> None:
    """Check for duplicates, then finalize or ask for confirmation."""
    # Parse amount + date for dup check
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
        await update_context(pool, chat_id, f"{prefix}:awaiting_dup_confirm", ctx)
        await query.edit_message_text(
            format_duplicate_warning(ctx),
            reply_markup=duplicate_confirm_keyboard(),
            parse_mode="Markdown",
        )
    else:
        await _finalize_and_confirm(pool, chat_id, ctx, query)


async def _finalize_and_confirm(pool, chat_id, ctx, query) -> None:
    """Write transaction and send confirmation."""
    tx_id = await finalize_income(pool, chat_id, ctx)

    if tx_id:
        confirmation = format_income_confirmation(ctx)
        await query.edit_message_text(confirmation, parse_mode="Markdown")
    else:
        await query.edit_message_text("❌ Помилка збереження. Спробуйте ще раз.")

    await clear_session(pool, chat_id)


# ---------------------------------------------------------------------------
# Text handler: dates input
# ---------------------------------------------------------------------------

async def handle_income_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: BotSession,
) -> None:
    """Handle text input during income OCR flow (dates step)."""
    pool: asyncpg.Pool = context.bot_data["db_pool"]
    chat_id = update.effective_chat.id
    state = session.state
    text = update.message.text.strip()

    if state == "income:awaiting_dates":
        ctx = dict(session.context)
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
            await update_context(pool, chat_id, "income:awaiting_dup_confirm", ctx)
            await update.message.reply_text(
                format_duplicate_warning(ctx),
                reply_markup=duplicate_confirm_keyboard(),
                parse_mode="Markdown",
            )
            return

        # Lock state to prevent duplicate writes
        await update_context(pool, chat_id, "income:finalizing", ctx)

        # Finalize
        tx_id = await finalize_income(pool, chat_id, ctx)

        if tx_id:
            confirmation = format_income_confirmation(ctx)
            await update.message.reply_text(confirmation, parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Помилка збереження. Спробуйте ще раз.")

        await clear_session(pool, chat_id)
